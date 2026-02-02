from __future__ import annotations

import argparse
import json
import os
from typing import List, Tuple

from sf2_to_opxy.audio import write_wav
from sf2_to_opxy.converter import apply_loop_end_offset
from sf2_to_opxy.preview import render_loop_preview
from sf2_to_opxy.sf2_reader import extract_presets, read_soundfont


def _match_name(value: str) -> str:
    return value.replace("_", " ").strip().lower()


def _select_zone(zones: List[dict]) -> dict:
    if len(zones) == 1:
        return zones[0]
    target = 60
    return min(zones, key=lambda z: abs(int(z.get("root_key", target)) - target))


def _parse_offsets(value: str) -> List[int]:
    offsets = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not offsets:
        raise argparse.ArgumentTypeError("offsets must not be empty")
    return offsets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render loop preview WAVs for a preset")
    parser.add_argument("--sf2", required=True, help="Path to SF2 file")
    parser.add_argument("--preset", required=True, help="Preset name (case-insensitive)")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--iterations", type=int, default=6, help="Loop iterations to render")
    parser.add_argument("--tail-frames", type=int, default=2, help="Frames to include after loop")
    parser.add_argument(
        "--offsets",
        type=_parse_offsets,
        default="-1,0,1",
        help="Comma-separated loop-end offsets (default: -1,0,1)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    sf2 = read_soundfont(args.sf2)
    presets, _ = extract_presets(sf2)

    desired = _match_name(args.preset)
    preset = None
    for item in presets:
        if _match_name(item["name"]) == desired:
            preset = item
            break
    if preset is None:
        raise SystemExit(f"Preset not found: {args.preset}")

    zone = _select_zone(preset["zones"])
    sample = zone["sample"]
    pcm = sample["data"]
    channels = int(sample.get("channels", 1))
    sample_rate = int(sample.get("rate", 22050))
    loop_start = int(zone.get("loop_start", 0))
    loop_end = int(zone.get("loop_end", 0))
    loop_enabled = bool(zone.get("loop_enabled", False))

    os.makedirs(args.out, exist_ok=True)
    framecount = len(pcm) // channels

    outputs: List[Tuple[int, str, int]] = []

    if not loop_enabled or loop_end <= loop_start:
        raise SystemExit("Preset does not contain a valid loop")

    for offset in args.offsets:
        adjusted_end = apply_loop_end_offset(loop_start, loop_end, framecount, offset)
        preview_pcm = render_loop_preview(
            pcm,
            channels,
            loop_start,
            adjusted_end,
            args.iterations,
            tail_frames=args.tail_frames,
        )
        filename = f"{_match_name(preset['name']).replace(' ', '_')}_loop_end_{offset:+d}.wav"
        out_path = os.path.join(args.out, filename)
        wav_bytes = write_wav(preview_pcm, sample_rate, channels, 16)
        with open(out_path, "wb") as handle:
            handle.write(wav_bytes)
        outputs.append((offset, filename, adjusted_end))

    manifest = {
        "preset": preset["name"],
        "sample": sample.get("name"),
        "channels": channels,
        "sample_rate": sample_rate,
        "framecount": framecount,
        "loop_start": loop_start,
        "loop_end": loop_end,
        "iterations": args.iterations,
        "tail_frames": args.tail_frames,
        "outputs": [
            {"offset": offset, "file": filename, "loop_end": adjusted_end}
            for offset, filename, adjusted_end in outputs
        ],
    }
    manifest_path = os.path.join(args.out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
