# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python utility that converts SoundFont 2 (.sf2) instruments and drum kits into OP-XY synthesizer multisample and drum presets. Handles zone selection, envelope mapping, loop points, FX sends, and audio resampling.

## Commands

```bash
# Run the converter
python3 sf2_to_opxy.py <source.sf2> --out <output_dir>

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_converter.py

# Run a specific test
pytest tests/test_envelope.py::test_timecents_to_seconds -v

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Architecture

**Data flow:** SF2 file → `sf2_reader` (parse/decode) → `converter` (transform) → `opxy_writer` (output JSON + WAVs)

### Source Modules (`src/sf2_to_opxy/`)

- **cli.py** — CLI argument parsing and orchestration. Entry point calls `build_parser()` then `run(args)`.
- **sf2_reader.py** — Reads SF2 files via `sf2utils`, decodes PCM samples (16/24-bit), extracts generators/envelopes/modulators, detects drum kits (bank 128 or name heuristics).
- **converter.py** — Core conversion logic. Maps SF2 timecent envelopes to OP-XY's 0–32767 range using calibrated exponential/power curves. Handles zero-crossing snapping, loop-end offsets, loop-on-release override, FX send mapping. Waveforms are preserved unmodified from the SF2 source.
- **opxy_writer.py** — Contains `BASE_MULTISAMPLE` and `BASE_DRUM` JSON templates. Writes final `.preset` files with region arrays.
- **selection.py** — Zone filtering by velocity, downsampling >24 zones to 24 (evenly distributed across A0–C8), key range assignment.
- **audio.py** — Linear interpolation resampling and WAV writing.
- **loop_variants.py** — Generates preset variants with different loop-end offsets.
- **preview.py** — Renders looped WAV previews for testing loop points.

### Tools (`tools/`)

Standalone scripts for envelope calibration and loop analysis. `generate_calibration_presets.py` creates test presets, `analyze_envelope.py` measures recorded results against expected values.

## Key Domain Concepts

- **Timecents:** SF2 time unit where 0 = 1 second, 1200 = 2 seconds (logarithmic: `2^(tc/1200)`).
- **Zone limit:** OP-XY supports max 24 zones per preset. Zones beyond 24 are downsampled by even distribution across A0–C8.
- **Loop-end offset:** SF2 uses inclusive loop-end; `--loop-end-offset -1` converts to exclusive semantics for FluidSynth compatibility.
- **Loop on release:** SF2 sample mode bit 0x2 indicates looping continues during note release. Exposed as `--loop-on-release auto|on|off` in CLI and as a dropdown in the web UI.
- **Fake loop detection:** Many SF2 samples have 1-3 sample loops at the very end of the file as a "one-shot" pattern. The converter detects these (≤3 samples, within 4 frames of end) and disables looping, treating them as true one-shots.
- **audioop polyfill:** `sf2_reader.py` includes a polyfill for the `audioop` module which may be missing in some Python environments.

## Output Structure

Each converted preset produces:
- `<name>.preset` — JSON file matching OP-XY's preset format (version 4, platform "OP-XY")
- `<name>_<idx>.wav` — One WAV per zone
- `conversion-log.json` / `.txt` — Conversion metadata
