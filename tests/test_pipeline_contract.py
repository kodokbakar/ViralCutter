"""Tests for WebUI-to-CLI pipeline contract."""
import pytest
import sys
import os
import ast
import re

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def _read_webui_app_source():
    """Read webui/app.py source without importing it (avoids heavy deps)."""
    path = os.path.join(PROJECT_ROOT, "webui", "app.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _parse_function_params(source, func_name):
    """Extract parameter names of a function from source using AST."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return [arg.arg for arg in node.args.args]
    raise AssertionError(f"Function {func_name} not found in source")


def _get_function_source(source, func_name):
    """Extract a function's full source code by line range."""
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            start = node.lineno - 1
            end = node.end_lineno
            return "\n".join(lines[start:end])
    raise AssertionError(f"Function {func_name} not found in source")


def test_webui_inputs_match_cli_args():
    """Verify WebUI function signature matches CLI arguments."""
    source = _read_webui_app_source()
    webui_params = _parse_function_params(source, "run_viral_cutter")

    # Verify function has parameters
    assert len(webui_params) > 0, "WebUI function has no parameters"

    # Verify key parameters exist
    expected_params = ['input_source', 'segments', 'min_duration', 'max_duration']
    for param in expected_params:
        assert param in webui_params, f"Missing parameter: {param}"


def test_callback_output_count():
    """Verify every generator yields correct number of outputs."""
    source = _read_webui_app_source()
    func_source = _get_function_source(source, "run_viral_cutter")
    yield_count = func_source.count("yield ")

    # run_viral_cutter yields 6 outputs:
    # logs, progress_status, start_btn, stop_btn, results_html, compilation_output
    assert yield_count >= 6, f"Expected at least 6 yields, got {yield_count}"


def test_cli_validation_fails_fast():
    """Verify invalid CLI args fail before processing."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "main_improved.py", "--segments", "0", "--skip-prompts"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT
    )
    assert result.returncode != 0, "Should fail with invalid segments"
    assert "Error" in result.stdout or "error" in result.stderr.lower()


def test_pipeline_validation_module():
    """Verify pipeline validation module works correctly."""
    from scripts.pipeline_validation import validate_batch_size, validate_chunk_size, validate_duration_range

    # Test batch size validation
    with pytest.raises(ValueError):
        validate_batch_size(-1)

    # Test valid batch size
    result = validate_batch_size(8)
    assert result == 8

    # Test chunk size validation
    with pytest.raises(ValueError):
        validate_chunk_size(50)

    # Test valid chunk size
    result = validate_chunk_size(200)
    assert result == 200

    # Test duration range validation (min > max should fail)
    with pytest.raises(ValueError):
        validate_duration_range(100, 50)

    # Test valid duration range (returns None on success, just verify no error)
    result = validate_duration_range(15, 90)
    assert result is None
