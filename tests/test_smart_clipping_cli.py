import subprocess
import sys

def test_smart_clipping_cli_flags():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "--smart-clipping" in result.stdout
    assert "--smart-clipping-mode" in result.stdout
    assert "--smart-snap-margin" in result.stdout
