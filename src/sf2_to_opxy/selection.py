from __future__ import annotations

from typing import Dict, List

Zone = Dict[str, object]


def filter_zones_by_velocity(
    zones: List[Zone],
    velocities: List[int],
    mode: str = "keep",
) -> List[Zone]:
    if mode not in ("keep", "split"):
        raise ValueError("mode must be keep or split")
    kept: List[Zone] = []
    for zone in zones:
        vel_range = zone.get("vel_range", (0, 127))
        lo, hi = vel_range
        if any(lo <= v <= hi for v in velocities):
            kept.append(zone)
    return kept


def select_zones_for_88_keys(
    zones: List[Zone],
    max_zones: int,
    key_min: int,
    key_max: int,
) -> List[Zone]:
    if len(zones) <= max_zones:
        return list(zones)
    zones_sorted = sorted(zones, key=lambda z: z.get("root_key", 60))
    targets = [
        round(key_min + i * (key_max - key_min) / (max_zones - 1))
        for i in range(max_zones)
    ]
    selected: List[Zone] = []
    used = set()
    for target in targets:
        best_dist = None
        best_idx = None
        for idx, zone in enumerate(zones_sorted):
            if idx in used:
                continue
            root_key = int(zone.get("root_key", 60))
            dist = abs(root_key - target)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx is not None:
            used.add(best_idx)
            selected.append(zones_sorted[best_idx])
    return sorted(selected, key=lambda z: z.get("root_key", 60))


def assign_key_ranges(zones: List[Zone], key_min: int, key_max: int) -> List[Zone]:
    zones_sorted = sorted(zones, key=lambda z: z.get("root_key", 60))
    roots = [int(zone.get("root_key", 60)) for zone in zones_sorted]
    for i, zone in enumerate(zones_sorted):
        if i == 0:
            low_key = key_min
        else:
            low_key = (roots[i - 1] + roots[i]) // 2 + 1
        if i == len(roots) - 1:
            high_key = key_max
        else:
            high_key = (roots[i] + roots[i + 1]) // 2
        zone["lokey"] = max(key_min, min(low_key, key_max))
        zone["hikey"] = max(key_min, min(high_key, key_max))
    return zones_sorted
