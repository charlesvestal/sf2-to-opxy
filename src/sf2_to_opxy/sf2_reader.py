from __future__ import annotations

import sys
import types
from array import array
from typing import Dict, List, Optional, Tuple


Range = Tuple[int, int]
DRUM_NAME_TOKENS = (
    "drum",
    "drums",
    "kit",
    "perc",
    "percussion",
    "beat",
)


def _ensure_audioop() -> None:
    try:
        import audioop  # noqa: F401
    except ModuleNotFoundError:
        def byteswap(data: bytes, width: int) -> bytes:
            if width <= 0:
                raise ValueError("width must be positive")
            out = bytearray(len(data))
            for idx in range(0, len(data), width):
                out[idx:idx + width] = data[idx:idx + width][::-1]
            return bytes(out)

        module = types.ModuleType("audioop")
        module.byteswap = byteswap
        sys.modules["audioop"] = module


def read_soundfont(sf2_path: str):
    _ensure_audioop()
    try:
        from sf2utils.sf2parse import Sf2File
    except Exception as exc:
        raise RuntimeError(
            "Missing dependency sf2utils. Install with: python3 -m pip install sf2utils"
        ) from exc

    import io

    with open(sf2_path, "rb") as handle:
        data = handle.read()
    sf2 = Sf2File(io.BytesIO(data))
    return sf2


def extract_presets(sf2) -> Tuple[List[Dict[str, object]], Dict[str, List[Dict[str, object]]]]:
    from sf2utils.generator import Sf2Gen

    parse_log: Dict[str, List[Dict[str, object]]] = {
        "warnings": [],
        "skipped_zones": [],
    }

    sample_index = {id(sample): idx for idx, sample in enumerate(sf2.samples)}
    sample_cache: Dict[Tuple[int, Optional[int]], Dict[str, object]] = {}

    def _decode_pcm(sample) -> List[int]:
        raw = sample.raw_sample_data
        width = sample.sample_width
        if width == 2:
            pcm = array("h")
            pcm.frombytes(raw)
            return list(pcm)
        if width == 3:
            pcm: List[int] = []
            for i in range(0, len(raw), 3):
                chunk = raw[i:i + 3]
                value = int.from_bytes(chunk, byteorder="little", signed=True)
                pcm.append(int(value >> 8))
            return pcm
        raise ValueError(f"Unsupported sample width: {width}")

    def _get_sample_pair(sample):
        if getattr(sample, "name", None) == "EOS":
            return None
        left_idx = sample_index.get(id(sample))
        if left_idx is None:
            return None
        if sample.is_mono:
            cache_key = (left_idx, None)
            if cache_key not in sample_cache:
                pcm = _decode_pcm(sample)
                sample_cache[cache_key] = {
                    "pcm": pcm,
                    "rate": sample.sample_rate,
                    "channels": 1,
                    "loop_start": sample.start_loop,
                    "loop_end": sample.end_loop,
                    "pitch_correction": sample.pitch_correction,
                }
            return sample_cache[cache_key]
        right_idx = sample.sample_link
        cache_key = (left_idx, right_idx)
        if cache_key in sample_cache:
            return sample_cache[cache_key]
        try:
            right_sample = sf2.samples[right_idx]
        except Exception:
            pcm = _decode_pcm(sample)
            sample_cache[cache_key] = {
                "pcm": pcm,
                "rate": sample.sample_rate,
                "channels": 1,
                "loop_start": sample.start_loop,
                "loop_end": sample.end_loop,
                "pitch_correction": sample.pitch_correction,
            }
            return sample_cache[cache_key]
        left_pcm = _decode_pcm(sample)
        right_pcm = _decode_pcm(right_sample)
        frames = min(len(left_pcm), len(right_pcm))
        interleaved: List[int] = []
        for i in range(frames):
            interleaved.append(left_pcm[i])
            interleaved.append(right_pcm[i])
        sample_cache[cache_key] = {
            "pcm": interleaved,
            "rate": sample.sample_rate,
            "channels": 2,
            "loop_start": sample.start_loop,
            "loop_end": sample.end_loop,
            "pitch_correction": sample.pitch_correction,
        }
        return sample_cache[cache_key]

    def _get_range(bag, oper: int) -> Optional[Range]:
        if bag is None:
            return None
        gen = bag.gens.get(oper)
        if gen is None:
            return None
        lo, hi = gen.amount_as_sorted_range
        return int(lo), int(hi)

    def _sum_short(bags, oper: int) -> Tuple[int, bool]:
        total = 0
        present = False
        for bag in bags:
            gen = bag.gens.get(oper)
            if gen is not None:
                total += int(gen.short)
                present = True
        return total, present

    def _sum_word(bags, oper: int) -> Tuple[int, bool]:
        total = 0
        present = False
        for bag in bags:
            gen = bag.gens.get(oper)
            if gen is not None:
                total += int(gen.word)
                present = True
        return total, present

    def _first_word(bags, oper: int) -> Optional[int]:
        for bag in bags:
            if bag is None:
                continue
            gen = bag.gens.get(oper)
            if gen is not None:
                return int(gen.word)
        return None

    def _sum_offset(bags, oper: int, coarse_oper: int) -> int:
        total = 0
        for bag in bags:
            gen = bag.gens.get(oper)
            if gen is not None:
                total += int(gen.short)
            coarse = bag.gens.get(coarse_oper)
            if coarse is not None:
                total += int(coarse.short) * 32768
        return total

    def _intersect_ranges(a: Optional[Range], b: Optional[Range]) -> Optional[Range]:
        if a is None and b is None:
            return None
        if a is None:
            return b
        if b is None:
            return a
        return max(a[0], b[0]), min(a[1], b[1])

    def _looks_like_drum(preset_name: str, zones: List[Dict[str, object]]) -> Optional[str]:
        name = (preset_name or "").lower()
        if any(token in name for token in DRUM_NAME_TOKENS):
            return "name"
        for zone in zones:
            instrument_name = str(zone.get("instrument", "")).lower()
            if any(token in instrument_name for token in DRUM_NAME_TOKENS):
                return "instrument_name"
        if not zones:
            return None
        narrow = 0
        roots = set()
        for zone in zones:
            key_range = zone.get("key_range", (0, 127))
            if key_range[0] == key_range[1]:
                narrow += 1
            root_key = zone.get("root_key")
            if root_key is not None:
                roots.add(int(root_key))
        if roots:
            ratio = narrow / max(1, len(zones))
            if ratio >= 0.7 and len(roots) >= min(8, len(zones)):
                return "single_note_zones"
        return None

    presets: List[Dict[str, object]] = []

    for preset in sf2.presets:
        if getattr(preset, "name", None) == "EOP":
            continue

        preset_global = None
        preset_zones = []
        for bag in preset.bags:
            instrument_gen = bag.gens.get(Sf2Gen.OPER_INSTRUMENT)
            if instrument_gen is None:
                preset_global = bag
                continue

            instrument = sf2.instruments[instrument_gen.word]
            if getattr(instrument, "name", None) == "EOI":
                continue

            instrument_global = None
            for inst_bag in instrument.bags:
                sample_gen = inst_bag.gens.get(Sf2Gen.OPER_SAMPLE_ID)
                if sample_gen is None:
                    instrument_global = inst_bag
                    continue

                sample = sf2.samples[sample_gen.word]
                sample_pair = _get_sample_pair(sample)
                if sample_pair is None:
                    parse_log["skipped_zones"].append(
                        {
                            "preset": preset.name,
                            "instrument": instrument.name,
                            "reason": "missing_sample",
                        }
                    )
                    continue

                bags = [b for b in (preset_global, bag, instrument_global, inst_bag) if b is not None]

                preset_key = _get_range(bag, Sf2Gen.OPER_KEY_RANGE) or _get_range(
                    preset_global, Sf2Gen.OPER_KEY_RANGE
                )
                inst_key = _get_range(inst_bag, Sf2Gen.OPER_KEY_RANGE) or _get_range(
                    instrument_global, Sf2Gen.OPER_KEY_RANGE
                )
                key_range = _intersect_ranges(preset_key, inst_key) or (0, 127)

                preset_vel = _get_range(bag, Sf2Gen.OPER_VEL_RANGE) or _get_range(
                    preset_global, Sf2Gen.OPER_VEL_RANGE
                )
                inst_vel = _get_range(inst_bag, Sf2Gen.OPER_VEL_RANGE) or _get_range(
                    instrument_global, Sf2Gen.OPER_VEL_RANGE
                )
                vel_range = _intersect_ranges(preset_vel, inst_vel) or (0, 127)

                if key_range[0] > key_range[1] or vel_range[0] > vel_range[1]:
                    parse_log["skipped_zones"].append(
                        {
                            "preset": preset.name,
                            "instrument": instrument.name,
                            "sample": getattr(sample, "name", None),
                            "reason": "invalid_range",
                            "key_range": key_range,
                            "vel_range": vel_range,
                        }
                    )
                    continue

                root_override = None
                for candidate in (inst_bag, instrument_global, bag, preset_global):
                    if candidate is None:
                        continue
                    gen = candidate.gens.get(Sf2Gen.OPER_OVERRIDING_ROOT_KEY)
                    if gen is not None:
                        root_override = int(gen.word)
                        break

                coarse, _ = _sum_short(bags, Sf2Gen.OPER_COARSE_TUNE)
                fine, _ = _sum_short(bags, Sf2Gen.OPER_FINE_TUNE)
                fine += int(sample_pair["pitch_correction"])

                root_key = root_override if root_override is not None else int(sample.original_pitch)
                if fine % 100 != 0:
                    parse_log["warnings"].append(
                        {
                            "preset": preset.name,
                            "instrument": instrument.name,
                            "sample": getattr(sample, "name", None),
                            "reason": "fine_tune_rounded",
                            "fine_cents": fine,
                        }
                    )
                root_key += coarse + int(round(fine / 100))
                root_key = max(0, min(127, root_key))

                start_offset = _sum_offset(bags, Sf2Gen.OPER_START_ADDR_OFFSET, Sf2Gen.OPER_START_ADDR_COARSE_OFFSET)
                end_offset = _sum_offset(bags, Sf2Gen.OPER_END_ADDR_OFFSET, Sf2Gen.OPER_END_ADDR_COARSE_OFFSET)
                loop_start_offset = _sum_offset(
                    bags, Sf2Gen.OPER_START_LOOP_ADDR_OFFSET, Sf2Gen.OPER_START_LOOP_ADDR_COARSE_OFFSET
                )
                loop_end_offset = _sum_offset(
                    bags, Sf2Gen.OPER_END_LOOP_ADDR_OFFSET, Sf2Gen.OPER_END_LOOP_ADDR_COARSE_OFFSET
                )

                pcm = sample_pair["pcm"]
                channels = int(sample_pair["channels"])
                total_frames = len(pcm) // channels

                start_frame = max(0, start_offset)
                end_frame = total_frames + end_offset
                end_frame = max(start_frame + 1, min(total_frames, end_frame))
                if start_frame >= total_frames:
                    parse_log["skipped_zones"].append(
                        {
                            "preset": preset.name,
                            "instrument": instrument.name,
                            "sample": getattr(sample, "name", None),
                            "reason": "start_offset_oob",
                            "start_offset": start_offset,
                            "frames": total_frames,
                        }
                    )
                    continue

                loop_start = int(sample_pair["loop_start"]) + loop_start_offset - start_frame
                loop_end = int(sample_pair["loop_end"]) + loop_end_offset - start_frame

                pcm = pcm[start_frame * channels:end_frame * channels]
                frame_count = len(pcm) // channels

                if frame_count <= 0:
                    parse_log["skipped_zones"].append(
                        {
                            "preset": preset.name,
                            "instrument": instrument.name,
                            "sample": getattr(sample, "name", None),
                            "reason": "empty_sample",
                        }
                    )
                    continue

                sample_mode = _first_word(
                    [inst_bag, instrument_global, bag, preset_global],
                    Sf2Gen.OPER_SAMPLE_MODES,
                )
                if sample_mode is None:
                    sample_mode = 0
                loop_enabled = False
                loop_on_release = False
                if loop_start < loop_end and sample_mode != 0:
                    loop_start = max(0, min(loop_start, frame_count - 1))
                    loop_end = max(loop_start + 1, min(loop_end, frame_count))
                    loop_enabled = True
                    if sample_mode & 0x2:
                        loop_on_release = True

                delay_vol_tc, delay_vol_present = _sum_short(bags, Sf2Gen.OPER_DELAY_VOL_ENV)
                attack_vol_tc, attack_vol_present = _sum_short(bags, Sf2Gen.OPER_ATTACK_VOL_ENV)
                hold_vol_tc, hold_vol_present = _sum_short(bags, Sf2Gen.OPER_HOLD_VOL_ENV)
                decay_vol_tc, decay_vol_present = _sum_short(bags, Sf2Gen.OPER_DECAY_VOL_ENV)
                sustain_vol_cb, sustain_vol_present = _sum_word(bags, Sf2Gen.OPER_SUSTAIN_VOL_ENV)
                release_vol_tc, release_vol_present = _sum_short(bags, Sf2Gen.OPER_RELEASE_VOL_ENV)

                delay_mod_tc, delay_mod_present = _sum_short(bags, Sf2Gen.OPER_DELAY_MOD_ENV)
                attack_mod_tc, attack_mod_present = _sum_short(bags, Sf2Gen.OPER_ATTACK_MOD_ENV)
                hold_mod_tc, hold_mod_present = _sum_short(bags, Sf2Gen.OPER_HOLD_MOD_ENV)
                decay_mod_tc, decay_mod_present = _sum_short(bags, Sf2Gen.OPER_DECAY_MOD_ENV)
                sustain_mod_cb, sustain_mod_present = _sum_word(bags, Sf2Gen.OPER_SUSTAIN_MOD_ENV)
                release_mod_tc, release_mod_present = _sum_short(bags, Sf2Gen.OPER_RELEASE_MOD_ENV)

                chorus_send_raw, chorus_present = _sum_word(bags, Sf2Gen.OPER_CHORUS_EFFECTS_SEND)
                reverb_send_raw, reverb_present = _sum_word(bags, Sf2Gen.OPER_REVERB_EFFECTS_SEND)
                exclusive_class = _first_word(bags, Sf2Gen.OPER_EXCLUSIVE_CLASS)

                preset_zones.append(
                    {
                        "preset": preset.name,
                        "instrument": instrument.name,
                        "root_key": root_key,
                        "key_range": key_range,
                        "vel_range": vel_range,
                        "sample": {
                            "name": getattr(sample, "name", None) or f"sample_{sample_gen.word}",
                            "data": pcm,
                            "rate": int(sample_pair["rate"]),
                            "channels": channels,
                        },
                        "loop_start": loop_start,
                        "loop_end": loop_end,
                        "loop_enabled": loop_enabled,
                        "loop_on_release": loop_on_release,
                        "amp_env": {
                            "delay_tc": delay_vol_tc if delay_vol_present else None,
                            "attack_tc": attack_vol_tc if attack_vol_present else None,
                            "hold_tc": hold_vol_tc if hold_vol_present else None,
                            "decay_tc": decay_vol_tc if decay_vol_present else None,
                            "sustain_cb": float(sustain_vol_cb) if sustain_vol_present else None,
                            "release_tc": release_vol_tc if release_vol_present else None,
                            "present": any(
                                (
                                    delay_vol_present,
                                    attack_vol_present,
                                    hold_vol_present,
                                    decay_vol_present,
                                    sustain_vol_present,
                                    release_vol_present,
                                )
                            ),
                        },
                        "mod_env": {
                            "delay_tc": delay_mod_tc if delay_mod_present else None,
                            "attack_tc": attack_mod_tc if attack_mod_present else None,
                            "hold_tc": hold_mod_tc if hold_mod_present else None,
                            "decay_tc": decay_mod_tc if decay_mod_present else None,
                            "sustain_cb": float(sustain_mod_cb) if sustain_mod_present else None,
                            "release_tc": release_mod_tc if release_mod_present else None,
                            "present": any(
                                (
                                    delay_mod_present,
                                    attack_mod_present,
                                    hold_mod_present,
                                    decay_mod_present,
                                    sustain_mod_present,
                                    release_mod_present,
                                )
                            ),
                        },
                        "fx_send": {
                            "chorus": min(100.0, max(0.0, chorus_send_raw / 10.0)),
                            "reverb": min(100.0, max(0.0, reverb_send_raw / 10.0)),
                            "present": chorus_present or reverb_present,
                        },
                        "exclusive_class": exclusive_class if exclusive_class is not None else 0,
                    }
                )

        if preset_zones:
            is_drum = int(preset.bank) == 128
            if not is_drum:
                drum_reason = _looks_like_drum(preset.name, preset_zones)
                if drum_reason:
                    is_drum = True
                    parse_log["warnings"].append(
                        {
                            "preset": preset.name,
                            "reason": "drum_heuristic",
                            "detail": drum_reason,
                        }
                    )
            presets.append(
                {
                    "name": preset.name,
                    "is_drum": is_drum,
                    "zones": preset_zones,
                }
            )

    return presets, parse_log
