from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from sf2_to_opxy.audio import write_wav

BASE_MULTISAMPLE = {
    "engine": {
        "bendrange": 13653,
        "highpass": 0,
        "modulation": {
            "aftertouch": {"amount": 30719, "target": 4096},
            "modwheel": {"amount": 32767, "target": 10240},
            "pitchbend": {"amount": 16383, "target": 0},
            "velocity": {"amount": 16383, "target": 0},
        },
        "params": [16384, 16384, 16384, 16384, 16384, 16384, 16384, 16384],
        "playmode": "poly",
        "portamento.amount": 0,
        "portamento.type": 32767,
        "transpose": 0,
        "tuning.root": 0,
        "tuning.scale": 0,
        "velocity.sensitivity": 10240,
        "volume": 16466,
        "width": 3072,
    },
    "envelope": {
        "amp": {"attack": 0, "decay": 20295, "release": 16383, "sustain": 14989},
        "filter": {"attack": 0, "decay": 16895, "release": 19968, "sustain": 16896},
    },
    "fx": {"active": False, "params": [19661, 0, 7391, 24063, 0, 32767, 0, 0], "type": "svf"},
    "lfo": {"active": False, "params": [19024, 32255, 4048, 17408, 0, 0, 0, 0], "type": "element"},
    "octave": 0,
    "platform": "OP-XY",
    "regions": [],
    "type": "multisampler",
    "version": 4,
}

BASE_DRUM = {
    "engine": {
        "bendrange": 8191,
        "highpass": 0,
        "modulation": {
            "aftertouch": {"amount": 16383, "target": 0},
            "modwheel": {"amount": 16383, "target": 0},
            "pitchbend": {"amount": 16383, "target": 0},
            "velocity": {"amount": 16383, "target": 0},
        },
        "params": [16384, 16384, 16384, 16384, 16384, 16384, 16384, 16384],
        "playmode": "poly",
        "portamento.amount": 0,
        "portamento.type": 32767,
        "transpose": 0,
        "tuning.root": 0,
        "tuning.scale": 0,
        "velocity.sensitivity": 19660,
        "volume": 18348,
        "width": 0,
    },
    "envelope": {
        "amp": {"attack": 0, "decay": 0, "release": 1000, "sustain": 32767},
        "filter": {"attack": 0, "decay": 3276, "release": 23757, "sustain": 983},
    },
    "fx": {"active": False, "params": [22014, 0, 30285, 11880, 0, 32767, 0, 0], "type": "ladder"},
    "lfo": {"active": False, "params": [20309, 5679, 19114, 15807, 0, 0, 0, 12287], "type": "random"},
    "octave": 0,
    "platform": "OP-XY",
    "regions": [],
    "type": "drum",
    "version": 4,
}

def _apply_envelope(patch: Dict[str, object], envelope: Dict[str, object] | None) -> None:
    if not envelope:
        return
    amp = envelope.get("amp")
    filt = envelope.get("filter")
    if amp:
        patch["envelope"]["amp"] = amp
    if filt:
        patch["envelope"]["filter"] = filt


def _apply_fx(patch: Dict[str, object], fx: Dict[str, object] | None) -> None:
    if not fx:
        return
    params = list(patch["fx"]["params"])
    params[6] = int(fx.get("delay_send", params[6]))
    params[7] = int(fx.get("reverb_send", params[7]))
    patch["fx"]["params"] = params
    patch["fx"]["active"] = params[6] > 0 or params[7] > 0


def _apply_playmode(patch: Dict[str, object], playmode: str | None) -> None:
    if not playmode:
        return
    patch["engine"]["playmode"] = playmode


def ensure_preset_dir(path: os.PathLike[str] | str) -> Path:
    out_dir = Path(path)
    if out_dir.suffix != ".preset":
        out_dir = out_dir.with_suffix(out_dir.suffix + ".preset" if out_dir.suffix else ".preset")
    return out_dir


def write_multisample_preset(preset: Dict[str, object], out_dir: str) -> None:
    out_dir_path = ensure_preset_dir(out_dir)
    os.makedirs(out_dir_path, exist_ok=True)
    patch = json.loads(json.dumps(BASE_MULTISAMPLE))
    patch["name"] = preset["name"]
    _apply_playmode(patch, preset.get("playmode"))
    _apply_envelope(patch, preset.get("envelope"))
    _apply_fx(patch, preset.get("fx"))
    patch["regions"] = []
    for region in preset["regions"]:
        wav_path = os.path.join(out_dir_path, region["sample"])
        wav_bytes = write_wav(region["pcm"], region["sample_rate"], region["channels"], 16)
        with open(wav_path, "wb") as handle:
            handle.write(wav_bytes)
        patch["regions"].append(
            {
                "framecount": region["framecount"],
                "gain": 0,
                "hikey": region["hikey"],
                "lokey": region["lokey"],
                "loop.crossfade": 0,
                "loop.end": region["loop_end"],
                "loop.onrelease": region.get("loop_on_release", False),
                "loop.enabled": region["loop_enabled"],
                "loop.start": region["loop_start"],
                "pitch.keycenter": region["root_key"],
                "reverse": False,
                "sample": region["sample"],
                "sample.end": region["framecount"],
                "sample.start": 0,
                "tune": 0,
            }
        )
    with open(os.path.join(out_dir_path, "patch.json"), "w", encoding="utf-8") as handle:
        json.dump(patch, handle, indent=2)


def write_drum_preset(preset: Dict[str, object], out_dir: str) -> None:
    out_dir_path = ensure_preset_dir(out_dir)
    os.makedirs(out_dir_path, exist_ok=True)
    patch = json.loads(json.dumps(BASE_DRUM))
    patch["name"] = preset["name"]
    _apply_envelope(patch, preset.get("envelope"))
    _apply_fx(patch, preset.get("fx"))
    patch["regions"] = []
    for region in preset["regions"]:
        wav_path = os.path.join(out_dir_path, region["sample"])
        wav_bytes = write_wav(region["pcm"], region["sample_rate"], region["channels"], 16)
        with open(wav_path, "wb") as handle:
            handle.write(wav_bytes)
        patch["regions"].append(
            {
                "fade.in": 0,
                "fade.out": 0,
                "framecount": region["framecount"],
                "hikey": region["midi_note"],
                "lokey": region["midi_note"],
                "pan": 0,
                "pitch.keycenter": 60,
                "playmode": "oneshot",
                "reverse": False,
                "sample": region["sample"],
                "transpose": 0,
                "tune": 0,
                "gain": 0,
                "sample.start": 0,
                "sample.end": region["framecount"],
            }
        )
    with open(os.path.join(out_dir_path, "patch.json"), "w", encoding="utf-8") as handle:
        json.dump(patch, handle, indent=2)
