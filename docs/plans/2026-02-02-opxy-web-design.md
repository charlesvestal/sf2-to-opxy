# OP-XY Web Converter (GitHub Pages) Design

**Goal:** Provide a browser-based SF2 to OP-XY converter hosted on GitHub Pages, using Pyodide in a Web Worker with OPFS storage for large files (200-500MB).

## Architecture

- **UI (main thread):** Single-page static app (Vite or plain static) that accepts SF2 files, renders all CLI options, shows progress/logs, and offers a ZIP download.
- **Worker (Pyodide):** Runs Python conversion in a Web Worker to keep the UI responsive. Installs `sf2utils` and uses the existing `sf2_to_opxy` modules.
- **Storage (OPFS):** Store input SF2 in the Origin Private File System when available. Copy into Pyodide FS in chunks to reduce memory spikes.
- **Output:** Write converted presets to a temporary directory in Pyodide FS. Stream files back to the main thread and build a ZIP incrementally for download.

## Data Flow

1. User selects SF2 file(s) and options (full CLI parity).
2. UI writes file to OPFS (fallback to memory if OPFS unavailable).
3. Worker loads Pyodide, installs dependencies, and runs Python entrypoint with options.
4. Worker streams output files back with progress events.
5. UI builds ZIP and provides download link.

## UI / Options

- Options map 1:1 with CLI flags (velocities, velocity mode, resample, loop end offset, zero crossing, playmode, force drum/instrument, etc.).
- Defaults match CLI defaults to avoid surprises.
- Progress panel shows stages (load, parse, convert, zip) plus per-preset counts.

## Error Handling

- Worker sends structured errors (stage, message, traceback summary) to UI.
- If OPFS unavailable, show warning and continue in memory.
- Provide retry if Pyodide initialization fails.

## Hosting (GitHub Pages)

- Build static output to `dist/`.
- GitHub Actions workflow builds on each commit to `main` and deploys to Pages.
- Keep `.nojekyll` if needed to prevent Jekyll processing.

## Testing

- Keep existing Python tests.
- Add JS unit tests for option serialization and Worker message schema.
- Provide a manual browser verification checklist for one medium SF2.
