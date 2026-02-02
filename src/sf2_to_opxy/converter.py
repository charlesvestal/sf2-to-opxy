from __future__ import annotations

import os
from typing import Dict, List, Tuple

from sf2_to_opxy.audio import resample_linear
from sf2_to_opxy.opxy_writer import write_drum_preset, write_multisample_preset
from sf2_to_opxy.selection import assign_key_ranges, select_zones_for_88_keys


Range = Tuple[int, int]


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
) -> Dict[str, object]:
    log: Dict[str, object] = {"discarded": [], "presets": [], "warnings": []}
    if bit_depth != 16:
        log["warnings"].append({"reason": "unsupported_bit_depth", "bit_depth": bit_depth})
    if not dry_run:
        os.makedirs(out_root, exist_ok=True)

    def write_preset(preset_name: str, preset: Dict[str, object], zones: List[Dict[str, object]]) -> None:
        if preset.get("is_drum"):
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
            write_multisample_preset({"name": preset_name, "regions": regions}, preset_dir)
        log["presets"].append({"name": preset_name, "zones": len(zones), "kept": len(selected)})

    def _write_drum_preset(preset_name: str, zones: List[Dict[str, object]]) -> None:
        if not zones:
            log["warnings"].append({"preset": preset_name, "reason": "no_zones"})
            return
        zones_sorted = sorted(zones, key=lambda z: int(z.get("root_key", 0)))
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
                    }
                )

            if not dry_run:
                preset_dir = os.path.join(out_root, _sanitize_name(name))
                write_drum_preset({"name": name, "regions": regions}, preset_dir)
            log["presets"].append({"name": name, "zones": len(zones), "kept": len(chunk)})

    for preset in presets:
        preset_name = preset.get("name", "Preset")
        zones = preset.get("zones", [])

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
