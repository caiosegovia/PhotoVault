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
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)

    assert tools.ffmpeg_path() is None

    tools.ffmpeg_path.cache_clear()
