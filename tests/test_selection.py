from sf2_to_opxy.selection import assign_key_ranges, select_zones_for_88_keys


def test_select_evenly_spaced():
    zones = [{"root_key": k} for k in range(21, 109)]
    selected = select_zones_for_88_keys(zones, 24, 21, 108)
    assert len(selected) == 24


def test_assign_key_ranges_bounds():
    zones = [{"root_key": 40}, {"root_key": 60}, {"root_key": 80}]
    assigned = assign_key_ranges(zones, 21, 108)
    assert assigned[0]["lokey"] == 21
    assert assigned[-1]["hikey"] == 108
