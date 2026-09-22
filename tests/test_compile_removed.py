import subprocess
import sys

def test_compile_args_removed():
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "--compile" not in result.stdout
    assert "--crossfade" not in result.stdout
    assert "--segment-order" not in result.stdout
    assert "--fade-to-black" not in result.stdout
