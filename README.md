# sf2-to-opxy

Convert SoundFont 2 (.sf2) instruments and drum kits into OP-XY multisample and drum presets.

## Features

- Multisample presets with up to 24 zones across A0–C8 (88-key coverage)
- Drum presets mapped to OP-XY drum kits (24 slots per kit)
- Loop points preserved (including loop-on-release when present)
- Amp + filter envelope mapping from SF2 timecents/centibels
- FX send mapping from SF2 chorus/reverb to OP-XY sends

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt -r requirements-dev.txt
python3 sf2_to_opxy.py /path/to/soundfont.sf2 --out /path/to/output
```

## Web app (GitHub Pages)

The browser converter lives in `web/` and is built with Vite. The build step runs
`tools/gen_web_py_manifest.py` to copy Python sources into `web/public/py/`.

```bash
npm --prefix web install
npm --prefix web run build
```

For local dev:

```bash
npm --prefix web run dev
```

## Usage

```bash
python3 sf2_to_opxy.py /path/to/soundfont.sf2 --out /path/to/output \\
  --velocities 101 \\
  --velocity-mode keep \\
  --resample-rate 22050 \\
  --bit-depth 16
```

Process a folder of SF2 files:

```bash
python3 sf2_to_opxy.py /path/to/soundfonts --out /path/to/output --recursive
```

### Options

- `--velocities`: Comma-separated MIDI velocities to keep (default `101`).
- `--velocity-mode keep|split`: `keep` uses a single preset per instrument, `split` outputs one preset per velocity.
- `--no-resample`: Keep original sample rate/bit depth (default is resample to 22.05kHz/16-bit).
- `--zero-crossing`: Enable snapping loop points to nearest zero crossing (default off).
- `--loop-end-offset`: Adjust loop end by N frames (use `-1` to match end-exclusive loop behavior in some players).
- `--resample-rate`: Target sample rate when resampling (default 22050).
- `--bit-depth`: Target bit depth (default 16).
- `--recursive`: Scan subdirectories when the source is a folder.
- `--force-drum`: Force all presets to drum kits (ignores detection).
- `--force-instrument`: Force all presets to multisample instruments (ignores detection).
- `--instrument-playmode`: Playmode for multisample presets (`auto|poly|mono|legato`).
- `--drum-velocity-mode`: Drum velocity selection (`closest|strict`). `closest` keeps one zone per drum note closest to the target velocity.

## Mapping Notes

- **Zone downselect:** If an instrument has more than 24 zones, the converter evenly spreads the chosen zones across A0–C8.
- **Key ranges:** If an instrument has 24 zones or fewer, original SF2 key ranges are preserved (clamped to A0–C8).
- **Velocity layers:** By default we keep velocity 101. You can pass multiple velocities or split into separate presets.
- **Envelopes:** SF2 timecents are converted to seconds and scaled into OP-XY 0–32767 envelope values.
  - Attack/decay use an exponential curve with ~365s max (fits 50% ≈ 2s, 75% ≈ 26s).
  - Release uses an offset power curve tuned to the measured 10% amplitude target (≈2.4s floor, ≈16.3s max).
  - Delay/hold are folded into attack/decay.
- **Per-zone gain:** SF2 initial attenuation is mapped to region gain (in dB).
- **Fine tune:** SF2 fine-tune (cents) and sample pitch correction are mapped to region tune.
- **FX sends:** SF2 chorus maps to OP-XY `fx.params[6]` (delay send) and SF2 reverb maps to `fx.params[7]` (reverb send).
  For best results, set FX1 to a chorus on the OP-XY so the chorus send behaves as intended.
- **Drum detection:** Drum kits are detected by bank 128 plus a name/keyrange heuristic (e.g. "Drum", "Kit", many single-note zones).
- **Choke groups:** SF2 exclusive class values are mapped to drum regions with playmode `group` (single mute group in OP-XY). Multiple exclusive classes are logged.
- **Drum velocities:** When `--velocity-mode keep`, drum kits use the closest velocity layer per note (so missing notes are filled without borrowing from other presets). Use `--drum-velocity-mode strict` to keep only exact velocity ranges.
- **Loop zero crossing:** Loop start/end points can be snapped to the nearest zero crossing (within a small window) to reduce clicks. Use `--zero-crossing` to enable.

## Loop preview tool

To compare loop end semantics, render a short preview WAV with multiple loop iterations:

```bash
python3 tools/render_loop_preview.py \\
  --sf2 /path/to/soundfont.sf2 \\
  --preset \"Choir Aahs\" \\
  --out /path/to/output
```

This writes WAVs for offsets `-1,0,1` plus a `manifest.json` with loop metadata.

To create multiple OP-XY presets with different loop-end offsets:

```bash
python3 tools/make_loop_offset_variants.py \\
  --preset /path/to/Choir_Aahs.preset \\
  --offsets -1,0,1 \\
  --base-offset -1
```

Use `--base-offset` if the source preset already had an offset applied.

## NKI workflow

This tool only accepts SF2. For NKI, use `nkitool` to export to SF2, then run this converter on the resulting SF2 files:

```
https://github.com/reales/nkitool
```

## Calibration workflow (envelope validation)

To validate the OP-XY envelope mapping, generate calibration presets, record a single WAV with hits in order, and analyze it.

1) Generate presets:

```bash
python3 tools/generate_calibration_presets.py --out /path/to/opxy-calibration
```

This writes presets plus a `calibration-manifest.json` describing the exact order.
To better measure release tails, you can enable looping during release:

```bash
python3 tools/generate_calibration_presets.py --out /path/to/opxy-calibration --release-loop-on
```

2) Copy the presets to the OP-XY and record **one WAV** with hits in manifest order.
   - Use a fixed note length (default hold time is 1.0s in the manifest).
   - Leave silence after each hit so onsets are easy to detect.

3) Analyze the recording:

```bash
python3 tools/analyze_envelope.py --wav /path/to/recording.wav --manifest /path/to/opxy-calibration/calibration-manifest.json --hold-seconds 1.0
```

This produces `/path/to/recording.analysis.json` with measured attack/release times and a fitted curve estimate.

Note: `tools/analyze_envelope.py` uses `numpy` (listed in `requirements-dev.txt`).

## License

MIT. See `LICENSE`.
