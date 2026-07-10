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
        "ISO": 400,
        "FNumber": 5.6,
        "ExposureTime": 0.0004,
        "FocalLength": 70,
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
    assert metadata["iso"] == 400
    assert metadata["aperture"] == 5.6
    assert metadata["shutter_speed"] == 0.0004
    assert metadata["focal_length"] == 70
    assert metadata["gps_latitude"] == -23.55
    assert metadata["gps_longitude"] == -46.63
    assert metadata["has_exif"] is True


def test_normalize_exiftool_metadata_maps_video_capture_fields(tmp_path):
    from core.metadata_enrichment import normalize_exiftool_metadata

    path = tmp_path / "DJI_0001.MP4"
    raw = {
        "QuickTime:CreateDate": "2024:06:20 14:12:10",
        "Make": "DJI",
        "Model": "FC3582",
        "VideoFrameWidth": 3840,
        "VideoFrameHeight": 2160,
        "Duration": 12.5,
        "VideoFrameRate": 29.97,
        "AvgBitrate": 105000000,
        "CompressorID": "avc1",
        "MIMEType": "video/mp4",
        "FileType": "MP4",
    }

    metadata = normalize_exiftool_metadata(path, raw)

    assert metadata["date_taken"] == datetime(2024, 6, 20, 14, 12, 10)
    assert metadata["media_type"] == "video"
    assert metadata["camera_make"] == "DJI"
    assert metadata["camera_model"] == "FC3582"
    assert metadata["device_name"] == "DJI FC3582"
    assert metadata["width"] == 3840
    assert metadata["height"] == 2160
    assert metadata["duration"] == 12.5
    assert metadata["exiftool"]["frame_rate"] == 29.97
    assert metadata["exiftool"]["bitrate"] == "105000000"
    assert metadata["exiftool"]["codec"] == "avc1"


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


def test_destination_instance_creates_pending_exiftool_state(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "database.db")
    database.init_db()

    photo = tmp_path / "IMG_0002.JPG"
    photo.write_bytes(b"photo")
    asset_id = database.upsert_asset({
        "sha256": "state-pending",
        "size": photo.stat().st_size,
        "media_type": "photo",
        "extension": ".jpg",
    })
    database.save_asset_instance(asset_id=asset_id, path=str(photo), role="destination")

    with database._get_conn() as conn:
        state = conn.execute(
            "SELECT * FROM asset_processing_state WHERE asset_id=? AND processor='exiftool'",
            (asset_id,),
        ).fetchone()

    assert state["status"] == "pending"
    assert state["path"] == str(photo)
    assert state["source_size"] == photo.stat().st_size


def test_exiftool_enrichment_queue_skips_completed_items(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "database.db")
    database.init_db()

    first = tmp_path / "IMG_DONE.JPG"
    second = tmp_path / "IMG_PENDING.JPG"
    first.write_bytes(b"done")
    second.write_bytes(b"pending")
    done_asset = database.upsert_asset({"sha256": "done", "size": first.stat().st_size, "media_type": "photo", "extension": ".jpg"})
    pending_asset = database.upsert_asset({"sha256": "pending", "size": second.stat().st_size, "media_type": "photo", "extension": ".jpg"})
    database.save_asset_instance(asset_id=done_asset, path=str(first), role="destination")
    database.save_asset_instance(asset_id=pending_asset, path=str(second), role="destination")
    database.apply_asset_metadata_enrichment(
        asset_id=done_asset,
        path=str(first),
        extractor="exiftool",
        extractor_version="13.59",
        status="ok",
        raw={"media_type": "photo", "extension": ".jpg"},
        normalized={"media_type": "photo", "extension": ".jpg"},
        mtime=first.stat().st_mtime,
    )

    rows = database.list_destination_assets_for_enrichment(limit=10)

    assert [row["asset_id"] for row in rows] == [pending_asset]
    assert database.processing_summary("exiftool")["ok"] == 1
    assert database.processing_summary("exiftool")["pending"] == 1


def test_enrich_gallery_metadata_reports_unavailable(monkeypatch):
    import core.metadata_enrichment as enrichment

    monkeypatch.setattr(enrichment, "exiftool_path", lambda: None)

    result = enrichment.enrich_gallery_metadata()

    assert result.unavailable is True
    assert result.enriched == 0


def test_extract_exiftool_metadata_uses_runtime_command(tmp_path, monkeypatch):
    import core.runtime_tools as runtime_tools
    import core.metadata_enrichment as enrichment

    bundled = tmp_path / "exiftool.exe"
    bundled.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("PHOTOVAULT_EXIFTOOL", str(bundled))
    monkeypatch.setattr(runtime_tools.shutil, "which", lambda _: None)
    monkeypatch.setattr(enrichment.subprocess, "run", lambda command, **_kwargs: type("Result", (), {
        "returncode": 0,
        "stdout": '[{"MIMEType":"image/jpeg","Make":"Canon"}]',
        "stderr": "",
    })())
    runtime_tools.exiftool_path.cache_clear()
    runtime_tools.exiftool_command.cache_clear()

    try:
        metadata = enrichment.extract_exiftool_metadata(tmp_path / "photo.jpg")
        assert runtime_tools.exiftool_path() == str(bundled)
        assert metadata["camera_make"] == "Canon"
    finally:
        runtime_tools.exiftool_path.cache_clear()
        runtime_tools.exiftool_command.cache_clear()
