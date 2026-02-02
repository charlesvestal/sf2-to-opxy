from __future__ import annotations

from typing import List


def render_loop_preview(
    pcm: List[int],
    channels: int,
    loop_start: int,
    loop_end: int,
    iterations: int,
    tail_frames: int = 2,
) -> List[int]:
    if channels <= 0:
        raise ValueError("channels must be positive")
    framecount = len(pcm) // channels
    loop_start = max(0, min(loop_start, framecount))
    loop_end = max(loop_start, min(loop_end, framecount))
    if loop_end <= loop_start or iterations <= 0:
        return list(pcm)

    pre = pcm[: loop_start * channels]
    loop = pcm[loop_start * channels: loop_end * channels]
    tail_end = min(framecount, loop_end + max(0, tail_frames))
    tail = pcm[loop_end * channels: tail_end * channels]
    return pre + loop * iterations + tail
