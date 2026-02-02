from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT_DIR / "src"
WEB_PY_ROOT = ROOT_DIR / "web" / "public" / "py"


def collect_py_files() -> List[str]:
    package_dir = SRC_ROOT / "sf2_to_opxy"
    files = [path for path in package_dir.rglob("*.py") if path.is_file()]
    return sorted(str(path.relative_to(SRC_ROOT)) for path in files)


def write_manifest() -> List[str]:
    WEB_PY_ROOT.mkdir(parents=True, exist_ok=True)
    package_dir = SRC_ROOT / "sf2_to_opxy"
    dest_pkg_dir = WEB_PY_ROOT / "sf2_to_opxy"
    if dest_pkg_dir.exists():
        shutil.rmtree(dest_pkg_dir)
    dest_pkg_dir.mkdir(parents=True, exist_ok=True)

    files = collect_py_files()
    for rel_path in files:
        src_path = SRC_ROOT / rel_path
        dest_path = WEB_PY_ROOT / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)

    manifest = {
        "files": files + ["web_entry.py"],
    }
    manifest_path = WEB_PY_ROOT / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest["files"]


def main() -> int:
    write_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
