from __future__ import annotations

import io
import math
import wave
from typing import List

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


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


def _blackman_window(n: int) -> List[float]:
    """Generate a Blackman window of length *n*."""
    if n <= 1:
        return [1.0]
    w: List[float] = []
    for i in range(n):
        w.append(0.42 - 0.5 * math.cos(2 * math.pi * i / (n - 1))
                 + 0.08 * math.cos(4 * math.pi * i / (n - 1)))
    return w


def _fir_lowpass_kernel(num_taps: int, cutoff_fraction: float) -> List[float]:
    """Design a windowed-sinc FIR lowpass filter kernel.

    *cutoff_fraction* is the cutoff as a fraction of the sample rate (0-0.5).
    Returns a kernel of length ``2 * num_taps + 1``.
    """
    n = 2 * num_taps + 1
    window = _blackman_window(n)
    kernel: List[float] = []
    pi = math.pi
    fc2 = 2.0 * cutoff_fraction
    for i in range(n):
        x = i - num_taps
        if x == 0:
            kernel.append(fc2 * window[i])
        else:
            kernel.append(math.sin(pi * fc2 * x) / (pi * x) * window[i])
    s = sum(kernel)
    if s != 0:
        kernel = [k / s for k in kernel]
    return kernel


def _resample_sinc_numpy(
    samples: List[int], src_rate: int, dst_rate: int, num_taps: int
) -> List[int]:
    """Resample using numpy for speed."""
    arr = np.array(samples, dtype=np.float64)
    n_in = len(samples)
    ratio = dst_rate / src_rate

    # Integer-ratio downsampling fast path
    if src_rate > dst_rate and src_rate % dst_rate == 0:
        factor = src_rate // dst_rate
        cutoff = 0.5 / factor * 0.9
        kernel = _fir_lowpass_kernel(num_taps * factor, cutoff)
        kernel_np = np.array(kernel, dtype=np.float64)
        filtered = np.convolve(arr, kernel_np, mode="same")
        decimated = filtered[::factor]
        return np.clip(np.round(decimated), -32768, 32767).astype(np.int64).tolist()

    # General case
    out_len = int(n_in * ratio)
    if out_len == 0:
        return []

    if ratio < 1.0:
        cutoff = ratio
    else:
        cutoff = 1.0

    half = int(num_taps / cutoff)
    kernel_len = 2 * half + 1
    window = np.blackman(kernel_len)

    out_indices = np.arange(out_len)
    src_positions = out_indices / ratio
    centers = src_positions.astype(np.int64)
    fracs = src_positions - centers

    out = np.zeros(out_len, dtype=np.float64)
    wsum = np.zeros(out_len, dtype=np.float64)

    for j in range(-half, half + 1):
        indices = centers + j
        valid = (indices >= 0) & (indices < n_in)
        x = (j - fracs) * cutoff
        px = np.pi * x
        with np.errstate(divide="ignore", invalid="ignore"):
            sinc = np.where(np.abs(px) > 1e-10, np.sin(px) / px, 1.0)
        w = sinc * window[j + half] * cutoff
        w_valid = np.where(valid, w, 0.0)
        src_vals = np.where(valid, arr[np.clip(indices, 0, n_in - 1)], 0.0)
        out += src_vals * w_valid
        wsum += w_valid

    nonzero = wsum != 0.0
    out[nonzero] /= wsum[nonzero]

    return np.clip(np.round(out), -32768, 32767).astype(np.int64).tolist()


def _resample_sinc_pure(
    samples: List[int], src_rate: int, dst_rate: int, num_taps: int
) -> List[int]:
    """Pure-Python windowed-sinc resampler (fallback when numpy unavailable)."""
    n_in = len(samples)
    ratio = dst_rate / src_rate

    # Integer-ratio downsampling fast path
    if src_rate > dst_rate and src_rate % dst_rate == 0:
        factor = src_rate // dst_rate
        cutoff = 0.5 / factor * 0.9
        kernel = _fir_lowpass_kernel(num_taps * factor, cutoff)
        half = len(kernel) // 2
        out: List[int] = []
        for i in range(0, n_in, factor):
            acc = 0.0
            j_lo = max(0, i - half)
            j_hi = min(n_in - 1, i + half)
            for j in range(j_lo, j_hi + 1):
                acc += samples[j] * kernel[half + (j - i)]
            v = int(round(acc))
            if v > 32767:
                v = 32767
            elif v < -32768:
                v = -32768
            out.append(v)
        return out

    # General case
    out_len = int(n_in * ratio)
    if out_len == 0:
        return []

    if ratio < 1.0:
        cutoff = ratio
    else:
        cutoff = 1.0

    half = int(num_taps / cutoff)
    kernel_len = 2 * half + 1
    window = _blackman_window(kernel_len)
    win_cutoff = [w * cutoff for w in window]

    pi = math.pi
    out = []
    last_n = n_in - 1
    for i in range(out_len):
        src_pos = i / ratio
        center = int(src_pos)
        frac = src_pos - center

        j_lo = max(-half, -center)
        j_hi = min(half, last_n - center)

        acc = 0.0
        wsum = 0.0
        for j in range(j_lo, j_hi + 1):
            x = (j - frac) * cutoff
            px = pi * x
            if px > 1e-10 or px < -1e-10:
                s = math.sin(px) / px
            else:
                s = 1.0
            w = s * win_cutoff[j + half]
            acc += samples[center + j] * w
            wsum += w

        if wsum != 0.0:
            acc /= wsum

        if acc > 32767:
            acc = 32767
        elif acc < -32768:
            acc = -32768
        out.append(int(round(acc)))

    return out


def resample_sinc(
    samples: List[int], src_rate: int, dst_rate: int, num_taps: int = 16
) -> List[int]:
    """Resample using a windowed-sinc interpolation filter.

    Uses numpy when available for speed, otherwise falls back to pure Python.
    Applies proper anti-aliasing when downsampling.
    """
    if src_rate == dst_rate:
        return list(samples)
    if _HAS_NUMPY:
        return _resample_sinc_numpy(samples, src_rate, dst_rate, num_taps)
    return _resample_sinc_pure(samples, src_rate, dst_rate, num_taps)


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
