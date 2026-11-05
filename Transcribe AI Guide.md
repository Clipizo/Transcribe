# Transcribe AI Guide

For **Transcribe 1.0** (Clipizo). Give this file to any AI chat, such as ChatGPT, Claude, Gemini or Copilot, and it can walk you through installing Transcribe and turning audio and video into text and subtitles on your own computer.

---

## Quick start (for you)

1. **Give this file to your AI.** Attach it to the chat (or paste all of its text), or give the AI the link `https://github.com/Clipizo/Transcribe` and ask it to read this file.
2. **Say what you have and what you want.** For example: *"I have a Mac with an M2 chip. Help me install Transcribe and make subtitles for my YouTube video."*
3. **Do one step at a time.** After each step, tell the AI what happened. If you see an error, copy the text from the window and paste it into the chat.

---

## Instructions for the AI

You are helping someone who may never have used a terminal. Transcribe is a kit that installs the open Qwen3-ASR speech-recognition models into one folder and runs them through a browser app and one simple command. Everything you need is in this guide. **Only use the commands, options and file names in this guide; don't invent others.**

**How to help:**

1. **Find out what you need to know first,** in one short message:
   - their computer: Windows, Mac or Linux (on a Mac: Apple Silicon or Intel; see section 2);
   - whether it has an NVIDIA graphics card (if they don't know, section 2 explains how to check);
   - what they want: a transcript, subtitles, or subtitles for a script they already have.
2. **Give one step at a time,** with the exact clicks or the exact command in a code block. Wait for them to say it worked before the next step. Tell them what they should see.
3. **When something fails,** ask them to paste the text from the window, find the problem in the troubleshooting table (section 8) and give the fix. `./transcribe check` (section 4) shows the state of the install. After an error, Transcribe also writes the technical details to `last-error.txt` in its folder; ask for that file if you need more.
4. **Never send them to install things by hand** (Python, pip, conda, PyTorch, CUDA, ffmpeg). The installer does all of it inside the Transcribe folder. To repair anything, run the installer again (section 2), with `--repair` if needed.
5. **Explain where the results are** (the `output` folder) and how to use them, for example how to put subtitles in their video editor (section 6).
6. If you can run commands on their computer yourself (an AI agent), also follow `SKILL.md`.

**Commands are the same on every system.** They start with `./transcribe` and are typed in **PowerShell** on Windows or in **Terminal** on Mac and Linux, inside the Transcribe folder. On Windows, `./transcribe` runs `transcribe.bat`; on Mac and Linux it runs `transcribe.sh` (the installer adds the `./transcribe` shortcut). Only in the old Windows Command Prompt, type `transcribe` without `./`.

The terminal must be **in the Transcribe folder** (section 4 explains how). File names with spaces need quote marks: `./transcribe "my holiday video.mp4"`. Dragging the file into the terminal window adds them automatically.

---

## 1. What Transcribe does

| Feature | Command | Model |
|---|---|---|
| Text of a recording | `./transcribe FILE --no-subtitles` | Qwen3-ASR (0.6B or 1.7B) |
| Text and subtitles | `./transcribe FILE` | Qwen3-ASR, plus Qwen3-ForcedAligner-0.6B for the timings |
| Subtitles with the exact words of a script | `./transcribe FILE --script SCRIPT.txt` | Qwen3-ForcedAligner-0.6B (plus Qwen3-ASR for recordings over 3 minutes) |
| Browser app: everything above, with a subtitle preview and controls | `./transcribe` | the same models |

- Everything runs on the user's computer. Nothing is uploaded; there is no account and no cost.
- The models download automatically from Hugging Face (huggingface.co) into the `models` folder the first time they're needed (about 4 to 7 GB in total, once). Section 9 lists every model with its download page.
- **Text in 30 languages:** Chinese, English, Cantonese, Arabic, German, French, Spanish, Portuguese, Indonesian, Italian, Korean, Russian, Thai, Vietnamese, Japanese, Turkish, Hindi, Malay, Dutch, Swedish, Danish, Finnish, Polish, Czech, Filipino, Persian, Greek, Romanian, Hungarian, Macedonian, plus 22 Chinese dialects. The language is detected automatically.
- **Subtitle timings in 11 languages:** Chinese, English, Cantonese, French, German, Italian, Japanese, Korean, Portuguese, Russian, Spanish. For other languages, Transcribe saves the text only.
- To make voiceovers, there is a companion kit: AIvoice (`https://github.com/Clipizo/AIvoice`).

## 2. Install

### Check the computer first

| Question | How to check | What it means |
|---|---|---|
| Enough disk space? | Windows: File Explorer > **This PC** shows the free space on `C:`. Mac: Apple menu > **System Settings** > **General** > **Storage**. | About **15 GB free** (about 8 GB for the programs, 4 to 7 GB for the models). |
| Which system? | | Windows 10 or 11 (64-bit), a Mac with Apple Silicon, or Linux. |
| Mac: Apple Silicon or Intel? | Apple menu > **About This Mac**. "Chip: Apple M1" (M2, M3, M4...) is Apple Silicon. "Processor: Intel" is Intel. | **Intel Macs can't run Transcribe** (current PyTorch doesn't support them). |
| Windows: NVIDIA graphics card? | Press Ctrl+Shift+Esc (Task Manager) > **Performance**. A "GPU" entry named "NVIDIA ..." means yes; it also shows the "Dedicated GPU memory". | With NVIDIA: fast. Without: Transcribe still works, on the processor, but long recordings take a while. |
| Windows on ARM? | Settings > System > About: "ARM-based processor". | Not supported. |

### Windows

Each command goes into **PowerShell** (press the Windows key, type `PowerShell`, press Enter). Give the user one command at a time; they paste it, press Enter, and wait until it finishes.

Many of these commands print nothing when they work; the next line starting with `PS` means it's ready for the next one. To paste in PowerShell: right-click, or Ctrl+V.

1. Download Transcribe:
   ```powershell
   Invoke-WebRequest "https://github.com/Clipizo/Transcribe/archive/refs/heads/main.zip" -OutFile "$env:TEMP\Transcribe.zip" -UseBasicParsing
   ```
2. Unzip it:
   ```powershell
   Expand-Archive "$env:TEMP\Transcribe.zip" -DestinationPath "C:\" -Force
   ```
3. Rename the folder to `C:\Transcribe`:
   ```powershell
   Rename-Item "C:\Transcribe-main" "Transcribe"
   ```
4. Go into the folder:
   ```powershell
   cd C:\Transcribe
   ```
5. Install:
   ```powershell
   ./install-windows.bat
   ```
   - It shows the progress in 4 steps. The PyTorch download (about 3 GB with an NVIDIA card) can take 5 to 20 minutes and may look stuck; it isn't.
   - **Don't click inside the window:** that pauses it (the title then starts with "Select"). If that happens, press Esc.
   - If Windows lacks a Microsoft component PyTorch needs, the installer offers to install it: press Enter, then click **Yes** when Windows asks for permission.
   - At the end it offers to download the models now: press Enter for yes.
   - **Done** when it says **Transcribe is installed!**, followed by "Press any key to continue": press a key.
6. Start Transcribe:
   ```powershell
   ./transcribe
   ```
   It opens in the browser (section 3). Keep the window open while using it.

**Without commands:** on the GitHub page, click **Code** > **Download ZIP**. Right-click the ZIP > **Extract All...**, extract it to `C:\`, rename `C:\Transcribe-main` to `C:\Transcribe`, then double-click `install-windows.bat` and later `transcribe.bat`. If Windows shows *"Windows protected your PC"*, click **More info** > **Run anyway**; if it asks *"Do you want to run this file?"*, click **Run**. Don't run anything from inside the ZIP without extracting it.

**Where the folder goes:** `C:\Transcribe` is ideal. Avoid long paths, OneDrive folders and the Desktop: the AI models are large and long paths can break the install.

**If a command fails:**
- `Rename-Item` says the file already exists: Transcribe was downloaded before. Use the existing `C:\Transcribe` (run the installer again in it), or, for a fresh copy, keep the old folder under another name with `Rename-Item "C:\Transcribe" "Transcribe-old"` and run step 3 again.
- `Invoke-WebRequest` fails with an SSL/TLS error (older Windows 10): use the "Without commands" way above.
- The installer stops with an error: it explains the problem in plain words. Running it again is safe and continues where it stopped (downloads that dropped are retried automatically first).

### Mac (Apple Silicon)

Each command goes into **Terminal** (press Cmd+Space, type `Terminal`, press Enter), one at a time:

1. Go to the home folder:
   ```bash
   cd ~
   ```
2. Download Transcribe:
   ```bash
   curl -L -o Transcribe.tar.gz https://github.com/Clipizo/Transcribe/archive/refs/heads/main.tar.gz
   ```
3. Unpack it:
   ```bash
   tar -xzf Transcribe.tar.gz
   ```
4. Rename the folder to `Transcribe`:
   ```bash
   mv Transcribe-main Transcribe
   ```
5. Go into the folder:
   ```bash
   cd ~/Transcribe
   ```
6. Install. It shows the progress in 4 steps and takes about 5 to 15 minutes. At the end, press Enter to download the models. Done when it says **Transcribe is installed!**
   ```bash
   bash install.sh
   ```
7. Start Transcribe:
   ```bash
   ./transcribe
   ```
   It opens in the browser (section 3). Keep the window open while using it.

If `~/Transcribe` already exists (Transcribe was downloaded before), `mv` would put the new folder inside it. Either use the existing `~/Transcribe` folder (run the installer again in it), or, for a fresh copy, first run `mv ~/Transcribe ~/Transcribe-old`, then step 4.

### Linux

The same commands as on a Mac, in a terminal (Ubuntu: Ctrl+Alt+T). They use `tar`, which every Linux has (`unzip` often isn't installed). If `curl` isn't installed, download with `wget -O Transcribe.tar.gz https://github.com/Clipizo/Transcribe/archive/refs/heads/main.tar.gz` instead. With `git`, `git clone https://github.com/Clipizo/Transcribe.git ~/Transcribe` replaces the download, unpack and rename steps. No step needs `sudo`; don't run the installer with `sudo`.

For NVIDIA graphics, the NVIDIA driver must be installed (`nvidia-smi` should work).

**WSL (Linux inside Windows)** works like Linux (tested on Ubuntu 24.04 with an NVIDIA card). Keep the folder in the Linux home folder (`~/Transcribe`), not under `/mnt/c`, which is much slower. The graphics card works through the normal Windows NVIDIA driver: don't install an NVIDIA driver inside WSL. For most Windows users the Windows steps above are simpler.

### Starting it next time

- **Windows:** double-click `transcribe.bat` in `C:\Transcribe`, or in PowerShell run `cd C:\Transcribe` and then `./transcribe`.
- **Mac and Linux:** in Terminal, run `cd ~/Transcribe` and then `./transcribe`.

### Installer options

Add these after `install-windows.bat` (in a terminal) or `bash install.sh`:

| Option | Use |
|---|---|
| `--repair` | Rebuild the environment from scratch. The fix for most broken installs. |
| `--torch cu126` | For older NVIDIA cards (GTX 900 and 1000 series) if the default build fails. Other values: `cu128` (default for NVIDIA), `cpu` (no graphics card), `pypi`. |
| `--yes` | Don't ask questions (for agents and scripts). |
| `--download` | Also download the models during the install. |

Running the installer again is always safe: it skips what is already done. Each run writes `install-log.txt` in the Transcribe folder.

## 3. The browser app (easiest)

**Windows:** double-click `transcribe.bat` (or run `./transcribe` in PowerShell in the Transcribe folder). **Mac/Linux:** in Terminal, in the Transcribe folder, run `./transcribe`. Transcribe opens in the browser at `http://127.0.0.1:7860` (the next free number if that one is busy). It runs only on this computer. The window that started it must stay open; closing it stops Transcribe.

The first time, if the models weren't downloaded during the install, they download first (4 to 7 GB, with progress in that window), and then the browser opens.

On the page:

- **Left:** the audio or video file (drop it in or click to choose), **Language** (Auto detects it), **Quality** (Auto, Fast = 0.6B model, Best = 1.7B model), **Names and terms** (like `--hint`), **Script** (optional: paste the exact words for script-accurate subtitles), and the **Transcribe** button.
- **Right:** a **Preview** that plays the file with the subtitles on it (formats the browser can't play, like MKV or AVI, get an audio preview), then the subtitle controls: **Characters per line** (10 to 60), **Words per line** (Any, or 1 for one word at a time), **Lines** (1 or 2 per subtitle), **Style** (UPPERCASE, No punctuation). Changing them re-cuts the subtitles at once from the saved word timings, without transcribing again.
- **Subtitles** and **Text** tabs show the result. **Download** has the `.srt`, `.txt` and `.words.json`, which are also saved in the `output` folder. **Open the output folder** opens it.

The first file after starting takes longer (the models load). With enough memory, the models stay loaded, so the next files are quick.

**A simple menu in the terminal** is still there for people who prefer it: `./transcribe menu` (1 transcribe a file, 2 subtitles from a script, 3 the browser app, 4 check the setup, 5 download the models). Dragging a file into the terminal window types its path.

## 4. Commands

**Open a terminal in the Transcribe folder:**

- **Windows:** in PowerShell, run `cd C:\Transcribe`. Or open the folder in File Explorer and right-click an empty spot > **Open in Terminal**. (Clicking the address bar, typing `cmd` and pressing Enter opens Command Prompt there instead, where you write `transcribe` without `.\`.)
- **Mac and Linux:** in Terminal, run `cd ~/Transcribe`. If the folder is somewhere else, type `cd ` (with a space), drag the folder into the window, and press Enter.

**All commands:**

```
./transcribe FILE [FILE...]           audio or video to text and subtitles
    --language NAME     force the language (normally detected)
    --no-subtitles      text only (faster)
    --hint "WORDS"      names and terms to expect, e.g. "Clipizo, DaVinci Resolve"
    --script FILE.txt   use the exact words of this script for the subtitles
    --max-chars N       longest subtitle line, 8 to 80 characters (default 42;
                        18 for Chinese, Japanese and Korean)
    --max-words N       at most N words per line, 1 to 30 (1 = one word at a time)
    --lines 1|2         lines per subtitle (default 1)
    --caps              subtitles in CAPITALS
    --no-punctuation    subtitles without punctuation (inside words, like "don't", it stays)
    --quality fast|best fast = 0.6B model, best = 1.7B model (default: chosen for your computer)
    --out PATH          where to save, without extension (default: the output folder)

./transcribe                          open the browser app (section 3)
./transcribe app --no-browser         start the browser app without opening a browser
./transcribe menu                     a simple menu in the terminal
./transcribe download [text|subtitles|all]   download the models now
./transcribe check                    check that everything works
./transcribe help                     show the commands
```

Transcribing also accepts `--device cpu` (to avoid the graphics card) and `--precision float32` (for problems on older graphics cards). `--out` and `--script` work with one file at a time.

**Where things are saved:** in `output/`, named after the file: `NAME.txt` (the text, one sentence per line; with `--script`, the script), `NAME.srt` (subtitles) and `NAME.words.json` (every word with its start and end time, in seconds). Nothing is overwritten: a second run adds `-2`. Downloaded models are in `models/`.

## 5. Transcripts and subtitles

```
./transcribe interview.mp3
./transcribe my-video.mp4 --hint "Clipizo, DaVinci Resolve"
./transcribe podcast.wav --language Spanish --no-subtitles
./transcribe vertical-short.mp4 --max-chars 20
./transcribe reel.mp4 --max-words 1 --caps --no-punctuation
./transcribe film.mp4 --lines 2
```

- **Files:** almost any audio or video: mp3, wav, m4a, aac, flac, ogg, mp4, mov, mkv, webm...
- **Long recordings** are processed in parts of about 3 minutes, with progress and the time left. An hour of audio is fine; it just takes longer.
- `--hint` helps with names, brands and technical terms.
- `--language` helps when the language is detected wrong, or when the recording mixes languages.
- **Subtitle lines** follow the sentences: each sentence starts a new subtitle, and long sentences are split evenly, preferably after a comma. A line has at most about 42 characters (18 for Chinese, Japanese and Korean; change it with `--max-chars`) and lasts at most 6 seconds. With `--max-words`, lines also have at most that many words. With `--lines 2`, a subtitle shows up to two balanced lines (a short one stays on one line). These options only change the `.srt`; the `.words.json` always has every word.

### Subtitles with the exact words of a script

When the words are known, for example for a voiceover read from a script, the subtitles can use them exactly instead of what the model heard:

```
./transcribe voiceover.wav --script my-script.txt
```

- The script must be what is spoken, in the same order. Markdown marks (`#`, `**`, bullets) are removed. Each line of the script starts a new subtitle line.
- For recordings up to about 3 minutes, Transcribe only times the words. For longer ones, it first listens to find where each part of the script is spoken, so small differences between the script and the recording are fine.
- **With AIvoice:** AIvoice saves the text of each voiceover next to it, so `./transcribe output/my-script.wav --script output/my-script.txt` (run from the Transcribe folder, with the full paths to the AIvoice files) gives perfect subtitles.

## 6. Subtitles in video editors

`.srt` files work in almost every editor. Usually you import the file like any media file and drag it onto the timeline:

- **DaVinci Resolve:** File > Import > Subtitle, then drag the subtitle clip onto the timeline.
- **Premiere Pro:** File > Import, then drag the file onto the timeline; it becomes a caption track.
- **CapCut:** in the Captions or Text panel, choose to import a local caption file.
- **YouTube:** in YouTube Studio, open the video > Subtitles > Add > Upload file > With timing.

The editor's menus may differ by version; the help of each program explains its current steps. The `.words.json` file has every word's timing, for tools that animate captions word by word.

## 7. More about the browser app

- It only runs on this computer (`127.0.0.1`); it isn't visible on the network, and nothing is uploaded anywhere. "Upload" in the page only means handing the file to Transcribe on the same computer.
- To stop it, close the window that started it (or press Ctrl+C in it).
- If the browser doesn't open by itself, open the address the window prints, for example `http://127.0.0.1:7860`.
- One file at a time: a second click on **Transcribe** waits until the first file is done.
- For many files at once, the command (`./transcribe a.mp4 b.mp4 c.mp4`) is quicker.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| "Windows protected your PC" | Click **More info** > **Run anyway**. |
| The installer window closes immediately, or Windows opens the file in Notepad | Make sure the ZIP was extracted (section 2) and double-click `install-windows.bat` itself. |
| "It looks like you started the installer from inside the ZIP file" | Extract the ZIP first, move the folder to `C:\Transcribe`, and run the installer from there. |
| "Could not download uv" | No internet, or the network blocks `astral.sh` or `github.com` (some school and office networks). Try another network. |
| Mac or Linux: `unzip: command not found` | Use the steps in section 2: they download a `.tar.gz` and unpack it with `tar -xzf Transcribe.tar.gz`, which every Mac and Linux has. |
| Linux: `curl: command not found` | Download with `wget -O Transcribe.tar.gz https://github.com/Clipizo/Transcribe/archive/refs/heads/main.tar.gz` instead. |
| "Please run the installer without sudo" | Run `bash install.sh` without `sudo`. If an earlier run with `sudo` left files the user can't change ("Permission denied" inside the Transcribe folder), give the folder back once with `sudo chown -R "$USER" ~/Transcribe`, then run the installer again. |
| Windows: the installer says a Microsoft component is missing, or an error mentions `c10.dll`, `WinError 126` or "DLL load failed" | The installer offers to install it (Microsoft's free Visual C++ Redistributable): press Enter, then click **Yes** when Windows asks for permission. If that fails, download it from `https://aka.ms/vs/17/release/vc_redist.x64.exe`, run it, restart the computer, and run the installer again. |
| "Installing PyTorch failed, 3 times" or another download error during the install | An internet problem. Check the connection and run the installer again: it keeps what it downloaded. On school, work or some country networks, `download.pytorch.org` or `pypi.org` may be blocked: try another network. |
| The install looks stuck | The PyTorch download is large; wait. On Windows, if the window title starts with "Select", press Esc (clicking the window pauses it). |
| A warning about a long path, OneDrive, iCloud or special characters | Move the folder to `C:\Transcribe` (Windows) or the home folder (Mac), then run the installer again with `--repair`. |
| "Transcribe isn't installed yet" | Run the installer (section 2). If it ran, look at the end of its window or `install-log.txt` for the error. |
| The folder was moved or renamed after installing | Run the installer again (it rebuilds what broke), or with `--repair`. |
| "This Mac has an Intel processor" | Intel Macs can't run Transcribe. Use a Mac with Apple Silicon, or a Windows or Linux PC. |
| Mac: "permission denied" for `./transcribe` | Run `bash transcribe.sh` instead, or run the installer again (it fixes the permission). |
| `./transcribe check` says "processor only" on a PC with an NVIDIA card | Update the NVIDIA driver (from nvidia.com or the NVIDIA App), restart the computer, then run the installer again. |
| "no kernel image is available" or "CUDA capability" errors | Older NVIDIA card: run the installer with `--torch cu126`. |
| "out of memory" | Close other programs (games, video editors, many browser tabs) and add `--quality fast`. |
| Very slow, or seems stuck after "Model ready" or "Timing the words" (often an 8 GB Mac or PC) | The computer has run out of free memory and is swapping. Close browsers, Discord, video editors and games (or restart the computer) and try again; add `--quality fast` if it's still slow. On a Mac, Activity Monitor > Memory shows "Memory Pressure": red means full. The first use after installing is also a minute or two slower than later ones. |
| The model download fails or is very slow | Check the internet and run the command again: downloads continue where they stopped. If `huggingface.co` is blocked, see section 9. |
| The installer ends with "The model download didn't finish. That's OK..." | Nothing is broken: the models finish downloading the first time Transcribe is used. To finish now: `./transcribe download`. |
| "I can't find this file" | Drag the file into the window instead of typing its name, or put quote marks around a name with spaces. |
| "I couldn't find any sound in this file" | The file has no audio track. Export the audio from your editor, or use the original recording. |
| Names or terms are wrong | Add `--hint "Name1, Name2"`. |
| The wrong language is detected | Add `--language` with the right one. |
| "Subtitles with timings are available for..." | That language has text only (section 1). |
| Subtitles are a little early or late in one place | Usually a long silence, music or background noise. Shorter files, or a cleaner recording, help. |
| The error mentions "nan" or "inf" | Add `--precision float32` (common on older NVIDIA cards). |
| A Mac error mentioning "MPS" | Add `--device cpu` (slower, but always works). |
| The browser doesn't open by itself | Open the address the window prints (for example `http://127.0.0.1:7860`) yourself. |
| The browser page says it can't connect, or stopped working | The window that started Transcribe was closed: start it again (section 3). |
| The preview shows no picture | The browser can't play that video format (some MKV, AVI or HEVC files). The subtitles and the files are still right. |
| Anything else | Run `./transcribe check` and paste its output, plus the error text or `last-error.txt`, to your AI assistant. |

## 9. Downloading models manually

If `huggingface.co` is blocked on the network, the model files can be put in place by hand:

1. Get the model folder from Hugging Face (`https://huggingface.co/Qwen/MODEL-NAME`, Files tab) or, in mainland China, from ModelScope (`https://modelscope.cn/models/Qwen/MODEL-NAME`). Download every file, keeping subfolders.
2. Put the files in `models/MODEL-NAME/` inside the Transcribe folder, for example `models/Qwen3-ASR-1.7B/config.json`.
3. Create an empty file named `.download-complete` in that folder, so Transcribe uses it without going online.

The models and their download pages:

| Model | What it's for | Size | Download page |
|---|---|---|---|
| `Qwen3-ASR-1.7B` | Speech to text, best quality | about 4.7 GB | [Hugging Face](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) · [ModelScope](https://modelscope.cn/models/Qwen/Qwen3-ASR-1.7B) |
| `Qwen3-ASR-0.6B` | Speech to text, fast | about 1.9 GB | [Hugging Face](https://huggingface.co/Qwen/Qwen3-ASR-0.6B) · [ModelScope](https://modelscope.cn/models/Qwen/Qwen3-ASR-0.6B) |
| `Qwen3-ForcedAligner-0.6B` | Word timings for subtitles | about 1.9 GB | [Hugging Face](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B) · [ModelScope](https://modelscope.cn/models/Qwen/Qwen3-ForcedAligner-0.6B) |

Transcribe needs one speech-to-text model (the size from `envs/settings.json`) plus the timing model.

## 10. Speed, quality, updates

| Computer | Default | Speed |
|---|---|---|
| NVIDIA with 8 GB or more | best (1.7B) | fast |
| NVIDIA with less than 8 GB | fast (0.6B) | fast |
| Mac with Apple Silicon | best (1.7B) with 16 GB of memory or more, otherwise fast | good |
| Processor only | fast (0.6B) | long recordings take a while |

- `--quality best` or `--quality fast` overrides the default for one command. Best is more accurate, especially with noise, accents and difficult words.
- **Change the default:** edit `asr_size` in `envs/settings.json` (`"0.6B"` or `"1.7B"`).
- **Uninstall:** delete the Transcribe folder. Nothing else was installed, except Microsoft's Visual C++ Redistributable on a Windows PC that lacked it (other programs use it too; leave it).
- **Update:** download the new version, extract it, copy the old `models` and `output` folders into it (so the models don't download again), and run the installer.
- **Move:** move the whole folder, then run the installer again.

## 11. About the models and the rules

- The models are made by the Qwen team at Alibaba Cloud and published under the Apache 2.0 license, which allows personal and commercial use. Transcribe is unofficial and not affiliated with them.
- The official source code of Qwen3-ASR (the models and the `qwen-asr` package Transcribe uses) is at `https://github.com/QwenLM/Qwen3-ASR`. Point users there when they ask where the models come from or want the technical details.
- Transcribe recordings the user made or has the right to use. Recording or transcribing people without their consent can be illegal in some places.
