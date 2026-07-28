from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from .models import ClipInfo, StyleConfig


VIDEO_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".mxf",
    ".r3d",
    ".webm",
}


def find_video_files(source_dir: Path, skip_keywords: Sequence[str]) -> List[Path]:
    skip = tuple(keyword.lower() for keyword in skip_keywords)
    files: List[Path] = []
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        lowered = str(path).lower()
        if skip and any(keyword in lowered for keyword in skip):
            continue
        files.append(path)
    return sorted(files, key=lambda item: str(item).lower())


def probe_clip(path: Path, style: StyleConfig) -> ClipInfo:
    data, probe_warning = _run_ffprobe(path)
    duration = _duration_from_probe(data) if data else None
    created_at = _created_at_from_probe(data) if data else None
    fps = _fps_from_probe(data) if data else None
    start_timecode_seconds = _start_timecode_from_probe(data, fps or style.fps)
    has_audio = _has_audio(data) if data else True

    warning = probe_warning
    if duration is None:
        duration = style.fallback_clip_seconds
        warning = (
            f"{path.name}: duree inconnue, {duration:.1f}s utilisees par defaut"
            if warning is None
            else f"{warning}; duree par defaut {duration:.1f}s"
        )
    if created_at is None:
        created_at = _created_at_from_filename(path) or _created_at_from_mtime(path)

    return ClipInfo(
        path=path,
        duration_seconds=max(0.1, duration),
        created_at=created_at,
        day=created_at.date(),
        is_drone=_is_drone_clip(path, style.drone_keywords),
        start_timecode_seconds=start_timecode_seconds,
        fps=fps,
        has_audio=has_audio,
        warning=warning,
    )


def _run_ffprobe(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None, "ffprobe introuvable: metadata limitee"

    cmd = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_entries",
        (
            "format=duration:format_tags=creation_time,timecode:"
            "stream=codec_type,duration,r_frame_rate:"
            "stream_tags=creation_time,timecode"
        ),
        str(path),
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return json.loads(completed.stdout), None
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return None, f"{path.name}: lecture ffprobe impossible ({exc})"


def _duration_from_probe(data: Optional[dict]) -> Optional[float]:
    if not data:
        return None
    candidates = []
    format_data = data.get("format") or {}
    if format_data.get("duration"):
        candidates.append(format_data["duration"])
    for stream in data.get("streams") or []:
        if stream.get("duration"):
            candidates.append(stream["duration"])
    for raw in candidates:
        try:
            duration = float(raw)
        except (TypeError, ValueError):
            continue
        if duration > 0:
            return duration
    return None


def _created_at_from_probe(data: Optional[dict]) -> Optional[datetime]:
    if not data:
        return None
    raw_dates = []
    format_tags = (data.get("format") or {}).get("tags") or {}
    raw_dates.append(format_tags.get("creation_time"))
    for stream in data.get("streams") or []:
        raw_dates.append(((stream.get("tags") or {}).get("creation_time")))
    for raw in raw_dates:
        parsed = _parse_datetime(raw)
        if parsed:
            return parsed
    return None


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[: len(fmt)], fmt)
        except ValueError:
            continue
    return None


def _fps_from_probe(data: Optional[dict]) -> Optional[float]:
    if not data:
        return None
    for stream in data.get("streams") or []:
        if stream.get("codec_type") != "video":
            continue
        raw = stream.get("r_frame_rate") or ""
        if "/" in raw:
            numerator, denominator = raw.split("/", 1)
            try:
                denominator_float = float(denominator)
                if denominator_float:
                    return float(numerator) / denominator_float
            except ValueError:
                continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _start_timecode_from_probe(data: Optional[dict], fps: float) -> float:
    if not data:
        return 0.0

    candidates = [((data.get("format") or {}).get("tags") or {}).get("timecode")]
    for stream in data.get("streams") or []:
        candidates.append(((stream.get("tags") or {}).get("timecode")))

    for raw in candidates:
        seconds = _parse_timecode(raw, fps)
        if seconds is not None:
            return seconds
    return 0.0


def _parse_timecode(value: Optional[str], fps: float) -> Optional[float]:
    if not value:
        return None

    match = re.fullmatch(r"(\d{1,2}):([0-5]\d):([0-5]\d)([:;])(\d{1,2})", value.strip())
    if not match:
        return None

    hours, minutes, seconds, separator, frames = match.groups()
    nominal_fps = max(1, int(round(fps)))
    frame_number = int(frames)
    if frame_number >= nominal_fps:
        return None

    total_minutes = int(hours) * 60 + int(minutes)
    total_frames = (
        ((int(hours) * 3600) + (int(minutes) * 60) + int(seconds)) * nominal_fps
        + frame_number
    )

    if separator == ";" and nominal_fps in (30, 60):
        drop_frames = 2 if nominal_fps == 30 else 4
        total_frames -= drop_frames * (total_minutes - (total_minutes // 10))

    return total_frames / nominal_fps


def _has_audio(data: Optional[dict]) -> bool:
    if not data:
        return True
    return any(stream.get("codec_type") == "audio" for stream in data.get("streams") or [])


def _created_at_from_filename(path: Path) -> Optional[datetime]:
    text = path.stem
    patterns = (
        r"(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)[-_ ]?([0-2]\d)?[-_]?([0-5]\d)?[-_]?([0-5]\d)?",
        r"([0-3]\d)[-_]([01]\d)[-_](20\d{2})[-_ ]?([0-2]\d)?[-_]?([0-5]\d)?[-_]?([0-5]\d)?",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 6 and groups[0].startswith("20"):
            year, month, day, hour, minute, second = groups
        else:
            day, month, year, hour, minute, second = groups
        try:
            return datetime(
                int(year),
                int(month),
                int(day),
                int(hour or 0),
                int(minute or 0),
                int(second or 0),
            )
        except ValueError:
            continue
    return None


def _created_at_from_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def _is_drone_clip(path: Path, drone_keywords: Iterable[str]) -> bool:
    lowered = str(path).lower()
    return any(keyword.lower() in lowered for keyword in drone_keywords if keyword)
