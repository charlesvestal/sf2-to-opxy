#!/usr/bin/env python3
"""Analyze a single WAV recording containing ordered envelope calibration hits."""
from __future__ import annotations

import argparse
import json
import math
import os
import wave
from pathlib import Path
from typing import List, Tuple

import numpy as np


def _read_wav(path: str) -> Tuple[np.ndarray, int]:
    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()
        raw = wf.readframes(frames)

    if sample_width == 2:
        data = np.frombuffer(raw, dtype="<i2")
        max_val = float(np.iinfo(np.int16).max)
    elif sample_width == 3:
        raw_u8 = np.frombuffer(raw, dtype=np.uint8)
        if len(raw_u8) % 3 != 0:
            raise ValueError("24-bit PCM data is not aligned")
        raw_u8 = raw_u8.reshape(-1, 3)
        data = (
            raw_u8[:, 0].astype(np.int32)
            | (raw_u8[:, 1].astype(np.int32) << 8)
            | (raw_u8[:, 2].astype(np.int32) << 16)
        )
        mask = 1 << 23
        data = (data ^ mask) - mask
        max_val = float(2 ** 23 - 1)
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype="<i4")
        max_val = float(np.iinfo(np.int32).max)
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    else:
        data = data.astype(np.float32)
    data = data.astype(np.float32) / max_val
    return data, sample_rate


def _compute_rms(signal: np.ndarray, sample_rate: int, window_ms: float, hop_ms: float) -> Tuple[np.ndarray, np.ndarray]:
    window = max(1, int(round(sample_rate * window_ms / 1000.0)))
    hop = max(1, int(round(sample_rate * hop_ms / 1000.0)))
    if len(signal) < window:
        raise ValueError("WAV too short for RMS window")
    frames = 1 + (len(signal) - window) // hop
    shape = (frames, window)
    strides = (signal.strides[0] * hop, signal.strides[0])
    windows = np.lib.stride_tricks.as_strided(signal, shape=shape, strides=strides)
    rms = np.sqrt(np.mean(windows ** 2, axis=1))
    times = (np.arange(frames) * hop) / float(sample_rate)
    return times, rms


def _detect_onsets(times: np.ndarray, rms: np.ndarray, threshold_db: float, min_gap: float) -> List[float]:
    threshold = 10 ** (threshold_db / 20.0)
    above = rms >= threshold
    onsets: List[float] = []
    for idx in range(1, len(above)):
        if above[idx] and not above[idx - 1]:
            t = float(times[idx])
            if not onsets or t - onsets[-1] >= min_gap:
                onsets.append(t)
    return onsets


def _first_crossing(times: np.ndarray, rms: np.ndarray, start_idx: int, threshold: float) -> float | None:
    for idx in range(start_idx, len(rms)):
        if rms[idx] >= threshold:
            return float(times[idx])
    return None


def _first_fall(times: np.ndarray, rms: np.ndarray, start_idx: int, threshold: float) -> float | None:
    for idx in range(start_idx, len(rms)):
        if rms[idx] <= threshold:
            return float(times[idx])
    return None


def _measure_attack(
    times: np.ndarray,
    rms: np.ndarray,
    onset: float,
    peak_window: float,
    segment_end: float | None = None,
) -> dict | None:
    onset_idx = int(np.searchsorted(times, onset, side="left"))
    if segment_end is not None:
        end_time = segment_end
    else:
        end_time = onset + peak_window
    end_idx = int(np.searchsorted(times, end_time, side="left"))
    if end_idx <= onset_idx + 1:
        return None
    local = rms[onset_idx:end_idx]
    peak = float(local.max())
    if peak <= 0:
        return None
    t10 = _first_crossing(times, rms, onset_idx, peak * 0.1)
    t90 = _first_crossing(times, rms, onset_idx, peak * 0.9)
    if t10 is None or t90 is None:
        return None
    return {
        "attack_seconds": max(0.0, t90 - t10),
        "peak": peak,
        "t10": t10,
        "t90": t90,
    }


def _measure_release(
    times: np.ndarray,
    rms: np.ndarray,
    onset: float,
    hold_seconds: float,
    release_db: float,
    release_ratio: float,
    release_window: float,
) -> dict | None:
    onset_idx = int(np.searchsorted(times, onset, side="left"))
    release_start = onset + hold_seconds
    release_idx = int(np.searchsorted(times, release_start, side="left"))
    if release_idx <= onset_idx:
        return None
    pre_peak = float(rms[onset_idx:release_idx].max())
    if pre_peak <= 0:
        return None
    floor = 10 ** (release_db / 20.0)
    target = max(pre_peak * release_ratio, floor)
    end_time = release_start + release_window
    end_idx = int(np.searchsorted(times, end_time, side="left"))
    end_idx = min(end_idx, len(rms))
    if end_idx <= release_idx:
        return None
    fall = _first_fall(times[:end_idx], rms[:end_idx], release_idx, target)
    if fall is None:
        return None
    return {
        "release_seconds": max(0.0, fall - release_start),
        "pre_release_peak": pre_peak,
        "target": target,
        "release_start": release_start,
        "release_end": fall,
    }


def _load_manifest(path: str) -> List[dict]:
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        return list(manifest.get("order", []))
    order: List[dict] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            order.append({"type": parts[0], "value": int(parts[1]), "preset": parts[2]})
    return order


def _fit_attack(values: List[int], times: List[float]) -> dict | None:
    filtered = [(v, t) for v, t in zip(values, times) if t > 0]
    if len(filtered) < 3:
        return None
    x = np.array([v / 32767.0 for v, _ in filtered], dtype=np.float64)
    y = np.array([t for _, t in filtered], dtype=np.float64)
    coeff = np.polyfit(x, np.log(y), 1)
    b = float(coeff[0])
    a = float(math.exp(coeff[1]))
    return {"model": "t = a * exp(b*x)", "a": a, "b": b}


def _fit_release(values: List[int], times: List[float]) -> dict | None:
    filtered = [(v, t) for v, t in zip(values, times) if t > 0 and v < 32767]
    if len(filtered) < 3:
        return None
    x = np.array([1.0 - v / 32767.0 for v, _ in filtered], dtype=np.float64)
    y = np.array([t for _, t in filtered], dtype=np.float64)
    coeff = np.polyfit(np.log(x), np.log(y), 1)
    p = float(coeff[0])
    max_seconds = float(math.exp(coeff[1]))
    return {"model": "t = max * (1 - x) ** p", "max": max_seconds, "p": p}


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a WAV with ordered OP-XY envelope tests.")
    parser.add_argument("--wav", required=True, help="Path to a recorded WAV")
    parser.add_argument("--manifest", required=True, help="Calibration manifest JSON or TXT")
    parser.add_argument("--out", default="", help="Optional output JSON path")
    parser.add_argument("--hold-seconds", type=float, default=1.0, help="Hold time before release (seconds)")
    parser.add_argument("--threshold-db", type=float, default=-35.0, help="Onset detection threshold (dBFS)")
    parser.add_argument("--min-gap", type=float, default=0.3, help="Minimum seconds between onsets")
    parser.add_argument("--window-ms", type=float, default=10.0, help="RMS window size (ms)")
    parser.add_argument("--hop-ms", type=float, default=5.0, help="RMS hop size (ms)")
    parser.add_argument("--peak-window", type=float, default=3.0, help="Attack peak search window (seconds)")
    parser.add_argument("--release-window", type=float, default=60.0, help="Release search window (seconds)")
    parser.add_argument("--release-db", type=float, default=-60.0, help="Release target floor (dBFS)")
    parser.add_argument("--release-ratio", type=float, default=0.1, help="Release target ratio of pre-peak")
    args = parser.parse_args()

    order = _load_manifest(args.manifest)
    if not order:
        raise SystemExit("No entries found in manifest")

    signal, sample_rate = _read_wav(args.wav)
    times, rms = _compute_rms(signal, sample_rate, args.window_ms, args.hop_ms)
    onsets = _detect_onsets(times, rms, args.threshold_db, args.min_gap)

    count = min(len(order), len(onsets))
    if count == 0:
        raise SystemExit("No onsets detected")

    results: List[dict] = []
    for idx in range(count):
        entry = order[idx]
        onset = onsets[idx]
        segment_end = onsets[idx + 1] if idx + 1 < count else times[-1]
        result = {
            "index": idx,
            "type": entry.get("type"),
            "value": int(entry.get("value", 0)),
            "preset": entry.get("preset"),
            "onset": onset,
        }
        if entry.get("type") == "attack":
            measurement = _measure_attack(times, rms, onset, args.peak_window, segment_end=segment_end)
            if measurement:
                result.update(measurement)
        elif entry.get("type") == "release":
            measurement = _measure_release(
                times,
                rms,
                onset,
                args.hold_seconds,
                args.release_db,
                args.release_ratio,
                args.release_window,
            )
            if measurement:
                result.update(measurement)
        results.append(result)

    attack_vals = [r["value"] for r in results if r.get("type") == "attack" and "attack_seconds" in r]
    attack_times = [r["attack_seconds"] for r in results if r.get("type") == "attack" and "attack_seconds" in r]
    release_vals = [r["value"] for r in results if r.get("type") == "release" and "release_seconds" in r]
    release_times = [r["release_seconds"] for r in results if r.get("type") == "release" and "release_seconds" in r]

    fit = {
        "attack": _fit_attack(attack_vals, attack_times),
        "release": _fit_release(release_vals, release_times),
    }

    output = {
        "wav": os.path.abspath(args.wav),
        "manifest": os.path.abspath(args.manifest),
        "sample_rate": sample_rate,
        "onsets_detected": len(onsets),
        "entries_used": count,
        "results": results,
        "fit": fit,
    }

    out_path = args.out
    if not out_path:
        wav_path = Path(args.wav)
        out_path = str(wav_path.with_suffix(".analysis.json"))
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)

    print(f"Detected onsets: {len(onsets)}")
    print(f"Used entries: {count}")
    print(f"Wrote analysis: {out_path}")
    if fit["attack"]:
        print(f"Attack fit: {fit['attack']}")
    if fit["release"]:
        print(f"Release fit: {fit['release']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
