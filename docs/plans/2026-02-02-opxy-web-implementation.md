# OP-XY Web Converter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a GitHub Pages–hosted browser app that converts SF2 → OP-XY using Pyodide in a Web Worker with OPFS for large files, exposing all CLI options.

**Architecture:** Static Vite app in `web/` with a module worker. Worker loads Pyodide + `sf2utils`, pulls python sources from `web/public/py/` (generated manifest), runs a Python entrypoint to perform conversion, then streams output files to the UI which zips them for download. GitHub Actions builds and deploys to Pages.

**Tech Stack:** Vite + TypeScript + fflate (zip), Pyodide, sf2utils, GitHub Pages actions.

### Task 1: Scaffold web app + base tests

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.ts`
- Create: `web/index.html`
- Create: `web/src/main.ts`
- Create: `web/src/styles.css`
- Create: `web/public/.nojekyll`
- Create: `web/tsconfig.json`
- Create: `web/vitest.config.ts`
- Create: `web/src/__tests__/options.test.ts`

**Step 1: Write the failing test**

```ts
import { buildOptions } from '../options';

test('buildOptions maps defaults', () => {
  const opts = buildOptions({});
  expect(opts.velocities).toEqual([101]);
  expect(opts.resampleRate).toBe(22050);
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix web test`
Expected: FAIL (module missing)

**Step 3: Minimal implementation**

Create `web/src/options.ts` with `buildOptions()` mapping UI inputs to a typed options object.

**Step 4: Run test to verify it passes**

Run: `npm --prefix web test`
Expected: PASS

**Step 5: Commit**

```bash
git add web
git commit -m "feat: scaffold web app"
```

### Task 2: Python payload + manifest generator

**Files:**
- Create: `web/public/py/web_entry.py`
- Create: `tools/gen_web_py_manifest.py`
- Create: `web/public/py/manifest.json`
- Modify: `web/package.json` (prebuild hook)
- Modify: `README.md`

**Step 1: Write the failing test**

```python
# tests/test_web_manifest.py
from tools.gen_web_py_manifest import collect_py_files

def test_collect_py_files_includes_converter():
    files = collect_py_files()
    assert any(path.endswith('converter.py') for path in files)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_manifest.py`
Expected: FAIL (module missing)

**Step 3: Minimal implementation**

- `tools/gen_web_py_manifest.py` copies `src/sf2_to_opxy/**` into `web/public/py/sf2_to_opxy` and writes `manifest.json` listing relative paths.
- `web_entry.py` exposes `run_conversion(sf2_path, out_dir, options_json)` that calls `read_soundfont`, `extract_presets`, `convert_presets`, and writes logs to `out_dir`.
- Add `prebuild` to run the manifest generator.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_manifest.py`
Expected: PASS

**Step 5: Commit**

```bash
git add tools/gen_web_py_manifest.py web/public/py README.md tests/test_web_manifest.py web/package.json
git commit -m "feat: add web python payload"
```

### Task 3: Worker with Pyodide + OPFS

**Files:**
- Create: `web/src/worker.ts`
- Modify: `web/src/main.ts`
- Create: `web/src/__tests__/worker-protocol.test.ts`

**Step 1: Write the failing test**

```ts
import { encodeMessage } from '../worker-protocol';

test('encodeMessage builds init payload', () => {
  const msg = encodeMessage('init', { pyodideUrl: 'x' });
  expect(msg.type).toBe('init');
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix web test`
Expected: FAIL (module missing)

**Step 3: Minimal implementation**

- `worker.ts`: loads `pyodide.mjs`, installs `sf2utils` via `micropip`, loads python files from `public/py/manifest.json`, writes input SF2 into pyodide FS in chunks, runs `web_entry.run_conversion`, then streams output files back.
- Implement OPFS storage when available; fallback to memory.
- Define `worker-protocol.ts` with typed message structures.

**Step 4: Run test to verify it passes**

Run: `npm --prefix web test`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src/worker.ts web/src/main.ts web/src/worker-protocol.ts web/src/__tests__/worker-protocol.test.ts
git commit -m "feat: add pyodide worker"
```

### Task 4: ZIP streaming + UI

**Files:**
- Modify: `web/src/main.ts`
- Modify: `web/index.html`
- Modify: `web/src/styles.css`
- Add dependency: `fflate`

**Step 1: Write the failing test**

```ts
import { zipStream } from '../zip';

test('zipStream appends files', () => {
  const z = zipStream();
  z.addFile('a.txt', new Uint8Array([1,2]));
  expect(z.count()).toBe(1);
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix web test`
Expected: FAIL

**Step 3: Minimal implementation**

- Implement `zip.ts` using fflate's streaming Zip.
- Update UI to show progress + logs + download link.

**Step 4: Run test to verify it passes**

Run: `npm --prefix web test`
Expected: PASS

**Step 5: Commit**

```bash
git add web/src zip files web/index.html web/src/styles.css web/package.json
git commit -m "feat: add streaming zip + UI"
```

### Task 5: GitHub Pages deployment workflow

**Files:**
- Create: `.github/workflows/pages.yml`
- Modify: `web/vite.config.ts`
- Modify: `README.md`

**Step 1: Write the failing test**

_No automated test; manual check in workflow._

**Step 2: Minimal implementation**

- Use `actions/deploy-pages` with build output `web/dist`.
- Set Vite `base` using repo name for GH Pages.

**Step 3: Manual verification**

Run: `npm --prefix web run build` locally and confirm `web/dist` has `index.html` and `assets/`.

**Step 4: Commit**

```bash
git add .github/workflows/pages.yml web/vite.config.ts README.md
git commit -m "ci: add pages deploy"
```

---

Plan complete and saved to `docs/plans/2026-02-02-opxy-web-implementation.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
