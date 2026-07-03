from PIL import Image


def test_thumbnail_cache_reuses_generated_file(tmp_path, monkeypatch):
    import core.thumbnail_cache as cache

    monkeypatch.setattr(cache, "THUMB_DIR", tmp_path / "thumbs")
    image_path = tmp_path / "photo.jpg"
    Image.new("RGB", (800, 600), (200, 20, 20)).save(image_path)

    first = cache.ensure_thumbnail(image_path)
    second = cache.ensure_thumbnail(image_path)

    assert first is not None
    assert first.exists()
    assert first == second
    assert first.parent == tmp_path / "thumbs"
