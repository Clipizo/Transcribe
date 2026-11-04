#!/usr/bin/env bash
# Transcribe for Mac and Linux.
#   ./transcribe.sh                 opens the menu
#   ./transcribe.sh my-video.mp4    see ./transcribe.sh help for all options
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$KIT/envs/asr/bin/python"
if [ ! -x "$PY" ]; then
  echo "Transcribe isn't installed yet. In this folder, run:  bash install.sh"
  exit 1
fi
export PYTHONUTF8=1
exec "$PY" "$KIT/app/transcribe.py" "$@"
