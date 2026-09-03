import tempfile
import unittest
from pathlib import Path

from voice_clip_sorter import (
    available_destination,
    classification_counts,
    discover_clips,
    format_time,
    load_preferences,
)


class VoiceClipSorterHelpersTests(unittest.TestCase):
    def test_discovers_supported_files_in_filename_order_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ["take10.ogg", "Take2.WAV", "take1.mp3", "notes.txt"]:
                (root / name).touch()
            child = root / "nested"
            child.mkdir()
            (child / "hidden.wav").touch()

            self.assertEqual(
                [path.name for path in discover_clips(root)],
                ["take1.mp3", "Take2.WAV", "take10.ogg"],
            )

    def test_destination_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "line.wav").touch()
            (root / "line (2).wav").touch()
            self.assertEqual(available_destination(root, "line.wav").name, "line (3).wav")

    def test_time_format(self):
        self.assertEqual(format_time(65.9), "1:05")

    def test_preferences_default_and_clamp_invalid_volume(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "preferences.json"
            self.assertEqual(load_preferences(path), {"autoplay": False, "volume": 1.0})
            path.write_text('{"autoplay": true, "volume": 4.5}', encoding="utf-8")
            self.assertEqual(load_preferences(path), {"autoplay": True, "volume": 1.0})

    def test_classification_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            clips = [
                root / "line1.wav",
                root / "Keep" / "line2.wav",
                root / "Rejected" / "line3.wav",
                root / "Rejected" / "line4.wav",
            ]
            self.assertEqual(
                classification_counts(clips, root),
                {"unsorted": 1, "rejected": 2, "keep": 1},
            )


if __name__ == "__main__":
    unittest.main()
