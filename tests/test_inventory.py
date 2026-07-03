from datetime import datetime


def test_scan_inventory_source_skips_unchanged_files(tmp_path, monkeypatch):
    import core.database as database
    import core.inventory as inventory

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    monkeypatch.setattr(inventory, 'save_source', database.save_source)
    monkeypatch.setattr(inventory, 'start_scan_job', database.start_scan_job)
    monkeypatch.setattr(inventory, 'finish_scan_job', database.finish_scan_job)
    monkeypatch.setattr(inventory, 'get_cached_metadata', database.get_cached_metadata)
    monkeypatch.setattr(inventory, 'save_file_record', database.save_file_record)

    database.init_db()
    src = tmp_path / 'photos'
    src.mkdir()
    photo = src / 'IMG_0001.jpg'
    photo.write_bytes(b'fake image payload')

    monkeypatch.setattr(
        inventory,
        'get_media_info',
        lambda path: {
            'date': datetime(2024, 3, 15, 10, 30, 0),
            'size': path.stat().st_size,
            'type': 'photo',
            'extension': '.jpg',
            'camera_make': 'Apple',
            'camera_model': 'iPhone 14 Pro',
            'lens_model': None,
            'software': None,
            'device_type': 'phone',
            'device_name': 'Apple iPhone 14 Pro',
            'origin_hint': 'metadata',
            'width': 4032,
            'height': 3024,
            'duration': None,
            'has_exif': True,
        },
    )

    first = inventory.scan_inventory_source(src)
    second = inventory.scan_inventory_source(src)

    assert first.files_seen == 1
    assert first.files_added == 1
    assert second.files_seen == 1
    assert second.files_skipped_cached == 1


def test_scan_inventory_source_can_register_destination_role(tmp_path, monkeypatch):
    import core.database as database
    import core.inventory as inventory

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    monkeypatch.setattr(inventory, 'save_source', database.save_source)
    monkeypatch.setattr(inventory, 'start_scan_job', database.start_scan_job)
    monkeypatch.setattr(inventory, 'finish_scan_job', database.finish_scan_job)
    monkeypatch.setattr(inventory, 'get_cached_metadata', database.get_cached_metadata)
    monkeypatch.setattr(inventory, 'save_file_record', database.save_file_record)

    database.init_db()
    dest = tmp_path / 'organized'
    dest.mkdir()
    photo = dest / 'IMG_0001.jpg'
    photo.write_bytes(b'fake image payload')

    monkeypatch.setattr(
        inventory,
        'get_media_info',
        lambda path: {
            'date': datetime(2024, 3, 15, 10, 30, 0),
            'size': path.stat().st_size,
            'type': 'photo',
            'extension': '.jpg',
            'camera_make': None,
            'camera_model': None,
            'lens_model': None,
            'software': None,
            'device_type': 'unknown',
            'device_name': 'Desconhecido',
            'origin_hint': 'path',
            'has_exif': False,
        },
    )

    result = inventory.scan_inventory_source(dest, label='Biblioteca organizada', source_type='destination', role='destination')
    sources = database.get_all_sources()
    records = database.get_all_file_records()

    assert result.files_seen == 1
    assert sources[0]['role'] == 'destination'
    assert records[0]['source_id'] == result.source_id
