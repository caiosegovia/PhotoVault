import sys
import types


def test_ffmpeg_path_uses_imageio_fallback(monkeypatch, tmp_path):
    import core.runtime_tools as tools

    exe = tmp_path / "ffmpeg.exe"
    exe.write_text("", encoding="utf-8")
    fake = types.SimpleNamespace(get_ffmpeg_exe=lambda: str(exe))

    tools.ffmpeg_path.cache_clear()
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", fake)

    assert tools.ffmpeg_path() == str(exe)
    assert tools.has_ffmpeg() is True

    tools.ffmpeg_path.cache_clear()


def test_ffmpeg_path_returns_none_when_unavailable(monkeypatch):
    import core.runtime_tools as tools

    tools.ffmpeg_path.cache_clear()


def test_exiftool_uses_explicit_env_path(tmp_path, monkeypatch):
    import core.runtime_tools as tools

    exe = tmp_path / "exiftool.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setenv("PHOTOVAULT_EXIFTOOL", str(exe))
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)

    tools.exiftool_command.cache_clear()
    tools.exiftool_path.cache_clear()
    try:
        assert tools.exiftool_command() == [str(exe)]
        assert tools.exiftool_path() == str(exe)
        assert tools.has_exiftool() is True
    finally:
        tools.exiftool_command.cache_clear()
        tools.exiftool_path.cache_clear()


def test_exiftool_status_reports_perl_script_without_perl(tmp_path, monkeypatch):
    import core.runtime_tools as tools

    script = tmp_path / "exiftool"
    script.write_text("#!/usr/bin/env perl\n", encoding="utf-8")
    monkeypatch.setenv("PHOTOVAULT_EXIFTOOL", str(script))
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)

    tools.exiftool_command.cache_clear()
    tools.exiftool_path.cache_clear()
    tools.perl_path.cache_clear()
    try:
        status = tools.exiftool_status()
        assert tools.exiftool_command() is None
        assert status["available"] is False
        assert status["path"] == str(script)
        assert status["reason"] == "perl_missing"
    finally:
        tools.exiftool_command.cache_clear()
        tools.exiftool_path.cache_clear()
        tools.perl_path.cache_clear()
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)

    assert tools.ffmpeg_path() is None

    tools.ffmpeg_path.cache_clear()
