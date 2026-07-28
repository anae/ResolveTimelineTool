from datetime import datetime
import tempfile
import unittest
from pathlib import Path

from video_timeline_tool.engine import build_timeline_plan, process_timeline
from video_timeline_tool.models import ClipInfo, StyleConfig


class EngineTests(unittest.TestCase):
    def test_process_timeline_writes_all_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            source = tmp_path / "rushes"
            output = tmp_path / "exports"
            source.mkdir()
            for name in (
                "20260728_main_a.mp4",
                "20260728_main_b.mp4",
                "20260728_DJI_drone.mp4",
            ):
                (source / name).write_bytes(b"")

            style_path = tmp_path / "style.md"
            style_path.write_text(
                "fps: 25\ntransition drone: 2s\n",
                encoding="utf-8",
            )

            result = process_timeline(
                source_dir=source,
                style_path=style_path,
                max_segment_seconds=4.0,
                output_dir=output,
            )

            self.assertTrue(result.edl_path.is_file())
            self.assertTrue(result.fcpxml_path.is_file())
            self.assertTrue(result.report_path.is_file())
            self.assertGreater(len(result.plan.segments), 0)

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
