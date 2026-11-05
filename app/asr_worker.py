"""Transcribe model worker. Runs inside envs/asr, which has Qwen3-ASR installed.

The launcher (transcribe.py) starts this file; you don't need to run it yourself.
Commands: transcribe, download, probe. The browser app (webapp.py) uses the same engine.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
import worker_utils as W  # noqa: E402

SR = 16000             # Qwen3-ASR works on 16 kHz audio
PIECE_SECONDS = 170    # the aligner handles up to 3 minutes at a time
SUBTITLE_OPTIONS = ("max_chars", "max_words", "lines", "caps", "no_punctuation")


class Progress:
    """Tells the user what is happening: lines in the terminal, or a progress bar in the browser.

    fraction is how much of the job is done (0 to 1); the terminal ignores it.
    where: "both", "terminal" (details only the terminal shows) or "browser".
    """

    def __init__(self, bar=None):
        self.bar = bar

    def __call__(self, text: str, fraction: float | None = None, where: str = "both") -> None:
        if self.bar is None:
            if where != "browser":
                C.say(text)
        elif where != "terminal":
            self.bar(min(max(fraction or 0.0, 0.0), 1.0), desc=text.strip())


def has_room_for_both(settings: dict) -> bool:
    """True if the speech and the timing model fit in memory together (then the browser app
    keeps both loaded between files, which saves the loading time)."""
    device = settings.get("device")
    if device == "cuda":
        return (settings.get("vram_gb") or 0) >= 10
    if device == "mps":
        return (settings.get("ram_gb") or 0) >= 16
    return (settings.get("ram_gb") or 0) >= 24


class Engine:
    """Loads the models when they are needed. With keep=True (the browser app), they stay loaded
    between files if the computer has room for both; otherwise only one is loaded at a time."""

    def __init__(self, settings: dict, keep: bool = False):
        self.settings = settings
        self.keep = keep and has_room_for_both(settings)
        self.asr = None        # (key, model)
        self.aligner = None    # (key, model)

    def _place(self, job: dict):
        return W.pick_device(self.settings, job.get("precision"), job.get("device"))

    def get_asr(self, size: str, job: dict, say: Progress):
        device, device_map, dtype = self._place(job)
        key = (size, device_map, str(dtype))
        if self.asr and self.asr[0] == key:
            return self.asr[1]
        self.drop_asr()
        if not self.keep:
            self.drop_aligner()
        if not C.model_is_downloaded(C.ASR_MODELS[size]):
            say(f"Downloading the {size} model (only once)...", 0.04, where="browser")
        path = W.ensure_model(C.ASR_MODELS[size])
        Qwen3ASRModel = W.import_quietly("qwen_asr").Qwen3ASRModel
        say(f"Loading the transcription model ({size}) on {W.DEVICE_LABELS[device]}...", 0.05)
        t = time.time()
        model = Qwen3ASRModel.from_pretrained(
            str(path), dtype=dtype, device_map=device_map,
            max_inference_batch_size=1, max_new_tokens=2048)
        say(f"Model ready after {C.format_duration(time.time() - t)}.", 0.1, where="terminal")
        self.asr = (key, model)
        return model

    def get_aligner(self, job: dict, say: Progress, fraction: float):
        device, device_map, dtype = self._place(job)
        key = (device_map, str(dtype))
        if self.aligner and self.aligner[0] == key:
            return self.aligner[1]
        self.drop_aligner()
        if not self.keep:
            self.drop_asr()
        if not C.model_is_downloaded(C.ALIGNER_MODEL):
            say("Downloading the subtitle timing model (only once)...", fraction, where="browser")
        path = W.ensure_model(C.ALIGNER_MODEL)
        Qwen3ForcedAligner = W.import_quietly("qwen_asr").Qwen3ForcedAligner
        say(f"Loading the subtitle timing model on {W.DEVICE_LABELS[device]}...", fraction)
        model = Qwen3ForcedAligner.from_pretrained(str(path), dtype=dtype, device_map=device_map)
        self.aligner = (key, model)
        return model

    def drop_asr(self) -> None:
        if self.asr:
            self.asr = None
            W.free_memory()

    def drop_aligner(self) -> None:
        if self.aligner:
            self.aligner = None
            W.free_memory()


def _first_language(value: str) -> str | None:
    for part in (value or "").split(","):
        part = part.strip()
        if part:
            return C.normalize_language(part)
    return None


def _aligner_language(language: str | None, text: str) -> str | None:
    lang = C.normalize_language(language) if language else None
    if lang is None:
        lang = C.guess_language(text) or "English"  # Latin-script languages are timed the same way
    return lang if lang in C.ALIGNER_LANGUAGES else None


def _recognize(model, pieces, job, say: Progress) -> tuple[list[str], list[str]]:
    forced = C.normalize_language(job.get("language"))
    hint = job.get("hint") or ""
    texts, languages = [], []
    t0 = time.time()
    n = len(pieces)
    for i, (samples, offset) in enumerate(pieces, 1):
        if n > 1:
            say(f"[{i}/{n}] listening to {C.format_duration(offset)} - "
                f"{C.format_duration(offset + len(samples) / SR)}", where="terminal")
        say(f"Listening ({i}/{n})" if n > 1 else "Listening...", 0.1 + 0.5 * (i - 1) / n, where="browser")
        if len(samples) < SR // 2:
            texts.append("")
            continue
        r = model.transcribe(audio=(samples, SR), context=hint, language=forced)[0]
        texts.append(r.text or "")
        if r.language:
            languages.append(r.language)
        if n > 1 and i < n:
            left = (time.time() - t0) / i * (n - i)
            say(f"      about {C.format_duration(left)} left", where="terminal")
    return texts, languages


def _align(aligner, pieces, texts, language: str, say: Progress) -> list[dict]:
    tokens: list[dict] = []
    n = len(pieces)
    for i, ((samples, offset), text) in enumerate(zip(pieces, texts), 1):
        if not text.strip():
            continue
        if n > 1:
            say(f"  timing part {i}/{n}", where="terminal")
        say(f"Timing the words ({i}/{n})" if n > 1 else "Timing the words...", 0.68 + 0.3 * (i - 1) / n,
            where="browser")
        result = aligner.align(audio=(samples, SR), text=text, language=language)[0]
        items = [(it.text, float(it.start_time) + offset, float(it.end_time) + offset) for it in result]
        tokens.extend(C.attach_display_text(text, items))
    return tokens


def run(job: dict, settings: dict, engine: Engine | None = None, say: Progress | None = None) -> dict:
    """Transcribe one file. Returns the text, the language and every word with its timing.

    job: input, language, hint, size, subtitles, script, precision, device.
    """
    say = say or Progress()
    engine = engine or Engine(settings)
    W.quiet()
    say("Reading the audio...", 0.02, where="browser")
    audio = W.load_audio(job["input"], SR)
    duration = len(audio) / SR
    if duration < 0.5:
        raise C.UserError("That file is too short to transcribe (less than half a second of audio).")
    say(f"Audio length: {C.format_duration(duration)}", 0.03, where="terminal")
    pieces = W.split_on_quiet(audio, SR, PIECE_SECONDS)
    script = C.clean_script(job.get("script") or "")
    want_subtitles = job.get("subtitles", True)
    forced = C.normalize_language(job.get("language"))

    if script:
        language = forced or C.guess_language(script)
        if len(pieces) == 1:
            texts = [script]  # short audio: no need to listen first, the script is the text
        else:
            say("Listening first, to find where each part of the script is spoken...", 0.05, where="terminal")
            model = engine.get_asr(job["size"], job, say)
            heard, languages = _recognize(model, pieces, job, say)
            del model  # so the engine can free it before the timing model loads
            language = language or _first_language(languages[0] if languages else "")
            texts = C.split_script_by_pieces(script, heard)
        full_text = script
    else:
        model = engine.get_asr(job["size"], job, say)
        texts, languages = _recognize(model, pieces, job, say)
        del model  # so the engine can free it before the timing model loads
        language = forced or _first_language(languages[0] if languages else "")
        full_text = C.join_texts(texts)

    data = {"text": full_text, "language": language, "duration": round(duration, 2),
            "used_script": bool(script), "tokens": [], "align_language": None}
    if want_subtitles and full_text.strip():
        align_lang = _aligner_language(language, full_text)
        if align_lang is None:
            data["subtitles_skipped"] = (
                f"Subtitles with timings are available for {', '.join(C.ALIGNER_LANGUAGES)}. "
                f"This audio is in {language or 'an unknown language'}, so only the text was saved.")
        else:
            aligner = engine.get_aligner(job, say, 0.63)
            say("Timing the words for subtitles...", 0.66, where="terminal")
            data["tokens"] = _align(aligner, pieces, texts, align_lang, say)
            data["align_language"] = align_lang
            del aligner
    if not engine.keep:
        engine.drop_asr()
        engine.drop_aligner()
    return data


def subtitle_options(job: dict) -> dict:
    return {k: job.get(k) for k in SUBTITLE_OPTIONS if job.get(k) is not None}


def write_subtitles(tokens: list[dict], srt_path: Path, options: dict) -> list[dict]:
    """Write the .srt with these subtitle options. Returns the subtitles (cues)."""
    cues = C.build_cues(tokens, max_chars=options.get("max_chars"), max_words=options.get("max_words"),
                        lines=options.get("lines") or 1, caps=bool(options.get("caps")),
                        no_punctuation=bool(options.get("no_punctuation")))
    srt_path.write_text(C.format_srt(cues), encoding="utf-8")
    return cues


def save(data: dict, out_base: Path, options: dict) -> dict:
    """Save NAME.txt, and with timings NAME.srt and NAME.words.json. Returns where they are."""
    out_base.parent.mkdir(parents=True, exist_ok=True)
    txt = Path(str(out_base) + ".txt")
    full_text = data["text"]
    if data["used_script"]:
        txt.write_text(full_text + "\n", encoding="utf-8")
    else:
        sentences = C.split_sentences(full_text) if full_text else []
        txt.write_text("\n".join(sentences) + ("\n" if sentences else ""), encoding="utf-8")
    result = {"txt": str(txt), "language": data["language"], "duration": data["duration"],
              "text": full_text, "used_script": data["used_script"]}
    if data.get("subtitles_skipped"):
        result["subtitles_skipped"] = data["subtitles_skipped"]
    tokens = data.get("tokens") or []
    if tokens:
        srt = Path(str(out_base) + ".srt")
        cues = write_subtitles(tokens, srt, options)
        words = Path(str(out_base) + ".words.json")
        words.write_text(json.dumps({
            "language": data["align_language"],
            "text": full_text,
            "words": [{"text": t["text"], "start": round(t["start"], 3), "end": round(t["end"], 3)}
                      for t in tokens],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        result.update({"srt": str(srt), "words": str(words), "cues": len(cues)})
    return result


def cmd_transcribe(job_path: str) -> None:
    job = W.read_job(job_path)
    data = run(job, C.load_settings())
    result = save(data, Path(job["out_base"]), subtitle_options(job))
    W.write_result(job_path, result)


def cmd_download(repos: list[str]) -> None:
    W.quiet()
    for repo in repos:
        if C.model_is_downloaded(repo):
            C.say(f"Already downloaded: {repo.split('/')[-1]}")
            continue
        W.ensure_model(repo)
        C.say(f"Downloaded: {repo.split('/')[-1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("transcribe")
    p.add_argument("--job", required=True)
    p = sub.add_parser("download")
    p.add_argument("--repo", action="append", required=True)
    sub.add_parser("probe")
    args = parser.parse_args()

    if args.cmd == "transcribe":
        W.run_main(lambda: cmd_transcribe(args.job))
    elif args.cmd == "download":
        W.run_main(lambda: cmd_download(args.repo))
    elif args.cmd == "probe":
        W.probe("qwen_asr")


if __name__ == "__main__":
    main()
