"""Tests for outro append functionality."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.append_outro import (
    get_video_info,
    apply_outro_to_clips,
    apply_outro_to_compilation,
)


class TestGetVideoInfo:
    def test_nonexistent_file(self):
        result = get_video_info("/nonexistent/video.mp4")
        assert result is None


class TestApplyOutroToClips:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmp)

    def test_no_outro_source_image(self):
        ok, msg = apply_outro_to_clips(self.tmp, outro_type="image", outro_source=None)
        assert not ok
        assert "No outro source" in msg

    def test_no_outro_source_video(self):
        ok, msg = apply_outro_to_clips(self.tmp, outro_type="video", outro_source=None)
        assert not ok

    def test_no_clips_found(self):
        ok, msg = apply_outro_to_clips(self.tmp, outro_type="image", outro_source="img.png")
        assert not ok
        assert "No clips found" in msg

    def test_prefers_burned_sub_over_cuts(self):
        burned = os.path.join(self.tmp, "burned_sub")
        cuts = os.path.join(self.tmp, "cuts")
        os.makedirs(burned)
        os.makedirs(cuts)
        open(os.path.join(burned, "clip1.mp4"), "w").close()
        open(os.path.join(cuts, "clip2.mp4"), "w").close()

        with patch("scripts.append_outro.append_image_outro", return_value=(True, "")) as mock:
            ok, msg = apply_outro_to_clips(self.tmp, outro_type="image", outro_source="img.png")
            assert mock.call_args[0][0].endswith("burned_sub/clip1.mp4")

    def test_falls_back_to_cuts(self):
        cuts = os.path.join(self.tmp, "cuts")
        os.makedirs(cuts)
        open(os.path.join(cuts, "clip1.mp4"), "w").close()

        with patch("scripts.append_outro.append_image_outro", return_value=(True, "")) as mock:
            ok, msg = apply_outro_to_clips(self.tmp, outro_type="image", outro_source="img.png")
            assert mock.call_args[0][0].endswith("cuts/clip1.mp4")

    def test_video_outro_type(self):
        cuts = os.path.join(self.tmp, "cuts")
        os.makedirs(cuts)
        open(os.path.join(cuts, "clip1.mp4"), "w").close()

        with patch("scripts.append_outro.append_video_outro", return_value=(True, "")) as mock:
            ok, msg = apply_outro_to_clips(self.tmp, outro_type="video", outro_source="outro.mp4")
            assert ok

    def test_text_outro_type(self):
        cuts = os.path.join(self.tmp, "cuts")
        os.makedirs(cuts)
        open(os.path.join(cuts, "clip1.mp4"), "w").close()

        with patch("scripts.append_outro.append_text_outro", return_value=(True, "")) as mock:
            ok, msg = apply_outro_to_clips(self.tmp, outro_type="text", outro_source=None, outro_text="Bye!")
            assert ok

    def test_unknown_outro_type(self):
        cuts = os.path.join(self.tmp, "cuts")
        os.makedirs(cuts)
        open(os.path.join(cuts, "clip1.mp4"), "w").close()

        ok, msg = apply_outro_to_clips(self.tmp, outro_type="unknown", outro_source="x")
        assert not ok
        assert "0/1" in msg

    def test_partial_failure(self):
        cuts = os.path.join(self.tmp, "cuts")
        os.makedirs(cuts)
        open(os.path.join(cuts, "a.mp4"), "w").close()
        open(os.path.join(cuts, "b.mp4"), "w").close()

        side_effects = [(True, ""), (False, "fail")]
        with patch("scripts.append_outro.append_image_outro", side_effect=side_effects):
            ok, msg = apply_outro_to_clips(self.tmp, outro_type="image", outro_source="img.png")
            assert not ok
            assert "1/2" in msg

    def test_creates_output_folder(self):
        cuts = os.path.join(self.tmp, "cuts")
        os.makedirs(cuts)
        open(os.path.join(cuts, "clip1.mp4"), "w").close()

        with patch("scripts.append_outro.append_image_outro", return_value=(True, "")):
            apply_outro_to_clips(self.tmp, outro_type="image", outro_source="img.png")
        assert os.path.isdir(os.path.join(self.tmp, "outro_clips"))


class TestApplyOutroToCompilation:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmp)

    def test_no_outro_source(self):
        ok, msg = apply_outro_to_compilation(self.tmp, outro_type="image", outro_source=None)
        assert not ok
        assert "No outro source" in msg

    def test_compilation_not_found(self):
        ok, msg = apply_outro_to_compilation(self.tmp, outro_type="video", outro_source="x.mp4")
        assert not ok
        assert "Compilation not found" in msg

    def test_image_outro(self):
        compiled = os.path.join(self.tmp, "compiled")
        os.makedirs(compiled)
        open(os.path.join(compiled, "compilation.mp4"), "w").close()

        with patch("scripts.append_outro.append_image_outro", return_value=(True, "ok")) as mock:
            ok, msg = apply_outro_to_compilation(self.tmp, outro_type="image", outro_source="img.png")
            assert ok
            assert "compilation_outro.mp4" in mock.call_args[0][2]

    def test_video_outro(self):
        compiled = os.path.join(self.tmp, "compiled")
        os.makedirs(compiled)
        open(os.path.join(compiled, "compilation.mp4"), "w").close()

        with patch("scripts.append_outro.append_video_outro", return_value=(True, "ok")) as mock:
            ok, msg = apply_outro_to_compilation(self.tmp, outro_type="video", outro_source="outro.mp4")
            assert ok

    def test_text_outro(self):
        compiled = os.path.join(self.tmp, "compiled")
        os.makedirs(compiled)
        open(os.path.join(compiled, "compilation.mp4"), "w").close()

        with patch("scripts.append_outro.append_text_outro", return_value=(True, "ok")) as mock:
            ok, msg = apply_outro_to_compilation(self.tmp, outro_type="text", outro_source=None)
            assert ok

    def test_unknown_type(self):
        compiled = os.path.join(self.tmp, "compiled")
        os.makedirs(compiled)
        open(os.path.join(compiled, "compilation.mp4"), "w").close()

        ok, msg = apply_outro_to_compilation(self.tmp, outro_type="zigzag", outro_source="x")
        assert not ok
        assert "Unknown" in msg
