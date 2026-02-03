from __future__ import annotations

import copy
from typing import Dict, List, Tuple

from sf2_to_opxy.converter import apply_loop_end_offset


def _apply_offset_to_patch(patch: Dict[str, object], delta: int, offset_label: str) -> Dict[str, object]:
    out = copy.deepcopy(patch)
    name = out.get("name")
    if isinstance(name, str):
        out["name"] = f"{name} offset {offset_label}"

    regions = out.get("regions") or []
    for region in regions:
        if not region.get("loop.enabled"):
            continue
        try:
            loop_start = int(region.get("loop.start", 0))
            loop_end = int(region.get("loop.end", 0))
            framecount = int(region.get("framecount", 0))
        except (TypeError, ValueError):
            continue
        if loop_end <= loop_start or framecount <= 0:
            continue
        if delta:
            loop_end = apply_loop_end_offset(loop_start, loop_end, framecount, delta)
            region["loop.end"] = loop_end
    return out


def make_offset_variants(
    patch: Dict[str, object],
    offsets: List[int],
    base_offset: int = 0,
) -> List[Tuple[int, Dict[str, object]]]:
    variants: List[Tuple[int, Dict[str, object]]] = []
    for offset in offsets:
        delta = offset - base_offset
        label = f"{offset:+d}" if offset else "0"
        variants.append((offset, _apply_offset_to_patch(patch, delta, label)))
    return variants
