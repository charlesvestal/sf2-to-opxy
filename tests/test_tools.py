import os
import subprocess
import sys
from pathlib import Path


def test_render_loop_preview_help_runs():
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "tools/render_loop_preview.py", "--help"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
