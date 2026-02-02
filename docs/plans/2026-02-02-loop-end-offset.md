# Loop End Offset + Preview WAVs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a loop-end offset option to SF2 conversion and generate Choir Aahs loop-preview WAVs for offsets -1/0/+1.

**Architecture:** Introduce a small helper in the converter to apply a loop-end offset with clamping, wire it through CLI, and create a preview renderer that builds short WAVs from the raw sample with a fixed number of loop iterations. Tests validate the helper and preview logic before implementation.

**Tech Stack:** Python 3, pytest, existing sf2_to_opxy modules (converter, audio).

### Task 0: Align envelope tests to calibrated mapping

**Files:**
- Modify: `tests/test_envelope.py`

**Step 1: Write the failing test**

```python
# Adjust expected values to calibrated mapping
assert scale_attack_seconds(360.0) == 32724
assert 29000 <= scale_release_seconds(4.0) <= 30000
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_envelope.py`
Expected: FAIL on attack/release expectations

**Step 3: Write minimal implementation**

_No production code change needed; update tests only._

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_envelope.py`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_envelope.py
git commit -m "test: align envelope expectations to calibrated curve"
```

### Task 1: Loop-end offset helper + CLI wiring

**Files:**
- Create: `tests/test_loop_offsets.py`
- Modify: `src/sf2_to_opxy/converter.py`
- Modify: `src/sf2_to_opxy/cli.py`
- Modify: `README.md`

**Step 1: Write the failing test**

```python
from sf2_to_opxy.converter import apply_loop_end_offset

def test_apply_loop_end_offset_subtracts_one():
    assert apply_loop_end_offset(loop_start=10, loop_end=20, framecount=30, offset=-1) == 19

def test_apply_loop_end_offset_clamps_to_min():
    assert apply_loop_end_offset(loop_start=10, loop_end=11, framecount=30, offset=-5) == 11

def test_apply_loop_end_offset_clamps_to_max():
    assert apply_loop_end_offset(loop_start=10, loop_end=29, framecount=30, offset=5) == 30
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_loop_offsets.py`
Expected: FAIL (function missing)

**Step 3: Write minimal implementation**

```python
# converter.py

def apply_loop_end_offset(loop_start: int, loop_end: int, framecount: int, offset: int) -> int:
    adjusted = loop_end + offset
    adjusted = max(loop_start + 1, min(adjusted, framecount))
    return adjusted
```

Wire into `convert_presets` with new parameter `loop_end_offset` (default 0) and apply after resampling scaling and before zero-crossing/crossfade.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_loop_offsets.py`
Expected: PASS

**Step 5: Update CLI + README**

- Add `--loop-end-offset` to CLI and pass through.
- Document in README under loop options.

**Step 6: Run full test suite**

Run: `pytest`
Expected: PASS

**Step 7: Commit**

```bash
git add tests/test_loop_offsets.py src/sf2_to_opxy/converter.py src/sf2_to_opxy/cli.py README.md
git commit -m "feat: add loop end offset option"
```

### Task 2: Loop preview renderer + Choir Aahs outputs

**Files:**
- Create: `src/sf2_to_opxy/preview.py`
- Create: `tests/test_preview.py`
- Create: `tools/render_loop_preview.py`
- Modify: `README.md`

**Step 1: Write the failing test**

```python
from sf2_to_opxy.preview import render_loop_preview

def test_render_loop_preview_repeats_loop_region():
    pcm = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    out = render_loop_preview(pcm, channels=1, loop_start=2, loop_end=5, iterations=2)
    # pre-loop 0..1, then loop region 2..4 repeated twice, then tail 5..6
    assert out == [0, 1, 2, 3, 4, 2, 3, 4, 5, 6]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_preview.py`
Expected: FAIL (function missing)

**Step 3: Write minimal implementation**

```python
# preview.py

def render_loop_preview(pcm, channels, loop_start, loop_end, iterations, tail_frames=2):
    framecount = len(pcm) // channels
    pre = pcm[: loop_start * channels]
    loop = pcm[loop_start * channels: loop_end * channels]
    tail_end = min(framecount, loop_end + tail_frames)
    tail = pcm[loop_end * channels: tail_end * channels]
    return pre + loop * iterations + tail
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_preview.py`
Expected: PASS

**Step 5: Add tool script + README**

- `tools/render_loop_preview.py` loads SF2, finds preset by name, extracts sample + loop points, applies offsets -1/0/+1, writes WAVs + manifest.
- Document usage in README.

**Step 6: Run full test suite**

Run: `pytest`
Expected: PASS

**Step 7: Commit**

```bash
git add src/sf2_to_opxy/preview.py tools/render_loop_preview.py tests/test_preview.py README.md
git commit -m "feat: add loop preview renderer"
```

### Task 3: Generate Choir Aahs previews + SNES re-run

**Files:**
- Outputs only (no repo changes)

**Step 1: Generate previews**

Run:
```
. .venv/bin/activate
python tools/render_loop_preview.py \
  --sf2 "/Users/charlesvestal/Desktop/Move-Everything/SF2_SoundFonts/Super_Nintendo_Unofficial_update.sf2" \
  --preset "Choir Aahs" \
  --out "/Volumes/ExtFS/charlesvestal/Downloads/op-xy/converted/SF2_SoundFonts/SNES/Choir_Aahs_previews"
```
Expected: 3 WAVs + manifest.json

**Step 2: Re-run SNES conversion with loop-end offset -1**

Run:
```
. .venv/bin/activate
python sf2_to_opxy.py \
  "/Users/charlesvestal/Desktop/Move-Everything/SF2_SoundFonts/Super_Nintendo_Unofficial_update.sf2" \
  --out "/Volumes/ExtFS/charlesvestal/Downloads/op-xy/converted/SF2_SoundFonts/SNES" \
  --no-resample \
  --loop-crossfade-percent 0 \
  --loop-end-offset -1
```
Expected: updated `Choir_Aahs.preset` with loop.end = 2970

---

Plan complete and saved to `docs/plans/2026-02-02-loop-end-offset.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
