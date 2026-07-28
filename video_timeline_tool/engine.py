from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .beat import detect_beats, nearest_beat
from .exporters import export_edl, export_fcpxml, write_report
from .metadata import find_video_files, probe_clip
from .models import ClipInfo, ExportResult, ProgressCallback, StyleConfig, TimelinePlan, TimelineSegment
from .style import read_style


def process_timeline(
    source_dir: Path,
    style_path: Path,
    max_segment_seconds: float,
    output_dir: Optional[Path] = None,
    progress: Optional[ProgressCallback] = None,
    target_duration_seconds: Optional[float] = None,
) -> ExportResult:
    source_dir = source_dir.expanduser().resolve()
    style_path = style_path.expanduser().resolve()
    if output_dir is None:
        output_dir = source_dir / "_resolve_timeline_exports"
    output_dir = output_dir.expanduser().resolve()

    _progress(progress, 0.02, "Lecture du style Markdown")
    style = read_style(style_path)
    max_segment_seconds = max(style.min_segment_seconds, float(max_segment_seconds))
    if target_duration_seconds is not None:
        target_duration_seconds = max(style.min_segment_seconds, float(target_duration_seconds))

    _progress(progress, 0.08, "Recherche des rushs video")
    video_files = find_video_files(source_dir, style.skip_keywords)
    if not video_files:
        raise ValueError(f"Aucun fichier video trouve dans {source_dir}")

    clips: List[ClipInfo] = []
    warnings: List[str] = []
    for index, path in enumerate(video_files, start=1):
        _progress(
            progress,
            0.08 + (0.37 * index / max(1, len(video_files))),
            f"Analyse metadata {index}/{len(video_files)}: {path.name}",
        )
        clip = probe_clip(path, style)
        clips.append(clip)
        if clip.warning:
            warnings.append(clip.warning)

    fps = _choose_fps(style, clips)
    _progress(progress, 0.48, "Construction de la timeline")
    plan = build_timeline_plan(
        source_dir=source_dir,
        style_path=style_path,
        output_dir=output_dir,
        clips=clips,
        style=style,
        fps=fps,
        max_segment_seconds=max_segment_seconds,
        target_duration_seconds=target_duration_seconds,
        warnings=warnings,
        progress=progress,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(f"resolve_timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    edl_path = output_dir / f"{stem}.edl"
    fcpxml_path = output_dir / f"{stem}.fcpxml"
    report_path = output_dir / f"{stem}_report.md"

    _progress(progress, 0.88, "Ecriture EDL")
    export_edl(plan, edl_path)
    _progress(progress, 0.93, "Ecriture FCPXML")
    export_fcpxml(plan, fcpxml_path)
    _progress(progress, 0.97, "Ecriture rapport")
    write_report(plan, report_path)
    _progress(progress, 1.0, "Termine")

    return ExportResult(plan=plan, edl_path=edl_path, fcpxml_path=fcpxml_path, report_path=report_path)


def build_timeline_plan(
    source_dir: Path,
    style_path: Path,
    output_dir: Path,
    clips: List[ClipInfo],
    style: StyleConfig,
    fps: int,
    max_segment_seconds: float,
    warnings: Optional[List[str]] = None,
    progress: Optional[ProgressCallback] = None,
    target_duration_seconds: Optional[float] = None,
) -> TimelinePlan:
    warnings = list(warnings or [])
    main_clips = [clip for clip in clips if not clip.is_drone]
    drone_clips = [clip for clip in clips if clip.is_drone]

    if not main_clips:
        main_clips = clips
        drone_clips = []
        warnings.append("Aucun rush principal detecte: tous les clips sont utilises en principal")

    grouped = _group_by_day(main_clips)
    beat_cache: Dict[Path, List[float]] = {}
    candidates_by_day: Dict[object, List[tuple[ClipInfo, float, float]]] = defaultdict(list)

    total_main = max(1, len(main_clips))
    processed = 0
    for day in sorted(grouped):
        day_clips = sorted(grouped[day], key=lambda clip: (clip.created_at, clip.name.lower()))
        for clip in day_clips:
            beats = []
            if style.beat_sync_enabled and clip.has_audio:
                if clip.path not in beat_cache:
                    _progress(progress, 0.50 + 0.30 * processed / total_main, f"Detection beats: {clip.name}")
                    beat_cache[clip.path] = detect_beats(clip.path, clip.duration_seconds)
                beats = beat_cache[clip.path]

            for source_in, source_out in _segment_ranges(
                clip.duration_seconds,
                max_segment_seconds,
                style.min_segment_seconds,
                beats,
                style.beat_snap_window_seconds,
            ):
                candidates_by_day[day].append((clip, source_in, source_out))

            processed += 1
            _progress(
                progress,
                0.50 + 0.30 * processed / total_main,
                f"Timeline: {processed}/{total_main} clips principaux",
            )

    if style.beat_sync_enabled and not any(beat_cache.values()):
        warnings.append("Aucun beat detecte: cuts places sur la duree maximale des segments")

    selected_by_day = candidates_by_day
    if target_duration_seconds is not None:
        selected_by_day = _select_for_target(
            candidates_by_day,
            target_duration_seconds,
            max_segment_seconds,
            style.min_segment_seconds,
            drone_clips,
            style.transition_seconds,
        )

    record_cursor = 0.0
    drone_index = 0
    segments: List[TimelineSegment] = []
    previous_clip_path: Optional[Path] = None
    selected_days = [day for day in sorted(selected_by_day) if selected_by_day[day]]
    for day_index, day in enumerate(selected_days):
        first_for_day = True
        for clip, source_in, source_out in selected_by_day[day]:
            starts_new_clip = previous_clip_path is not None and clip.path != previous_clip_path
            needs_drone = (
                drone_clips
                and segments
                and (
                    (target_duration_seconds is None and starts_new_clip)
                    or (target_duration_seconds is not None and day_index > 0 and first_for_day)
                )
            )
            if needs_drone:
                drone_clip = drone_clips[drone_index % len(drone_clips)]
                drone_index += 1
                drone_duration = min(style.transition_seconds, drone_clip.duration_seconds)
                if drone_duration > 0:
                    segments.append(
                        TimelineSegment(
                            clip=drone_clip,
                            source_in=0.0,
                            source_out=drone_duration,
                            record_in=record_cursor,
                            record_out=record_cursor + drone_duration,
                            day=day,
                            role="drone_transition",
                        )
                    )
                    record_cursor += drone_duration

            duration = source_out - source_in
            segments.append(
                TimelineSegment(
                    clip=clip,
                    source_in=source_in,
                    source_out=source_out,
                    record_in=record_cursor,
                    record_out=record_cursor + duration,
                    day=day,
                    role="main",
                    marker=f"Jour {day.isoformat()}" if first_for_day else None,
                )
            )
            first_for_day = False
            previous_clip_path = clip.path
            record_cursor += duration

    if target_duration_seconds is not None and record_cursor < target_duration_seconds - 1.0:
        warnings.append(
            f"Duree cible de {target_duration_seconds:.1f}s non atteinte: "
            f"{record_cursor:.1f}s de rushs exploitables"
        )

    return TimelinePlan(
        name=f"Auto Resolve {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        fps=fps,
        segments=segments,
        warnings=_dedupe(warnings),
        source_dir=source_dir,
        style_path=style_path,
        output_dir=output_dir,
        target_duration_seconds=target_duration_seconds,
    )


def _select_for_target(
    candidates_by_day: Dict[object, List[tuple[ClipInfo, float, float]]],
    target_duration_seconds: float,
    max_segment_seconds: float,
    min_segment_seconds: float,
    drone_clips: List[ClipInfo],
    transition_seconds: float,
) -> Dict[object, List[tuple[ClipInfo, float, float]]]:
    days = [day for day in sorted(candidates_by_day) if candidates_by_day[day]]
    transition_budget = 0.0
    if drone_clips and len(days) > 1:
        for index in range(len(days) - 1):
            drone_clip = drone_clips[index % len(drone_clips)]
            transition_budget += min(transition_seconds, drone_clip.duration_seconds)

    main_budget = max(0.0, target_duration_seconds - transition_budget)
    capacities = {
        day: sum(source_out - source_in for _, source_in, source_out in candidates_by_day[day])
        for day in days
    }
    day_budgets = _balanced_budgets(capacities, main_budget)
    return {
        day: _select_evenly_spaced_ranges(
            candidates_by_day[day],
            day_budgets.get(day, 0.0),
            max_segment_seconds,
            min_segment_seconds,
        )
        for day in days
    }


def _balanced_budgets(capacities: Dict[object, float], total_budget: float) -> Dict[object, float]:
    budgets = {key: 0.0 for key in capacities}
    remaining = min(max(0.0, total_budget), sum(capacities.values()))
    active = list(capacities)

    while active and remaining > 0.001:
        share = remaining / len(active)
        saturated = [key for key in active if capacities[key] - budgets[key] <= share + 0.001]
        if not saturated:
            for key in active:
                budgets[key] += share
            break
        for key in saturated:
            available = capacities[key] - budgets[key]
            budgets[key] += available
            remaining -= available
            active.remove(key)

    return budgets


def _select_evenly_spaced_ranges(
    candidates: List[tuple[ClipInfo, float, float]],
    budget: float,
    max_segment_seconds: float,
    min_segment_seconds: float,
) -> List[tuple[ClipInfo, float, float]]:
    if not candidates or budget <= 0:
        return []

    total_duration = sum(source_out - source_in for _, source_in, source_out in candidates)
    if budget >= total_duration - 0.001:
        return candidates

    eligible = [
        candidate
        for candidate in candidates
        if candidate[2] - candidate[1] >= min_segment_seconds
    ]
    if not eligible or sum(source_out - source_in for _, source_in, source_out in eligible) < budget:
        eligible = candidates

    count = min(len(eligible), max(1, ceil(budget / max_segment_seconds)))
    while count < len(eligible):
        selected = [eligible[index] for index in _evenly_spaced_indices(len(eligible), count)]
        if sum(source_out - source_in for _, source_in, source_out in selected) >= budget:
            break
        count += 1

    selected = [eligible[index] for index in _evenly_spaced_indices(len(eligible), count)]
    allocations = _equal_allocations(
        [source_out - source_in for _, source_in, source_out in selected],
        min(budget, sum(source_out - source_in for _, source_in, source_out in selected)),
    )

    fitted: List[tuple[ClipInfo, float, float]] = []
    for (clip, source_in, source_out), duration in zip(selected, allocations):
        available = source_out - source_in
        trim = max(0.0, (available - duration) / 2.0)
        fitted_in = source_in + trim
        fitted.append((clip, fitted_in, fitted_in + duration))
    return fitted


def _evenly_spaced_indices(length: int, count: int) -> List[int]:
    return [min(length - 1, int((index + 0.5) * length / count)) for index in range(count)]


def _equal_allocations(capacities: List[float], total: float) -> List[float]:
    allocations = [0.0] * len(capacities)
    remaining = total
    active = list(range(len(capacities)))

    while active and remaining > 0.001:
        share = remaining / len(active)
        saturated = [index for index in active if capacities[index] <= share + 0.001]
        if not saturated:
            for index in active:
                allocations[index] = share
            break
        for index in saturated:
            allocations[index] = capacities[index]
            remaining -= capacities[index]
            active.remove(index)

    return allocations


def _segment_ranges(
    duration: float,
    max_segment_seconds: float,
    min_segment_seconds: float,
    beats: List[float],
    beat_snap_window: float,
) -> Iterable[tuple[float, float]]:
    source_in = 0.0
    while source_in < duration - 0.001:
        target_out = min(duration, source_in + max_segment_seconds)
        if target_out < duration:
            snapped = nearest_beat(beats, target_out, beat_snap_window)
            if source_in + min_segment_seconds <= snapped <= duration:
                target_out = snapped
        if target_out <= source_in:
            target_out = min(duration, source_in + max_segment_seconds)
        yield source_in, target_out
        source_in = target_out


def _group_by_day(clips: Iterable[ClipInfo]) -> Dict[object, List[ClipInfo]]:
    grouped: Dict[object, List[ClipInfo]] = defaultdict(list)
    for clip in clips:
        grouped[clip.day].append(clip)
    return grouped


def _choose_fps(style: StyleConfig, clips: List[ClipInfo]) -> int:
    for clip in clips:
        if clip.fps:
            rounded = int(round(clip.fps))
            if rounded > 0:
                return rounded
    return style.fps


def _safe_stem(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "_" for character in value)


def _progress(progress: Optional[ProgressCallback], fraction: float, message: str) -> None:
    if progress:
        progress(max(0.0, min(1.0, fraction)), message)


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    deduped = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
