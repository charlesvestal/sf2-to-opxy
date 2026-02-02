from sf2_to_opxy.audio import resample_linear


def test_resample_linear_identity():
    pcm = [0, 100, -100, 50]
    assert resample_linear(pcm, 22050, 22050) == pcm
