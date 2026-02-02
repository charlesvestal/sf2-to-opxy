#!/usr/bin/env python3
"""Generate OP-XY calibration presets for envelope validation."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import List, Tuple

from sf2_to_opxy.opxy_writer import write_multisample_preset


DEFAULT_VALUES = [
    0,
    256,
    512,
    1024,
    2048,
    4096,
    8192,
    12288,
    16384,
    20480,
    24576,
    28672,
    32767,
]


def _parse_values(raw: str) -> List[int]:
    if not raw:
        return DEFAULT_VALUES
    values = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.append(int(chunk))
    if not values:
        return DEFAULT_VALUES
    return values


def _sanitize(name: str) -> str:
    out = []
    for ch in name:
        if ch.isalnum() or ch in ("_", "-"):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_") or "preset"


def _generate_sine(sample_rate: int, freq: float, duration: float, amplitude: float) -> Tuple[List[int], float]:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be > 0")
    if freq <= 0:
        raise ValueError("freq must be > 0")
    if duration <= 0:
        raise ValueError("duration must be > 0")
    if amplitude <= 0 or amplitude > 1.0:
        raise ValueError("amplitude must be in (0, 1]")

    samples_per_cycle = int(round(sample_rate / freq))
    if samples_per_cycle <= 0:
        samples_per_cycle = 1
    actual_freq = sample_rate / samples_per_cycle

    total_frames = int(round(sample_rate * duration))
    if total_frames < samples_per_cycle:
        total_frames = samples_per_cycle
    total_frames = (total_frames // samples_per_cycle) * samples_per_cycle
    if total_frames <= 0:
        total_frames = samples_per_cycle

    pcm: List[int] = []
    for i in range(total_frames):
        value = math.sin(2.0 * math.pi * actual_freq * (i / sample_rate))
        pcm.append(int(round(value * amplitude * 32767)))
    return pcm, actual_freq


def _generate_noise(sample_rate: int, duration: float, amplitude: float) -> List[int]:
    import random

    if sample_rate <= 0:
        raise ValueError("sample_rate must be > 0")
    if duration <= 0:
        raise ValueError("duration must be > 0")
    if amplitude <= 0 or amplitude > 1.0:
        raise ValueError("amplitude must be in (0, 1]")

    total_frames = int(round(sample_rate * duration))
    if total_frames <= 0:
        total_frames = 1
    pcm: List[int] = []
    for _ in range(total_frames):
        value = random.uniform(-1.0, 1.0)
        pcm.append(int(round(value * amplitude * 32767)))
    return pcm


def _build_region(pcm: List[int], sample_rate: int) -> dict:
    framecount = len(pcm)
    return {
        "sample": "calibration.wav",
        "pcm": pcm,
        "sample_rate": sample_rate,
        "channels": 1,
        "root_key": 60,
        "loop_start": 0,
        "loop_end": framecount,
        "loop_enabled": True,
        "loop_on_release": False,
        "framecount": framecount,
        "lokey": 21,
        "hikey": 108,
        "tune": 0,
        "gain": 0,
    }


def _write_preset(out_dir: Path, name: str, envelope: dict, region: dict) -> None:
    write_multisample_preset(
        {
            "name": name,
            "regions": [region],
            "envelope": {"amp": envelope, "filter": {"attack": 0, "decay": 0, "sustain": 32767, "release": 0}},
            "fx": {"delay_send": 0, "reverb_send": 0},
            "playmode": "poly",
        },
        str(out_dir / name),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OP-XY calibration presets.")
    parser.add_argument("--out", required=True, help="Output folder for calibration presets")
    parser.add_argument("--values", default="", help="Comma-separated ADSR values (0-32767)")
    parser.add_argument("--sample-rate", type=int, default=22050, help="Sample rate for the calibration tone")
    parser.add_argument("--duration", type=float, default=1.0, help="Sample duration in seconds")
    parser.add_argument("--amplitude", type=float, default=0.8, help="Tone amplitude (0-1)")
    parser.add_argument("--wave", choices=["sine", "noise"], default="sine", help="Waveform for calibration")
    parser.add_argument("--frequency", type=float, default=441.0, help="Sine frequency (Hz)")
    parser.add_argument("--include-attack", action="store_true", help="Include attack test presets")
    parser.add_argument("--include-release", action="store_true", help="Include release test presets")
    parser.add_argument(
        "--release-loop-on",
        action="store_true",
        help="Enable loop-on-release for release presets (recommended for measuring release tails)",
    )
    parser.add_argument("--hold-seconds", type=float, default=1.0, help="Recommended hold time for release tests")

    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    values = _parse_values(args.values)
    if not args.include_attack and not args.include_release:
        args.include_attack = True
        args.include_release = True

    if args.wave == "sine":
        pcm, actual_freq = _generate_sine(args.sample_rate, args.frequency, args.duration, args.amplitude)
    else:
        pcm = _generate_noise(args.sample_rate, args.duration, args.amplitude)
        actual_freq = 0.0

    region = _build_region(pcm, args.sample_rate)

    manifest = {
        "sample_rate": args.sample_rate,
        "wave": args.wave,
        "frequency": actual_freq if args.wave == "sine" else None,
        "duration": args.duration,
        "amplitude": args.amplitude,
        "values": values,
        "order": [],
        "recommended_hold_seconds": args.hold_seconds,
        "notes": "Play each preset in order, record one WAV. Hold each note for the recommended hold time, then release and leave silence until the next hit.",
    }

    order_lines: List[str] = []
    for value in values:
        value = max(0, min(32767, value))
        if args.include_attack:
            name = _sanitize(f"Attack_{value:05d}")
            envelope = {"attack": value, "decay": 0, "sustain": 32767, "release": 32767}
            _write_preset(out_dir, name, envelope, region)
            manifest["order"].append({"type": "attack", "value": value, "preset": name})
            order_lines.append(f"attack {value} {name}")
        if args.include_release:
            name = _sanitize(f"Release_{value:05d}")
            envelope = {"attack": 0, "decay": 0, "sustain": 32767, "release": value}
            release_region = dict(region)
            if args.release_loop_on:
                release_region["loop_on_release"] = True
            _write_preset(out_dir, name, envelope, release_region)
            manifest["order"].append({"type": "release", "value": value, "preset": name})
            order_lines.append(f"release {value} {name}")

    manifest_path = out_dir / "calibration-manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    text_path = out_dir / "calibration-manifest.txt"
    with open(text_path, "w", encoding="utf-8") as handle:
        handle.write("# type value preset\n")
        handle.write("\n".join(order_lines))
        handle.write("\n")

    print(f"Wrote {len(manifest['order'])} presets to {out_dir}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
