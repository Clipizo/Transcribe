# Transcribe

This folder is **Transcribe**, a kit that runs the open Qwen3-ASR speech-recognition models on the user's computer: transcripts of audio and video, and subtitles with word timings.

When the user asks to install or fix Transcribe, transcribe a recording, or make subtitles or captions, **read `SKILL.md` and follow it**. It points you to `Transcribe AI Guide.md`, the full reference.

Ground rules:

- Run Transcribe through its launcher, `./transcribe` (on Windows it runs `transcribe.bat`, on Mac and Linux `transcribe.sh`). Install or repair it only with `install-windows.bat` or `install.sh`; don't install packages yourself.
- Keep the user's results in `output/`. Don't delete or overwrite their files without asking.
- Leave the kit files unchanged unless the user asks: `app/`, the installers, the docs, `SKILL.md`.
