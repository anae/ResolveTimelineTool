"""Launch the Resolve timeline assistant."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Iterable, Optional


HOMEBREW_PYTHON_CANDIDATES = (
    Path("/opt/homebrew/bin/python3.12"),
    Path("/usr/local/bin/python3.12"),
)


def select_macos_python(
    current: Path,
    candidates: Iterable[Path],
    current_version: tuple[int, int],
) -> Optional[Path]:
    """Return a Homebrew Python when the current macOS Python is too old."""

    if sys.platform != "darwin" or current_version >= (3, 12):
        return None

    for candidate in candidates:
        if candidate.is_file() and candidate.resolve() != current.resolve():
            return candidate
    return None


def relaunch_with_supported_python() -> None:
    discovered = shutil.which("python3.12")
    candidates = ([Path(discovered)] if discovered else []) + list(HOMEBREW_PYTHON_CANDIDATES)
    preferred = select_macos_python(
        Path(sys.executable),
        candidates,
        (sys.version_info.major, sys.version_info.minor),
    )
    if preferred is None:
        return

    os.execv(
        str(preferred),
        [str(preferred), str(Path(__file__).resolve()), *sys.argv[1:]],
    )


def main() -> None:
    relaunch_with_supported_python()

    # Tkinter is imported only after selecting a compatible Python.
    from video_timeline_tool.app import main as app_main

    app_main()


if __name__ == "__main__":
    main()
