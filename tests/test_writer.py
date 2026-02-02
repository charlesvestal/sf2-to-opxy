from sf2_to_opxy.opxy_writer import ensure_preset_dir


def test_ensure_preset_dir_suffix(tmp_path):
    out = ensure_preset_dir(tmp_path / "MyPreset")
    assert str(out).endswith(".preset")
