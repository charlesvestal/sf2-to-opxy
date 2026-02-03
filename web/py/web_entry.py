"""Pyodide entry point for SF2 to OP-XY web converter."""

import json
import os
import sys

# Ensure our package is importable
sys.path.insert(0, "/py")


def run_conversion(sf2_path, out_dir, options_json, progress_callback=None):
    """Run the SF2 to OP-XY conversion and return output file paths.

    Args:
        sf2_path: Path to the uploaded SF2 file in Pyodide FS.
        out_dir: Directory for output files.
        options_json: JSON string with conversion options.
        progress_callback: callable(current, total, preset_name) for progress.

    Returns:
        dict with 'files' (list of output paths) and 'log' (conversion log).
    """
    from sf2_to_opxy.sf2_reader import read_soundfont, extract_presets
    from sf2_to_opxy.converter import convert_presets

    options = json.loads(options_json) if options_json else {}

    velocities = options.get("velocities", [101])
    velocity_mode = options.get("velocity_mode", "keep")
    resample_rate = options.get("resample_rate", 22050)
    bit_depth = options.get("bit_depth", 16)
    resample = options.get("resample", True)
    force_mode = options.get("force_mode", None)
    instrument_playmode = options.get("instrument_playmode", "auto")
    drum_velocity_mode = options.get("drum_velocity_mode", "closest")
    zero_crossing = options.get("zero_crossing", False)
    loop_end_offset = options.get("loop_end_offset", 0)
    loop_on_release = options.get("loop_on_release", "auto")

    os.makedirs(out_dir, exist_ok=True)

    sf2 = read_soundfont(sf2_path)
    presets, parse_log = extract_presets(sf2)

    log = convert_presets(
        presets,
        out_dir,
        velocities,
        velocity_mode,
        resample_rate,
        bit_depth,
        resample=resample,
        force_mode=force_mode,
        instrument_playmode=instrument_playmode,
        drum_velocity_mode=drum_velocity_mode,
        zero_crossing=zero_crossing,
        loop_end_offset=loop_end_offset,
        loop_on_release=loop_on_release,
        progress_callback=progress_callback,
    )
    log["parse_warnings"] = parse_log

    # Collect output files
    output_files = []
    for root, _dirs, files in os.walk(out_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, out_dir)
            output_files.append(rel)

    # Write conversion log
    log_path = os.path.join(out_dir, "conversion-log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    if "conversion-log.json" not in output_files:
        output_files.append("conversion-log.json")

    return {"files": sorted(output_files), "log": log}
