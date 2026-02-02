import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gen_web_py_manifest import collect_py_files


def test_collect_py_files_includes_converter():
    files = collect_py_files()
    assert any(path.endswith('converter.py') for path in files)
