# Third-party notices

Transcribe is an unofficial kit made by Clipizo. It is **not affiliated with, sponsored by or endorsed by Alibaba Cloud or the Qwen team.** "Qwen" is a trademark of its owner and is used here only to describe which models the kit works with.

This repository contains only Transcribe's own files. It does **not** include the AI models or the libraries below. The installer and the first run download them from their official sources (PyPI, the PyTorch download site, Hugging Face and Astral), and each one stays under its own license.

## AI models

| Model | Made by | License | Source |
|---|---|---|---|
| Qwen3-ASR-1.7B, Qwen3-ASR-0.6B, Qwen3-ForcedAligner-0.6B | Qwen team, Alibaba Cloud | Apache License 2.0 | https://github.com/QwenLM/Qwen3-ASR |

## Main software

| Software | License | Source |
|---|---|---|
| qwen-asr (the official Python package) | Apache License 2.0 | https://github.com/QwenLM/Qwen3-ASR |
| PyTorch | BSD 3-Clause | https://pytorch.org |
| Transformers, Accelerate, huggingface_hub | Apache License 2.0 | https://github.com/huggingface |
| Gradio (the browser app) | Apache License 2.0 | https://www.gradio.app |
| librosa | ISC | https://librosa.org |
| soundfile, NumPy, SciPy | BSD 3-Clause | https://pypi.org |
| nagisa (Japanese word splitting) and soynlp (Korean word splitting), used for subtitle timing | MIT and GPL-3.0 | https://github.com/taishi-i/nagisa, https://github.com/lovit/soynlp |
| imageio-ffmpeg, which provides an FFmpeg program | BSD 2-Clause (imageio-ffmpeg); LGPL/GPL (FFmpeg) | https://github.com/imageio/imageio-ffmpeg, https://ffmpeg.org |
| uv, which installs Python and the packages | MIT or Apache License 2.0 | https://github.com/astral-sh/uv |
| Python | Python Software Foundation License | https://www.python.org |

The complete list of packages and exact versions is in `app/requirements/asr.txt`. After installation, each package's license text is in its folder under `envs/`.
