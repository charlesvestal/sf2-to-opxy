from __future__ import annotations

import io
import wave
from typing import List


def resample_linear(samples: List[int], src_rate: int, dst_rate: int) -> List[int]:
    if src_rate == dst_rate:
        return list(samples)
    ratio = dst_rate / src_rate
    out_len = int(len(samples) * ratio)
    out: List[int] = []
    for i in range(out_len):
        src_pos = i / ratio
        i0 = int(src_pos)
        i1 = min(i0 + 1, len(samples) - 1)
        frac = src_pos - i0
        val = samples[i0] * (1 - frac) + samples[i1] * frac
        out.append(int(round(val)))
    return out


def write_wav(samples: List[int], sample_rate: int, channels: int, bit_depth: int) -> bytes:
    if bit_depth != 16:
        raise ValueError("Only 16-bit output supported")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            if sample > 32767:
                sample = 32767
            elif sample < -32768:
                sample = -32768
            frames += int(sample).to_bytes(2, byteorder="little", signed=True)
        wf.writeframes(frames)
    return buf.getvalue()
