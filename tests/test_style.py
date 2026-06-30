import tempfile
import unittest
from pathlib import Path

from video_timeline_tool.style import read_style


class StyleTests(unittest.TestCase):
    def test_read_style_extracts_practical_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "style.md"
            style_path.write_text(
                """
                fps: 30
                mots-cles drone: DJI, Mavic, travelling aerien
                transition drone: 4s
                minimum segment: 1.5s
                fenetre beat: 0.2s
                """,
                encoding="utf-8",
            )

            style = read_style(style_path)

        self.assertEqual(style.fps, 30)
        self.assertIn("dji", style.drone_keywords)
        self.assertIn("mavic", style.drone_keywords)
        self.assertEqual(style.transition_seconds, 4.0)
        self.assertEqual(style.min_segment_seconds, 1.5)
        self.assertEqual(style.beat_snap_window_seconds, 0.2)
        self.assertNotIn("4s", style.drone_keywords)


if __name__ == "__main__":
    unittest.main()
