from sf2_to_opxy.converter import _sanitize_name


def test_sanitize_name():
    assert _sanitize_name("My*Preset") == "My_Preset"
