"""Transcribe installer.

Started by install-windows.bat (Windows) or install.sh (Mac and Linux).
It uses only the Python standard library.

What it does:
  1. checks your computer (graphics card, memory, disk space)
  2. creates a private Python environment in envs/ and installs PyTorch for
     your graphics card plus the official Qwen package, with versions that
     are known to work together
  3. tests that everything loads
  4. saves the settings in envs/settings.json

Options (for advanced users and AI agents):
  --yes            don't ask questions (use the recommended answers)
  --download       also download the models now
  --no-download    don't offer to download models
  --torch NAME     force a PyTorch build: cu128, cu126, cpu or pypi
  --repair         delete and rebuild the environment
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402

# --- What this kit installs -------------------------------------------------
ENV = "asr"                                  # folder in envs/
REQUIREMENTS = "asr.txt"                     # in app/requirements/
TORCH_PACKAGES = ["torch"]
PACKAGE = "qwen_asr"                         # the import that must work
WORKER = "asr_worker.py"
MODEL_LABEL = "Qwen3-ASR"
SIZE_KEY = "asr_size"
LAUNCHER_WINDOWS = "transcribe.bat"
LAUNCHER_UNIX = "transcribe.sh"
FIRST_USE = "transcribe a file right away:  {cmd} my-video.mp4"


def first_models(settings: dict) -> list[str]:
    """The model(s) offered for download at the end of the install."""
    return [C.ASR_MODELS[settings[SIZE_KEY]], C.ALIGNER_MODEL]


def default_size(device: str, vram_gb: float, ram_gb: float, dtype: str) -> str:
    if device == "cuda":
        return "1.7B" if vram_gb >= (14 if dtype == "float32" else 7.5) else "0.6B"
    if device == "mps":
        return "1.7B" if ram_gb >= 16 else "0.6B"
    return "0.6B"
# ----------------------------------------------------------------------------

PYTHON_VERSION = "3.12"
TORCH_VERSION = "2.8.0"
TORCH_INDEXES = {
    "cu128": "https://download.pytorch.org/whl/cu128",
    "cu126": "https://download.pytorch.org/whl/cu126",
    "cpu": "https://download.pytorch.org/whl/cpu",
    "pypi": None,
}
LOG_FILE = C.KIT / "install-log.txt"


class InstallError(Exception):
    pass


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def log(msg: str = "") -> None:
    print(msg, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def step(n: int, total: int, title: str) -> None:
    log("")
    log(f"[{n}/{total}] {title}")
    log("-" * 60)


def ask_yes_no(question: str, default: bool, assume_yes: bool) -> bool:
    if assume_yes or not sys.stdin.isatty():
        return default
    hint = "Y/n" if default else "y/N"
    while True:
        try:
            a = input(f"{question} ({hint}): ").strip().lower()
        except EOFError:
            return default
        if not a:
            return default
        if a in ("y", "yes"):
            return True
        if a in ("n", "no"):
            return False


def run(cmd: list[str], what: str) -> None:
    log("  > " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    code = subprocess.call(cmd, cwd=str(C.KIT))
    log(f"  (exit code {code})")
    if code != 0:
        raise InstallError(f"{what} failed.")


# ---------------------------------------------------------------------------
# Detecting the computer
# ---------------------------------------------------------------------------

def ram_gb() -> float | None:
    try:
        if C.IS_WINDOWS:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
            return stat.ullTotalPhys / 1024**3
        if C.IS_MAC:
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout
            return int(out.strip()) / 1024**3
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024**2
    except Exception:
        return None
    return None


def nvidia_gpu() -> dict | None:
    exe = shutil.which("nvidia-smi")
    if not exe and C.IS_WINDOWS:
        for p in (r"C:\Windows\System32\nvidia-smi.exe",
                  r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
            if Path(p).exists():
                exe = p
                break
    if not exe:
        return None
    for fields in ("name,memory.total,driver_version,compute_cap", "name,memory.total,driver_version"):
        try:
            proc = subprocess.run([exe, f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
                                  capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode == 0 and proc.stdout.strip():
            parts = [p.strip() for p in proc.stdout.strip().splitlines()[0].split(",")]
            gpu = {"name": parts[0], "driver": parts[2] if len(parts) > 2 else ""}
            try:
                gpu["vram_gb"] = round(float(parts[1]) / 1024, 1)
            except (ValueError, IndexError):
                gpu["vram_gb"] = None
            try:
                gpu["cc"] = float(parts[3]) if len(parts) > 3 else None
            except ValueError:
                gpu["cc"] = None
            return gpu
    return None


def apple_silicon() -> bool:
    if not C.IS_MAC:
        return False
    if platform.machine().lower() == "arm64":
        return True
    out = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout
    return out.strip() == "1"


def detect() -> dict:
    info = {
        "os": platform.system(),
        "os_version": platform.release(),
        "machine": platform.machine().lower(),
        "ram_gb": ram_gb(),
        "apple_silicon": apple_silicon(),
        "nvidia": None if C.IS_MAC else nvidia_gpu(),
    }
    try:
        info["disk_free_gb"] = shutil.disk_usage(C.KIT).free / 1024**3
    except OSError:
        info["disk_free_gb"] = None
    return info


def choose_torch(info: dict, forced: str | None) -> str:
    if forced:
        return forced
    if C.IS_MAC:
        return "pypi"
    gpu = info.get("nvidia")
    if gpu:
        cc = gpu.get("cc")
        return "cu126" if cc is not None and cc < 7.5 else "cu128"
    if info["machine"] in ("aarch64", "arm64"):
        return "pypi"
    return "cpu"


def check_supported(info: dict) -> None:
    if C.IS_MAC and not info["apple_silicon"]:
        raise InstallError(
            f"This Mac has an Intel processor. Current PyTorch versions only support Macs with Apple\n"
            f"Silicon (M1 or newer), so {C.KIT_NAME} can't run here. You can use it on a Windows or Linux PC,\n"
            "or on any Mac with an M-series chip.")
    if C.IS_WINDOWS and info["machine"] in ("arm64", "aarch64"):
        raise InstallError("Windows on ARM (for example Snapdragon laptops) isn't supported yet.")
    if info["machine"] not in ("x86_64", "amd64", "arm64", "aarch64"):
        raise InstallError(f"This kind of processor ({info['machine']}) isn't supported.")


def check_folder(assume_yes: bool) -> None:
    path = str(C.KIT)
    short = f"C:\\{C.KIT_NAME}"
    problems = []
    if C.IS_WINDOWS:
        low = path.lower()
        if "\\appdata\\local\\temp" in low or ".zip" in low:
            raise InstallError(
                "It looks like you started the installer from inside the ZIP file.\n"
                "Please extract (unzip) the folder first: right-click the ZIP > Extract All...\n"
                f"Then move the folder to {short} and run install-windows.bat from there.")
        if len(path) > 60:
            problems.append(f"The folder path is long ({len(path)} characters). Windows can fail on long paths.\n"
                            f"  Recommended: move the folder to {short} and run the installer again.")
    if "onedrive" in path.lower() or "icloud" in path.lower() or "dropbox" in path.lower():
        problems.append("This folder is synced to the cloud (OneDrive, iCloud or Dropbox). The models are\n"
                        "  large (several GB) and would be uploaded. Recommended: move the folder outside it,\n"
                        f"  for example to {short} (Windows) or your home folder (Mac).")
    if not path.isascii():
        problems.append("The folder path contains special characters. If something fails, move the folder\n"
                        f"  to a simple path like {short}.")
    for p in problems:
        log("WARNING: " + p)
    if problems and not ask_yes_no("Continue anyway?", default=True, assume_yes=assume_yes):
        raise InstallError("Install stopped. Move the folder and run the installer again.")


# ---------------------------------------------------------------------------
# Installing
# ---------------------------------------------------------------------------

def find_uv() -> str:
    candidates = [os.environ.get("KIT_UV", "")]
    exe = "uv.exe" if C.IS_WINDOWS else "uv"
    candidates += [str(C.TOOLS / "uv" / exe), str(C.TOOLS / "uv" / "bin" / exe), shutil.which("uv") or ""]
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise InstallError("I couldn't find 'uv' (the tool that installs Python). Run the installer\n"
                       "with install-windows.bat or install.sh instead of running this file directly.")


def installed_torch() -> str | None:
    py = C.env_python(ENV)
    if not py.exists():
        return None
    proc = subprocess.run([str(py), "-c", "import importlib.metadata as m; print(m.version('torch'))"],
                          capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def torch_matches(version: str | None, index: str) -> bool:
    if not version or not version.startswith(TORCH_VERSION):
        return False
    local = version.split("+", 1)[1] if "+" in version else ""
    if index in ("cu128", "cu126", "cpu"):
        return local == index
    return local == ""


def probe() -> dict:
    py = C.env_python(ENV)
    proc = subprocess.run([str(py), str(C.APP / WORKER), "probe"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=C.child_env(), cwd=str(C.KIT))
    for line in proc.stdout.splitlines():
        if line.startswith("KIT_PROBE="):
            return json.loads(line.split("=", 1)[1])
    return {"error": (proc.stderr or proc.stdout)[-800:]}


def env_works(py: Path) -> bool:
    """False if the environment is broken, for example after the folder was moved."""
    try:
        proc = subprocess.run([str(py), "-c", "import sys; print(sys.prefix)"], capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    try:
        return Path(proc.stdout.strip()).resolve() == py.parent.parent.resolve()
    except OSError:
        return False


def install_env(uv: str, index: str, repair: bool) -> None:
    env_dir = C.ENVS / ENV
    py = C.env_python(ENV)
    if repair and env_dir.exists():
        log("  Removing the old environment...")
        shutil.rmtree(env_dir)
    elif py.exists() and not env_works(py):
        log("  The environment is broken (was the folder moved?). Rebuilding it...")
        shutil.rmtree(env_dir)
    if not py.exists():
        if env_dir.exists():
            shutil.rmtree(env_dir)
        run([uv, "venv", str(env_dir), "--python", PYTHON_VERSION, "--quiet"], "Creating the environment")
    else:
        log("  The environment already exists; checking it.")

    cmd = [uv, "pip", "install", "--python", str(py), *[f"{p}=={TORCH_VERSION}" for p in TORCH_PACKAGES]]
    url = TORCH_INDEXES[index]
    if url:
        cmd += ["--index-url", url]
    current = installed_torch()
    if current and not torch_matches(current, index):
        log(f"  Replacing PyTorch {current} with the {index} build.")
        for p in TORCH_PACKAGES:
            cmd += ["--reinstall-package", p]
    if not torch_matches(current, index):
        log("  Downloading PyTorch. It is big (Mac: about 100 MB, NVIDIA: about 3 GB), so this can take a while.")
    run(cmd, "Installing PyTorch")
    run([uv, "pip", "install", "--python", str(py), "--no-deps", "-r", str(C.APP / "requirements" / REQUIREMENTS)],
        f"Installing {MODEL_LABEL} and the other packages")
    code = subprocess.call([uv, "pip", "check", "--python", str(py)], cwd=str(C.KIT))
    if code != 0:
        log("  (uv pip check reported the issues above; continuing, the test below decides.)")


def make_settings(info: dict, p: dict, index: str) -> dict:
    s = {"kit": C.KIT_NAME, "kit_version": C.KIT_VERSION, "torch_build": index,
         "installed": time.strftime("%Y-%m-%d %H:%M")}
    ram = info.get("ram_gb") or 8
    if p.get("cuda") and p.get("cuda_ok"):
        major = (p.get("cc") or [0])[0]
        dtype = "bfloat16" if major >= 8 else ("float16" if major >= 7 else "float32")
        vram = p.get("vram_gb") or 0
        s.update(device="cuda", dtype=dtype, gpu=p.get("gpu"), vram_gb=vram)
    elif p.get("mps"):
        s.update(device="mps", dtype="float32", ram_gb=round(ram))
    else:
        s.update(device="cpu", dtype="float32", ram_gb=round(ram))
    s[SIZE_KEY] = default_size(s["device"], s.get("vram_gb") or 0, ram, s["dtype"])
    return s


def describe(info: dict) -> None:
    log(f"  System:     {info['os']} {info['os_version']} ({info['machine']})")
    if info.get("ram_gb"):
        log(f"  Memory:     {info['ram_gb']:.0f} GB")
    gpu = info.get("nvidia")
    if gpu:
        cc = f", compute {gpu['cc']}" if gpu.get("cc") else ""
        log(f"  Graphics:   NVIDIA {gpu['name']} ({gpu.get('vram_gb')} GB, driver {gpu.get('driver')}{cc})")
    elif info["apple_silicon"]:
        log("  Graphics:   Apple Silicon (M-series)")
    else:
        log(f"  Graphics:   no NVIDIA graphics card found, so {C.KIT_NAME} will use the processor (slow)")
    if info.get("disk_free_gb") is not None:
        log(f"  Free disk:  {info['disk_free_gb']:.0f} GB")


def main() -> int:
    C.setup_console()
    parser = argparse.ArgumentParser(description=f"{C.KIT_NAME} installer")
    parser.add_argument("--yes", action="store_true", help="don't ask questions")
    parser.add_argument("--download", action="store_true", help="also download the models")
    parser.add_argument("--no-download", action="store_true", help="don't offer to download models")
    parser.add_argument("--torch", choices=list(TORCH_INDEXES), help="force a PyTorch build")
    parser.add_argument("--repair", action="store_true", help="rebuild the environment from scratch")
    args = parser.parse_args()

    try:
        LOG_FILE.write_text(f"{C.KIT_NAME} {C.KIT_VERSION} install log, {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
                            encoding="utf-8")
    except OSError:
        pass

    log("")
    log("=" * 60)
    log(f"  {C.KIT_NAME} {C.KIT_VERSION} installer")
    log("=" * 60)
    log(f"This sets up everything {C.KIT_NAME} needs inside this folder. Nothing")
    log("else on your computer is changed. It takes 5 to 30 minutes, depending")
    log("on your internet connection.")
    total = 4
    try:
        step(1, total, "Checking your computer")
        info = detect()
        describe(info)
        check_supported(info)
        check_folder(args.yes)
        free = info.get("disk_free_gb")
        if free is not None and free < 12:
            log(f"WARNING: only {free:.0f} GB free. {C.KIT_NAME} needs about 6 GB for the programs and")
            log("         2 to 5 GB for each AI model.")
            if not ask_yes_no("Continue anyway?", default=free >= 8, assume_yes=args.yes):
                raise InstallError("Install stopped. Free up disk space and run the installer again.")
        gpu = info.get("nvidia")
        if gpu and gpu.get("driver"):
            try:
                if int(gpu["driver"].split(".")[0]) < 525:
                    log("WARNING: your NVIDIA driver is old. If the graphics card isn't used, update the")
                    log("         driver from nvidia.com (or the NVIDIA App) and run this again.")
            except ValueError:
                pass
        index = choose_torch(info, args.torch)
        label = {"cu128": "NVIDIA graphics (CUDA 12.8)", "cu126": "NVIDIA graphics (CUDA 12.6)",
                 "cpu": "processor only", "pypi": "standard build"}[index]
        log(f"  PyTorch:    {label}")

        uv = find_uv()
        C.ENVS.mkdir(parents=True, exist_ok=True)
        step(2, total, f"Installing Python, PyTorch and {MODEL_LABEL}")
        install_env(uv, index, args.repair)

        step(3, total, "Testing the installation")
        p = probe()
        if p.get("cuda") and not p.get("cuda_ok") and index == "cu128":
            log(f"  The graphics card can't run the CUDA 12.8 build ({p.get('cuda_error', '')[:120]}).")
            log("  Switching to the CUDA 12.6 build...")
            index = "cu126"
            install_env(uv, index, False)
            p = probe()
        if not p.get("package_ok"):
            raise InstallError("The installation doesn't load:\n  "
                               f"{p.get('package_error') or p.get('torch_error') or p.get('error')}")
        where = ("NVIDIA " + str(p.get("gpu"))) if p.get("cuda_ok") else ("Apple Silicon" if p.get("mps") else "processor")
        log(f"  OK: Python {p.get('python')}, PyTorch {p.get('torch')}, runs on {where}")
        if not p.get("ffmpeg"):
            raise InstallError("The audio converter (ffmpeg) didn't install.")
        if gpu and not p.get("cuda_ok"):
            log(f"WARNING: an NVIDIA graphics card was found, but PyTorch can't use it, so {C.KIT_NAME} will")
            log("         use the processor (slow). Updating the NVIDIA driver usually fixes this;")
            log("         then run the installer again.")

        step(4, total, "Saving settings")
        settings = make_settings(info, p, index)
        C.save_settings(settings)
        log(f"  Runs on: {settings['device']} ({settings['dtype']}).  Default model size: {settings[SIZE_KEY]}.")
        if not C.IS_WINDOWS:
            for f in (LAUNCHER_UNIX, "install.sh"):
                try:
                    os.chmod(C.KIT / f, 0o755)
                except OSError:
                    pass
        for d in (C.OUTPUT, C.MODELS):
            d.mkdir(exist_ok=True)

        repos = [r for r in first_models(settings) if not C.model_is_downloaded(r)]
        if repos:
            gb = sum(C.MODEL_SIZES_GB.get(r, 0) for r in repos)
            want = args.download or (not args.no_download and not args.yes and ask_yes_no(
                f"\nDownload the AI models now? (about {gb:.1f} GB; otherwise they download\n"
                "the first time you use it)", default=True, assume_yes=False))
            if want:
                code = subprocess.call([str(C.env_python(ENV)), str(C.APP / WORKER), "download",
                                        *[x for r in repos for x in ("--repo", r)]],
                                       env=C.child_env(), cwd=str(C.KIT))
                if code != 0:
                    log("The model download didn't finish. That's OK: it continues the first time you use it.")
    except InstallError as e:
        log("")
        log("!" * 60)
        log(str(e))
        log("!" * 60)
        log(f"A log was saved to {LOG_FILE.name}. If you're stuck, give that file (or the text above)")
        log("to your AI assistant.")
        return 1
    except KeyboardInterrupt:
        log("\nInstall stopped. Run the installer again to continue where it stopped.")
        return 130

    log("")
    log("=" * 60)
    log(f"  {C.KIT_NAME} is installed!")
    log("=" * 60)
    if C.IS_WINDOWS:
        log(f"Start it: double-click  {LAUNCHER_WINDOWS}  in this folder.")
        log("Or, in a terminal in this folder, " + FIRST_USE.format(cmd=C.launcher_command()))
    else:
        log(f"Start it from Terminal, in this folder:  ./{LAUNCHER_UNIX}")
        log("Or " + FIRST_USE.format(cmd=C.launcher_command()))
    if settings["device"] == "cpu":
        log("")
        log("Note: no supported graphics card, so the AI runs on the processor. It works, but it")
        log("is slow. Short texts and recordings are fine; long ones take a while.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
