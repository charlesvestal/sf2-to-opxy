from sf2_to_opxy.converter import apply_loop_end_offset


def test_apply_loop_end_offset_subtracts_one():
    assert apply_loop_end_offset(loop_start=10, loop_end=20, framecount=30, offset=-1) == 19


def test_apply_loop_end_offset_clamps_to_min():
    assert apply_loop_end_offset(loop_start=10, loop_end=11, framecount=30, offset=-5) == 11


def test_apply_loop_end_offset_clamps_to_max():
    assert apply_loop_end_offset(loop_start=10, loop_end=29, framecount=30, offset=5) == 30
