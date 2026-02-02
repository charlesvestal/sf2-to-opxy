from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from sf2_to_opxy.loop_variants import make_offset_variants


def _parse_offsets(value: str) -> List[int]:
    offsets = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not offsets:
        raise argparse.ArgumentTypeError("offsets must not be empty")
    return offsets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clone a preset with multiple loop-end offsets")
    parser.add_argument("--preset", required=True, help="Path to a .preset directory")
    parser.add_argument("--offsets", default="-1,0,1", type=_parse_offsets)
    parser.add_argument(
        "--base-offset",
        type=int,
        default=0,
        help="Offset already applied to the source preset (default 0)",
    )
    parser.add_argument("--out", default="", help="Output directory (default: preset parent)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing presets")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    preset_dir = os.path.abspath(args.preset)
    if not os.path.isdir(preset_dir):
        raise SystemExit(f"Preset directory not found: {preset_dir}")

    patch_path = os.path.join(preset_dir, "patch.json")
    if not os.path.isfile(patch_path):
        raise SystemExit(f"patch.json not found in: {preset_dir}")

    with open(patch_path, "r", encoding="utf-8") as handle:
        patch = json.load(handle)

    offsets = args.offsets
    variants = make_offset_variants(patch, offsets, base_offset=args.base_offset)

    parent_dir = os.path.abspath(args.out) if args.out else os.path.dirname(preset_dir)
    os.makedirs(parent_dir, exist_ok=True)

    base_name = os.path.basename(preset_dir)
    if base_name.endswith(".preset"):
        base_name = base_name[: -len(".preset")]

    manifest = {
        "source": preset_dir,
        "base_offset": args.base_offset,
        "outputs": [],
    }

    for offset, variant in variants:
        suffix = f"_offset_{offset:+d}"
        target_dir = os.path.join(parent_dir, f"{base_name}{suffix}.preset")
        if os.path.exists(target_dir):
            if args.overwrite:
                shutil.rmtree(target_dir)
            else:
                raise SystemExit(f"Output exists: {target_dir} (use --overwrite)")
        shutil.copytree(preset_dir, target_dir)

        target_patch = os.path.join(target_dir, "patch.json")
        with open(target_patch, "w", encoding="utf-8") as handle:
            json.dump(variant, handle, indent=2)

        manifest["outputs"].append({"offset": offset, "preset": target_dir})

    manifest_path = os.path.join(parent_dir, f"{base_name}_offset_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
