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

## Usage

```bash
python3 sf2_to_opxy.py /path/to/soundfont.sf2 --out /path/to/output \\
  --velocities 101 \\
  --velocity-mode keep \\
  --resample-rate 22050 \\
  --bit-depth 16
```

### Options

- `--velocities`: Comma-separated MIDI velocities to keep (default `101`).
- `--velocity-mode keep|split`: `keep` uses a single preset per instrument, `split` outputs one preset per velocity.
- `--no-resample`: Keep original sample rate/bit depth (default is resample to 22.05kHz/16-bit).
- `--resample-rate`: Target sample rate when resampling (default 22050).
- `--bit-depth`: Target bit depth (default 16).

## Mapping Notes

- **Zone downselect:** If an instrument has more than 24 zones, the converter evenly spreads the chosen zones across A0–C8.
- **Velocity layers:** By default we keep velocity 101. You can pass multiple velocities or split into separate presets.
- **Envelopes:** SF2 timecents are converted to seconds and scaled into OP-XY 0–32767 envelope values. Delay/hold are folded into attack/decay.
- **FX sends:** SF2 chorus maps to OP-XY `fx.params[6]` (delay send) and SF2 reverb maps to `fx.params[7]` (reverb send).
  For best results, set FX1 to a chorus on the OP-XY so the chorus send behaves as intended.

## License

MIT. See `LICENSE`.
