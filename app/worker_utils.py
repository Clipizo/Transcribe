"""Helpers for the model worker.

This runs inside the kit's environment (envs/), where torch, numpy and soundfile are
installed. Heavy libraries are imported inside functions so that error
messages stay friendly even when something is missing.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import traceback
import warnings
from pathlib import Path

import common as C


# ---------------------------------------------------------------------------
# Quiet, friendly output
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def silenced():
    """Hide everything printed while the Qwen libraries load. They print harmless notes
    ("flash-attn is not installed", "sox: not found") that look like errors to beginners.
    Errors are still raised normally."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = [os.dup(1), os.dup(2)]
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        for fd in (devnull, *saved):
            os.close(fd)


def import_quietly(module: str):
    quiet()
    with silenced():
        return __import__(module)


def quiet() -> None:
    """Hide the library warnings that only confuse beginners."""
    warnings.filterwarnings("ignore")
    for name in ("sox", "transformers", "huggingface_hub", "accelerate", "numba",
                 "urllib3", "httpx", "gradio", "torch", "librosa", "audioread"):
        logging.getLogger(name).setLevel(logging.ERROR)
    try:
        import transformers
        transformers.logging.set_verbosity_error()
    except Exception:
        pass


def explain_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if "out of memory" in text or "outofmemory" in text or "not enough memory" in text:
        return ("Your computer ran out of graphics or main memory.\n"
                "  - Close other programs (games, video editors, browser tabs) and try again.\n"
                "  - Use the faster, smaller model: add  --quality fast\n"
                "  - For a long script, it can help to split it into smaller files.")
    if "no kernel image" in text or "not compatible with the current pytorch" in text \
            or "cuda capability" in text:
        return ("Your NVIDIA graphics card is older than this PyTorch build supports.\n"
                "  Run the installer again with:  --torch cu126\n"
                "  (Windows: install-windows.bat --torch cu126   Linux: bash install.sh --torch cu126)")
    if "probability tensor contains" in text or ("nan" in text and "inf" in text):
        return ("The model produced invalid numbers, which happens with some older graphics cards.\n"
                "  Try again with:  --precision float32")
    if any(k in text for k in ("connection", "timed out", "timeout", "name resolution",
                               "max retries", "ssl", "offline", "localentrynotfound",
                               "huggingface.co", "temporary failure", "network")):
        return ("I couldn't download the model from Hugging Face (huggingface.co).\n"
                "  - Check your internet connection and try again: the download continues where it stopped.\n"
                "  - Some school, work and country networks block huggingface.co. See\n"
                f"    'Downloading models manually' in the {C.KIT_NAME} AI Guide.")
    if "mps" in text:
        return ("Apple's graphics (MPS) ran into a problem.\n"
                "  Try again with:  --device cpu  (slower, but always works)")
    if isinstance(exc, (FileNotFoundError, PermissionError)):
        return "Check that the file exists, isn't open in another program, and that the path is correct."
    return ""


def run_main(fn) -> None:
    """Run a worker command and turn errors into plain-language messages."""
    C.setup_console()
    try:
        fn()
    except KeyboardInterrupt:
        C.say("\nStopped.")
        sys.exit(130)
    except C.UserError as e:
        C.say(f"\n{e}")
        sys.exit(2)
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001 - show everything to the user
        details = traceback.format_exc()
        report = C.KIT / "last-error.txt"
        try:
            report.write_text(f"{C.KIT_NAME} {C.KIT_VERSION}, {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{details}",
                              encoding="utf-8")
        except OSError:
            report = None
        hint = explain_error(e)
        if not hint:
            print(details, file=sys.stderr, flush=True)  # unknown problem: show the details too
        summary = " ".join(f"{type(e).__name__}: {e}".split())
        C.say("\n" + "-" * 60)
        C.say(f"Something went wrong: {summary[:200]}{'...' if len(summary) > 200 else ''}")
        if hint:
            C.say(hint)
        if report is not None:
            C.say(f"The technical details are in {report.name} (in the {C.KIT_NAME} folder).")
        C.say("If you're stuck, give that file, or the text above, to your AI assistant.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Jobs (the launcher passes work in a JSON file, which avoids quoting problems)
# ---------------------------------------------------------------------------

def read_job(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_result(job_path: str, data: dict) -> None:
    Path(job_path + ".result.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------

DEVICE_LABELS = {
    "cuda": "your NVIDIA graphics card",
    "mps": "your Mac's graphics (Apple Silicon)",
    "cpu": "the processor (CPU, slow)",
}


def pick_device(settings: dict, precision: str | None = None, device: str | None = None):
    """Return (device, device_map, dtype) for loading a model."""
    import torch

    want = device or settings.get("device")
    has_cuda = torch.cuda.is_available()
    has_mps = bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available()
    if want == "cpu":
        dev = "cpu"
    elif want == "mps" and has_mps:
        dev = "mps"
    elif want == "cuda" and has_cuda:
        dev = "cuda"
    elif has_cuda:
        dev = "cuda"
    elif has_mps:
        dev = "mps"
    else:
        dev = "cpu"

    if dev == "cuda":
        major, _minor = torch.cuda.get_device_capability(0)
        dtype = torch.bfloat16 if major >= 8 else (torch.float16 if major >= 7 else torch.float32)
        device_map = "cuda:0"
    elif dev == "mps":
        dtype, device_map = torch.float32, "mps"  # half precision is unreliable on MPS
    else:
        dtype, device_map = torch.float32, "cpu"

    chosen = precision or settings.get("precision")
    if chosen:
        dtype = {"float32": torch.float32, "float16": torch.float16, "bfloat16": torch.bfloat16}[chosen]
    return dev, device_map, dtype


def free_memory() -> None:
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


def probe(package: str) -> None:
    """Print facts about this environment as one JSON line (used by the installer and `check`)."""
    quiet()
    out: dict = {"python": sys.version.split()[0]}
    try:
        import torch
        out["torch"] = torch.__version__
        out["cuda"] = bool(torch.cuda.is_available())
        out["mps"] = bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available()
        if out["cuda"]:
            props = torch.cuda.get_device_properties(0)
            out["gpu"] = props.name
            out["vram_gb"] = round(props.total_memory / 1024**3, 1)
            out["cc"] = list(torch.cuda.get_device_capability(0))
            try:
                x = torch.ones(16, device="cuda") * 2
                out["cuda_ok"] = float(x.sum().item()) == 32.0
            except Exception as e:  # e.g. "no kernel image is available"
                out["cuda_ok"] = False
                out["cuda_error"] = str(e)[:300]
    except Exception as e:
        out["torch_error"] = f"{type(e).__name__}: {e}"[:300]
    try:
        with silenced():
            __import__(package)
        out["package_ok"] = True
    except Exception as e:
        out["package_ok"] = False
        out["package_error"] = f"{type(e).__name__}: {e}"[:300]
    try:
        import imageio_ffmpeg
        out["ffmpeg"] = bool(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        out["ffmpeg"] = bool(shutil.which("ffmpeg"))
    print("KIT_PROBE=" + json.dumps(out), flush=True)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def _looks_complete(folder: Path) -> bool:
    return (folder / "config.json").exists() and any(folder.glob("*.safetensors"))


def ensure_model(repo_id: str) -> Path:
    """Download a model into models/ the first time it is needed."""
    folder = C.model_dir(repo_id)
    marker = folder / C.DONE_MARKER
    if marker.exists():
        return folder
    size = C.MODEL_SIZES_GB.get(repo_id)
    about = f" (about {size:.1f} GB)" if size else ""
    C.say(f"Downloading the model {repo_id.split('/')[-1]}{about}.")
    C.say("This happens only once. If it stops, run the same command again: it continues where it left off.")
    from huggingface_hub import snapshot_download

    last_error = None
    for attempt in range(3):
        try:
            snapshot_download(repo_id=repo_id, local_dir=str(folder))
            last_error = None
            break
        except KeyboardInterrupt:
            raise
        except Exception as e:  # network hiccups: retry a couple of times
            last_error = e
            if attempt < 2:
                C.say(f"The download was interrupted ({type(e).__name__}). Trying again in 5 seconds...")
                time.sleep(5)
    if last_error is not None:
        if _looks_complete(folder):
            C.say("Couldn't reach Hugging Face, but the model folder looks complete, so I'll use it.")
            return folder
        raise last_error
    marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        if exe:
            return exe
    raise C.UserError("The audio converter (ffmpeg) is missing. Run the installer again to fix it.")


def load_audio(path, sr: int):
    """Read any audio or video file as mono float32 samples at `sr` Hz."""
    import numpy as np

    path = Path(path)
    if not path.exists():
        raise C.UserError(f"I can't find this file:\n  {path}\nCheck the name and the folder, then try again.")
    cmd = [ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path),
           "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        msg = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        detail = msg[-1] if msg else "no audio found"
        if "does not contain any stream" in detail or "matches no streams" in detail or not proc.stdout:
            raise C.UserError(f"I couldn't find any sound in this file:\n  {path}")
        raise C.UserError(f"I couldn't read this file as audio or video:\n  {path}\n  ({detail})")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def write_wav(path, audio, sr: int) -> None:
    import soundfile as sf
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, subtype="PCM_16")


def wav_to_mp3(wav_path, mp3_path) -> bool:
    cmd = [ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)]
    return subprocess.run(cmd).returncode == 0


def trim_silence(wav, sr: int, threshold_db: float = -42.0, keep: float = 0.06):
    """Cut silence from the start and end (keeps a tiny margin)."""
    import numpy as np

    if wav.size == 0:
        return wav
    frame = max(1, int(sr * 0.02))
    n = len(wav) // frame
    if n == 0:
        return wav
    rms = np.sqrt(np.mean(wav[: n * frame].reshape(n, frame) ** 2, axis=1) + 1e-12)
    peak = float(rms.max())
    if peak <= 1e-6:
        return wav
    loud = np.where(20 * np.log10(rms / peak) > threshold_db)[0]
    if loud.size == 0:
        return wav
    start = max(0, int(loud[0]) * frame - int(keep * sr))
    end = min(len(wav), (int(loud[-1]) + 1) * frame + int(keep * sr))
    return wav[start:end]


def quietest_point(wav, sr: int, start_s: float, end_s: float, window_s: float = 0.1) -> int:
    """Sample index of the quietest moment between start_s and end_s."""
    import numpy as np

    a = max(0, int(start_s * sr))
    b = min(len(wav), int(end_s * sr))
    win = max(4, int(window_s * sr))
    if b - a <= win:
        return min(len(wav), max(a, b))
    seg = np.abs(wav[a:b])
    sums = np.convolve(seg, np.ones(win, dtype=np.float32), mode="valid")
    return a + int(np.argmin(sums)) + win // 2


def split_on_quiet(wav, sr: int, max_seconds: float, search_seconds: float = 5.0):
    """Split long audio into pieces of at most max_seconds, cutting at quiet moments.

    Returns [(samples, offset_seconds), ...].
    """
    pieces = []
    total = len(wav)
    max_len = int(max_seconds * sr)
    start = 0
    while total - start > max_len:
        target = (start + max_len) / sr
        cut = quietest_point(wav, sr, target - search_seconds, target)
        cut = max(start + sr, min(cut, start + max_len))
        pieces.append((wav[start:cut], start / sr))
        start = cut
    pieces.append((wav[start:], start / sr))
    return pieces
