import subprocess
import sys


def test_help_runs():
    result = subprocess.run(
        [sys.executable, "sf2_to_opxy.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "SF2 to OP-XY" in result.stdout
