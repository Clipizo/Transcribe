"""Transcribe model worker. Runs inside envs/asr, which has Qwen3-ASR installed.

The launcher (transcribe.py) starts this file; you don't need to run it yourself.
Commands: transcribe, download, probe.
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


def load_asr(size: str, job: dict, settings: dict):
    path = W.ensure_model(C.ASR_MODELS[size])
    Qwen3ASRModel = W.import_quietly("qwen_asr").Qwen3ASRModel
    device, device_map, dtype = W.pick_device(settings, job.get("precision"), job.get("device"))
    C.say(f"Loading the transcription model ({size}) on {W.DEVICE_LABELS[device]}...")
    t = time.time()
    model = Qwen3ASRModel.from_pretrained(
        str(path), dtype=dtype, device_map=device_map,
        max_inference_batch_size=1, max_new_tokens=2048)
    C.say(f"Model ready after {C.format_duration(time.time() - t)}.")
    return model


def load_aligner(job: dict, settings: dict):
    path = W.ensure_model(C.ALIGNER_MODEL)
    Qwen3ForcedAligner = W.import_quietly("qwen_asr").Qwen3ForcedAligner
    device, device_map, dtype = W.pick_device(settings, job.get("precision"), job.get("device"))
    C.say(f"Loading the subtitle timing model on {W.DEVICE_LABELS[device]}...")
    return Qwen3ForcedAligner.from_pretrained(str(path), dtype=dtype, device_map=device_map)


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


def _recognize(model, pieces, job) -> tuple[list[str], list[str]]:
    forced = C.normalize_language(job.get("language"))
    hint = job.get("hint") or ""
    texts, languages = [], []
    t0 = time.time()
    for i, (samples, offset) in enumerate(pieces, 1):
        if len(pieces) > 1:
            C.say(f"[{i}/{len(pieces)}] listening to {C.format_duration(offset)} - "
                  f"{C.format_duration(offset + len(samples) / SR)}")
        if len(samples) < SR // 2:
            texts.append("")
            continue
        r = model.transcribe(audio=(samples, SR), context=hint, language=forced)[0]
        texts.append(r.text or "")
        if r.language:
            languages.append(r.language)
        if len(pieces) > 1 and i < len(pieces):
            left = (time.time() - t0) / i * (len(pieces) - i)
            C.say(f"      about {C.format_duration(left)} left")
    return texts, languages


def _align(aligner, pieces, texts, language: str) -> list[dict]:
    tokens: list[dict] = []
    for i, ((samples, offset), text) in enumerate(zip(pieces, texts), 1):
        if not text.strip():
            continue
        if len(pieces) > 1:
            C.say(f"  timing part {i}/{len(pieces)}")
        result = aligner.align(audio=(samples, SR), text=text, language=language)[0]
        items = [(it.text, float(it.start_time) + offset, float(it.end_time) + offset) for it in result]
        tokens.extend(C.attach_display_text(text, items))
    return tokens


def cmd_transcribe(job_path: str) -> None:
    job = W.read_job(job_path)
    settings = C.load_settings()
    W.quiet()
    audio = W.load_audio(job["input"], SR)
    duration = len(audio) / SR
    if duration < 0.5:
        raise C.UserError("That file is too short to transcribe (less than half a second of audio).")
    C.say(f"Audio length: {C.format_duration(duration)}")
    pieces = W.split_on_quiet(audio, SR, PIECE_SECONDS)
    script = C.clean_script(job.get("script") or "")
    want_subtitles = job.get("subtitles", True)
    forced = C.normalize_language(job.get("language"))

    if script:
        language = forced or C.guess_language(script)
        if len(pieces) == 1:
            texts = [script]  # short audio: no need to listen first, the script is the text
        else:
            C.say("Listening first, to find where each part of the script is spoken...")
            model = load_asr(job["size"], job, settings)
            heard, languages = _recognize(model, pieces, job)
            language = language or _first_language(languages[0] if languages else "")
            texts = C.split_script_by_pieces(script, heard)
            del model
            W.free_memory()
        full_text = script
    else:
        model = load_asr(job["size"], job, settings)
        texts, languages = _recognize(model, pieces, job)
        language = forced or _first_language(languages[0] if languages else "")
        full_text = C.join_texts(texts)
        if want_subtitles:
            del model
            W.free_memory()

    out_base = Path(job["out_base"])
    out_base.parent.mkdir(parents=True, exist_ok=True)
    txt = Path(str(out_base) + ".txt")
    if script:
        txt.write_text(script + "\n", encoding="utf-8")
    else:
        sentences = C.split_sentences(full_text) if full_text else []
        txt.write_text("\n".join(sentences) + ("\n" if sentences else ""), encoding="utf-8")
    result = {"txt": str(txt), "language": language, "duration": round(duration, 2), "text": full_text,
              "used_script": bool(script)}

    if want_subtitles and full_text.strip():
        align_lang = _aligner_language(language, full_text)
        if align_lang is None:
            result["subtitles_skipped"] = (
                f"Subtitles with timings are available for {', '.join(C.ALIGNER_LANGUAGES)}. "
                f"This audio is in {language or 'an unknown language'}, so only the text was saved.")
        else:
            aligner = load_aligner(job, settings)
            C.say("Timing the words for subtitles...")
            tokens = _align(aligner, pieces, texts, align_lang)
            cues = C.build_cues(tokens, max_chars=job.get("max_chars"))
            srt = Path(str(out_base) + ".srt")
            srt.write_text(C.format_srt(cues), encoding="utf-8")
            words = Path(str(out_base) + ".words.json")
            words.write_text(json.dumps({
                "language": align_lang,
                "text": full_text,
                "words": [{"text": t["text"], "start": round(t["start"], 3), "end": round(t["end"], 3)}
                          for t in tokens],
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            result.update({"srt": str(srt), "words": str(words), "cues": len(cues)})
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
