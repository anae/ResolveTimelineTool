from datetime import datetime
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from video_timeline_tool.exporters import export_fcpxml, fcpx_time, seconds_to_timecode
from video_timeline_tool.models import ClipInfo, TimelinePlan, TimelineSegment


class ExporterTests(unittest.TestCase):
    def test_fcpxml_uses_media_rep_for_original_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            clip_path = tmp_path / "Mountain clip.mp4"
            clip_path.touch()
            created_at = datetime(2026, 7, 28, 12, 0)
            clip = ClipInfo(
                path=clip_path,
                duration_seconds=8.0,
                created_at=created_at,
                day=created_at.date(),
                is_drone=False,
                start_timecode_seconds=3600.12,
            )
            plan = TimelinePlan(
                name="Mountain test",
                fps=25,
                segments=[
                    TimelineSegment(
                        clip=clip,
                        source_in=0.0,
                        source_out=8.0,
                        record_in=0.0,
                        record_out=8.0,
                        day=created_at.date(),
                    )
                ],
                warnings=[],
                source_dir=tmp_path,
                style_path=tmp_path / "style.md",
                output_dir=tmp_path,
            )
            output_path = tmp_path / "timeline.fcpxml"

            export_fcpxml(plan, output_path)

            root = ET.parse(output_path).getroot()
            asset = root.find("./resources/asset")
            media_rep = root.find("./resources/asset/media-rep")
            asset_clip = root.find("./library/event/project/sequence/spine/asset-clip")

        self.assertIsNotNone(asset)
        self.assertNotIn("src", asset.attrib)
        self.assertEqual(asset.attrib["format"], "r0")
        self.assertEqual(asset.attrib["start"], "90003/25s")
        self.assertIsNotNone(media_rep)
        self.assertEqual(media_rep.attrib["kind"], "original-media")
        self.assertEqual(media_rep.attrib["src"], clip_path.resolve().as_uri())
        self.assertIsNotNone(asset_clip)
        self.assertEqual(asset_clip.attrib["start"], "90003/25s")

    def test_timecode_at_25fps(self) -> None:
        self.assertEqual(seconds_to_timecode(0, 25), "00:00:00:00")
        self.assertEqual(seconds_to_timecode(1.0, 25), "00:00:01:00")
        self.assertEqual(seconds_to_timecode(61.04, 25), "00:01:01:01")

    def test_fcpx_time_uses_frame_rationals(self) -> None:
        self.assertEqual(fcpx_time(0, 25), "0s")
        self.assertEqual(fcpx_time(2.0, 25), "50/25s")


if __name__ == "__main__":
    unittest.main()
