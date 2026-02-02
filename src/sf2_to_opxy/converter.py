from __future__ import annotations

import math
import os
from collections import Counter
from typing import Dict, List, Tuple

from sf2_to_opxy.audio import resample_linear
from sf2_to_opxy.opxy_writer import write_drum_preset, write_multisample_preset
from sf2_to_opxy.selection import assign_key_ranges, select_zones_for_88_keys


Range = Tuple[int, int]
ATTACK_MIN_SECONDS = 0.0111
ATTACK_CURVE_B = 10.386
ATTACK_MAX_SECONDS = 360.0
RELEASE_MAX_SECONDS = 30.0
ZERO_CROSS_THRESHOLD = 1
ZERO_CROSS_MAX_DISTANCE = 1000


def timecents_to_seconds(timecents: float) -> float:
    return 2 ** (timecents / 1200.0)


def centibels_to_level(centibels: float) -> float:
    if centibels < 0:
        centibels = 0
    return math.pow(10.0, -centibels / 200.0)


def scale_attack_seconds(seconds: float, max_seconds: float = ATTACK_MAX_SECONDS) -> int:
    if seconds <= 0:
        return 0
    clipped = min(seconds, max_seconds)
    if clipped <= ATTACK_MIN_SECONDS:
        return 0
    x = math.log(clipped / ATTACK_MIN_SECONDS) / ATTACK_CURVE_B
    x = max(0.0, min(1.0, x))
    return int(round(x * 32767))


def scale_release_seconds(seconds: float, max_seconds: float = RELEASE_MAX_SECONDS) -> int:
    if seconds <= 0:
        return 32767
    clipped = min(seconds, max_seconds)
    ratio = clipped / max_seconds
    inverted = 1.0 - ratio ** (1.0 / 3.0)
    return int(round(inverted * 32767))


def map_fx_send(percent: float) -> int:
    value = max(0.0, min(100.0, percent))
    return int(round(value / 100.0 * 32767))


def _env_to_opxy(env: Dict[str, object]) -> Dict[str, int]:
    delay_tc = env.get("delay_tc")
    attack_tc = env.get("attack_tc")
    hold_tc = env.get("hold_tc")
    decay_tc = env.get("decay_tc")
    release_tc = env.get("release_tc")
    sustain_cb = env.get("sustain_cb")

    delay_sec = timecents_to_seconds(delay_tc) if delay_tc is not None else 0.0
    attack_sec = timecents_to_seconds(attack_tc) if attack_tc is not None else 0.0
    hold_sec = timecents_to_seconds(hold_tc) if hold_tc is not None else 0.0
    decay_sec = timecents_to_seconds(decay_tc) if decay_tc is not None else 0.0
    release_sec = timecents_to_seconds(release_tc) if release_tc is not None else 0.0

    if sustain_cb is None:
        sustain_level = 1.0
    else:
        sustain_level = centibels_to_level(float(sustain_cb))
    sustain_level = max(0.0, min(1.0, sustain_level))

    attack_total = delay_sec + attack_sec
    decay_total = hold_sec + decay_sec

    return {
        "attack": scale_attack_seconds(attack_total),
        "decay": scale_attack_seconds(decay_total),
        "sustain": int(round(sustain_level * 32767)),
        "release": scale_release_seconds(release_sec),
    }


def _choose_mode(values: List[Tuple[int, int, int, int]]) -> Tuple[Tuple[int, int, int, int], int]:
    counts = Counter(values)
    choice, count = counts.most_common(1)[0]
    return choice, len(counts)


def _derive_envelope(zones: List[Dict[str, object]], key: str, preset_name: str, log: Dict[str, object]) -> Dict[str, int] | None:
    tuples: List[Tuple[int, int, int, int]] = []
    missing = 0
    for zone in zones:
        env = zone.get(key)
        if not env or not env.get("present"):
            missing += 1
            continue
        opxy_env = _env_to_opxy(env)
        tuples.append((opxy_env["attack"], opxy_env["decay"], opxy_env["sustain"], opxy_env["release"]))
    if not tuples:
        return None
    chosen, variants = _choose_mode(tuples)
    if variants > 1:
        log["warnings"].append(
            {"preset": preset_name, "reason": "mixed_envelope", "env": key, "variants": variants}
        )
    if missing > 0:
        log["warnings"].append(
            {"preset": preset_name, "reason": "missing_envelope_zones", "env": key, "missing": missing}
        )
    return {"attack": chosen[0], "decay": chosen[1], "sustain": chosen[2], "release": chosen[3]}


def _derive_fx(zones: List[Dict[str, object]], preset_name: str, log: Dict[str, object]) -> Dict[str, int] | None:
    tuples: List[Tuple[float, float]] = []
    for zone in zones:
        fx = zone.get("fx_send") or {}
        chorus = float(fx.get("chorus", 0.0))
        reverb = float(fx.get("reverb", 0.0))
        tuples.append((chorus, reverb))
    if not tuples:
        return None
    counts = Counter(tuples)
    (chorus, reverb), variants = counts.most_common(1)[0]
    if variants > 1:
        log["warnings"].append(
            {"preset": preset_name, "reason": "mixed_fx_send", "variants": variants}
        )
    return {
        "delay_send": map_fx_send(chorus),
        "reverb_send": map_fx_send(reverb),
        "chorus_percent": chorus,
        "reverb_percent": reverb,
    }


def _auto_playmode(preset_name: str, zones: List[Dict[str, object]]) -> str:
    name = (preset_name or "").lower()
    if "legato" in name or "porta" in name or "portamento" in name:
        return "legato"
    if "mono" in name:
        return "mono"
    for zone in zones:
        if int(zone.get("exclusive_class", 0)) > 0:
            return "mono"
    return "poly"

def _sanitize_name(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in ("_", "-", " "):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip().replace("  ", " ").replace(" ", "_") or "preset"


def _zone_descriptor(zone: Dict[str, object]) -> Dict[str, object]:
    return {
        "preset": zone.get("preset"),
        "instrument": zone.get("instrument"),
        "sample": zone.get("sample", {}).get("name"),
        "root_key": zone.get("root_key"),
        "key_range": zone.get("key_range"),
        "vel_range": zone.get("vel_range"),
    }


def _velocity_match(vel_range: Range, velocities: List[int]) -> bool:
    low, high = vel_range
    return any(low <= vel <= high for vel in velocities)


def _frame_amplitude(pcm: List[int], frame_idx: int, channels: int) -> int:
    start = frame_idx * channels
    end = start + channels
    max_amp = 0
    for i in range(start, end):
        value = pcm[i]
        if value < 0:
            value = -value
        if value > max_amp:
            max_amp = value
    return max_amp


def _find_nearest_zero_crossing(
    pcm: List[int],
    channels: int,
    frame_position: int,
    direction: str = "both",
    max_distance: int = ZERO_CROSS_MAX_DISTANCE,
    min_frame: int = 0,
    max_frame: int | None = None,
    threshold: int = ZERO_CROSS_THRESHOLD,
) -> int:
    framecount = len(pcm) // channels
    if max_frame is None:
        max_frame = max(0, framecount - 1)
    frame_position = max(min_frame, min(frame_position, max_frame))

    if direction == "forward":
        search_start = frame_position
        search_end = min(frame_position + max_distance, max_frame)
    elif direction == "backward":
        search_start = max(frame_position - max_distance, min_frame)
        search_end = frame_position
    else:
        search_start = max(frame_position - max_distance, min_frame)
        search_end = min(frame_position + max_distance, max_frame)

    best_position = frame_position
    min_amplitude = _frame_amplitude(pcm, frame_position, channels)
    for i in range(search_start, search_end + 1):
        amplitude = _frame_amplitude(pcm, i, channels)
        if amplitude < min_amplitude:
            min_amplitude = amplitude
            best_position = i
            if amplitude <= threshold:
                break
    return best_position


def _adjust_loop_zero_crossing(
    pcm: List[int],
    channels: int,
    loop_start: int,
    loop_end: int,
    max_distance: int,
    threshold: int,
    preset_name: str,
    zone: Dict[str, object],
    log: Dict[str, object],
) -> Tuple[int, int]:
    if loop_end <= loop_start:
        return loop_start, loop_end
    framecount = len(pcm) // channels
    if framecount <= 1:
        return loop_start, loop_end

    max_frame = framecount - 1
    original_start = loop_start
    original_end = loop_end
    loop_start = max(0, min(loop_start, max_frame))
    loop_end = max(loop_start + 1, min(loop_end, max_frame))

    adjusted_start = _find_nearest_zero_crossing(
        pcm,
        channels,
        loop_start,
        direction="both",
        max_distance=max_distance,
        min_frame=0,
        max_frame=max(loop_end - 1, 0),
        threshold=threshold,
    )
    adjusted_end = _find_nearest_zero_crossing(
        pcm,
        channels,
        loop_end,
        direction="both",
        max_distance=max_distance,
        min_frame=min(adjusted_start + 1, max_frame),
        max_frame=max_frame,
        threshold=threshold,
    )

    if adjusted_end <= adjusted_start:
        return original_start, original_end

    if adjusted_start != original_start or adjusted_end != original_end:
        log["warnings"].append(
            {
                "preset": preset_name,
                "reason": "loop_zero_crossing_adjusted",
                "original_start": original_start,
                "original_end": original_end,
                "adjusted_start": adjusted_start,
                "adjusted_end": adjusted_end,
                **_zone_descriptor(zone),
            }
        )
    return adjusted_start, adjusted_end


def _velocity_distance(vel_range: Range, velocities: List[int]) -> int:
    low, high = vel_range
    best = None
    for vel in velocities:
        if low <= vel <= high:
            return 0
        dist = min(abs(vel - low), abs(vel - high))
        if best is None or dist < best:
            best = dist
    return best if best is not None else 999


def _select_drum_zones_by_velocity(
    zones: List[Dict[str, object]],
    velocities: List[int],
    preset_name: str,
    log: Dict[str, object],
) -> List[Dict[str, object]]:
    grouped: Dict[int, List[Dict[str, object]]] = {}
    for zone in zones:
        root = int(zone.get("root_key", 0))
        grouped.setdefault(root, []).append(zone)

    selected: List[Dict[str, object]] = []
    for root, group in grouped.items():
        best_zone = None
        best_key = None
        for zone in group:
            vel_range = zone.get("vel_range", (0, 127))
            dist = _velocity_distance(vel_range, velocities)
            width = int(vel_range[1]) - int(vel_range[0])
            key = (dist, width, -int(vel_range[0]))
            if best_key is None or key < best_key:
                best_key = key
                best_zone = zone
        if best_zone is not None:
            selected.append(best_zone)
            for zone in group:
                if zone is best_zone:
                    continue
                log["discarded"].append(
                    {
                        "reason": "drum_velocity_choice",
                        "selected_vel_range": best_zone.get("vel_range"),
                        **_zone_descriptor(zone),
                    }
                )
        else:
            log["warnings"].append(
                {
                    "preset": preset_name,
                    "reason": "drum_velocity_missing",
                    "root_key": root,
                }
            )
    return selected

def _resample_pcm(pcm: List[int], channels: int, src_rate: int, dst_rate: int) -> List[int]:
    if src_rate == dst_rate:
        return list(pcm)
    if channels == 1:
        return resample_linear(pcm, src_rate, dst_rate)
    channel_data = [pcm[ch::channels] for ch in range(channels)]
    resampled = [resample_linear(ch_data, src_rate, dst_rate) for ch_data in channel_data]
    frames = min(len(ch) for ch in resampled)
    out: List[int] = []
    for idx in range(frames):
        for ch in range(channels):
            out.append(resampled[ch][idx])
    return out


def convert_presets(
    presets: List[Dict[str, object]],
    out_root: str,
    velocities: List[int],
    velocity_mode: str,
    resample_rate: int,
    bit_depth: int,
    resample: bool = True,
    dry_run: bool = False,
    force_mode: str | None = None,
    instrument_playmode: str = "auto",
    drum_velocity_mode: str = "closest",
    zero_crossing: bool = True,
    zero_crossing_max_distance: int = ZERO_CROSS_MAX_DISTANCE,
    zero_crossing_threshold: int = ZERO_CROSS_THRESHOLD,
) -> Dict[str, object]:
    log: Dict[str, object] = {"discarded": [], "presets": [], "warnings": []}
    if bit_depth != 16:
        log["warnings"].append({"reason": "unsupported_bit_depth", "bit_depth": bit_depth})
    if not dry_run:
        os.makedirs(out_root, exist_ok=True)

    def _resolve_is_drum(preset: Dict[str, object]) -> bool:
        is_drum = bool(preset.get("is_drum"))
        if force_mode == "drum":
            return True
        if force_mode == "instrument":
            return False
        return is_drum

    def write_preset(preset_name: str, preset: Dict[str, object], zones: List[Dict[str, object]]) -> None:
        if _resolve_is_drum(preset):
            _write_drum_preset(preset_name, zones)
        else:
            _write_multisample_preset(preset_name, zones)

    def _write_multisample_preset(preset_name: str, zones: List[Dict[str, object]]) -> None:
        if not zones:
            log["warnings"].append({"preset": preset_name, "reason": "no_zones"})
            return
        for zone in zones:
            root_key = int(zone.get("root_key", 60))
            if root_key < 21 or root_key > 108:
                log["warnings"].append(
                    {"preset": preset_name, "reason": "root_key_clamped", "root_key": root_key}
                )
                zone["root_key"] = max(21, min(108, root_key))
        selected = select_zones_for_88_keys(zones, 24, 21, 108)
        selected_ids = {id(z) for z in selected}
        for zone in zones:
            if id(zone) not in selected_ids:
                log["discarded"].append({"reason": "zone_downselect", **_zone_descriptor(zone)})
        selected = assign_key_ranges(selected, 21, 108)
        amp_env = _derive_envelope(selected, "amp_env", preset_name, log)
        filter_env = _derive_envelope(selected, "mod_env", preset_name, log)
        fx_send = _derive_fx(selected, preset_name, log)
        if instrument_playmode == "auto":
            playmode = _auto_playmode(preset_name, selected)
        else:
            playmode = instrument_playmode

        seen_names: Dict[str, int] = {}
        regions = []
        for idx, zone in enumerate(selected):
            sample = zone["sample"]
            pcm = sample["data"]
            channels = int(sample.get("channels", 1))
            source_rate = int(sample.get("rate", resample_rate))
            loop_start = int(zone.get("loop_start", 0))
            loop_end = int(zone.get("loop_end", 0))
            loop_enabled = bool(zone.get("loop_enabled", False))
            loop_on_release = bool(zone.get("loop_on_release", False))

            if resample:
                pcm = _resample_pcm(pcm, channels, source_rate, resample_rate)
                scale = resample_rate / source_rate
                loop_start = int(round(loop_start * scale))
                loop_end = int(round(loop_end * scale))
                output_rate = resample_rate
            else:
                output_rate = source_rate

            framecount = len(pcm) // channels
            if loop_enabled:
                loop_start = max(0, min(loop_start, framecount - 1))
                loop_end = max(loop_start + 1, min(loop_end, framecount))
                if loop_end <= loop_start:
                    loop_enabled = False
                    log["warnings"].append(
                        {"preset": preset_name, "reason": "invalid_loop", **_zone_descriptor(zone)}
                    )
                elif zero_crossing:
                    loop_start, loop_end = _adjust_loop_zero_crossing(
                        pcm,
                        channels,
                        loop_start,
                        loop_end,
                        zero_crossing_max_distance,
                        zero_crossing_threshold,
                        preset_name,
                        zone,
                        log,
                    )
            else:
                loop_start = 0
                loop_end = 0

            base_name = _sanitize_name(str(sample.get("name", f"sample_{idx}")))
            base_name = f"{base_name}_{zone['root_key']}"
            count = seen_names.get(base_name, 0)
            seen_names[base_name] = count + 1
            if count:
                base_name = f"{base_name}_{count}"
            filename = f"{base_name}.wav"

            regions.append(
                {
                    "sample": filename,
                    "pcm": pcm,
                    "sample_rate": output_rate,
                    "channels": channels,
                    "root_key": zone["root_key"],
                    "loop_start": loop_start,
                    "loop_end": loop_end,
                    "loop_enabled": loop_enabled,
                    "loop_on_release": loop_on_release,
                    "framecount": framecount,
                    "lokey": zone["lokey"],
                    "hikey": zone["hikey"],
                }
            )

        if not dry_run:
            preset_dir = os.path.join(out_root, _sanitize_name(preset_name))
            write_multisample_preset(
                {
                    "name": preset_name,
                    "regions": regions,
                    "envelope": {"amp": amp_env, "filter": filter_env},
                    "fx": fx_send,
                    "playmode": playmode,
                },
                preset_dir,
            )
        log["presets"].append(
            {
                "name": preset_name,
                "zones": len(zones),
                "kept": len(selected),
                "fx": fx_send,
                "envelope": {"amp": amp_env, "filter": filter_env},
                "playmode": playmode,
            }
        )

    def _write_drum_preset(preset_name: str, zones: List[Dict[str, object]]) -> None:
        if not zones:
            log["warnings"].append({"preset": preset_name, "reason": "no_zones"})
            return
        zones_sorted = sorted(zones, key=lambda z: int(z.get("root_key", 0)))
        exclusive_classes = sorted(
            {int(z.get("exclusive_class", 0)) for z in zones_sorted if int(z.get("exclusive_class", 0)) > 0}
        )
        if len(exclusive_classes) > 1:
            log["warnings"].append(
                {
                    "preset": preset_name,
                    "reason": "multiple_exclusive_classes",
                    "classes": exclusive_classes,
                }
            )
        amp_env = _derive_envelope(zones_sorted, "amp_env", preset_name, log)
        filter_env = _derive_envelope(zones_sorted, "mod_env", preset_name, log)
        fx_send = _derive_fx(zones_sorted, preset_name, log)
        chunks = [zones_sorted[i:i + 24] for i in range(0, len(zones_sorted), 24)]
        for chunk_index, chunk in enumerate(chunks):
            name = preset_name
            if len(chunks) > 1:
                name = f"{preset_name}_{chunk_index + 1:02d}"

            regions = []
            seen_names: Dict[str, int] = {}
            for slot, zone in enumerate(chunk):
                sample = zone["sample"]
                pcm = sample["data"]
                channels = int(sample.get("channels", 1))
                source_rate = int(sample.get("rate", resample_rate))
                playmode = "group" if int(zone.get("exclusive_class", 0)) > 0 else "oneshot"

                if resample:
                    pcm = _resample_pcm(pcm, channels, source_rate, resample_rate)
                    output_rate = resample_rate
                else:
                    output_rate = source_rate

                framecount = len(pcm) // channels
                base_name = _sanitize_name(str(sample.get("name", f"drum_{slot}")))
                count = seen_names.get(base_name, 0)
                seen_names[base_name] = count + 1
                if count:
                    base_name = f"{base_name}_{count}"
                filename = f"{base_name}.wav"
                regions.append(
                    {
                        "sample": filename,
                        "pcm": pcm,
                        "sample_rate": output_rate,
                        "channels": channels,
                        "framecount": framecount,
                        "midi_note": 53 + slot,
                        "playmode": playmode,
                    }
                )

            if not dry_run:
                preset_dir = os.path.join(out_root, _sanitize_name(name))
                write_drum_preset(
                    {
                        "name": name,
                        "regions": regions,
                        "envelope": {"amp": amp_env, "filter": filter_env},
                        "fx": fx_send,
                    },
                    preset_dir,
                )
            log["presets"].append(
                {
                    "name": name,
                    "zones": len(zones),
                    "kept": len(chunk),
                    "fx": fx_send,
                    "envelope": {"amp": amp_env, "filter": filter_env},
                }
            )

    for preset in presets:
        preset_name = preset.get("name", "Preset")
        zones = preset.get("zones", [])
        is_drum = _resolve_is_drum(preset)

        if velocity_mode == "split":
            for velocity in velocities:
                filtered = []
                for zone in zones:
                    vel_range = zone.get("vel_range", (0, 127))
                    if _velocity_match(vel_range, [velocity]):
                        filtered.append(zone)
                    else:
                        log["discarded"].append(
                            {
                                "reason": "velocity_filtered",
                                "velocity": velocity,
                                **_zone_descriptor(zone),
                            }
                        )
                variant = f"{preset_name}_vel{velocity}"
                write_preset(variant, preset, filtered)
        else:
            if is_drum and drum_velocity_mode == "closest":
                filtered = _select_drum_zones_by_velocity(zones, velocities, preset_name, log)
            else:
                filtered = []
                for zone in zones:
                    vel_range = zone.get("vel_range", (0, 127))
                    if _velocity_match(vel_range, velocities):
                        filtered.append(zone)
                    else:
                        log["discarded"].append(
                            {
                                "reason": "velocity_filtered",
                                "velocities": velocities,
                                **_zone_descriptor(zone),
                            }
                        )
            write_preset(preset_name, preset, filtered)

    return log
