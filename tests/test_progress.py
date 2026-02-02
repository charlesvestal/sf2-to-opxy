from sf2_to_opxy.converter import convert_presets


def _base_zone():
    return {
        "root_key": 60,
        "key_range": (60, 60),
        "vel_range": (0, 127),
        "sample": {"name": "s1", "data": [0] * 16, "rate": 22050, "channels": 1},
        "loop_start": 0,
        "loop_end": 0,
        "loop_enabled": False,
        "loop_on_release": False,
        "amp_env": {"present": False},
        "mod_env": {"present": False},
        "fx_send": {"chorus": 0.0, "reverb": 0.0, "present": False},
        "exclusive_class": 0,
        "tune_cents": 0,
        "initial_atten_cb": 0,
    }


def test_progress_callback_reports_preset_count():
    presets = [
        {"name": "One", "is_drum": False, "zones": [_base_zone()]},
        {"name": "Two", "is_drum": False, "zones": [_base_zone()]},
    ]
    seen = []

    def progress(current, total, name):
        seen.append((current, total, name))

    convert_presets(
        presets,
        out_root="/tmp",
        velocities=[101],
        velocity_mode="keep",
        resample_rate=22050,
        bit_depth=16,
        resample=False,
        dry_run=True,
        progress_callback=progress,
    )

    assert seen == [(1, 2, "One"), (2, 2, "Two")]
