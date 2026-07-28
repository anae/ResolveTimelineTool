import unittest

from video_timeline_tool.metadata import _parse_timecode, _start_timecode_from_probe


class MetadataTests(unittest.TestCase):
    def test_parses_gopro_non_drop_timecode(self) -> None:
        expected_frames = ((21 * 3600) + (40 * 60) + 1) * 30 + 3

        seconds = _parse_timecode("21:40:01:03", 30000 / 1001)

        self.assertEqual(seconds, expected_frames / 30)

    def test_reads_timecode_from_video_stream(self) -> None:
        data = {
            "streams": [
                {
                    "codec_type": "video",
                    "tags": {"timecode": "03:48:06:17"},
                }
            ]
        }

        seconds = _start_timecode_from_probe(data, 30000 / 1001)

        self.assertEqual(seconds, (((3 * 3600) + (48 * 60) + 6) * 30 + 17) / 30)


if __name__ == "__main__":
    unittest.main()
