"""Transcribe in the browser.

transcribe.py starts this file inside envs/asr (run ./transcribe, or double-click transcribe.bat).
The page only runs on this computer (127.0.0.1). It uses the same engine as the commands, and
changing the subtitle controls re-cuts the subtitles from the word timings without transcribing again.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
import worker_utils as W  # noqa: E402
import asr_worker as A  # noqa: E402

VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".webm"}    # the browser can usually play these itself
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac"}
PREVIEWS = C.TOOLS / "preview"
WORDS = ["Any", "1", "2", "3", "4", "5", "6", "8", "10"]
STYLES = ["UPPERCASE", "No punctuation"]
CSS = """
.gradio-container { max-width: 1200px !important; margin: auto; }
footer { display: none !important; }
"""


def preview_for(src: Path) -> tuple[str, str]:
    """("video" or "audio", file) for the preview player. Files the browser can't play (mkv, avi,
    wma...) get an audio copy, made with the kit's own ffmpeg."""
    ext = src.suffix.lower()
    if ext in VIDEO_EXTS:
        return "video", str(src)
    if ext in AUDIO_EXTS:
        return "audio", str(src)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    out = PREVIEWS / "preview.mp3"  # one file, replaced each time, so previews don't pile up
    cmd = [W.ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
           "-vn", "-ac", "1", "-codec:a", "libmp3lame", "-b:a", "96k", str(out)]
    subprocess.run(cmd, check=False)
    return "audio", str(out)


def subtitle_options(chars, words, lines, style) -> dict:
    style = style or []
    return {"max_chars": int(chars), "max_words": None if words in (None, "Any") else int(words),
            "lines": int(lines or 1), "caps": "UPPERCASE" in style, "no_punctuation": "No punctuation" in style}


def friendly_error(e: BaseException) -> str:
    """The message for the browser; the details go to last-error.txt, as with the commands."""
    try:
        (C.KIT / "last-error.txt").write_text(
            f"{C.KIT_NAME} {C.KIT_VERSION}, {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{traceback.format_exc()}",
            encoding="utf-8")
    except OSError:
        pass
    hint = W.explain_error(e)
    summary = " ".join(f"{type(e).__name__}: {e}".split())[:200]
    return f"{hint or 'Something went wrong: ' + summary}\n(Details: last-error.txt in the {C.KIT_NAME} folder.)"


def open_folder(path: Path) -> None:
    try:
        if C.IS_WINDOWS:
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif C.IS_MAC:
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)], stderr=subprocess.DEVNULL)
    except Exception:
        pass


def build(settings: dict, engine: A.Engine, default_quality: str):
    import gradio as gr

    def render(state: dict, options: dict):
        """Subtitles with these options: the player, the .srt text and the files to download."""
        data, out_base = state["data"], Path(state["out_base"])
        txt = Path(str(out_base) + ".txt")
        files, cues = [str(txt)], []
        if data["tokens"]:
            srt = Path(str(out_base) + ".srt")
            cues = A.write_subtitles(data["tokens"], srt, options)
            files = [str(srt), str(txt), str(out_base) + ".words.json"]
        subs = [{"text": c["text"], "timestamp": [c["start"], c["end"]]} for c in cues] or None
        if state["kind"] == "video":
            video = gr.Video(value=state["preview"], subtitles=subs, visible=True)
            audio = gr.Audio(value=None, visible="hidden")
        else:
            video = gr.Video(value=None, visible="hidden")
            audio = gr.Audio(value=state["preview"], subtitles=subs, visible=True)
        srt_text = C.format_srt(cues) if cues else (data.get("subtitles_skipped") or "")
        return video, audio, srt_text, files

    def transcribe(media, language, quality, hint, script, chars, words, lines, style, progress=gr.Progress()):
        if not media:
            raise gr.Error("Add an audio or video file first.", print_exception=False)
        src = Path(media)
        job = {"input": str(src), "language": None if language in (None, "Auto") else language,
               "hint": hint or "", "subtitles": True, "script": script if (script or "").strip() else None,
               "size": C.resolve_size((quality or "auto").lower(), settings)}
        try:
            kind, preview = preview_for(src)
            data = A.run(job, settings, engine, A.Progress(progress))
        except C.UserError as e:
            raise gr.Error(str(e), print_exception=False) from None
        except Exception as e:  # noqa: BLE001
            raise gr.Error(friendly_error(e), print_exception=False) from None
        if data["tokens"] and int(chars) == 42 and C.default_max_chars(data["tokens"]) != 42:
            chars = C.default_max_chars(data["tokens"])  # Chinese, Japanese, Korean: shorter lines
        out_base = C.unique_base(C.OUTPUT, C.safe_name(src.stem, 60) or "transcript", [".txt", ".srt", ".words.json"])
        A.save(data, out_base, subtitle_options(chars, words, lines, style))
        state = {"data": data, "out_base": str(out_base), "kind": kind, "preview": preview}
        video, audio, srt_text, files = render(state, subtitle_options(chars, words, lines, style))
        text = Path(str(out_base) + ".txt").read_text(encoding="utf-8")
        return state, video, audio, srt_text, text, files, gr.Slider(value=chars)

    def restyle(state, chars, words, lines, style):
        if not state:
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return render(state, subtitle_options(chars, words, lines, style))

    def show_folder():
        C.OUTPUT.mkdir(exist_ok=True)
        open_folder(C.OUTPUT)
        gr.Info(str(C.OUTPUT), title="Output folder")

    with gr.Blocks(title=C.KIT_NAME, delete_cache=(3600, 86400)) as demo:
        state = gr.State(None)
        gr.Markdown(f"## {C.KIT_NAME}")
        with gr.Row(equal_height=False):
            with gr.Column(scale=2, min_width=300):
                media = gr.File(label="Audio or video", file_types=["audio", "video"], type="filepath")
                language = gr.Dropdown(["Auto"] + C.ASR_LANGUAGES, value="Auto", label="Language")
                quality = gr.Radio(["Auto", "Fast", "Best"], value=default_quality, label="Quality")
                hint = gr.Textbox(label="Names and terms", placeholder="Clipizo, DaVinci Resolve")
                with gr.Accordion("Script", open=False):
                    script = gr.Textbox(show_label=False, lines=5, placeholder="The exact words (optional)")
                go = gr.Button("Transcribe", variant="primary", size="lg")
            with gr.Column(scale=3, min_width=360):
                # "hidden" (not False) keeps the players on the page, so a new file reaches them.
                video = gr.Video(label="Preview", visible="hidden", interactive=False)
                audio = gr.Audio(label="Preview", visible="hidden", interactive=False, type="filepath")
                with gr.Row():
                    chars = gr.Slider(10, 60, value=42, step=1, label="Characters per line")
                    words = gr.Dropdown(WORDS, value="Any", label="Words per line")
                with gr.Row():
                    lines = gr.Radio([1, 2], value=1, label="Lines")
                    style = gr.CheckboxGroup(STYLES, label="Style")
                with gr.Tabs():
                    with gr.Tab("Subtitles"):
                        srt_view = gr.Textbox(show_label=False, lines=12, max_lines=12, interactive=False)
                    with gr.Tab("Text"):
                        text_view = gr.Textbox(show_label=False, lines=12, max_lines=12, interactive=False)
                files = gr.File(label="Download", file_count="multiple", interactive=False)
                folder = gr.Button("Open the output folder", size="sm")

        go.click(transcribe, [media, language, quality, hint, script, chars, words, lines, style],
                 [state, video, audio, srt_view, text_view, files, chars], concurrency_limit=1,
                 show_progress_on=[srt_view])
        controls = [state, chars, words, lines, style]
        outputs = [video, audio, srt_view, files]
        for control in (chars, words, lines, style):
            # always_last: while the slider is dragged, only the last value is re-cut.
            control.change(restyle, controls, outputs, show_progress="hidden", trigger_mode="always_last")
        folder.click(show_folder, None, None)
    return demo


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe in the browser")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--quality", choices=["fast", "best", "auto"], default=None)
    args = parser.parse_args()
    W.quiet()
    settings = C.load_settings()
    engine = A.Engine(settings, keep=True)
    with W.silenced():
        import gradio as gr
    demo = build(settings, engine, (args.quality or "auto").capitalize())
    demo.queue(default_concurrency_limit=1).launch(
        server_name="127.0.0.1", server_port=args.port, inbrowser=False, quiet=True, show_error=True,
        footer_links=[], ssr_mode=False, theme=gr.themes.Soft(), css=CSS,
        allowed_paths=[str(C.OUTPUT), str(PREVIEWS)])


if __name__ == "__main__":
    W.run_main(main)
