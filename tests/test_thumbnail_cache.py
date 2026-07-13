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


def test_thumbnail_cache_generates_fixed_3x2_preview_without_letterbox(tmp_path, monkeypatch):
    import core.thumbnail_cache as cache

    monkeypatch.setattr(cache, "THUMB_DIR", tmp_path / "thumbs")
    image_path = tmp_path / "photo.jpg"
    Image.new("RGB", (800, 600), (200, 20, 20)).save(image_path)

    thumb = cache.ensure_thumbnail(image_path)

    assert thumb is not None
    with Image.open(thumb) as image:
        assert image.size == cache.THUMB_SIZE
        assert image.getpixel((0, image.height // 2))[0] > 150
        assert image.getpixel((image.width - 1, image.height // 2))[0] > 150
