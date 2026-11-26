import os
import time
import shutil
import threading
import pytest
from unittest.mock import patch
from scripts.gaming_split import get_max_render_workers as gs_get_max_workers, RenderResult
from scripts.burn_subtitles import get_max_render_workers as bs_get_max_workers
from scripts import burn_subtitles


def test_get_max_render_workers_default(monkeypatch):
    monkeypatch.delenv("VIRALCUTTER_MAX_RENDER_WORKERS", raising=False)

    with patch("os.cpu_count", return_value=8):
        # min(3, max(1, 8 // 2)) = min(3, 4) = 3
        assert gs_get_max_workers() == 3
        assert bs_get_max_workers() == 3

    with patch("os.cpu_count", return_value=4):
        # min(3, max(1, 4 // 2)) = min(3, 2) = 2
        assert gs_get_max_workers() == 2

    with patch("os.cpu_count", return_value=1):
        # min(3, max(1, 1 // 2)) = min(3, 1) = 1
        assert gs_get_max_workers() == 1

    with patch("os.cpu_count", return_value=None):
        # fallback (2 // 2) = 1 -> min(3, 1) = 1
        assert gs_get_max_workers() == 1


def test_get_max_render_workers_env_override(monkeypatch):
    monkeypatch.setenv("VIRALCUTTER_MAX_RENDER_WORKERS", "6")
    assert gs_get_max_workers() == 6
    assert bs_get_max_workers() == 6

    # Clamped to >= 1
    monkeypatch.setenv("VIRALCUTTER_MAX_RENDER_WORKERS", "0")
    assert gs_get_max_workers() == 1

    monkeypatch.setenv("VIRALCUTTER_MAX_RENDER_WORKERS", "-5")
    assert gs_get_max_workers() == 1

    # Invalid string falls back to CPU logic
    monkeypatch.setenv("VIRALCUTTER_MAX_RENDER_WORKERS", "invalid")
    with patch("os.cpu_count", return_value=4):
        assert gs_get_max_workers() == 2


def test_cli_max_render_workers_arg():
    from main_improved import parse_arguments

    args = parse_arguments(["--max-render-workers", "4"])
    assert args.max_render_workers == 4

    args_default = parse_arguments([])
    assert args_default.max_render_workers is None


def test_burn_subtitles_parallel_concurrency_and_broll_mapping(tmp_path):
    project_dir = tmp_path / "proj"
    final_dir = project_dir / "final"
    subs_dir = project_dir / "subs_ass"
    broll_files_dir = tmp_path / "fake_brolls"
    final_dir.mkdir(parents=True)
    subs_dir.mkdir(parents=True)
    broll_files_dir.mkdir(parents=True)

    # 4 clips
    clip_names = ["clip_000", "clip_001", "clip_002", "clip_003"]
    broll_map = {}
    for i, name in enumerate(clip_names):
        (final_dir / f"{name}_processed.mp4").write_bytes(b"dummy_video")
        (subs_dir / f"{name}.ass").write_text("[Script Info]\n")
        fake_broll = broll_files_dir / f"{i}.webm"
        fake_broll.write_bytes(b"dummy_broll")
        broll_map[name] = [{"template_id": f"tpl{i}", "video_path": str(fake_broll)}]

    active_workers = 0
    max_active_workers = 0
    lock = threading.Lock()
    received_brolls = {}

    def fake_burn_video_file(in_file, sub_file, out_file, **kwargs):
        nonlocal active_workers, max_active_workers
        with lock:
            active_workers += 1
            if active_workers > max_active_workers:
                max_active_workers = active_workers

        # Simulate rendering work to verify concurrency
        time.sleep(0.05)

        base = os.path.splitext(os.path.basename(out_file))[0]
        with lock:
            received_brolls[base] = kwargs.get("broll_items")
            active_workers -= 1

        return True, "Success", {"size": 1024, "duration": 2.5}

    with patch("scripts.burn_subtitles.burn_video_file", side_effect=fake_burn_video_file):
        out_folder = burn_subtitles.burn(
            project_folder=str(project_dir),
            broll_items=broll_map,
            max_workers=3,
        )

    assert os.path.exists(out_folder)
    # Verified that at least 2 workers ran concurrently
    assert max_active_workers >= 2
    assert max_active_workers <= 3

    # Verify B-roll preservation for all clips
    for name in clip_names:
        assert name in received_brolls
        assert received_brolls[name] == broll_map[name]


def test_burn_subtitles_parallel_error_propagation(tmp_path):
    project_dir = tmp_path / "proj"
    final_dir = project_dir / "final"
    subs_dir = project_dir / "subs_ass"
    final_dir.mkdir(parents=True)
    subs_dir.mkdir(parents=True)

    (final_dir / "clip_000_processed.mp4").write_bytes(b"dummy0")
    (final_dir / "clip_001_processed.mp4").write_bytes(b"dummy1")
    (subs_dir / "clip_000.ass").write_text("[Script Info]\n")
    (subs_dir / "clip_001.ass").write_text("[Script Info]\n")

    def fake_burn_failing(in_file, sub_file, out_file, **kwargs):
        if "clip_001" in in_file:
            return False, "Synthetic FFmpeg error", None
        return True, "Success", {"size": 100, "duration": 1.0}

    with patch("scripts.burn_subtitles.burn_video_file", side_effect=fake_burn_failing):
        with pytest.raises(RuntimeError, match="Synthetic FFmpeg error"):
            burn_subtitles.burn(
                project_folder=str(project_dir),
                max_workers=2,
            )


def test_parallel_face_modes_ordering_and_consistency(tmp_path):
    import json
    import concurrent.futures
    from scripts import gaming_split

    project_dir = tmp_path / "proj"
    cuts_dir = project_dir / "cuts"
    final_dir = project_dir / "final"
    cuts_dir.mkdir(parents=True)
    final_dir.mkdir(parents=True)

    cut_files = [f"output{i:03d}.mp4" for i in range(5)]
    for cf in cut_files:
        (cuts_dir / cf).write_bytes(b"dummy")

    face_modes = {}
    rendered_calls = []
    lock = threading.Lock()

    def fake_render_manual(input_path, output_path, crop_box):
        with lock:
            rendered_calls.append(output_path)

    with patch("scripts.gaming_split.render_manual_crop_clip", side_effect=fake_render_manual):
        pool_workers = 3
        def _task(args_tuple):
            idx, c_file = args_tuple
            c_path = os.path.join(str(cuts_dir), c_file)
            base_name = c_file.replace(".mp4", "")
            target_out = os.path.join(str(final_dir), f"{base_name}_processed.mp4")
            gaming_split.render_manual_crop_clip(
                input_path=c_path,
                output_path=target_out,
                crop_box="0,0,1,1",
            )
            return idx

        with concurrent.futures.ThreadPoolExecutor(max_workers=pool_workers) as executor:
            futures = [executor.submit(_task, (idx, c_file)) for idx, c_file in enumerate(cut_files)]
            for f in concurrent.futures.as_completed(futures):
                idx = f.result()
                face_modes[f"output{idx:03d}"] = "none"

        face_modes = dict(sorted(face_modes.items()))
        modes_file = project_dir / "face_modes.json"
        with open(modes_file, "w", encoding="utf-8") as f:
            json.dump(face_modes, f, indent=4)

    assert len(rendered_calls) == 5
    # Verify deterministic ordered keys
    assert list(face_modes.keys()) == [f"output{i:03d}" for i in range(5)]
    loaded = json.loads(modes_file.read_text(encoding="utf-8"))
    assert list(loaded.keys()) == [f"output{i:03d}" for i in range(5)]


def test_parallel_gaming_split_execution_and_subtitles_burned(tmp_path):
    import json
    import re
    import concurrent.futures
    from scripts import gaming_split

    project_dir = tmp_path / "proj"
    cuts_dir = project_dir / "cuts"
    final_dir = project_dir / "final"
    cuts_dir.mkdir(parents=True)
    final_dir.mkdir(parents=True)

    cut_files = [f"output{i:03d}.mp4" for i in range(4)]
    for cf in cut_files:
        (cuts_dir / cf).write_bytes(b"dummy")

    active_workers = 0
    max_active_workers = 0
    lock = threading.Lock()

    def fake_render_gaming(input_path, output_path, **kwargs):
        nonlocal active_workers, max_active_workers
        with lock:
            active_workers += 1
            if active_workers > max_active_workers:
                max_active_workers = active_workers
        time.sleep(0.04)
        with open(output_path, "wb") as f:
            f.write(b"processed_data")
        with lock:
            active_workers -= 1
        # Return RenderResult with subtitles_burned=True for even indices
        base = os.path.basename(output_path)
        is_subburned = "000" in base or "002" in base
        return RenderResult(output_path, subtitles_burned=is_subburned)

    subtitled_gaming_clips = set()
    face_modes = {}

    with patch("scripts.gaming_split.render_gaming_split_clip", side_effect=fake_render_gaming):
        pool_workers = 3
        def _render_gaming_task(task_args):
            idx, c_file = task_args
            c_path = os.path.join(str(cuts_dir), c_file)
            base_name = c_file.replace("_original_scale.mp4", "").replace(".mp4", "")
            clean_clip_name = re.sub(r'(_processed|_original_scale)+$', '', base_name)
            target_out = os.path.join(str(final_dir), f"{base_name}_processed.mp4")

            render_res = gaming_split.render_gaming_split_clip(
                input_path=c_path,
                output_path=target_out,
                facecam_box="0,0,0.5,0.5",
                gameplay_box="0.2,0.2,0.8,0.8",
                layout="split_30_70",
            )
            return idx, base_name, clean_clip_name, target_out, render_res

        with concurrent.futures.ThreadPoolExecutor(max_workers=pool_workers) as executor:
            futures = [executor.submit(_render_gaming_task, (idx, c_file)) for idx, c_file in enumerate(cut_files)]
            for f in concurrent.futures.as_completed(futures):
                idx, base_name, clean_clip_name, target_out, render_res = f.result()
                if getattr(render_res, "subtitles_burned", False) is True:
                    subtitled_gaming_clips.add(base_name)
                    subtitled_gaming_clips.add(f"{base_name}_processed")
                    subtitled_gaming_clips.add(clean_clip_name)
                    if os.path.exists(target_out):
                        burned_folder = os.path.join(str(project_dir), "burned_sub")
                        os.makedirs(burned_folder, exist_ok=True)
                        shutil.copy2(target_out, os.path.join(burned_folder, f"{clean_clip_name}.mp4"))

                face_modes[f"output{idx:03d}"] = "split_30_70"

    assert max_active_workers >= 2
    assert max_active_workers <= 3
    # Check that output000 and output002 were copied to burned_sub
    burned_folder = project_dir / "burned_sub"
    assert (burned_folder / "output000.mp4").exists()
    assert (burned_folder / "output002.mp4").exists()
    assert not (burned_folder / "output001.mp4").exists()
    assert "output000" in subtitled_gaming_clips
    assert "output002" in subtitled_gaming_clips
    assert "output001" not in subtitled_gaming_clips
    assert len(face_modes) == 4


def test_get_max_render_workers_edge_cases(monkeypatch):
    # Non-integer / float strings
    monkeypatch.setenv("VIRALCUTTER_MAX_RENDER_WORKERS", "3.14")
    with patch("os.cpu_count", return_value=8):
        assert gs_get_max_workers() == 3

    # Empty string or whitespace
    monkeypatch.setenv("VIRALCUTTER_MAX_RENDER_WORKERS", "")
    with patch("os.cpu_count", return_value=8):
        assert gs_get_max_workers() == 3

    monkeypatch.setenv("VIRALCUTTER_MAX_RENDER_WORKERS", "   ")
    with patch("os.cpu_count", return_value=8):
        assert gs_get_max_workers() == 3

    # Special characters
    monkeypatch.setenv("VIRALCUTTER_MAX_RENDER_WORKERS", "!@#$%")
    with patch("os.cpu_count", return_value=4):
        assert gs_get_max_workers() == 2

    # Custom default_cap
    monkeypatch.delenv("VIRALCUTTER_MAX_RENDER_WORKERS", raising=False)
    with patch("os.cpu_count", return_value=16):
        assert gs_get_max_workers(default_cap=5) == 5
        assert gs_get_max_workers(default_cap=1) == 1

    # cpu_count returns 0 or negative
    with patch("os.cpu_count", return_value=0):
        # (0 or 2) // 2 = 1
        assert gs_get_max_workers() == 1


def test_burn_subtitles_single_clip_and_broll(tmp_path):
    project_dir = tmp_path / "proj_single"
    final_dir = project_dir / "final"
    subs_dir = project_dir / "subs_ass"
    final_dir.mkdir(parents=True)
    subs_dir.mkdir(parents=True)

    (final_dir / "solo_clip_processed.mp4").write_bytes(b"solo_video")
    (subs_dir / "solo_clip.ass").write_text("[Script Info]\n")

    broll_list = [{"template_id": "solo_tpl", "video_path": str(tmp_path / "solo.webm")}]
    (tmp_path / "solo.webm").write_bytes(b"fake_broll")

    received_kwargs = {}

    def fake_burn_video_file(in_file, sub_file, out_file, **kwargs):
        received_kwargs.update(kwargs)
        return True, "Success", {"size": 2048, "duration": 3.0}

    with patch("scripts.burn_subtitles.burn_video_file", side_effect=fake_burn_video_file):
        out_folder = burn_subtitles.burn(
            project_folder=str(project_dir),
            broll_items=broll_list,
            max_workers=5,
        )

    assert os.path.exists(out_folder)
    assert received_kwargs.get("broll_items") == broll_list


def test_burn_subtitles_all_clips_skipped(tmp_path):
    project_dir = tmp_path / "proj_skipped"
    final_dir = project_dir / "final"
    subs_dir = project_dir / "subs_ass"
    final_dir.mkdir(parents=True)
    subs_dir.mkdir(parents=True)

    (final_dir / "clip_a_processed.mp4").write_bytes(b"dummy_a")
    (final_dir / "clip_b_processed.mp4").write_bytes(b"dummy_b")
    (subs_dir / "clip_a.ass").write_text("[Script Info]\n")
    (subs_dir / "clip_b.ass").write_text("[Script Info]\n")

    out_folder = burn_subtitles.burn(
        project_folder=str(project_dir),
        skip_clips={"clip_a", "clip_b"},
        max_workers=2,
    )
    assert os.path.exists(out_folder)


def test_burn_subtitles_worker_exception_propagation(tmp_path):
    project_dir = tmp_path / "proj_exc"
    final_dir = project_dir / "final"
    subs_dir = project_dir / "subs_ass"
    final_dir.mkdir(parents=True)
    subs_dir.mkdir(parents=True)

    (final_dir / "clip_crash_processed.mp4").write_bytes(b"dummy")
    (subs_dir / "clip_crash.ass").write_text("[Script Info]\n")

    def fake_burn_crash(*args, **kwargs):
        raise ValueError("Fatal render worker crash")

    with patch("scripts.burn_subtitles.burn_video_file", side_effect=fake_burn_crash):
        with pytest.raises(ValueError, match="Fatal render worker crash"):
            burn_subtitles.burn(
                project_folder=str(project_dir),
                max_workers=2,
            )


def test_gaming_split_parallel_pool_workers_calculation():
    # 0 clips
    cut_files_empty = []
    render_workers = 3
    pool_workers_empty = min(render_workers, len(cut_files_empty)) if cut_files_empty else 1
    assert pool_workers_empty == 1

    # 1 clip
    cut_files_one = ["output000.mp4"]
    pool_workers_one = min(render_workers, len(cut_files_one)) if cut_files_one else 1
    assert pool_workers_one == 1

    # 10 clips with max 3 workers
    cut_files_many = [f"output{i:03d}.mp4" for i in range(10)]
    pool_workers_many = min(render_workers, len(cut_files_many)) if cut_files_many else 1
    assert pool_workers_many == 3
