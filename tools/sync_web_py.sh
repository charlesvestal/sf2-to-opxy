#!/usr/bin/env bash
# Copy Python sources from src/sf2_to_opxy/ into web/py/sf2_to_opxy/
# Run from the repository root: bash tools/sync_web_py.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SRC="$REPO_ROOT/src/sf2_to_opxy"
DST="$REPO_ROOT/web/py/sf2_to_opxy"

mkdir -p "$DST"

for f in __init__.py audio.py converter.py selection.py sf2_reader.py opxy_writer.py loop_variants.py preview.py; do
    if [ -f "$SRC/$f" ]; then
        cp "$SRC/$f" "$DST/$f"
        echo "  copied $f"
    else
        echo "  WARN: $SRC/$f not found, skipping"
    fi
done

echo "Sync complete: $DST"
