"""Tests for i18n.i18n"""
import sys
import os
import json
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from i18n.i18n import I18nAuto, load_language_list


class TestLoadLanguageList:
    def test_loads_json_file(self, tmp_path, monkeypatch):
        locale_dir = tmp_path / "i18n" / "locale"
        locale_dir.mkdir(parents=True)
        (locale_dir / "en_US.json").write_text(json.dumps({"hello": "Hello", "bye": "Goodbye"}))
        monkeypatch.chdir(tmp_path)
        result = load_language_list("en_US")
        assert result == {"hello": "Hello", "bye": "Goodbye"}

    def test_missing_file_raises(self, tmp_path, monkeypatch):
        locale_dir = tmp_path / "i18n" / "locale"
        locale_dir.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            load_language_list("xx_NONEXISTENT")


class TestI18nAuto:
    def _make_i18n(self, tmp_path, monkeypatch, language_code, translations):
        """Helper: create locale JSON in tmp_path and return I18nAuto."""
        locale_dir = tmp_path / "i18n" / "locale"
        locale_dir.mkdir(parents=True)
        (locale_dir / f"{language_code}.json").write_text(json.dumps(translations))
        monkeypatch.chdir(tmp_path)
        return I18nAuto(language=language_code)

    def test_known_key_returns_translation(self, tmp_path, monkeypatch):
        i18n = self._make_i18n(tmp_path, monkeypatch, "en_US", {"hello": "Hello"})
        assert i18n("hello") == "Hello"

    def test_unknown_key_returns_key_itself(self, tmp_path, monkeypatch):
        i18n = self._make_i18n(tmp_path, monkeypatch, "en_US", {"hello": "Hello"})
        assert i18n("nonexistent_key") == "nonexistent_key"

    def test_missing_locale_falls_back_to_en_US(self, tmp_path, monkeypatch):
        locale_dir = tmp_path / "i18n" / "locale"
        locale_dir.mkdir(parents=True)
        (locale_dir / "en_US.json").write_text(json.dumps({"fallback": "OK"}))
        monkeypatch.chdir(tmp_path)
        # Request non-existent locale; should fall back to en_US
        i18n = I18nAuto(language="xx_NONEXISTENT")
        assert i18n("fallback") == "OK"
        assert i18n.language == "en_US"

    def test_multiple_keys(self, tmp_path, monkeypatch):
        translations = {
            "save": "Save",
            "cancel": "Cancel",
            "delete": "Delete",
        }
        i18n = self._make_i18n(tmp_path, monkeypatch, "en_US", translations)
        assert i18n("save") == "Save"
        assert i18n("cancel") == "Cancel"
        assert i18n("delete") == "Delete"

    def test_repr(self, tmp_path, monkeypatch):
        i18n = self._make_i18n(tmp_path, monkeypatch, "en_US", {"x": "X"})
        assert "en_US" in repr(i18n)

    def test_auto_language_detection(self, tmp_path, monkeypatch):
        locale_dir = tmp_path / "i18n" / "locale"
        locale_dir.mkdir(parents=True)
        (locale_dir / "en_US.json").write_text(json.dumps({"auto": "yes"}))
        monkeypatch.chdir(tmp_path)
        with patch("i18n.i18n.locale.getdefaultlocale", return_value=("en_US", "UTF-8")):
            i18n = I18nAuto(language=None)
            assert i18n("auto") == "yes"
            assert i18n.language == "en_US"

    def test_auto_language_via_string(self, tmp_path, monkeypatch):
        locale_dir = tmp_path / "i18n" / "locale"
        locale_dir.mkdir(parents=True)
        (locale_dir / "en_US.json").write_text(json.dumps({"ok": "yes"}))
        monkeypatch.chdir(tmp_path)
        with patch("i18n.i18n.locale.getdefaultlocale", return_value=("en_US", "UTF-8")):
            i18n = I18nAuto(language="Auto")
            assert i18n("ok") == "yes"

    def test_unknown_key_returns_original_string(self, tmp_path, monkeypatch):
        i18n = self._make_i18n(tmp_path, monkeypatch, "en_US", {"a": "1"})
        assert i18n("completely_unknown") == "completely_unknown"
        assert i18n("") == ""
