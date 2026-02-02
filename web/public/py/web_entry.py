from __future__ import annotations

import json
import os
from typing import Any, Dict

from sf2_to_opxy.converter import convert_presets
from sf2_to_opxy.sf2_reader import extract_presets, read_soundfont


def _normalize_options(raw: str) -> Dict[str, Any]:
    payload = json.loads(raw) if raw else {}
    return {
        "velocities": payload.get("velocities", [101]),
        "velocity_mode": payload.get("velocityMode", "keep"),
        "resample_rate": int(payload.get("resampleRate", 22050)),
        "bit_depth": int(payload.get("bitDepth", 16)),
        "no_resample": bool(payload.get("noResample", False)),
        "zero_crossing": bool(payload.get("zeroCrossing", False)),
        "loop_end_offset": int(payload.get("loopEndOffset", 0)),
        "force_drum": bool(payload.get("forceDrum", False)),
        "force_instrument": bool(payload.get("forceInstrument", False)),
        "instrument_playmode": payload.get("instrumentPlaymode", "auto"),
        "drum_velocity_mode": payload.get("drumVelocityMode", "closest"),
    }


def run_conversion(sf2_path: str, out_dir: str, options_json: str) -> Dict[str, Any]:
    opts = _normalize_options(options_json)

    if opts["force_drum"] and opts["force_instrument"]:
        raise ValueError("Cannot force drum and instrument simultaneously")

    if opts["force_drum"]:
        force_mode = "drum"
    elif opts["force_instrument"]:
        force_mode = "instrument"
    else:
        force_mode = None

    sf2 = read_soundfont(sf2_path)
    presets, parse_log = extract_presets(sf2)

    os.makedirs(out_dir, exist_ok=True)
    log = convert_presets(
        presets,
        out_dir,
        opts["velocities"],
        opts["velocity_mode"],
        opts["resample_rate"],
        opts["bit_depth"],
        resample=not opts["no_resample"],
        force_mode=force_mode,
        instrument_playmode=opts["instrument_playmode"],
        drum_velocity_mode=opts["drum_velocity_mode"],
        zero_crossing=opts["zero_crossing"],
        loop_end_offset=opts["loop_end_offset"],
    )
    log["parse_warnings"] = parse_log
    return log
