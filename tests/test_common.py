"""Tests for app/common.py (standard library only).

Run from the Transcribe folder:  python -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import common as C  # noqa: E402


def timed(text, step=0.3):
    """Fake aligner output for a text: each word step seconds long."""
    words = [w[2] for w in C.word_spans(text)]
    raw = [w for w in text.split() if any(C.is_kept_char(c) for c in w)]
    if not C.mostly_cjk(text):
        words = ["".join(c for c in w if C.is_kept_char(c)) for w in raw]
    return [(w, i * step, i * step + step * 0.8) for i, w in enumerate(words)]


class SubtitleTests(unittest.TestCase):
    def test_punctuation_comes_back(self):
        text = 'Hello, world! He said, "Okay." Done.'
        items = [("Hello", 0.0, 0.4), ("world", 0.5, 0.9), ("He", 1.2, 1.3), ("said", 1.3, 1.6),
                 ("Okay", 1.7, 2.0), ("Done", 2.4, 2.8)]
        tokens = C.attach_display_text(text, items)
        self.assertEqual([t["text"] for t in tokens], ["Hello,", "world!", "He", "said,", '"Okay."', "Done."])

    def test_no_match_inside_other_words(self):
        tokens = C.attach_display_text("that at", [("that", 0, 1), ("at", 1, 2)])
        self.assertEqual([t["text"] for t in tokens], ["that", "at"])

    def test_hyphen_and_apostrophe(self):
        tokens = C.attach_display_text("A well-known don't.", [("A", 0, 1), ("wellknown", 1, 2), ("don't", 2, 3)])
        self.assertEqual([t["text"] for t in tokens], ["A", "well-known", "don't."])

    def test_chinese_characters(self):
        text = "你好，世界。"
        items = [(ch, i * 0.3, i * 0.3 + 0.3) for i, ch in enumerate("你好世界")]
        tokens = C.attach_display_text(text, items)
        self.assertEqual([t["text"] for t in tokens], ["你", "好，", "世", "界。"])
        self.assertEqual([c["text"] for c in C.build_cues(tokens)], ["你好，世界。"])

    def test_unknown_word_falls_back(self):
        tokens = C.attach_display_text("Hello there.", [("Hello", 0, 1), ("zzz", 1, 2), ("there", 2, 3)])
        self.assertEqual([t["text"] for t in tokens], ["Hello", "zzz", "there."])

    def test_lines_are_balanced_without_orphans(self):
        text = "An empty line, like the one above, starts a new paragraph with a longer pause."
        cues = C.build_cues(C.attach_display_text(text, timed(text)))
        self.assertEqual([c["text"] for c in cues],
                         ["An empty line, like the one above,", "starts a new paragraph with a longer pause."])

    def test_sentences_start_new_lines_and_limits_hold(self):
        text = "One two three. " + " ".join(["word"] * 40) + "."
        cues = C.build_cues(C.attach_display_text(text, timed(text, 0.1)))
        self.assertEqual(cues[0]["text"], "One two three.")
        self.assertTrue(all(len(c["text"]) <= 48 for c in cues))
        self.assertTrue(all(len(c["text"]) >= 15 for c in cues[1:]))
        for a, b in zip(cues, cues[1:]):
            self.assertLessEqual(a["end"], b["start"])

    def test_no_lonely_last_word(self):
        text = "Hello world, this is a test of the transcription."
        cues = C.build_cues(C.attach_display_text(text, timed(text)))
        self.assertEqual([c["text"] for c in cues], ["Hello world,", "this is a test of the transcription."])

    def test_script_line_breaks_start_new_lines(self):
        text = "My voiceover\n\nThis is my exact script.\nIt has two lines"
        cues = C.build_cues(C.attach_display_text(text, timed(text)))
        self.assertEqual([c["text"] for c in cues], ["My voiceover", "This is my exact script.", "It has two lines"])

    def test_very_long_run_without_punctuation_is_fast(self):
        import time
        text = " ".join(["lyrics"] * 1500)
        tokens = C.attach_display_text(text, timed(text, 0.2))
        t = time.time()
        cues = C.build_cues(tokens)
        self.assertLess(time.time() - t, 5.0)
        self.assertEqual(sum(len(c["text"].split()) for c in cues), 1500)
        self.assertTrue(all(len(c["text"]) <= 48 for c in cues))

    def test_long_pause_starts_a_new_line(self):
        tokens = C.attach_display_text("one two three four", [("one", 0, .3), ("two", .4, .7),
                                                               ("three", 3.0, 3.3), ("four", 3.4, 3.7)])
        self.assertEqual([c["text"] for c in C.build_cues(tokens)], ["one two", "three four"])

    def test_max_chars_option(self):
        text = "This sentence should be cut into several short lines for vertical videos."
        cues = C.build_cues(C.attach_display_text(text, timed(text)), max_chars=20)
        self.assertGreater(len(cues), 3)
        self.assertTrue(all(len(c["text"]) <= 23 for c in cues))

    def test_srt_format(self):
        self.assertEqual(C.srt_time(3661.5), "01:01:01,500")
        srt = C.format_srt([{"start": 0, "end": 1.25, "text": "Hi."}, {"start": 1.5, "end": 2, "text": "Bye."}])
        self.assertEqual(srt, "1\n00:00:00,000 --> 00:00:01,250\nHi.\n\n2\n00:00:01,500 --> 00:00:02,000\nBye.\n")


class ScriptTests(unittest.TestCase):
    SCRIPT = ("Welcome back to the channel! Today we build a birdhouse.\n\n"
              "First, cut the wood. Then, sand every edge carefully.\n\n"
              "Finally, paint it and hang it in a tree.")

    def test_word_spans(self):
        self.assertEqual([w[2] for w in C.word_spans('Hi, "Bob"! 你好')], ["hi", "bob", "你", "好"])

    def test_script_is_shared_out_by_what_was_heard(self):
        heard = ["welcome back to the channel today we build a bird house first cut the",
                 "wood then sand every edge carefully",
                 "finally paint it and hang it in a tree"]
        pieces = C.split_script_by_pieces(self.SCRIPT, heard)
        self.assertEqual(pieces[0], "Welcome back to the channel! Today we build a birdhouse.\n\nFirst, cut the")
        self.assertEqual(pieces[1], "wood. Then, sand every edge carefully.")
        self.assertEqual(pieces[2], "Finally, paint it and hang it in a tree.")
        self.assertEqual(" ".join(pieces).split(), self.SCRIPT.split())

    def test_mistakes_and_silent_pieces(self):
        heard = ["welcome bak to the chanel today we build a", "", "birdhouse first cut the wood then sand every edge",
                 "carefully finally paint it and hang it in a three"]
        pieces = C.split_script_by_pieces(self.SCRIPT, heard)
        self.assertEqual(pieces[1], "")
        self.assertEqual(" ".join(p for p in pieces if p).split(), self.SCRIPT.split())
        self.assertTrue(pieces[3].startswith("carefully."))

    def test_one_piece_or_nothing_heard(self):
        self.assertEqual(C.split_script_by_pieces(self.SCRIPT, ["anything"]), [self.SCRIPT])
        self.assertEqual(C.split_script_by_pieces(self.SCRIPT, ["", ""]), [self.SCRIPT, ""])

    def test_chinese_script(self):
        script = "今天天气很好。我们去公园散步吧！"
        pieces = C.split_script_by_pieces(script, ["今天天气很好", "我们去公园散步吧"])
        self.assertEqual(pieces, ["今天天气很好。", "我们去公园散步吧！"])

    def test_clean_script(self):
        self.assertEqual(C.clean_script("# Title\n- **Bold** point"), "Title\nBold point")


class TextTests(unittest.TestCase):
    def test_sentences(self):
        self.assertEqual(C.split_sentences("Dr. Smith met J. Doe at 3.5 km. Then he left."),
                         ["Dr. Smith met J. Doe at 3.5 km.", "Then he left."])
        self.assertEqual(C.split_sentences("你好。我很好！"), ["你好。", "我很好！"])

    def test_join_texts(self):
        self.assertEqual(C.join_texts(["Hello there.", "", "Bye."]), "Hello there. Bye.")
        self.assertEqual(C.join_texts(["你好。", "再见。"]), "你好。再见。")

    def test_languages(self):
        self.assertEqual(C.normalize_language("es"), "Spanish")
        self.assertEqual(C.normalize_language("yue"), "Cantonese")
        self.assertIsNone(C.normalize_language("auto"))
        self.assertEqual(C.guess_language("こんにちは"), "Japanese")
        self.assertTrue(set(C.ALIGNER_LANGUAGES) <= set(C.ASR_LANGUAGES))
        self.assertEqual(len(C.ASR_LANGUAGES), 30)

    def test_resolve_size(self):
        self.assertEqual(C.resolve_size("fast", {"asr_size": "1.7B"}), "0.6B")
        self.assertEqual(C.resolve_size(None, {"asr_size": "1.7B"}), "1.7B")
        self.assertEqual(C.resolve_size(None, {}), "0.6B")


class FileTests(unittest.TestCase):
    def test_clean_path_input(self):
        self.assertEqual(C.clean_path_input('"C:\\My Files\\a.mp4"'), "C:\\My Files\\a.mp4")
        if not C.IS_WINDOWS:
            self.assertEqual(C.clean_path_input("/Users/me/My\\ Video.mov"), "/Users/me/My Video.mov")
        self.assertTrue(C.user_path("video.mp4").is_absolute())

    def test_unique_base(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            self.assertEqual(C.unique_base(folder, "talk", [".txt", ".srt"]).name, "talk")
            (folder / "talk.srt").write_text("x")
            self.assertEqual(C.unique_base(folder, "talk", [".txt", ".srt"]).name, "talk-2")

    def test_read_text_file_encodings(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.txt"
            p.write_bytes("Café".encode("utf-16"))
            self.assertEqual(C.read_text_file(p), "Café")
            p.write_bytes("Café".encode("cp1252"))
            self.assertEqual(C.read_text_file(p), "Café")


if __name__ == "__main__":
    unittest.main()


class CommandTests(unittest.TestCase):
    def test_commands_work_inside_the_kit_folder(self):
        """'./transcribe app' starts the web app, even though the kit has a folder named app."""
        import os
        from unittest import mock

        import transcribe as T

        old = os.getcwd()
        os.chdir(Path(__file__).resolve().parent.parent)
        try:
            self.assertTrue(Path("app").is_dir())
            with mock.patch.object(T, "cmd_app") as app, mock.patch.object(T, "cmd_check") as check:
                self.assertEqual(T.main(["app"]), 0)
                self.assertEqual(T.main(["check"]), 0)
            app.assert_called_once_with(None)
            check.assert_called_once_with()
        finally:
            os.chdir(old)
