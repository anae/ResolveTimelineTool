import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run import select_macos_python


class LauncherTests(unittest.TestCase):
    def test_selects_homebrew_python_for_macos_system_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "python3.12"
            candidate.touch()

            with patch.object(sys, "platform", "darwin"):
                selected = select_macos_python(
                    Path("/Library/Developer/CommandLineTools/usr/bin/python3"),
                    [candidate],
                    (3, 9),
                )

        self.assertEqual(selected, candidate)

    def test_keeps_supported_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "python3.12"
            candidate.touch()

            with patch.object(sys, "platform", "darwin"):
                selected = select_macos_python(Path("/custom/python3"), [candidate], (3, 12))

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
