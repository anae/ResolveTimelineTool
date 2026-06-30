from datetime import datetime
import tempfile
import unittest
from pathlib import Path

from video_timeline_tool.engine import build_timeline_plan
from video_timeline_tool.models import ClipInfo, StyleConfig


class EngineTests(unittest.TestCase):
    def test_build_timeline_inserts_drone_between_main_clips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            source = tmp_path / "rushes"
            source.mkdir()
            main_a = source / "20260618_main_a.mp4"
            main_b = source / "20260618_main_b.mp4"
            drone = source / "DJI_transition.mp4"
            for path in (main_a, main_b, drone):
                path.write_bytes(b"")

            day = datetime(2026, 6, 18, 10, 0, 0)
            clips = [
                ClipInfo(main_a, 5.0, day, day.date(), False),
                ClipInfo(main_b, 5.0, day, day.date(), False),
                ClipInfo(drone, 3.0, day, day.date(), True),
            ]

            plan = build_timeline_plan(
                source_dir=source,
                style_path=tmp_path / "style.md",
                output_dir=tmp_path / "out",
                clips=clips,
                style=StyleConfig(beat_sync_enabled=False, transition_seconds=2.0),
                fps=25,
                max_segment_seconds=10.0,
            )

        self.assertEqual([segment.role for segment in plan.segments], ["main", "drone_transition", "main"])
        self.assertEqual(plan.segments[0].marker, "Jour 2026-06-18")


if __name__ == "__main__":
    unittest.main()
