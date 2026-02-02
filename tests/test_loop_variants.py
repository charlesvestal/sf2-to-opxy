from sf2_to_opxy.loop_variants import make_offset_variants


def test_make_offset_variants_applies_base_offset_and_suffix():
    patch = {
        "name": "Test",
        "regions": [
            {
                "loop.enabled": True,
                "loop.start": 10,
                "loop.end": 20,
                "framecount": 30,
            }
        ],
    }
    variants = make_offset_variants(patch, offsets=[-1, 0, 1], base_offset=-1)
    out = {offset: data for offset, data in variants}

    assert out[-1]["name"] == "Test offset -1"
    assert out[0]["name"] == "Test offset 0"
    assert out[1]["name"] == "Test offset +1"

    assert out[-1]["regions"][0]["loop.end"] == 20
    assert out[0]["regions"][0]["loop.end"] == 21
    assert out[1]["regions"][0]["loop.end"] == 22
