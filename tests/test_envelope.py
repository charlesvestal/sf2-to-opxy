from sf2_to_opxy.converter import (
    map_fx_send,
    scale_attack_seconds,
    scale_release_seconds,
    timecents_to_seconds,
)


def test_timecents_to_seconds():
    assert round(timecents_to_seconds(0), 6) == 1.0
    assert round(timecents_to_seconds(1200), 6) == 2.0


def test_scale_attack_seconds():
    assert scale_attack_seconds(0.0) == 0
    assert scale_attack_seconds(10.0) == 32767
    assert 14000 <= scale_attack_seconds(2.0) <= 18000


def test_scale_release_seconds():
    assert scale_release_seconds(0.0) == 32767
    assert scale_release_seconds(30.0) == 0
    assert 15000 <= scale_release_seconds(4.0) <= 18000


def test_fx_send_mapping():
    assert 16000 <= map_fx_send(50.0) <= 17000
