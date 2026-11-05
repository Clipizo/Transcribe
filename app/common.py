"""Shared helpers for Transcribe.

This file uses only the Python standard library, so the launcher, the
installer and the model environment can all import it.
"""

from __future__ import annotations

import difflib
import json
import math
import os
import re
import sys
import unicodedata
from pathlib import Path

KIT_NAME = "Transcribe"
KIT_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

KIT = Path(__file__).resolve().parent.parent
APP = KIT / "app"
ENVS = KIT / "envs"
MODELS = KIT / "models"
OUTPUT = KIT / "output"
TOOLS = KIT / ".tools"
SETTINGS_FILE = ENVS / "settings.json"
ENV_NAME = "asr"

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"


def env_python(name: str = ENV_NAME) -> Path:
    """Path of the Python interpreter inside envs/<name>."""
    if IS_WINDOWS:
        return ENVS / name / "Scripts" / "python.exe"
    return ENVS / name / "bin" / "python"


def gpu_label(name) -> str:
    """'GeForce RTX 3060' -> 'NVIDIA GeForce RTX 3060' (without saying NVIDIA twice)."""
    name = str(name or "graphics card").strip()
    return name if name.lower().startswith("nvidia") else f"NVIDIA {name}"


def launcher_command() -> str:
    """How the user starts Transcribe from a terminal on this computer."""
    # PowerShell on Windows accepts ./transcribe (it runs transcribe.bat); on Mac and Linux the
    # installer adds a ./transcribe shortcut to transcribe.sh. So the command is the same everywhere.
    return "./transcribe"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

ASR_MODELS = {
    "1.7B": "Qwen/Qwen3-ASR-1.7B",
    "0.6B": "Qwen/Qwen3-ASR-0.6B",
}
ALIGNER_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"

# Approximate download sizes in GB, only used for messages.
MODEL_SIZES_GB = {
    "Qwen/Qwen3-ASR-1.7B": 4.7,
    "Qwen/Qwen3-ASR-0.6B": 1.9,
    "Qwen/Qwen3-ForcedAligner-0.6B": 1.9,
}

DONE_MARKER = ".download-complete"


def model_dir(repo_id: str) -> Path:
    return MODELS / repo_id.split("/")[-1]


def model_is_downloaded(repo_id: str) -> bool:
    return (model_dir(repo_id) / DONE_MARKER).exists()


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------

# Languages Qwen3-ASR understands (it also knows 22 Chinese dialects).
ASR_LANGUAGES = [
    "Chinese", "English", "Cantonese", "Arabic", "German", "French", "Spanish", "Portuguese",
    "Indonesian", "Italian", "Korean", "Russian", "Thai", "Vietnamese", "Japanese", "Turkish",
    "Hindi", "Malay", "Dutch", "Swedish", "Danish", "Finnish", "Polish", "Czech", "Filipino",
    "Persian", "Greek", "Romanian", "Hungarian", "Macedonian",
]

# Languages the forced aligner can time (needed for subtitles).
ALIGNER_LANGUAGES = [
    "Chinese", "English", "Cantonese", "French", "German", "Italian",
    "Japanese", "Korean", "Portuguese", "Russian", "Spanish",
]

LANGUAGE_CODES = {
    "en": "English", "zh": "Chinese", "cn": "Chinese", "ja": "Japanese", "jp": "Japanese",
    "ko": "Korean", "kr": "Korean", "de": "German", "fr": "French", "ru": "Russian",
    "pt": "Portuguese", "es": "Spanish", "it": "Italian", "yue": "Cantonese",
    "ar": "Arabic", "id": "Indonesian", "th": "Thai", "vi": "Vietnamese", "tr": "Turkish",
    "hi": "Hindi", "ms": "Malay", "nl": "Dutch", "sv": "Swedish", "da": "Danish",
    "fi": "Finnish", "pl": "Polish", "cs": "Czech", "fil": "Filipino", "fa": "Persian",
    "el": "Greek", "hu": "Hungarian", "mk": "Macedonian", "ro": "Romanian",
}


def normalize_language(value: str | None) -> str | None:
    """'en', 'english', 'English' -> 'English'. 'auto'/'' -> None."""
    if value is None:
        return None
    v = str(value).strip()
    if not v or v.lower() == "auto":
        return None
    if v.lower() in LANGUAGE_CODES:
        return LANGUAGE_CODES[v.lower()]
    return v[:1].upper() + v[1:].lower()


def _in_ranges(ch: str, ranges) -> bool:
    o = ord(ch)
    return any(a <= o <= b for a, b in ranges)


_KANA = [(0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F)]
_HANGUL = [(0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F)]
_HAN = [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x2FFFF)]
_CYRILLIC = [(0x0400, 0x04FF)]


def is_cjk_char(ch: str) -> bool:
    return _in_ranges(ch, _HAN) or _in_ranges(ch, _KANA) or _in_ranges(ch, _HANGUL)


def guess_language(text: str) -> str | None:
    """Rough guess from the alphabet used. Returns None for Latin-script text."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    n = len(letters)
    if sum(_in_ranges(c, _KANA) for c in letters) / n > 0.05:
        return "Japanese"
    if sum(_in_ranges(c, _HANGUL) for c in letters) / n > 0.2:
        return "Korean"
    if sum(_in_ranges(c, _HAN) for c in letters) / n > 0.3:
        return "Chinese"
    if sum(_in_ranges(c, _CYRILLIC) for c in letters) / n > 0.3:
        return "Russian"
    return None


def mostly_cjk(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(is_cjk_char(c) for c in letters) / len(letters) > 0.3


# ---------------------------------------------------------------------------
# Settings (written by the installer)
# ---------------------------------------------------------------------------

def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def resolve_size(quality: str | None, settings: dict) -> str:
    """Map 'fast'/'best'/'auto' to a model size ('0.6B' or '1.7B')."""
    q = (quality or "auto").strip().lower()
    if q in ("fast", "small", "0.6b", "0.6"):
        return "0.6B"
    if q in ("best", "large", "1.7b", "1.7"):
        return "1.7B"
    return settings.get("asr_size") or "0.6B"


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def setup_console() -> None:
    """Make printing safe on every console (no crashes on unusual characters)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def say(text: str = "") -> None:
    print(text, flush=True)


def child_env() -> dict:
    """Environment variables for the model process."""
    env = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH"):  # set by some other programs; they'd break the environment
        env.pop(name, None)
    env.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONWARNINGS": "ignore",
        "HF_HOME": str(TOOLS / "hf-home"),
        "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        # Hide Hugging Face's technical notes (retries, "install hf_xet with pip"): they look like
        # errors to beginners. Real errors still show, and ensure_model explains them.
        "HF_HUB_VERBOSITY": "error",
        "HF_XET_CHUNK_CACHE_SIZE_BYTES": "0",
        "TOKENIZERS_PARALLELISM": "false",
        "TRANSFORMERS_VERBOSITY": "error",
        "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
        "PYTORCH_ENABLE_MPS_FALLBACK": "1",
        "GRADIO_ANALYTICS_ENABLED": "False",
    })
    return env


class UserError(Exception):
    """A problem the user can fix. The message is shown without a traceback."""


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def clean_path_input(text: str) -> str:
    """Turn what a terminal pastes when you drag a file into it into a path."""
    s = text.replace("\ufeff", "").strip()
    if s.startswith("& "):  # PowerShell sometimes adds "& '...'"
        s = s[2:].strip()
    quoted = len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'"
    if quoted:
        s = s[1:-1]
    elif not IS_WINDOWS:
        s = re.sub(r"\\(.)", r"\1", s)  # Mac/Linux Terminal: "My\ File.txt" -> "My File.txt"
    if s.startswith("file://"):
        from urllib.parse import unquote, urlparse
        s = unquote(urlparse(s).path)
    return os.path.expanduser(s)


def user_path(text: str) -> Path:
    """A path the user typed or dragged in, made absolute (the model process runs in the kit folder)."""
    return Path(os.path.abspath(clean_path_input(text)))


def read_text_file(path: Path) -> str:
    """Read a text file saved by any editor (UTF-8, UTF-16 or old Windows encodings)."""
    data = path.read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def safe_name(text: str, max_len: int = 40) -> str:
    """A file-name-safe version of some text."""
    text = unicodedata.normalize("NFKC", text)
    words = re.findall(r"\w+", text)
    return "-".join(words)[:max_len].strip("-_").lower()


def unique_base(folder: Path, base: str, exts) -> Path:
    """folder/base without extension, where none of base+ext exists yet."""
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / base
    n = 2
    while any(Path(str(candidate) + e).exists() for e in exts):
        candidate = folder / f"{base}-{n}"
        n += 1
    return candidate


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds} s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m} min {s:02d} s"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min"


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

SENTENCE_END = ".!?…。！？"
CLAUSE_END = ",;:，、；："
CLOSERS = "\"'”’»」』）)]】}"
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e",
    "no", "fig", "approx", "inc", "ltd", "co", "mt", "ft", "u.s", "u.k",
}


def clean_script(text: str) -> str:
    """Remove Markdown marks from a script (headings, bullets, bold...)."""
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    lines = []
    for line in text.split("\n"):
        s = line.strip()
        s = re.sub(r"^#{1,6}\s+", "", s)
        s = re.sub(r"^(?:[-*+•▪●]|\d+[.)])\s+", "", s)
        s = re.sub(r"^>\s?", "", s)
        s = re.sub(r"(\*\*|__|`+)", "", s)
        s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
        s = re.sub(r"\[([^\]]+)\]\((?:https?://)?[^)]+\)", r"\1", s)
        s = re.sub(r"[  ]{2,}", " ", s)
        lines.append(s)
    return "\n".join(lines).strip()


def split_sentences(text: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        buf.append(ch)
        if ch in SENTENCE_END:
            j = i + 1
            while j < n and (text[j] in SENTENCE_END or text[j] in CLOSERS):
                buf.append(text[j])
                j += 1
            boundary = ch in "。！？" or j >= n or text[j].isspace()
            if boundary and ch == ".":
                word = re.findall(r"([\w.]+)\.$", "".join(buf).rstrip(CLOSERS))
                if word and word[-1].lower() in _ABBREVIATIONS:
                    boundary = False
                elif word and len(word[-1]) == 1 and word[-1].isupper():
                    boundary = False  # initials like "J. Smith"
            if boundary:
                s = "".join(buf).strip()
                if s:
                    out.append(s)
                buf = []
            i = j
            continue
        i += 1
    s = "".join(buf).strip()
    if s:
        out.append(s)
    return out


def joiner(left: str, right: str) -> str:
    """'' between Chinese/Japanese/Korean text, ' ' otherwise."""
    if not left or not right:
        return ""
    if (is_cjk_char(left[-1]) or left[-1] in "。！？，、；：") and is_cjk_char(right[0]):
        return ""
    return " "


def join_texts(texts: list[str]) -> str:
    out = ""
    for t in texts:
        t = t.strip()
        if t:
            out = out + joiner(out, t) + t if out else t
    return out


# ---------------------------------------------------------------------------
# Matching an exact script to the recognized text (for --script)
# ---------------------------------------------------------------------------

def is_kept_char(ch: str) -> bool:
    """Characters the forced aligner keeps (letters, numbers and ')."""
    if ch == "'":
        return True
    cat = unicodedata.category(ch)
    return cat.startswith("L") or cat.startswith("N")


def word_spans(text: str) -> list[tuple[int, int, str]]:
    """Words of a text as (start, end, normalized word). Chinese, Japanese and
    Korean characters count as one word each."""
    spans = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if is_cjk_char(ch):
            spans.append((i, i + 1, ch))
            i += 1
            continue
        j = i
        while j < n and not text[j].isspace() and not is_cjk_char(text[j]):
            j += 1
        norm = "".join(c for c in text[i:j] if is_kept_char(c)).lower()
        if norm:
            spans.append((i, j, norm))
        i = j
    return spans


def split_script_by_pieces(script: str, recognized: list[str]) -> list[str]:
    """Share out an exact script between audio pieces.

    recognized: what speech recognition heard in each piece, in order.
    Returns the part of the script spoken in each piece (same order). Words are
    matched with difflib, so recognition mistakes don't matter much.
    """
    n = len(recognized)
    if n == 0:
        return []
    words = word_spans(script)
    if n == 1 or not words:
        return [script.strip()] + [""] * (n - 1)
    heard = [(k, w[2]) for k, text in enumerate(recognized) for w in word_spans(text)]
    if not heard:
        return [script.strip()] + [""] * (n - 1)
    matcher = difflib.SequenceMatcher(None, [w[2] for w in words], [h[1] for h in heard], autojunk=False)
    owner: list[int | None] = [None] * len(words)
    for a, b, size in matcher.get_matching_blocks():
        for k in range(size):
            owner[a + k] = heard[b + k][0]
    first = next((o for o in owner if o is not None), 0)
    last = first
    for i, o in enumerate(owner):  # unmatched words go with the piece before them
        if o is None:
            owner[i] = last
        else:
            last = max(last, o)
            owner[i] = last
    pieces = [""] * n
    start = 0
    for i in range(1, len(words) + 1):
        if i == len(words) or owner[i] != owner[i - 1]:
            end = len(script) if i == len(words) else words[i][0]
            pieces[owner[i - 1]] = script[start:end].strip()
            start = end
    return pieces


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------

def attach_display_text(transcript: str, items: list[tuple[str, float, float]]) -> list[dict]:
    """Give aligner words back their punctuation and spacing from the transcript.

    items: [(word_without_punctuation, start_seconds, end_seconds), ...]
    Returns [{"text", "word", "start", "end", "space_before"}, ...].
    """
    out: list[dict] = []
    pos = 0
    n = len(transcript)

    def match_at(i: int, target: str):
        j, k = i, 0
        while j < n and k < len(target):
            c = transcript[j]
            if c == target[k]:
                j += 1
                k += 1
            elif not is_kept_char(c) and not c.isspace() and k > 0:
                j += 1  # punctuation inside a word, e.g. "well-known"
            else:
                return None
        return j if k == len(target) else None

    def can_start(i: int, start_pos: int) -> bool:
        # Only match at the start of a word, except in Chinese, Japanese and
        # Korean text, where words are not separated by spaces.
        if i == start_pos:
            return True
        prev = transcript[i - 1]
        if not is_kept_char(prev):
            return True
        return is_cjk_char(transcript[i]) or is_cjk_char(prev)

    for word, start, end in items:
        target = word.strip()
        if not target:
            continue
        found = None
        i = pos
        space_before = False
        newline_before = False
        prefix_start = None
        limit = min(n, pos + 80 + len(target) * 2)
        while i < limit:
            c = transcript[i]
            if c.isspace():
                space_before = True
                newline_before = newline_before or c == "\n"
                prefix_start = None
                i += 1
                continue
            if not is_kept_char(c):
                if prefix_start is None:
                    prefix_start = i
                i += 1
                continue
            j = match_at(i, target) if can_start(i, pos) else None
            if j is not None:
                found = (prefix_start if prefix_start is not None else i, j)
                break
            prefix_start = None
            i += 1
        if found is None:
            out.append({"text": target, "word": target, "start": start, "end": end, "space_before": True})
            continue
        a, j = found
        while j < n and not transcript[j].isspace() and not is_kept_char(transcript[j]):
            j += 1  # trailing punctuation: "word," "end." "对。"
        out.append({
            "text": transcript[a:j],
            "word": target,
            "start": start,
            "end": end,
            "space_before": space_before or not out,
            "newline_before": newline_before and bool(out),  # a line break in a script
        })
        pos = j
    return out


def _join_tokens(tokens: list[dict]) -> str:
    s = ""
    for t in tokens:
        if s and t["space_before"]:
            s += " "
        s += t["text"]
    return s.strip()


def _last_mark(token: dict) -> str:
    text = token["text"].rstrip(CLOSERS)
    return text[-1:] if text else ""


def _greedy_lines(tokens: list[dict], max_chars: int, max_duration: float) -> list[list[dict]]:
    lines: list[list[dict]] = []
    cur: list[dict] = []
    for tok in tokens:
        if cur and (len(_join_tokens(cur + [tok])) > max_chars or tok["end"] - cur[0]["start"] > max_duration):
            lines.append(cur)
            cur = []
        cur.append(tok)
    if cur:
        lines.append(cur)
    return lines


def _best_cut(tokens: list[dict], limit: int) -> int:
    """Where to cut a very long run of words: at the longest pause, preferably after a comma."""
    best, best_score = limit, -1.0
    for p in range(max(1, limit // 2), min(limit, len(tokens) - 1) + 1):
        score = tokens[p]["start"] - tokens[p - 1]["end"]
        if _last_mark(tokens[p - 1]) in CLAUSE_END + SENTENCE_END:
            score += 1.0
        if score > best_score:
            best, best_score = p, score
    return best


def _split_line(tokens: list[dict], max_chars: int, max_duration: float) -> list[list[dict]]:
    """Split one sentence into subtitle lines.

    Finds the split with lines of similar length (no lonely last word), preferring
    to break after a comma, with no line longer than about max_chars or max_duration.
    """
    if len(tokens) > 80:  # keep the search fast for very long runs without punctuation
        cut = _best_cut(tokens, 80)
        return (_split_line(tokens[:cut], max_chars, max_duration)
                + _split_line(tokens[cut:], max_chars, max_duration))
    n = len(tokens)
    widths = [len(t["text"]) for t in tokens]
    spaces = [1 if (i > 0 and t["space_before"]) else 0 for i, t in enumerate(tokens)]
    pw, ps = [0], [0]
    for w, s in zip(widths, spaces):
        pw.append(pw[-1] + w)
        ps.append(ps[-1] + s)

    def length(i: int, j: int) -> int:  # characters of the line tokens[i:j]
        return pw[j] - pw[i] + ps[j] - ps[i + 1]

    def seconds(i: int, j: int) -> float:
        return tokens[j - 1]["end"] - tokens[i]["start"]

    total = length(0, n)
    count = max(1, math.ceil(total / max_chars), math.ceil(seconds(0, n) / max_duration))
    if count == 1 or n == 1:
        return [tokens]
    hard_max = int(max_chars * 1.15)
    inf = float("inf")
    for lines_wanted in range(min(count, n), min(n, count + 3) + 1):
        target = total / lines_wanted
        best = [[inf] * (n + 1) for _ in range(lines_wanted + 1)]
        back = [[0] * (n + 1) for _ in range(lines_wanted + 1)]
        best[0][0] = 0.0
        for k in range(1, lines_wanted + 1):
            for j in range(k, n + 1):
                for i in range(max(k - 1, j - 40), j):
                    if best[k - 1][i] == inf:
                        continue
                    if j - i > 1 and (length(i, j) > hard_max or seconds(i, j) > max_duration):
                        continue
                    cost = (length(i, j) - target) ** 2
                    if j < n and _last_mark(tokens[j - 1]) in CLAUSE_END:
                        cost -= 0.5 * target ** 2  # breaking after a comma reads best
                    if best[k - 1][i] + cost < best[k][j]:
                        best[k][j] = best[k - 1][i] + cost
                        back[k][j] = i
        if best[lines_wanted][n] < inf:
            lines, j = [], n
            for k in range(lines_wanted, 0, -1):
                i = back[k][j]
                lines.append(tokens[i:j])
                j = i
            return lines[::-1]
    return _greedy_lines(tokens, max_chars, max_duration)


def build_cues(tokens: list[dict], max_chars: int | None = None, max_duration: float = 6.0,
               max_gap: float = 0.9, min_duration: float = 0.7) -> list[dict]:
    """Group timed words into subtitle lines: one sentence (or part of one) per line."""
    if not tokens:
        return []
    if max_chars is None:
        max_chars = 18 if mostly_cjk("".join(t["text"] for t in tokens)) else 42
    sentences: list[list[dict]] = []
    cur: list[dict] = []
    for tok in tokens:
        if cur and (_last_mark(cur[-1]) in SENTENCE_END or tok.get("newline_before")
                    or tok["start"] - cur[-1]["end"] > max_gap):
            sentences.append(cur)
            cur = []
        cur.append(tok)
    if cur:
        sentences.append(cur)

    cues = []
    for sentence in sentences:
        for line in _split_line(sentence, max_chars, max_duration):
            start = float(line[0]["start"])
            end = max(float(line[-1]["end"]), start + 0.05)
            cues.append({"start": start, "end": end, "text": _join_tokens(line)})
    for i, cue in enumerate(cues):
        next_start = cues[i + 1]["start"] if i + 1 < len(cues) else None
        if cue["end"] - cue["start"] < min_duration:
            target = cue["start"] + min_duration
            if next_start is not None:
                target = min(target, next_start - 0.04)
            cue["end"] = max(cue["end"], target)
        if next_start is not None and cue["end"] > next_start:
            cue["end"] = max(cue["start"] + 0.05, next_start - 0.001)
    return cues


def srt_time(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_srt(cues: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(cues, 1):
        blocks.append(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}\n")
    return "\n".join(blocks)
