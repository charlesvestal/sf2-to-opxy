import math

from sf2_to_opxy.audio import resample_linear, resample_sinc


def test_resample_linear_identity():
    pcm = [0, 100, -100, 50]
    assert resample_linear(pcm, 22050, 22050) == pcm


def test_resample_sinc_identity():
    pcm = [0, 100, -100, 50]
    assert resample_sinc(pcm, 22050, 22050) == pcm


def test_resample_sinc_downsample_preserves_length():
    """2:1 downsample should produce half as many samples."""
    pcm = list(range(1000))
    result = resample_sinc(pcm, 44100, 22050)
    assert len(result) == 500


def test_resample_sinc_attenuates_alias():
    """A tone above the target Nyquist should be attenuated when downsampling."""
    # Generate a 15kHz tone at 44100Hz (343 samples ≈ several cycles)
    n = 343
    freq = 15000
    pcm = [int(10000 * math.sin(2 * math.pi * freq * i / 44100)) for i in range(n)]

    # Downsample to 22050Hz -- 15kHz is above 11025Hz Nyquist, should be filtered
    sinc_out = resample_sinc(pcm, 44100, 22050)
    linear_out = resample_linear(pcm, 44100, 22050)

    # Measure RMS energy of each output
    def rms(data):
        return math.sqrt(sum(x * x for x in data) / max(len(data), 1))

    sinc_rms = rms(sinc_out)
    linear_rms = rms(linear_out)

    # Sinc should have significantly less aliased energy than linear
    assert sinc_rms < linear_rms * 0.5, (
        f"sinc RMS {sinc_rms:.1f} should be much less than linear RMS {linear_rms:.1f}"
    )
