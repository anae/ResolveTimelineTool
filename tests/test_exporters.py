import unittest

from video_timeline_tool.exporters import fcpx_time, seconds_to_timecode


class ExporterTests(unittest.TestCase):
    def test_timecode_at_25fps(self) -> None:
        self.assertEqual(seconds_to_timecode(0, 25), "00:00:00:00")
        self.assertEqual(seconds_to_timecode(1.0, 25), "00:00:01:00")
        self.assertEqual(seconds_to_timecode(61.04, 25), "00:01:01:01")

    def test_fcpx_time_uses_frame_rationals(self) -> None:
        self.assertEqual(fcpx_time(0, 25), "0s")
        self.assertEqual(fcpx_time(2.0, 25), "50/25s")


if __name__ == "__main__":
    unittest.main()
