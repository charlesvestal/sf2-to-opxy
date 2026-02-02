import argparse
import json
import os
import sys
from typing import List

from sf2_to_opxy.converter import convert_presets
from sf2_to_opxy.sf2_reader import extract_presets, read_soundfont


def _parse_velocities(value: str) -> List[int]:
    velocities = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not velocities:
        raise argparse.ArgumentTypeError("velocities must not be empty")
    return velocities


def _sanitize_name(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in ("_", "-", " "):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip().replace("  ", " ").replace(" ", "_") or "soundfont"


def _gather_sf2_paths(source: str, recursive: bool) -> List[str]:
    if os.path.isfile(source):
        return [source]
    if not os.path.isdir(source):
        raise FileNotFoundError(f"Input not found: {source}")

    paths: List[str] = []
    if recursive:
        for root, _, files in os.walk(source):
            for name in files:
                if name.lower().endswith(".sf2"):
                    paths.append(os.path.join(root, name))
    else:
        for name in os.listdir(source):
            if name.lower().endswith(".sf2"):
                paths.append(os.path.join(source, name))
    return sorted(paths)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SF2 to OP-XY converter")
    parser.add_argument("source", help="Path to .sf2 or a directory of .sf2 files")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--velocities", default="101", type=_parse_velocities, help="Comma-separated velocities")
    parser.add_argument("--velocity-mode", choices=["keep", "split"], default="keep")
    parser.add_argument("--resample-rate", type=int, default=22050)
    parser.add_argument("--bit-depth", type=int, default=16)
    parser.add_argument("--no-resample", action="store_true")
    parser.add_argument(
        "--zero-crossing",
        action="store_true",
        help="Enable loop zero-crossing snapping (default: off)",
    )
    parser.add_argument(
        "--no-zero-crossing",
        action="store_false",
        dest="zero_crossing",
        help="Disable loop zero-crossing snapping",
    )
    parser.set_defaults(zero_crossing=False)
    parser.add_argument("--recursive", action="store_true", help="Scan subdirectories for .sf2 files")
    parser.add_argument("--force-drum", action="store_true", help="Force all presets to drum kits")
    parser.add_argument("--force-instrument", action="store_true", help="Force all presets to instruments")
    parser.add_argument(
        "--loop-end-offset",
        type=int,
        default=0,
        help="Adjust loop end by this many frames (use -1 for FluidSynth-style end-exclusive loops)",
    )
    parser.add_argument(
        "--instrument-playmode",
        choices=["auto", "poly", "mono", "legato"],
        default="auto",
        help="Playmode for multisample presets",
    )
    parser.add_argument(
        "--drum-velocity-mode",
        choices=["closest", "strict"],
        default="closest",
        help="How to select drum zones for a target velocity",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    if args.force_drum and args.force_instrument:
        print("Cannot use --force-drum and --force-instrument together.", file=sys.stderr)
        return 2
    if args.force_drum:
        force_mode = "drum"
    elif args.force_instrument:
        force_mode = "instrument"
    else:
        force_mode = None

    sf2_paths = _gather_sf2_paths(args.source, args.recursive)
    if not sf2_paths:
        print(f"No .sf2 files found in {args.source}", file=sys.stderr)
        return 1

    os.makedirs(args.out, exist_ok=True)
    summary = []
    had_errors = False
    multi_source = len(sf2_paths) > 1 or os.path.isdir(args.source)

    for sf2_path in sf2_paths:
        base_name = _sanitize_name(os.path.splitext(os.path.basename(sf2_path))[0])
        out_dir = os.path.join(args.out, base_name) if multi_source else args.out
        os.makedirs(out_dir, exist_ok=True)

        try:
            sf2 = read_soundfont(sf2_path)
            presets, parse_log = extract_presets(sf2)

            log = convert_presets(
                presets,
                out_dir,
                args.velocities,
                args.velocity_mode,
                args.resample_rate,
                args.bit_depth,
                resample=not args.no_resample,
                force_mode=force_mode,
                instrument_playmode=args.instrument_playmode,
                drum_velocity_mode=args.drum_velocity_mode,
                zero_crossing=args.zero_crossing,
                loop_end_offset=args.loop_end_offset,
            )
            log["parse_warnings"] = parse_log
            log["source"] = sf2_path
            log["output"] = out_dir

            log_path = os.path.join(out_dir, "conversion-log.json")
            with open(log_path, "w", encoding="utf-8") as handle:
                json.dump(log, handle, indent=2)

            text_log_path = os.path.join(out_dir, "conversion-log.txt")
            with open(text_log_path, "w", encoding="utf-8") as handle:
                handle.write(f"Source: {sf2_path}\n")
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

            summary.append(
                {
                    "source": sf2_path,
                    "output": out_dir,
                    "presets": len(log.get("presets", [])),
                    "discarded": len(log.get("discarded", [])),
                }
            )
        except Exception as exc:
            had_errors = True
            summary.append({"source": sf2_path, "error": str(exc)})

    if len(summary) > 1:
        batch_path = os.path.join(args.out, "conversion-batch.json")
        with open(batch_path, "w", encoding="utf-8") as handle:
            json.dump({"inputs": summary}, handle, indent=2)

        batch_text = os.path.join(args.out, "conversion-batch.txt")
        with open(batch_text, "w", encoding="utf-8") as handle:
            for entry in summary:
                handle.write(json.dumps(entry, ensure_ascii=True) + "\n")

    return 1 if had_errors else 0
