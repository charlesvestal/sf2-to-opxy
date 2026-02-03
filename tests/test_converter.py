from sf2_to_opxy.converter import _sanitize_name, _pad_loop_for_interpolation


def test_sanitize_name():
    assert _sanitize_name("My*Preset") == "My_Preset"


def test_pad_loop_for_interpolation_basic():
    """Post-loop samples are replaced with loop-start data."""
    # 20 mono frames: values 0..19, loop from frame 4 to frame 14
    pcm = list(range(20))
    channels = 1
    loop_start = 4
    loop_end = 14

    result_pcm, result_fc = _pad_loop_for_interpolation(pcm, channels, loop_start, loop_end)

    # Frames 14..17 should now mirror frames 4..7
    for i in range(4):
        assert result_pcm[loop_end + i] == result_pcm[loop_start + i]
    assert result_fc == 20


def test_pad_loop_for_interpolation_extends_buffer():
    """When loop_end is at framecount, buffer is extended."""
    # 16 mono frames, loop ends at frame 16 (== framecount), no room for padding
    pcm = list(range(16))
    channels = 1
    loop_start = 4
    loop_end = 16

    result_pcm, result_fc = _pad_loop_for_interpolation(pcm, channels, loop_start, loop_end)

    # Buffer should have been extended by 4 frames
    assert result_fc == 20
    assert len(result_pcm) == 20
    # Padded frames should match loop start
    for i in range(4):
        assert result_pcm[loop_end + i] == result_pcm[loop_start + i]


def test_pad_loop_for_interpolation_short_loop():
    """No-op when loop is too short (loop_len <= pad_frames * 2)."""
    # Loop of length 6, pad_frames=4 -> 6 <= 8, should be a no-op
    pcm = list(range(20))
    channels = 1
    loop_start = 5
    loop_end = 11  # loop_len = 6

    original_pcm = list(pcm)
    result_pcm, result_fc = _pad_loop_for_interpolation(pcm, channels, loop_start, loop_end)

    assert result_pcm == original_pcm
    assert result_fc == 20


def test_pad_loop_for_interpolation_stereo():
    """Correctly handles multi-channel interleaved data."""
    # 20 stereo frames = 40 samples. Interleaved L/R pattern.
    channels = 2
    frames = 20
    pcm = []
    for f in range(frames):
        pcm.append(f * 10)       # left channel
        pcm.append(f * 10 + 1)   # right channel

    loop_start = 4
    loop_end = 14

    result_pcm, result_fc = _pad_loop_for_interpolation(pcm, channels, loop_start, loop_end)

    assert result_fc == 20
    # Check both channels are correctly copied
    for i in range(4):
        src_frame = loop_start + i
        dst_frame = loop_end + i
        for ch in range(channels):
            assert result_pcm[dst_frame * channels + ch] == result_pcm[src_frame * channels + ch]
