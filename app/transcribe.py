"""Transcribe: free transcripts and subtitles on your own computer.

Start it with `transcribe` (Windows: double-click transcribe.bat) for a simple
menu, or run `transcribe FILE` to transcribe a file. `transcribe help` shows
everything. This file uses only the Python standard library; the AI models run
in envs/asr.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
from common import UserError, say  # noqa: E402

CMD = C.launcher_command()
WORKER = "asr_worker.py"
SUBCOMMANDS = ("check", "app", "download", "help", "menu")


class WorkerFailed(Exception):
    """The model worker stopped with an error (it already explained it)."""

    def __init__(self, code: int):
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# Running the model worker
# ---------------------------------------------------------------------------

def install_hint() -> str:
    if C.IS_WINDOWS:
        return "Double-click install-windows.bat in the Transcribe folder, then try again."
    return "Open Terminal in the Transcribe folder and run:  bash install.sh"


def require_installed() -> None:
    if not C.env_python().exists():
        raise UserError("Transcribe isn't installed yet, or the install didn't finish.\n" + install_hint())


def run_worker(command: str, job: dict | None = None, extra=()) -> dict | None:
    require_installed()
    args = [str(C.env_python()), str(C.APP / WORKER), command, *extra]
    job_file = None
    if job is not None:
        fd, job_file = tempfile.mkstemp(prefix="transcribe-", suffix=".json")
        os.close(fd)
        Path(job_file).write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        args += ["--job", job_file]
    try:
        code = subprocess.call(args, env=C.child_env(), cwd=str(C.KIT))
        result = None
        if job_file:
            rf = Path(job_file + ".result.json")
            if rf.exists():
                result = json.loads(rf.read_text(encoding="utf-8"))
                rf.unlink()
    finally:
        if job_file:
            Path(job_file).unlink(missing_ok=True)
    if code != 0:
        raise WorkerFailed(code)
    return result


def probe_env() -> dict:
    if not C.env_python().exists():
        return {"missing": True}
    proc = subprocess.run([str(C.env_python()), str(C.APP / WORKER), "probe"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=C.child_env(), cwd=str(C.KIT))
    for line in proc.stdout.splitlines():
        if line.startswith("KIT_PROBE="):
            return json.loads(line.split("=", 1)[1])
    return {"error": (proc.stderr or proc.stdout).strip()[-500:]}


def rel(path) -> str:
    """Show paths inside the Transcribe folder in a short form."""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(C.KIT))
    except ValueError:
        return str(p)


def speed_note(settings: dict) -> str:
    if settings.get("device") == "cpu":
        return ("Note: this computer has no supported graphics card, so this runs on the processor.\n"
                "It works, but long recordings take a while.")
    return ""


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------

def cmd_transcribe(audio: str, language=None, subtitles=True, hint=None, quality=None, out=None,
                   script=None, max_chars=None, precision=None, device=None) -> dict:
    if not audio:
        raise UserError("Give me an audio or video file, for example:\n"
                        f"  {CMD} my-video.mp4")
    src = C.user_path(audio)
    if not src.is_file():
        raise UserError(f"I can't find this file:\n  {src}")
    lang = C.normalize_language(language)
    if lang and lang not in C.ASR_LANGUAGES:
        raise UserError(f"Transcribe understands: {', '.join(C.ASR_LANGUAGES)}.\n'{language}' isn't one of them.")
    script_text = None
    if script:
        script_file = C.user_path(script)
        if not script_file.is_file():
            raise UserError(f"I can't find the script file:\n  {script_file}")
        script_text = C.clean_script(C.read_text_file(script_file))
        if not script_text:
            raise UserError(f"The script file is empty:\n  {script_file}")
        if not subtitles:
            say("Note: --script is only used for subtitles, so I'll make subtitles anyway.")
            subtitles = True
    if max_chars is not None and not 8 <= max_chars <= 80:
        raise UserError("--max-chars must be between 8 and 80 (characters per subtitle line).")
    settings = C.load_settings()
    size = C.resolve_size(quality, settings)
    if out:
        out_base = C.user_path(out).with_suffix("")
        out_base.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_base = C.unique_base(C.OUTPUT, C.safe_name(src.stem, 60) or "transcript", [".txt", ".srt", ".words.json"])
    note = speed_note(settings)
    if note:
        say(note)
    job = {"input": str(src), "language": lang, "subtitles": subtitles, "hint": hint or "",
           "size": size, "out_base": str(out_base), "script": script_text, "max_chars": max_chars,
           "precision": precision, "device": device}
    result = run_worker("transcribe", job) or {}
    say("\nDone! Saved:")
    if result.get("used_script"):
        say(f"  {rel(result['txt'])}   (your script)")
    else:
        say(f"  {rel(result['txt'])}   (the text)")
    if result.get("srt"):
        say(f"  {rel(result['srt'])}   (subtitles for video editors and YouTube)")
        say(f"  {rel(result['words'])}   (every word with its timing)")
    if result.get("subtitles_skipped"):
        say(f"  {result['subtitles_skipped']}")
    if result.get("language"):
        say(f"Language: {result['language']}")
    text = result.get("text", "")
    if text and not result.get("used_script"):
        say("\n" + (text if len(text) <= 400 else text[:400] + " ..."))
    return result


# ---------------------------------------------------------------------------
# download, check, app
# ---------------------------------------------------------------------------

def models_for(what: str, settings: dict, quality=None) -> list[str]:
    size = C.resolve_size(quality, settings)
    groups = {"text": [C.ASR_MODELS[size]], "subtitles": [C.ALIGNER_MODEL]}
    if what == "all":
        return groups["text"] + groups["subtitles"]
    if what not in groups:
        raise UserError("Choose what to download: text, subtitles or all")
    return groups[what]


def cmd_download(what="all", quality=None) -> None:
    settings = C.load_settings()
    todo = [repo for repo in models_for(what, settings, quality) if not C.model_is_downloaded(repo)]
    if not todo:
        say("Everything you asked for is already downloaded.")
        return
    total = sum(C.MODEL_SIZES_GB.get(repo, 0) for repo in todo)
    say(f"Downloading {len(todo)} model(s), about {total:.1f} GB in total.")
    run_worker("download", extra=[x for repo in todo for x in ("--repo", repo)])
    say("\nAll done.")


def cmd_check() -> None:
    settings = C.load_settings()
    say(f"{C.KIT_NAME} {C.KIT_VERSION} - setup check\n")
    say(f"  Folder:      {C.KIT}")
    ok = True
    info = probe_env()
    if info.get("missing"):
        say(f"  Install:     not installed. {install_hint()}")
        ok = False
    elif info.get("error") or not info.get("package_ok"):
        say(f"  Install:     BROKEN: {info.get('package_error') or info.get('torch_error') or info.get('error')}")
        say("               Run the installer again to repair it.")
        ok = False
    else:
        if info.get("cuda") and info.get("cuda_ok", True):
            where = f"{C.gpu_label(info.get('gpu'))} ({info.get('vram_gb')} GB) - fast"
        elif info.get("cuda"):
            where = f"{C.gpu_label(info.get('gpu'))} found, but it can't run this PyTorch build: {info.get('cuda_error', '')[:80]}"
            ok = False
        elif info.get("mps"):
            where = "Apple Silicon graphics"
        else:
            where = "processor only (slow)"
        say(f"  Install:     ready (Qwen3-ASR, PyTorch {info.get('torch')})")
        say(f"  Runs on:     {where}")
        if not info.get("ffmpeg"):
            say("               The audio converter (ffmpeg) is missing. Run the installer again.")
            ok = False
    if settings:
        say(f"  Quality:     {settings.get('asr_size')} by default (change per command with --quality fast or best)")
    downloaded = [r for r in C.MODEL_SIZES_GB if C.model_is_downloaded(r)]
    say("  Models:      " + (", ".join(r.split('/')[-1] for r in downloaded) if downloaded
                             else "none downloaded yet (they download the first time you use them)"))
    try:
        free = shutil.disk_usage(C.KIT).free / 1024**3
        say(f"  Free disk:   {free:.0f} GB" + ("  (low: the models need 2 to 7 GB)" if free < 10 else ""))
    except OSError:
        pass
    say("\n" + ("Everything looks good." if ok else "Something needs fixing (see above)."))


def free_port(start: int = 7860) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise UserError("I couldn't find a free network port for the web app.")


def _open_when_ready(url: str, proc: subprocess.Popen) -> None:
    for _ in range(1800):
        if proc.poll() is not None:
            return
        try:
            with urllib.request.urlopen(url, timeout=2):
                pass
            say(f"\nThe web app is open at {url}  (keep this window open while you use it;"
                " press Ctrl+C here to stop it)\n")
            webbrowser.open(url)
            return
        except Exception:
            time.sleep(1)


def cmd_app(quality=None) -> None:
    settings = C.load_settings()
    device = settings.get("device", "cpu")
    dtype = settings.get("dtype", "float32")
    device_arg = "cuda:0" if device == "cuda" else device
    asr, aligner = C.ASR_MODELS[C.resolve_size(quality, settings)], C.ALIGNER_MODEL
    run_worker("download", extra=["--repo", asr, "--repo", aligner])
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    kwargs = {"device_map": device_arg, "dtype": dtype, "max_inference_batch_size": 1, "max_new_tokens": 2048}
    cmd = [str(C.env_python()), str(C.APP / WORKER), "app",
           "--asr-checkpoint", str(C.model_dir(asr)), "--aligner-checkpoint", str(C.model_dir(aligner)),
           "--backend", "transformers", "--backend-kwargs", json.dumps(kwargs),
           "--aligner-kwargs", json.dumps({"device_map": device_arg, "dtype": dtype}),
           "--ip", "127.0.0.1", "--port", str(port)]
    say("Starting the web app (the official Qwen demo). Loading the models can take a minute...")
    proc = subprocess.Popen(cmd, env=C.child_env(), cwd=str(C.KIT))
    threading.Thread(target=_open_when_ready, args=(url, proc), daemon=True).start()
    try:
        code = proc.wait()
    except KeyboardInterrupt:
        say("\nStopping the web app...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    if code != 0:
        raise WorkerFailed(code)


# ---------------------------------------------------------------------------
# Menu (what people see when they double-click Transcribe)
# ---------------------------------------------------------------------------

def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        # Text piped from Windows PowerShell can start with an invisible byte-order mark.
        answer = input(f"{prompt}{suffix}: ").replace("\ufeff", "").strip()
    except EOFError:
        answer = ""
    return answer or default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        a = ask(f"{prompt} ({hint})").lower()
        if not a:
            return default
        if a in ("y", "yes", "j", "ja", "si", "sí", "oui", "o"):
            return True
        if a in ("n", "no", "nein", "non"):
            return False


def ask_file(prompt: str) -> str:
    while True:
        raw = ask(prompt)
        if not raw:
            return ""
        path = C.user_path(raw)
        if path.is_file():
            return str(path)
        say(f"I can't find that file: {path}\nTip: drag the file into this window, then press Enter.")


def open_path(path) -> None:
    try:
        if C.IS_WINDOWS:
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif C.IS_MAC:
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        say(f"(Open this yourself: {path})")


def menu_transcribe() -> None:
    say("\nTranscribe audio or video into text and subtitles.")
    audio = ask_file("Drag the audio or video file into this window (or type its path), then press Enter")
    if not audio:
        return
    subtitles = ask_yes_no("Also make subtitles (.srt)?", default=True)
    language = ask("Language? Press Enter to detect it automatically") or None
    say("")
    result = cmd_transcribe(audio, language=language, subtitles=subtitles)
    if ask_yes_no("\nOpen the output folder?", default=True):
        open_path(Path(result["txt"]).parent)


def menu_script() -> None:
    say("\nSubtitles with the exact words of your script (for example for a voiceover).")
    audio = ask_file("Drag the audio or video file into this window (or type its path), then press Enter")
    if not audio:
        return
    script = ask_file("Now drag the script (.txt file) into this window, then press Enter")
    if not script:
        return
    say("")
    result = cmd_transcribe(audio, script=script)
    if ask_yes_no("\nOpen the output folder?", default=True):
        open_path(Path(result["txt"]).parent)


def run_menu() -> None:
    settings = C.load_settings()
    while True:
        say("\n" + "=" * 60)
        say("  Transcribe - transcripts and subtitles on your own computer")
        say("=" * 60)
        if not settings:
            say("\n  Transcribe isn't installed yet. " + install_hint())
        say("\n  1  Transcribe audio or video (text + subtitles)")
        say("  2  Subtitles from my script (exact words, for example a voiceover)")
        say("  3  Open the web app in your browser")
        say("  4  Check my setup")
        say("  5  Download the models now (so nothing downloads later)")
        say("  0  Exit")
        try:
            choice = input("\nType a number and press Enter: ").replace("\ufeff", "").strip()
        except EOFError:  # input closed (Ctrl+D): leave instead of showing the menu forever
            say("")
            return
        actions = {"1": menu_transcribe, "2": menu_script, "3": cmd_app, "4": cmd_check,
                   "5": lambda: cmd_download("all")}
        if choice in ("0", "q", "exit", "quit"):
            return
        action = actions.get(choice)
        if action is None:
            continue
        try:
            action()
        except UserError as e:
            say(f"\n{e}")
        except WorkerFailed:
            pass
        except KeyboardInterrupt:
            say("\nStopped.")
        ask("\nPress Enter to go back to the menu")


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

HELP = f"""{C.KIT_NAME} {C.KIT_VERSION} - free transcripts and subtitles on your own computer.

Run without anything for a simple menu:   {CMD}

  {CMD} my-video.mp4                 audio or video to text + subtitles
      --language NAME   force the language (normally detected)
      --no-subtitles    text only (faster)
      --hint "WORDS"    names and terms to expect, e.g. "Clipizo, DaVinci Resolve"
      --script FILE     use the exact words of your script for the subtitles
      --max-chars N     longest subtitle line (default 42; 18 for Chinese, Japanese, Korean)
      --quality fast|best
      --out PATH        where to save, without extension (default: the output folder)
  {CMD} a.mp3 b.mp3 c.mp4            several files, one after the other

  {CMD} app                          open the official web app in your browser
  {CMD} download [text|subtitles|all]
                                     download the models now
  {CMD} check                        check that everything works

Results are saved in the output folder: NAME.txt, NAME.srt and NAME.words.json.
To make voiceovers, use the AIvoice kit: https://github.com/Clipizo/AIvoice
"""


def transcribe_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="transcribe", add_help=False)
    p.add_argument("files", nargs="*")
    p.add_argument("--language")
    p.add_argument("--no-subtitles", action="store_true")
    p.add_argument("--hint")
    p.add_argument("--script")
    p.add_argument("--max-chars", type=int)
    p.add_argument("--quality", choices=["fast", "best", "auto"], default=None)
    p.add_argument("--out")
    p.add_argument("--precision", choices=["float32", "float16", "bfloat16"], default=None)
    p.add_argument("--device", choices=["cuda", "mps", "cpu"], default=None)
    return p


def main(argv=None) -> int:
    C.setup_console()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        if sys.stdin.isatty():
            run_menu()
            return 0
        say(HELP)
        return 0
    if argv[0] in ("help", "/?") or any(a in ("-h", "--help") for a in argv):
        say(HELP)
        return 0
    try:
        if argv[0] in SUBCOMMANDS and not Path(argv[0]).is_file():
            sub = argparse.ArgumentParser(prog="transcribe", add_help=False)
            sub.add_argument("command")
            sub.add_argument("what", nargs="?", default="all")
            sub.add_argument("--quality", choices=["fast", "best", "auto"], default=None)
            try:
                args, unknown = sub.parse_known_args(argv)
            except SystemExit:
                say(f"\nI didn't understand that. See the commands with:  {CMD} help")
                return 2
            if unknown:
                say(f"I didn't understand: {' '.join(unknown)}\nSee the commands with:  {CMD} help")
                return 2
            if args.command == "check":
                cmd_check()
            elif args.command == "app":
                cmd_app(args.quality)
            elif args.command == "download":
                cmd_download(args.what, args.quality)
            elif args.command == "menu":
                run_menu()
            return 0

        try:
            args, unknown = transcribe_parser().parse_known_args(argv)
        except SystemExit:
            say(f"\nI didn't understand that. See the commands with:  {CMD} help")
            return 2
        if unknown:
            say(f"I didn't understand: {' '.join(unknown)}\nSee the commands with:  {CMD} help")
            return 2
        if not args.files:
            raise UserError(f"Give me an audio or video file, for example:  {CMD} my-video.mp4")
        if len(args.files) > 1 and (args.out or args.script):
            raise UserError("--out and --script work with one file at a time.")
        for i, f in enumerate(args.files, 1):
            if len(args.files) > 1:
                say(f"\n===== File {i} of {len(args.files)}: {f}")
            cmd_transcribe(f, args.language, not args.no_subtitles, args.hint, args.quality, args.out,
                           args.script, args.max_chars, args.precision, args.device)
    except UserError as e:
        say(f"\n{e}")
        return 2
    except WorkerFailed as e:
        return e.code
    except KeyboardInterrupt:
        say("\nStopped.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
