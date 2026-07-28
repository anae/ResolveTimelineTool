from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Tuple

from .models import StyleConfig


_DEFAULT_DRONE_KEYWORDS = ("drone", "dji", "mavic", "aerial", "air", "fpv")


def read_style(path: Path) -> StyleConfig:
    """Read a Markdown style file and extract practical timeline hints.

    The parser intentionally accepts informal notes. It also understands simple
    key/value lines such as:

    - fps: 25
    - transition drone: 4s
    - mots-cles drone: DJI, drone, aerial
    - sans beat sync
    """

    text = path.read_text(encoding="utf-8")
    lowered = text.lower()

    drone_keywords = _extract_keywords(lowered, ("drone", "dji", "aerien", "aérien"))
    if any(anchor in lowered for anchor in ("drone", "dji", "mavic", "fpv")):
        drone_keywords = tuple(sorted(set(drone_keywords).union(_DEFAULT_DRONE_KEYWORDS)))
    skip_keywords = _extract_keywords(lowered, ("skip", "ignorer", "exclure"))

    transition_seconds = _extract_duration(
        lowered,
        patterns=(
            r"(?:transition|drone|plan drone|plans drone)[^\n]{0,50}?(\d+(?:[\.,]\d+)?)\s*(?:s|sec|secondes?)",
            r"(\d+(?:[\.,]\d+)?)\s*(?:s|sec|secondes?)[^\n]{0,50}?(?:transition|drone|plan drone|plans drone)",
        ),
        default=3.0,
    )
    min_segment_seconds = _extract_duration(
        lowered,
        patterns=(
            r"(?:minimum|min)[^\n]{0,50}?(?:segment|cut|plan)[^\n]{0,50}?(\d+(?:[\.,]\d+)?)\s*(?:s|sec|secondes?)",
            r"(\d+(?:[\.,]\d+)?)\s*(?:s|sec|secondes?)[^\n]{0,50}?(?:minimum|min)[^\n]{0,50}?(?:segment|cut|plan)",
        ),
        default=2.0,
    )
    fallback_clip_seconds = _extract_duration(
        lowered,
        patterns=(
            r"(?:defaut|défaut|fallback)[^\n]{0,50}?(?:clip|rush)[^\n]{0,50}?(\d+(?:[\.,]\d+)?)\s*(?:s|sec|secondes?)",
        ),
        default=8.0,
    )

    fps = int(
        _extract_number(
            lowered,
            patterns=(
                r"(\d+(?:[\.,]\d+)?)\s*(?:fps|ips|images\s*/\s*s|images par seconde)",
                r"(?:fps|ips)[^\n]{0,20}?(\d+(?:[\.,]\d+)?)",
            ),
            default=25,
        )
    )

    beat_sync_enabled = not any(
        phrase in lowered
        for phrase in (
            "sans beat",
            "pas de beat",
            "beat sync off",
            "desactiver beat",
            "désactiver beat",
        )
    )

    beat_snap_window_seconds = _extract_duration(
        lowered,
        patterns=(
            r"(?:beat|rythme)[^\n]{0,50}?(?:fenetre|fenêtre|window|tolerance|tolérance)[^\n]{0,50}?(\d+(?:[\.,]\d+)?)\s*(?:s|sec|secondes?)",
            r"(?:fenetre|fenêtre|window|tolerance|tolérance)[^\n]{0,50}?(?:beat|rythme)[^\n]{0,50}?(\d+(?:[\.,]\d+)?)\s*(?:s|sec|secondes?)",
        ),
        default=0.35,
    )

    return StyleConfig(
        drone_keywords=drone_keywords or _DEFAULT_DRONE_KEYWORDS,
        skip_keywords=skip_keywords,
        transition_seconds=max(0.5, transition_seconds),
        beat_sync_enabled=beat_sync_enabled,
        beat_snap_window_seconds=max(0.05, beat_snap_window_seconds),
        min_segment_seconds=max(0.5, min_segment_seconds),
        fallback_clip_seconds=max(1.0, fallback_clip_seconds),
        fps=max(1, fps),
    )


def _extract_keywords(text: str, anchors: Iterable[str]) -> Tuple[str, ...]:
    keywords = set()

    for line in text.splitlines():
        normalized = line.strip().lower()
        if not normalized:
            continue
        if not any(anchor in normalized for anchor in anchors):
            continue
        if ":" in normalized:
            _, value = normalized.split(":", 1)
            for item in re.split(r"[,;/|]", value):
                cleaned = _clean_keyword(item)
                if cleaned:
                    keywords.add(cleaned)

    return tuple(sorted(keywords))


def _clean_keyword(value: str) -> str:
    value = re.sub(r"[*`#\-\[\]\(\)]", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()
    if len(value) < 2:
        return ""
    if re.fullmatch(r"\d+(?:[\.,]\d+)?\s*(?:s|sec|secondes?)?", value):
        return ""
    if len(value.split()) > 4:
        return ""
    return value


def _extract_duration(text: str, patterns: Iterable[str], default: float) -> float:
    return _extract_number(text, patterns, default)


def _extract_number(text: str, patterns: Iterable[str], default: float) -> float:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                continue
    return default
