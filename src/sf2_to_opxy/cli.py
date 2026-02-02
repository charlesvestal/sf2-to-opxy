import argparse
import json
import os
from typing import List

from sf2_to_opxy.converter import convert_presets
from sf2_to_opxy.sf2_reader import extract_presets, read_soundfont


def _parse_velocities(value: str) -> List[int]:
    velocities = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not velocities:
        raise argparse.ArgumentTypeError("velocities must not be empty")
    return velocities


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SF2 to OP-XY converter")
    parser.add_argument("sf2", help="Path to .sf2")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--velocities", default="101", type=_parse_velocities, help="Comma-separated velocities")
    parser.add_argument("--velocity-mode", choices=["keep", "split"], default="keep")
    parser.add_argument("--resample-rate", type=int, default=22050)
    parser.add_argument("--bit-depth", type=int, default=16)
    parser.add_argument("--no-resample", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    sf2 = read_soundfont(args.sf2)
    presets, parse_log = extract_presets(sf2)

    log = convert_presets(
        presets,
        args.out,
        args.velocities,
        args.velocity_mode,
        args.resample_rate,
        args.bit_depth,
        resample=not args.no_resample,
    )
    log["parse_warnings"] = parse_log

    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, "conversion-log.json")
    with open(log_path, "w", encoding="utf-8") as handle:
        json.dump(log, handle, indent=2)

    text_log_path = os.path.join(args.out, "conversion-log.txt")
    with open(text_log_path, "w", encoding="utf-8") as handle:
        handle.write(f"Presets converted: {len(log.get('presets', []))}\n")
        handle.write(f"Discarded zones: {len(log.get('discarded', []))}\n")
        handle.write("\nDiscarded entries:\n")
        for entry in log.get("discarded", []):
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        handle.write("\nWarnings:\n")
        for entry in log.get("warnings", []):
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        handle.write("\nParse warnings:\n")
        for entry in log.get("parse_warnings", {}).get("warnings", []):
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        handle.write("\nParse skipped zones:\n")
        for entry in log.get("parse_warnings", {}).get("skipped_zones", []):
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return 0
