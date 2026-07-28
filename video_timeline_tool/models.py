from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, List, Optional, Sequence


ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class StyleConfig:
    drone_keywords: Sequence[str] = field(
        default_factory=lambda: ("drone", "dji", "mavic", "aerial", "air", "fpv")
    )
    skip_keywords: Sequence[str] = field(default_factory=tuple)
    transition_seconds: float = 3.0
    beat_sync_enabled: bool = True
    beat_snap_window_seconds: float = 0.35
    min_segment_seconds: float = 2.0
    fallback_clip_seconds: float = 8.0
    fps: int = 25


@dataclass(frozen=True)
class ClipInfo:
    path: Path
    duration_seconds: float
    created_at: datetime
    day: date
    is_drone: bool
    start_timecode_seconds: float = 0.0
    fps: Optional[float] = None
    has_audio: bool = True
    warning: Optional[str] = None

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class TimelineSegment:
    clip: ClipInfo
    source_in: float
    source_out: float
    record_in: float
    record_out: float
    day: date
    role: str = "main"
    marker: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.source_out - self.source_in)


@dataclass(frozen=True)
class TimelinePlan:
    name: str
    fps: int
    segments: List[TimelineSegment]
    warnings: List[str]
    source_dir: Path
    style_path: Path
    output_dir: Path

    @property
    def duration_seconds(self) -> float:
        if not self.segments:
            return 0.0
        return max(segment.record_out for segment in self.segments)


@dataclass(frozen=True)
class ExportResult:
    plan: TimelinePlan
    edl_path: Path
    fcpxml_path: Path
    report_path: Path
