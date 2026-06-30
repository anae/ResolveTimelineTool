from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from statistics import mean, pstdev
from typing import List


def detect_beats(path: Path, max_seconds: float) -> List[float]:
    """Return rough audio-energy beat candidates in seconds.

    This is deliberately lightweight. If ffmpeg is unavailable or the clip has
    no readable audio, an empty list is returned and the timeline remains valid.
    """

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or max_seconds <= 0:
        return []

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp:
        cmd = [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-i",
            str(path),
            "-t",
            f"{max_seconds:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "11025",
            "-f",
            "wav",
            temp.name,
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return _read_energy_peaks(Path(temp.name))
        except (subprocess.CalledProcessError, wave.Error, OSError):
            return []


def nearest_beat(beats: List[float], target: float, window: float) -> float:
    if not beats:
        return target
    nearest = min(beats, key=lambda value: abs(value - target))
    if abs(nearest - target) <= window:
        return nearest
    return target


def _read_energy_peaks(wav_path: Path) -> List[float]:
    with wave.open(str(wav_path), "rb") as wav:
        frame_rate = wav.getframerate()
        sample_width = wav.getsampwidth()
        frame_count = wav.getnframes()
        frames = wav.readframes(frame_count)

    if sample_width != 2 or frame_rate <= 0:
        return []

    samples = [
        int.from_bytes(frames[index : index + 2], byteorder="little", signed=True)
        for index in range(0, len(frames), 2)
    ]
    window_size = max(1, int(frame_rate * 0.05))
    energies = []
    for index in range(0, len(samples), window_size):
        window = samples[index : index + window_size]
        if not window:
            continue
        rms = math.sqrt(sum(sample * sample for sample in window) / len(window))
        energies.append(rms)

    if len(energies) < 5:
        return []

    threshold = mean(energies) + (pstdev(energies) * 0.8)
    peaks: List[float] = []
    last_peak = -1.0
    for index in range(1, len(energies) - 1):
        value = energies[index]
        if value < threshold:
            continue
        if value < energies[index - 1] or value < energies[index + 1]:
            continue
        seconds = index * window_size / frame_rate
        if seconds - last_peak < 0.25:
            continue
        peaks.append(seconds)
        last_peak = seconds

    return peaks
