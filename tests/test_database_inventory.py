from datetime import datetime


def test_save_file_record_persists_device_fields(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    database.save_file_record(
        path='D:/Fotos/IMG_0001.JPG',
        hash_sha256='abc',
        hash_phash='def',
        date_taken=datetime(2024, 3, 15, 10, 30, 0),
        size=123,
        media_type='photo',
        extension='.jpg',
        mtime=1.0,
        camera_make='Apple',
        camera_model='iPhone 14 Pro',
        device_type='phone',
        device_name='Apple iPhone 14 Pro',
        origin_hint='metadata',
    )

    rows = database.get_files_by_device()

    assert rows[0]['device_name'] == 'Apple iPhone 14 Pro'
    assert rows[0]['device_type'] == 'phone'
    assert rows[0]['count'] == 1
    assert rows[0]['size_bytes'] == 123


def test_save_file_record_persists_metadata_extraction_and_search(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    database.save_file_record(
        path='D:/Fotos/IMG_0002.JPG',
        hash_sha256='abc2',
        hash_phash=None,
        date_taken=datetime(2024, 4, 1, 8, 0, 0),
        size=456,
        media_type='photo',
        extension='.jpg',
        mtime=2.0,
        camera_make='Canon',
        camera_model='R6',
        device_name='Canon R6',
        has_exif=True,
    )

    with database._get_conn() as conn:
        meta = conn.execute("SELECT * FROM metadata_extractions WHERE path=?", ('D:/Fotos/IMG_0002.JPG',)).fetchone()
        search = conn.execute("SELECT path FROM catalog_search WHERE catalog_search MATCH ?", ('Canon',)).fetchall()

    assert meta['extractor'] == 'photovault-core'
    assert 'Canon R6' in meta['raw_json']
    assert [row['path'] for row in search] == ['D:/Fotos/IMG_0002.JPG']


def test_save_source_tracks_role_and_file_source_id(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    source_id = database.save_source(
        label='Biblioteca organizada',
        source_type='destination',
        root_path='D:/PhotoVault',
        role='destination',
    )
    database.save_file_record(
        path='D:/PhotoVault/2024/IMG_0001.JPG',
        hash_sha256='abc',
        hash_phash=None,
        date_taken=datetime(2024, 3, 15, 10, 30, 0),
        size=123,
        media_type='photo',
        extension='.jpg',
        mtime=1.0,
        source_id=source_id,
    )

    sources = database.get_all_sources()
    records = database.get_all_file_records()

    assert sources[0]['role'] == 'destination'
    assert sources[0]['type'] == 'destination'
    assert records[0]['source_id'] == source_id


def test_save_vault_persists_gallery_label(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    vault_id = database.save_vault('Arquivo da Familia', 'D:/PhotoVault', '{year}/{month:02d}')
    database.save_vault('Memoria Permanente', 'D:/PhotoVault', '{year}/{extension}')

    latest = database.get_latest_vault()

    assert latest['id'] == vault_id
    assert latest['label'] == 'Memoria Permanente'
    assert latest['pattern'] == '{year}/{extension}'


def test_query_gallery_records_filters_quality_role_and_media_type(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    origin_id = database.save_source('Camera', 'local', 'D:/Camera', role='origin')
    dest_id = database.save_source('Biblioteca organizada', 'destination', 'D:/Vault', role='destination')
    database.save_file_record(
        path='D:/Camera/low.jpg',
        hash_sha256=None,
        hash_phash=None,
        date_taken=datetime(2020, 1, 1, 12, 0, 0),
        size=100,
        media_type='photo',
        extension='.jpg',
        mtime=1.0,
        width=640,
        height=480,
        has_exif=False,
        source_id=origin_id,
    )
    database.save_file_record(
        path='D:/Vault/video.mp4',
        hash_sha256=None,
        hash_phash=None,
        date_taken=datetime(2024, 1, 1, 12, 0, 0),
        size=60 * 1024 * 1024,
        media_type='video',
        extension='.mp4',
        mtime=2.0,
        has_exif=True,
        source_id=dest_id,
    )

    low = database.query_gallery_records({'quality': 'low_resolution'})
    dest_videos = database.query_gallery_records({'source_role': 'destination', 'media_type': 'video'})

    assert [row['path'] for row in low] == ['D:/Camera/low.jpg']
    assert [row['path'] for row in dest_videos] == ['D:/Vault/video.mp4']
