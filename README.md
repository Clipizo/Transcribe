# Transcribe

Turn **audio and video into text and subtitles** on your own computer, for free. No account, no subscription, no upload limits, and your recordings never leave your computer.

Transcribe is a beginner-friendly kit for **Qwen3-ASR**, the free, open speech-recognition models from the Qwen team:

- transcripts in 30 languages (and 22 Chinese dialects), from almost any audio or video file;
- subtitles (`.srt`) with accurate word timings, for DaVinci Resolve, Premiere Pro, CapCut, Final Cut and YouTube;
- subtitles with the **exact words of your script**, for example for a voiceover.

It installs everything into this one folder. You use it from a simple menu, with one short command, or by letting your AI assistant run it for you.

> Transcribe is an unofficial kit made by Clipizo. It is not affiliated with or endorsed by Alibaba Cloud or the Qwen team.
> Want AI voiceovers? See the companion kit **[AIvoice](https://github.com/Clipizo/AIvoice)**.

## The easiest way: ask your AI

Give this to your AI assistant (ChatGPT, Claude, Gemini, Copilot...):

> Help me install and use Transcribe: https://github.com/Clipizo/Transcribe
> Read its file "Transcribe AI Guide.md" first, then guide me one step at a time.

If your AI can't open links, download the file **`Transcribe AI Guide.md`** and attach it to the chat instead.

**AI agents that can open folders and run commands** (Claude Code, OpenAI Codex, Gemini CLI, Cursor, VS Code with Copilot): open this folder in the agent and ask for what you want, for example *"install Transcribe and make subtitles for my-video.mp4"*. The agent follows `AGENTS.md` and `SKILL.md`.

## Install it yourself

You need about **15 GB of free disk space** and an internet connection. The install takes 5 to 30 minutes.

**Windows 10 or 11**

1. On this page, click the green **Code** button, then **Download ZIP**.
2. Right-click the ZIP, choose **Extract All...**, and extract it to `C:\`. Rename the folder to `C:\Transcribe` (short paths avoid problems).
3. Open the folder and double-click **`install-windows.bat`**. If Windows says *"Windows protected your PC"*, click **More info**, then **Run anyway**.
4. Wait until it says **Transcribe is installed!**

**Mac with Apple Silicon (M1 or newer)**

1. Click **Code**, then **Download ZIP**. Move the unzipped folder to your home folder and rename it `Transcribe`.
2. Open **Terminal** (press Cmd+Space, type *Terminal*, press Enter).
3. Type `cd ` (with a space), drag the Transcribe folder into the Terminal window, and press Enter.
4. Type `bash install.sh` and press Enter.

**Linux**

```bash
git clone https://github.com/Clipizo/Transcribe.git && cd Transcribe && bash install.sh
```

## Use it

**Windows:** double-click **`transcribe.bat`**. **Mac and Linux:** in Terminal, in the Transcribe folder, type `./transcribe.sh`.

A menu opens:

```
  1  Transcribe audio or video (text + subtitles)
  2  Subtitles from my script (exact words, for example a voiceover)
  3  Open the web app in your browser
  4  Check my setup
  5  Download the models now (so nothing downloads later)
```

Drag your file into the window when it asks, and press Enter. The results go to the **`output`** folder. The first time, Transcribe downloads its AI models (about 4 to 7 GB, only once).

### Or use commands

On Windows, type these in a terminal opened in the Transcribe folder (in File Explorer: right-click inside the folder, then **Open in Terminal**). On Mac and Linux, write `./transcribe.sh` instead of `.\transcribe`.

| What | Command |
|---|---|
| Text and subtitles of a video | `.\transcribe my-video.mp4` |
| Text only (faster) | `.\transcribe interview.mp3 --no-subtitles` |
| Help with names and terms | `.\transcribe podcast.mp3 --hint "Clipizo, DaVinci Resolve"` |
| Force the language | `.\transcribe lecture.m4a --language Spanish` |
| Subtitles with your script's exact words | `.\transcribe voiceover.wav --script my-script.txt` |
| Short lines for vertical videos | `.\transcribe short.mp4 --max-chars 20` |
| Several files | `.\transcribe part1.mp4 part2.mp4 part3.mp4` |
| The browser app | `.\transcribe app` |
| Check the setup | `.\transcribe check` |

`.\transcribe help` lists every option.

## What you get

For `my-video.mp4`, the `output` folder gets:

| File | Contents |
|---|---|
| `my-video.txt` | The text, one sentence per line. |
| `my-video.srt` | Subtitles. Import them into your video editor like a media file, or upload them to YouTube. |
| `my-video.words.json` | Every word with its start and end time, for animated captions and other tools. |

- **Languages for text:** Chinese, English, Cantonese, Arabic, German, French, Spanish, Portuguese, Indonesian, Italian, Korean, Russian, Thai, Vietnamese, Japanese, Turkish, Hindi, Malay, Dutch, Swedish, Danish, Finnish, Polish, Czech, Filipino, Persian, Greek, Romanian, Hungarian, Macedonian, and 22 Chinese dialects.
- **Languages for subtitle timings:** English, Chinese, Cantonese, French, German, Italian, Japanese, Korean, Portuguese, Russian and Spanish. Other languages get the text only.
- **Files:** almost any audio or video: mp3, wav, m4a, aac, flac, ogg, mp4, mov, mkv, webm...
- **Long recordings** are processed in parts of about 3 minutes; an hour-long recording is fine.

## What your computer needs

| Computer | How it runs |
|---|---|
| Windows or Linux PC with an **NVIDIA graphics card** (6 GB or more; 8 GB or more for best quality) | Fast. |
| **Mac with Apple Silicon** (M1 or newer) | Works well; uses the best model with 16 GB of memory or more. |
| Any other Windows or Linux PC | Works on the processor, but long recordings take a while. |

Intel Macs and Windows on ARM aren't supported. Transcribe picks the best settings for your computer automatically; `--quality fast` (the smaller 0.6B model) or `--quality best` (the 1.7B model) overrides them.

## What is inside

| File or folder | Contents |
|---|---|
| `install-windows.bat`, `install.sh` | The installers. Run them again at any time to repair the install. |
| `transcribe.bat`, `transcribe.sh` | Start Transcribe (menu or commands). |
| `Transcribe AI Guide.md` | Everything an AI assistant needs to help you, step by step, including troubleshooting. |
| `AGENTS.md`, `SKILL.md` | Instructions for AI agents. `CLAUDE.md` and `GEMINI.md` point to them. |
| `app/` | The Transcribe program. |
| `output/` | Your transcripts and subtitles. |
| `envs/`, `models/`, `.tools/` | Created by the installer: Python, the AI libraries and the downloaded models. |

**To uninstall,** delete the Transcribe folder. Nothing else is installed on your computer.

## Respect people's privacy

Transcribe recordings you made, or have the right to use. Recording or transcribing people without their consent can be illegal in some places.

## License and credits

Transcribe is free of charge, under the Clipizo product license in `LICENSE.txt`. Use it and what you make with it in your own projects, personal or commercial, including client work and monetized videos. Please don't re-upload or redistribute the kit's files; link to this page instead.

The AI models are made by the Qwen team at Alibaba Cloud and released under the Apache 2.0 license: [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR). The installer downloads them, and the other open-source tools Transcribe uses, from their official sources. See `THIRD-PARTY-NOTICES.md`.
