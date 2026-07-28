from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List

from .models import TimelinePlan, TimelineSegment


def seconds_to_frames(seconds: float, fps: int) -> int:
    return max(0, int(round(seconds * fps)))


def seconds_to_timecode(seconds: float, fps: int) -> str:
    total_frames = seconds_to_frames(seconds, fps)
    frames = total_frames % fps
    total_seconds = total_frames // fps
    seconds_part = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}:{frames:02d}"


def fcpx_time(seconds: float, fps: int) -> str:
    frames = seconds_to_frames(seconds, fps)
    if frames == 0:
        return "0s"
    return f"{frames}/{fps}s"


def export_edl(plan: TimelinePlan, output_path: Path) -> None:
    lines = [
        f"TITLE: {plan.name}",
        "FCM: NON-DROP FRAME",
        "",
    ]
    current_day = None
    for index, segment in enumerate(plan.segments, start=1):
        if segment.day != current_day:
            current_day = segment.day
            lines.append(f"* DAY: {current_day.isoformat()}")

        source_start = segment.clip.start_timecode_seconds
        source_in = seconds_to_timecode(source_start + segment.source_in, plan.fps)
        source_out = seconds_to_timecode(source_start + segment.source_out, plan.fps)
        record_in = seconds_to_timecode(segment.record_in, plan.fps)
        record_out = seconds_to_timecode(segment.record_out, plan.fps)
        reel = _edl_reel(segment.clip.path)
        lines.append(
            f"{index:03d}  {reel:<8} V     C        "
            f"{source_in} {source_out} {record_in} {record_out}"
        )
        lines.append(f"* FROM CLIP NAME: {segment.clip.name}")
        lines.append(f"* SOURCE FILE: {segment.clip.path}")
        lines.append(f"* ROLE: {segment.role}")
        if segment.marker:
            lines.append(f"* MARKER: {segment.marker}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def export_fcpxml(plan: TimelinePlan, output_path: Path) -> None:
    root = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(root, "resources")
    ET.SubElement(
        resources,
        "format",
        {
            "id": "r0",
            "name": f"FFVideoFormat1080p{plan.fps}",
            "frameDuration": f"1/{plan.fps}s",
            "width": "1920",
            "height": "1080",
        },
    )

    asset_ids = _asset_ids(plan.segments)
    for path, asset_id in asset_ids.items():
        matching_clips = [
            segment.clip for segment in plan.segments if segment.clip.path == path
        ]
        longest_duration = max(clip.duration_seconds for clip in matching_clips)
        start_timecode_seconds = matching_clips[0].start_timecode_seconds
        asset = ET.SubElement(
            resources,
            "asset",
            {
                "id": asset_id,
                "name": path.name,
                "format": "r0",
                "start": fcpx_time(start_timecode_seconds, plan.fps),
                "duration": fcpx_time(longest_duration, plan.fps),
                "hasVideo": "1",
                "hasAudio": "1",
                "audioSources": "1",
                "audioChannels": "2",
                "audioRate": "48000",
            },
        )
        ET.SubElement(
            asset,
            "media-rep",
            {
                "kind": "original-media",
                "src": path.resolve().as_uri(),
            },
        )

    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": "Auto timelines"})
    project = ET.SubElement(event, "project", {"name": plan.name})
    sequence = ET.SubElement(
        project,
        "sequence",
        {
            "format": "r0",
            "tcStart": "0s",
            "tcFormat": "NDF",
            "duration": fcpx_time(plan.duration_seconds, plan.fps),
        },
    )
    spine = ET.SubElement(sequence, "spine")

    for segment in plan.segments:
        attrs = {
            "name": segment.clip.name,
            "ref": asset_ids[segment.clip.path],
            "offset": fcpx_time(segment.record_in, plan.fps),
            "start": fcpx_time(
                segment.clip.start_timecode_seconds + segment.source_in,
                plan.fps,
            ),
            "duration": fcpx_time(segment.duration_seconds, plan.fps),
        }
        asset_clip = ET.SubElement(spine, "asset-clip", attrs)
        if segment.role == "drone_transition":
            asset_clip.set("note", "Drone transition")
        if segment.marker:
            ET.SubElement(
                asset_clip,
                "marker",
                {"start": "0s", "value": segment.marker, "completed": "0"},
            )

    _indent(root)
    xml_body = ET.tostring(root, encoding="unicode")
    output_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n'
        + xml_body
        + "\n",
        encoding="utf-8",
    )


def write_report(plan: TimelinePlan, output_path: Path) -> None:
    day_counts: Dict[str, int] = {}
    role_counts: Dict[str, int] = {}
    for segment in plan.segments:
        day_counts[segment.day.isoformat()] = day_counts.get(segment.day.isoformat(), 0) + 1
        role_counts[segment.role] = role_counts.get(segment.role, 0) + 1

    lines = [
        f"# {plan.name}",
        "",
        f"- Source: `{plan.source_dir}`",
        f"- Style: `{plan.style_path}`",
        f"- FPS: `{plan.fps}`",
        f"- Segments: `{len(plan.segments)}`",
        f"- Duree timeline: `{seconds_to_timecode(plan.duration_seconds, plan.fps)}`",
        "",
        "## Decoupage par jour",
        "",
    ]
    for day, count in sorted(day_counts.items()):
        lines.append(f"- {day}: {count} segment(s)")
    lines.extend(["", "## Roles", ""])
    for role, count in sorted(role_counts.items()):
        lines.append(f"- {role}: {count}")
    if plan.warnings:
        lines.extend(["", "## Avertissements", ""])
        for warning in plan.warnings:
            lines.append(f"- {warning}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _asset_ids(segments: Iterable[TimelineSegment]) -> Dict[Path, str]:
    asset_ids: Dict[Path, str] = {}
    for segment in segments:
        if segment.clip.path not in asset_ids:
            asset_ids[segment.clip.path] = f"r{len(asset_ids) + 1}"
    return asset_ids


def _edl_reel(path: Path) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", path.stem.upper())
    return (cleaned[:8] or "AX")


def _indent(element: ET.Element, level: int = 0) -> None:
    indent = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + "  "
        for child in element:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indent
