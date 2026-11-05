---
name: transcribe
description: Installs and runs Transcribe, a local kit for the open Qwen3-ASR speech-recognition models. It turns audio or video files into text (30 languages) and .srt subtitles with word timings, including subtitles that use the exact words of a script. Use it whenever the user asks to transcribe a recording, make subtitles or captions, get word timings, or install, check or repair Transcribe.
---

# Transcribe

You run **Transcribe** for the user on their own computer. It wraps the official Qwen3-ASR models in one simple command. Everything stays on the computer; nothing is uploaded.

## Before you start

- **Read `Transcribe AI Guide.md` once per session.** It is the reference for:
  - every option (section 4);
  - transcripts, subtitles and scripts (section 5);
  - using subtitles in video editors (section 6);
  - troubleshooting (section 8).

  This file only adds the workflow for agents that can run commands.
- **Run commands from the Transcribe folder** (the folder with this file) as `./transcribe ...`. It is the same on every system: in PowerShell on Windows it runs `transcribe.bat`, and on Mac and Linux the installer adds the `./transcribe` shortcut to `transcribe.sh`. If your shell can't run it that way (for example Git Bash or Command Prompt on Windows), run `transcribe.bat` on Windows or `bash transcribe.sh` on Mac and Linux, with the same arguments.

  Below, `transcribe` means `./transcribe`.

## Workflow

1. **Get Transcribe, if the folder isn't on the computer yet.** Use the commands in the guide's section 2: on Windows, `Invoke-WebRequest` and `Expand-Archive` into `C:\Transcribe`; on Mac and Linux, `curl` and `tar` into `~/Transcribe`. Don't depend on `git` or `unzip`: many computers don't have them.
2. **Check the install.** If `envs/settings.json` exists, run `transcribe check` and fix anything it reports. Otherwise install:
   - Windows: `./install-windows.bat --yes` in PowerShell (Command Prompt: `install-windows.bat --yes`)
   - Mac and Linux: `bash install.sh --yes`, never with `sudo` (the installer refuses it).

   The install takes 5 to 30 minutes and downloads 3 to 4 GB with an NVIDIA card (Mac: well under 1 GB). If your command runner has a time limit shorter than that, start it in the background and follow `install-log.txt`, or ask the user to run the installer themselves (on Windows: double-click `install-windows.bat`). Then run `transcribe check`.

   On Windows without Microsoft's Visual C++ component (PyTorch needs it), the installer installs it and **Windows shows a permission prompt**: tell the user to click **Yes**, because the install waits for that answer. With `--yes` the models aren't downloaded during the install; they download the first time Transcribe runs (4 to 7 GB), or add `--download`.

   If the install fails, use the guide's troubleshooting table. `--repair` rebuilds the environment; `--torch cu126` helps older NVIDIA cards. **Never install packages yourself** (pip, conda, brew, PyTorch, CUDA, ffmpeg) and never edit `envs/`.
3. **Understand the request.** Ask, in one message and only for what is missing:
   - which file or files;
   - whether they want subtitles or just the text;
   - names or terms to expect (for `--hint`);
   - whether they have the exact script (for `--script`).

   Defaults: automatic language, text and subtitles, results in `output/`.
4. **Run the command:**
   - `transcribe FILE [--hint "names, terms"] [--language LANGUAGE] [--no-subtitles] [--max-chars N] [--max-words N] [--lines 1|2] [--caps] [--no-punctuation]`
   - With a script: `transcribe FILE --script SCRIPT.txt`
   - Ahead-of-time downloads: `transcribe download`

   Quote file paths that contain spaces. The models download the first time (about 4 to 7 GB). Long recordings take time, a lot without an NVIDIA card: let the command finish (allow 30 minutes or more for long files, or run it in the background). It prints its progress.
5. **Tell the user:**
   - where the files are (the paths printed at the end, in `output/`): `.txt`, `.srt` and `.words.json`;
   - the detected language, and any notes the command printed (for example that subtitle timings aren't available for that language);
   - how to import the `.srt` into their editor or YouTube (guide section 6).

   Check the transcript for obvious mistakes in names and offer a rerun with `--hint`.

## Rules

- **Don't run `transcribe` without arguments** from your command runner: it starts the browser app and keeps running until it's stopped. Use the file commands. If the user wants the browser app, tell them to start it themselves (double-click `transcribe.bat`, or `./transcribe` in their terminal), or start `transcribe app` in the background and give them the address it prints.
- **Only write to `output/`,** or to a place the user names. Never delete the user's files or overwrite them without asking.
- **Leave the kit unchanged** (`app/`, the installers, the docs, this file) unless the user asks.
- **Use the launcher** (`transcribe`), not the files in `app/` directly, and only the options in the guide.
- **Keep it local:** don't upload the user's recordings or transcripts anywhere unless they ask you to.
- **Privacy:** only transcribe recordings the user made or has the right to use.
- **If a command fails,** read its message: Transcribe explains most problems in plain words and suggests a fix, and saves the details in `last-error.txt`. Otherwise, use the guide's troubleshooting table, then `transcribe check`.
