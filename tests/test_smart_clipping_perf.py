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
