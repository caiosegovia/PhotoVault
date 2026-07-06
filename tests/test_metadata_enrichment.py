from datetime import datetime


def test_normalize_exiftool_metadata_maps_rich_fields(tmp_path):
    from core.metadata_enrichment import normalize_exiftool_metadata

    path = tmp_path / "IMG_0001.JPG"
    raw = {
        "DateTimeOriginal": "2024:03:15 10:30:00",
        "Make": "Canon",
        "Model": "EOS R6",
        "LensModel": "RF 24-70mm",
        "Software": "Camera",
        "ImageWidth": 6000,
        "ImageHeight": 4000,
        "GPSLatitude": -23.55,
        "GPSLongitude": -46.63,
        "MIMEType": "image/jpeg",
    }

    metadata = normalize_exiftool_metadata(path, raw)

    assert metadata["date_taken"] == datetime(2024, 3, 15, 10, 30, 0)
    assert metadata["camera_make"] == "Canon"
    assert metadata["camera_model"] == "EOS R6"
    assert metadata["lens_model"] == "RF 24-70mm"
    assert metadata["width"] == 6000
    assert metadata["height"] == 4000
    assert metadata["gps_latitude"] == -23.55
    assert metadata["gps_longitude"] == -46.63
    assert metadata["has_exif"] is True


def test_apply_asset_metadata_enrichment_updates_catalog(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "database.db")
    database.init_db()

    asset_id = database.upsert_asset({
        "sha256": "abc",
        "size": 123,
        "media_type": "photo",
        "extension": ".jpg",
    })
    database.save_asset_instance(asset_id=asset_id, path=str(tmp_path / "IMG_0001.JPG"), role="destination")

    database.apply_asset_metadata_enrichment(
        asset_id=asset_id,
        path=str(tmp_path / "IMG_0001.JPG"),
        extractor="exiftool",
        extractor_version="12.99",
        status="ok",
        raw={
            "date_taken": datetime(2024, 3, 15, 10, 30, 0),
            "media_type": "photo",
            "extension": ".jpg",
            "camera_make": "Canon",
            "camera_model": "EOS R6",
            "lens_model": "RF 24-70mm",
            "device_name": "Canon EOS R6",
            "has_exif": True,
        },
        normalized={
            "date_taken": datetime(2024, 3, 15, 10, 30, 0),
            "media_type": "photo",
            "extension": ".jpg",
            "camera_make": "Canon",
            "camera_model": "EOS R6",
            "lens_model": "RF 24-70mm",
            "device_name": "Canon EOS R6",
            "has_exif": True,
        },
    )

    with database._get_conn() as conn:
        asset = conn.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        meta = conn.execute("SELECT * FROM metadata_extractions WHERE asset_id=? AND extractor='exiftool'", (asset_id,)).fetchone()
        search = conn.execute("SELECT path FROM catalog_search WHERE catalog_search MATCH ?", ("Canon",)).fetchall()

    assert asset["date_taken"].startswith("2024-03-15")
    assert meta["extractor_version"] == "12.99"
    assert "Canon EOS R6" in meta["raw_json"]
    assert [row["path"] for row in search] == [str(tmp_path / "IMG_0001.JPG")]


def test_enrich_gallery_metadata_reports_unavailable(monkeypatch):
    import core.metadata_enrichment as enrichment

    monkeypatch.setattr(enrichment, "exiftool_path", lambda: None)

    result = enrichment.enrich_gallery_metadata()

    assert result.unavailable is True
    assert result.enriched == 0


def test_runtime_ignores_bundled_exiftool_env(tmp_path, monkeypatch):
    import core.runtime_tools as runtime_tools

    bundled = tmp_path / "exiftool.exe"
    bundled.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("PHOTOVAULT_EXIFTOOL", str(bundled))
    monkeypatch.setattr(runtime_tools.shutil, "which", lambda _: None)
    runtime_tools.exiftool_path.cache_clear()

    try:
        assert runtime_tools.exiftool_path() is None
    finally:
        runtime_tools.exiftool_path.cache_clear()
