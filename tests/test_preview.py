from sf2_to_opxy.preview import render_loop_preview


def test_render_loop_preview_repeats_loop_region():
    pcm = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    out = render_loop_preview(pcm, channels=1, loop_start=2, loop_end=5, iterations=2)
    assert out == [0, 1, 2, 3, 4, 2, 3, 4, 5, 6]
