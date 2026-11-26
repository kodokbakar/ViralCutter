import os
import pytest
from unittest.mock import patch, MagicMock
from scripts import smart_clipping, cut_segments

def test_smart_clipping_bypasses_splicing_when_render_clips_false(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")

    mock_topics = [{
        "title": "Topic 1",
        "score": 90,
        "rationale": "Great hook",
        "segments": {
            "hook": {"start_time": 0.0, "end_time": 5.0, "text": "Hook"},
            "core": {"start_time": 10.0, "end_time": 20.0, "text": "Core"},
            "payoff": {"start_time": 25.0, "end_time": 30.0, "text": "Payoff"}
        }
    }]

    with patch("scripts.smart_clipping.extract_words_from_transcript", return_value=[]), \
         patch("scripts.create_viral_segments.load_transcript", return_value=[]), \
         patch("scripts.create_viral_segments.preprocess_transcript_for_ai", return_value="test text"), \
         patch("scripts.smart_clipping.query_ai_backend", return_value="{}"), \
         patch("scripts.smart_clipping.parse_narrative_topics", return_value=mock_topics), \
         patch("scripts.smart_clipping.compute_audio_energy_score", return_value=80.0), \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice:

        res = smart_clipping.run_smart_clipping_pipeline(
            project_folder=project_folder,
            render_clips=False
        )

        assert "segments" in res
        assert len(res["segments"]) == 1
        # Verifies FFmpeg splice was completely bypassed
        mock_splice.assert_not_called()
        seg = res["segments"][0]
        assert "segments_to_splice" in seg
        assert len(seg["segments_to_splice"]) > 0

def test_cut_segments_handles_segments_to_splice(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")
    cuts_dir = tmp_path / "cuts"
    cuts_dir.mkdir()

    segments_data = {
        "segments": [{
            "title": "Multi Slice Segment",
            "score": 88,
            "start_time": 0.0,
            "duration": 15.0,
            "segments_to_splice": [(0.0, 5.0), (10.0, 20.0)]
        }]
    }

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice, \
         patch("scripts.cut_json.cut_json_transcript"):

        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)
        mock_splice.assert_called_once()
        args, kwargs = mock_splice.call_args
        assert args[1] == [(0.0, 5.0), (10.0, 20.0)]

def test_smart_clipping_calls_splice_when_render_clips_true(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")

    mock_topics = [{
        "title": "Topic 1",
        "score": 90,
        "rationale": "Great hook",
        "segments": {
            "hook": {"start_time": 0.0, "end_time": 5.0, "text": "Hook"},
            "core": {"start_time": 10.0, "end_time": 20.0, "text": "Core"},
            "payoff": {"start_time": 25.0, "end_time": 30.0, "text": "Payoff"}
        }
    }]

    with patch("scripts.smart_clipping.extract_words_from_transcript", return_value=[]), \
         patch("scripts.create_viral_segments.load_transcript", return_value=[]), \
         patch("scripts.create_viral_segments.preprocess_transcript_for_ai", return_value="test text"), \
         patch("scripts.smart_clipping.query_ai_backend", return_value="{}"), \
         patch("scripts.smart_clipping.parse_narrative_topics", return_value=mock_topics), \
         patch("scripts.smart_clipping.compute_audio_energy_score", return_value=80.0), \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice:

        res = smart_clipping.run_smart_clipping_pipeline(
            project_folder=project_folder,
            render_clips=True
        )

        assert "segments" in res
        mock_splice.assert_called_once()

def test_cut_segments_skip_video_skips_splicing(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")
    cuts_dir = tmp_path / "cuts"
    cuts_dir.mkdir()

    segments_data = {
        "segments": [{
            "title": "Multi Slice Segment",
            "score": 88,
            "start_time": 0.0,
            "duration": 15.0,
            "segments_to_splice": [(0.0, 5.0), (10.0, 20.0)]
        }]
    }

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice, \
         patch("scripts.cut_json.cut_json_transcript"):

        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=True)
        mock_splice.assert_not_called()

def test_cut_segments_single_slice_does_not_splice(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")
    cuts_dir = tmp_path / "cuts"
    cuts_dir.mkdir()

    segments_data = {
        "segments": [{
            "title": "Single Slice Segment",
            "score": 88,
            "start_time": 0.0,
            "duration": 5.0,
            "segments_to_splice": [(0.0, 5.0)]
        }]
    }

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice, \
         patch("subprocess.run") as mock_run, \
         patch("scripts.cut_json.cut_json_transcript"):

        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)
        mock_splice.assert_not_called()
        mock_run.assert_called_once()

def test_cut_segments_sub_segments_fallback(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")
    cuts_dir = tmp_path / "cuts"
    cuts_dir.mkdir()

    segments_data = {
        "segments": [{
            "title": "Sub Segments Fallback",
            "score": 85,
            "start_time": 0.0,
            "duration": 12.0,
            "sub_segments": [(0.0, 4.0), (8.0, 16.0)]
        }]
    }

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("scripts.smart_clipping.splice_topic_segments") as mock_splice, \
         patch("scripts.cut_json.cut_json_transcript"):

        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)
        mock_splice.assert_called_once()
        args, _ = mock_splice.call_args
        assert args[1] == [(0.0, 4.0), (8.0, 16.0)]


def test_cut_segments_single_cut_uses_stream_copy(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")
    cuts_dir = tmp_path / "cuts"
    cuts_dir.mkdir()

    segments_data = {
        "segments": [{
            "title": "Continuous Clip",
            "score": 95,
            "start_time": 10.0,
            "duration": 25.0
        }]
    }

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("subprocess.run") as mock_run, \
         patch("scripts.cut_json.cut_json_transcript"):

        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        # Verify -ss is placed before -i for fast keyframe seeking
        ss_idx = cmd.index("-ss")
        i_idx = cmd.index("-i")
        assert ss_idx < i_idx
        assert cmd[ss_idx + 1] == "10.000"
        # Verify stream copy codecs
        assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "copy"
        assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "copy"


def test_cut_segments_stream_copy_fallback_to_reencode_on_error(tmp_path):
    import subprocess
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")
    cuts_dir = tmp_path / "cuts"
    cuts_dir.mkdir()

    segments_data = {
        "segments": [{
            "title": "Fallback Clip",
            "score": 85,
            "start_time": 5.0,
            "duration": 15.0
        }]
    }

    # First call (stream copy) fails, second call (re-encode) succeeds
    calls = []
    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, cmd, stderr="Stream copy muxing error")
        return MagicMock(returncode=0)

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("subprocess.run", side_effect=fake_run), \
         patch("scripts.cut_json.cut_json_transcript"):

        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)

        assert len(calls) == 2
        # First call was stream copy
        first_cmd = calls[0]
        assert first_cmd[first_cmd.index("-c:v") + 1] == "copy"
        # Second call fell back to re-encoding libx264
        second_cmd = calls[1]
        assert second_cmd[second_cmd.index("-c:v") + 1] == "libx264"
        assert "-preset" in second_cmd
        assert second_cmd[second_cmd.index("-c:a") + 1] == "aac"


def test_cut_segments_stream_copy_fallback_on_corrupt_empty_file(tmp_path):
    project_folder = str(tmp_path)
    (tmp_path / "input.mp4").write_bytes(b"fake video content")
    cuts_dir = tmp_path / "cuts"
    cuts_dir.mkdir()

    segments_data = {
        "segments": [{
            "title": "Corrupt Output Clip",
            "score": 90,
            "start_time": 2.0,
            "duration": 8.0
        }]
    }

    out_file = cuts_dir / "001_90_Corrupt_Output_Clip_original_scale.mp4"

    calls = []
    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        if len(calls) == 1:
            # First call creates 0-byte corrupt file
            out_file.write_bytes(b"")
            return MagicMock(returncode=0)
        else:
            # Second call creates valid re-encoded file
            out_file.write_bytes(b"re-encoded video content")
            return MagicMock(returncode=0)

    with patch("scripts.cut_segments.check_nvenc_support", return_value=False), \
         patch("subprocess.run", side_effect=fake_run), \
         patch("scripts.cut_json.cut_json_transcript"):

        cut_segments.cut(segments_data, project_folder=project_folder, skip_video=False)

        assert len(calls) == 2
        assert calls[0][calls[0].index("-c:v") + 1] == "copy"
        assert calls[1][calls[1].index("-c:v") + 1] == "libx264"
        assert out_file.exists()
        assert out_file.read_bytes() == b"re-encoded video content"


def test_cut_segments_real_stream_copy_e2e(tmp_path):
    import subprocess
    input_file = tmp_path / "input.mp4"
    gen_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=160x120:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=3",
        "-c:v", "libx264", "-c:a", "aac",
        str(input_file)
    ]
    res = subprocess.run(gen_cmd, capture_output=True)
    if res.returncode != 0:
        pytest.skip("ffmpeg not available or failed to create test video")

    segments_data = {
        "segments": [{
            "title": "Real Test Cut",
            "score": 99,
            "start_time": 0.5,
            "duration": 1.5
        }]
    }

    with patch("scripts.cut_json.cut_json_transcript"):
        cut_segments.cut(segments_data, project_folder=str(tmp_path), skip_video=False)

    out_file = tmp_path / "cuts" / "001_99_Real_Test_Cut_original_scale.mp4"
    assert out_file.exists()
    assert out_file.stat().st_size > 0

