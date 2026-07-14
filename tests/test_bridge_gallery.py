def test_gallery_payload_lists_assets_once_after_backfill(monkeypatch):
    import bridge

    calls = []

    monkeypatch.setattr(bridge, 'init_db', lambda: None)
    monkeypatch.setattr(bridge, 'backfill_catalog_metadata_from_gallery', lambda: calls.append('backfill') or 2)
    monkeypatch.setattr(bridge, 'gallery_totals', lambda: {
        'total': 1,
        'photos': 1,
        'videos': 0,
        'without_date': 0,
        'bytes_total': 123,
        'photo_bytes': 123,
        'video_bytes': 0,
        'first_date': '2024-01-01T10:00:00',
        'last_date': '2024-01-01T10:00:00',
        'year_count': 1,
        'month_count': 1,
        'extension_count': 1,
    })
    monkeypatch.setattr(bridge, 'gallery_breakdowns', lambda: {
        'media': [],
        'years': [],
        'months': [],
        'extensions': [],
        'devices': [],
        'deviceTypes': [],
        'cameras': [],
    })
    monkeypatch.setattr(bridge, 'duplicate_savings_total', lambda: {'count': 0, 'bytes': 0})
    monkeypatch.setattr(bridge, 'gallery_month_timeline', lambda: [])
    monkeypatch.setattr(bridge, 'get_cached_thumbnail', lambda _path: None)
    monkeypatch.setattr(bridge, 'has_ffmpeg', lambda: False)
    monkeypatch.setattr(bridge, 'has_exiftool', lambda: False)
    monkeypatch.setattr(bridge, 'exiftool_version', lambda: '')
    monkeypatch.setattr(bridge, 'exiftool_status', lambda: {'available': False})
    monkeypatch.setattr(bridge, 'processing_summary', lambda _processor: {'total': 0})
    monkeypatch.setattr(bridge, 'environment_diagnostics', lambda: {'status': 'ok'})
    monkeypatch.setattr(bridge, 'gallery_health', lambda: {'total': 0})

    monkeypatch.setattr(bridge, 'count_gallery_assets', lambda filters=None, query='': 6)

    def list_assets(limit, offset=0, filters=None, query='', sort=''):
        calls.append(f'assets:{limit}:{offset}')
        return [{
            'instance_id': 7,
            'asset_id': 11,
            'path': 'D:/Vault/IMG_0001.jpg',
            'media_type': 'photo',
            'extension': '.jpg',
            'size': 123,
            'date_taken': '2024-01-01T10:00:00',
            'device_name': 'Canon R6',
            'device_type': 'camera',
        }]

    monkeypatch.setattr(bridge, 'list_gallery_assets', list_assets)

    result = bridge.gallery({'limit': 10, 'offset': 5})

    assert calls == ['backfill', 'assets:10:5']
    assert result['timings']['backfillCount'] == 2
    assert result['page'] == {'limit': 10, 'offset': 5, 'count': 1, 'hasMore': False}
    assert result['filteredTotal'] == 6
    assert result['items'][0]['name'] == 'IMG_0001.jpg'
    assert result['items'][0]['deviceName'] == 'Canon R6'


def test_state_returns_gallery_summary_without_loading_items(monkeypatch):
    import bridge

    monkeypatch.setattr(bridge, 'init_db', lambda: None)
    monkeypatch.setattr(bridge, 'get_latest_vault', lambda: None)
    monkeypatch.setattr(bridge, 'list_imports', lambda _limit: [])
    monkeypatch.setattr(bridge, '_progress_payload', lambda: {'status': 'idle'})
    monkeypatch.setattr(bridge, 'get_log_path', lambda: 'photovault.log')
    monkeypatch.setattr(bridge, 'backfill_catalog_metadata_from_gallery', lambda: 0)
    monkeypatch.setattr(bridge, 'gallery_totals', lambda: {
        'total': 25000,
        'photos': 20000,
        'videos': 5000,
        'without_date': 3,
        'bytes_total': 999,
        'photo_bytes': 800,
        'video_bytes': 199,
        'first_date': None,
        'last_date': None,
        'year_count': 4,
        'month_count': 30,
        'extension_count': 8,
    })
    monkeypatch.setattr(bridge, 'gallery_breakdowns', lambda: {
        'media': [],
        'years': [],
        'months': [],
        'extensions': [],
        'devices': [],
        'deviceTypes': [],
        'cameras': [],
    })
    monkeypatch.setattr(bridge, 'duplicate_savings_total', lambda: {'count': 2, 'bytes': 100})
    monkeypatch.setattr(bridge, 'gallery_month_timeline', lambda: [])
    monkeypatch.setattr(bridge, 'list_gallery_assets', lambda _limit, offset=0, filters=None, query='', sort='': (_ for _ in ()).throw(AssertionError('assets should not load')))
    monkeypatch.setattr(bridge, 'has_ffmpeg', lambda: False)
    monkeypatch.setattr(bridge, 'has_exiftool', lambda: False)
    monkeypatch.setattr(bridge, 'exiftool_version', lambda: '')
    monkeypatch.setattr(bridge, 'exiftool_status', lambda: {'available': False})
    monkeypatch.setattr(bridge, 'processing_summary', lambda _processor: {'total': 0})
    monkeypatch.setattr(bridge, 'environment_diagnostics', lambda: {'status': 'ok'})
    monkeypatch.setattr(bridge, 'gallery_health', lambda: {'total': 0})

    result = bridge.state({})

    assert result['gallery']['total'] == 25000
    assert result['gallery']['items'] == []
    assert result['diagnostics']['status'] == 'ok'
    assert result['health']['total'] == 0


def test_gallery_payload_can_hydrate_thumbnails_in_same_pass(tmp_path, monkeypatch):
    import bridge

    photo = tmp_path / 'IMG_0002.jpg'
    thumb = tmp_path / 'thumb.jpg'
    photo.write_bytes(b'photo')
    thumb.write_bytes(b'thumb')
    hydrated = set()

    monkeypatch.setattr(bridge, 'init_db', lambda: None)
    monkeypatch.setattr(bridge, 'backfill_catalog_metadata_from_gallery', lambda: 0)
    monkeypatch.setattr(bridge, 'gallery_totals', lambda: {
        'total': 1,
        'photos': 1,
        'videos': 0,
        'without_date': 0,
        'bytes_total': 5,
        'photo_bytes': 5,
        'video_bytes': 0,
        'first_date': None,
        'last_date': None,
        'year_count': 0,
        'month_count': 0,
        'extension_count': 1,
    })
    monkeypatch.setattr(bridge, 'gallery_breakdowns', lambda: {
        'media': [],
        'years': [],
        'months': [],
        'extensions': [],
        'devices': [],
        'deviceTypes': [],
        'cameras': [],
    })
    monkeypatch.setattr(bridge, 'duplicate_savings_total', lambda: {'count': 0, 'bytes': 0})
    monkeypatch.setattr(bridge, 'gallery_month_timeline', lambda: [])
    monkeypatch.setattr(bridge, 'count_gallery_assets', lambda filters=None, query='': 1)
    monkeypatch.setattr(bridge, 'list_gallery_assets', lambda _limit, offset=0, filters=None, query='', sort='': [{
        'instance_id': 8,
        'asset_id': 12,
        'path': str(photo),
        'media_type': 'photo',
        'extension': '.jpg',
        'size': 5,
    }])
    monkeypatch.setattr(bridge, 'ensure_thumbnail', lambda path: hydrated.add(str(path)) or thumb)
    monkeypatch.setattr(bridge, 'get_cached_thumbnail', lambda path: thumb if str(path) in hydrated else None)
    monkeypatch.setattr(bridge, 'has_ffmpeg', lambda: False)
    monkeypatch.setattr(bridge, 'has_exiftool', lambda: False)
    monkeypatch.setattr(bridge, 'exiftool_version', lambda: '')
    monkeypatch.setattr(bridge, 'exiftool_status', lambda: {'available': False})
    monkeypatch.setattr(bridge, 'processing_summary', lambda _processor: {'total': 0})
    monkeypatch.setattr(bridge, 'start_background_job', lambda *args, **kwargs: 99)
    monkeypatch.setattr(bridge, 'finish_background_job', lambda *args, **kwargs: None)

    result = bridge.gallery({'limit': 10, 'ensureThumbnails': True})

    assert str(photo) in hydrated
    assert result['items'][0]['thumbnail'] == str(thumb)
    assert result['items'][0]['previewStatus'] == 'ready'


def test_search_gallery_uses_search_assets(monkeypatch):
    import bridge

    monkeypatch.setattr(bridge, 'init_db', lambda: None)
    monkeypatch.setattr(bridge, '_gallery_payload', lambda _limit, offset=0, include_items=False: {
        'items': [],
        'total': 2,
        'breakdowns': {'media': [], 'years': [], 'months': [], 'extensions': []},
    })
    monkeypatch.setattr(bridge, 'count_gallery_assets', lambda filters=None, query='': 12)
    monkeypatch.setattr(bridge, 'search_gallery_assets', lambda query, limit, offset=0, filters=None, sort='': [{
        'instance_id': 9,
        'asset_id': 13,
        'path': 'D:/Vault/drone-shot.mp4',
        'media_type': 'video',
        'extension': '.mp4',
        'size': 20,
        'tags': 'drone',
        'note_count': 1,
        'latest_note': 'Bom take',
    }] if query == 'drone' and limit == 25 and offset == 10 else [])
    monkeypatch.setattr(bridge, 'get_cached_thumbnail', lambda _path: None)
    monkeypatch.setattr(bridge, 'has_ffmpeg', lambda: True)

    result = bridge.search_gallery({'query': 'drone', 'limit': 25, 'offset': 10})

    assert result['search']['count'] == 1
    assert result['search']['offset'] == 10
    assert result['page']['offset'] == 10
    assert result['page']['hasMore'] is True
    assert result['items'][0]['tags'] == 'drone'
    assert result['items'][0]['latestNote'] == 'Bom take'
from datetime import datetime


def _seed_gallery_asset(database, index: int, *, path: str, sha: str, size: int, media_type: str,
                        extension: str, date_taken: datetime | None, device_name: str,
                        device_type: str, camera_make: str = "", camera_model: str = "",
                        lens_model: str = "", width: int = 2000, height: int = 1500) -> int:
    asset_id = database.upsert_asset({
        'sha256': sha,
        'size': size,
        'media_type': media_type,
        'extension': extension,
        'date_taken': date_taken,
        'width': width,
        'height': height,
    })
    database.save_asset_instance(asset_id, path, role='destination', quality_score=index)
    database.save_asset_metadata(asset_id, path, 'exiftool', {
        'media_type': media_type,
        'extension': extension,
        'device_name': device_name,
        'device_type': device_type,
        'camera_make': camera_make,
        'camera_model': camera_model,
        'lens_model': lens_model,
        'width': width,
        'height': height,
    }, extractor_version='12.99', status='ok')
    return asset_id


def test_gallery_facets_round_trip_against_real_sqlite(tmp_path, monkeypatch):
    import bridge
    import core.database as database

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    monkeypatch.setattr(bridge, 'backfill_catalog_metadata_from_gallery', lambda: 0)
    monkeypatch.setattr(bridge, 'get_cached_thumbnail', lambda _path: None)
    monkeypatch.setattr(bridge, 'has_ffmpeg', lambda: True)
    monkeypatch.setattr(bridge, 'has_exiftool', lambda: True)
    monkeypatch.setattr(bridge, 'exiftool_version', lambda: '12.99')
    monkeypatch.setattr(bridge, 'exiftool_status', lambda: {'available': True})
    monkeypatch.setattr(bridge, 'processing_summary', lambda _processor: {'total': 0})
    database.init_db()

    _seed_gallery_asset(
        database, 1, path='D:/Vault/2026/06/DJI_0001.JPG', sha='a' * 64,
        size=1_500_000, media_type='photo', extension='jpg',
        date_taken=datetime(2026, 6, 26, 8, 34, 43),
        device_name='DJI FC7303', device_type='drone', camera_model='FC7303', lens_model='24mm',
    )
    _seed_gallery_asset(
        database, 2, path='D:/Vault/2026/06/DJI_0002.DNG', sha='b' * 64,
        size=23_400_000, media_type='photo', extension='dng',
        date_taken=datetime(2026, 6, 26, 8, 34, 45),
        device_name='DJI FC7303', device_type='drone', camera_make='DJI', camera_model='FC7303', lens_model='24mm',
    )
    _seed_gallery_asset(
        database, 3, path='D:/Vault/2025/12/DJI_VIDEO.MP4', sha='c' * 64,
        size=2_760_000_000, media_type='video', extension='mp4',
        date_taken=datetime(2025, 12, 1, 10, 0, 0),
        device_name='DJI FC7303', device_type='drone', camera_make='DJI', camera_model='FC7303',
        width=3840, height=2160,
    )
    _seed_gallery_asset(
        database, 4, path='D:/Vault/2024/01/CANON_0001.JPG', sha='d' * 64,
        size=8_000_000, media_type='photo', extension='.jpg',
        date_taken=datetime(2024, 1, 10, 12, 0, 0),
        device_name='Canon EOS 5D Mark III', device_type='camera', camera_make='Canon', camera_model='EOS 5D Mark III', lens_model='50mm',
    )
    _seed_gallery_asset(
        database, 5, path='D:/Vault/2025/11/PHONE_0001.HEIC', sha='e' * 64,
        size=4_000_000, media_type='photo', extension='heic',
        date_taken=datetime(2025, 11, 5, 9, 0, 0),
        device_name='Apple iPhone 15 Pro', device_type='phone', camera_make='Apple', camera_model='iPhone 15 Pro',
    )

    base = bridge.gallery({'limit': 20})

    assert base['total'] == 5
    assert {item['label'] for item in base['breakdowns']['sizes']} == {'large', 'medium', 'small'}
    assert any(item['label'] == '24mm' for item in base['breakdowns']['lenses'])

    facet_cases = [
        ('media', 'video', {'media': 'video'}),
        ('months', '2026-06', {'month': '2026-06'}),
        ('extensions', 'dng', {'extension': 'dng'}),
        ('extensions', 'jpg', {'extension': 'jpg'}),
        ('devices', 'DJI FC7303', {'device': 'DJI FC7303'}),
        ('cameras', 'DJI FC7303', {'camera': 'DJI FC7303'}),
        ('lenses', '24mm', {'lens': '24mm'}),
        ('sizes', 'large', {'size': 'large'}),
        ('sizes', 'medium', {'size': 'medium'}),
        ('sizes', 'small', {'size': 'small'}),
    ]
    for _facet, _label, filters in facet_cases:
        result = bridge.gallery({'limit': 10, 'filter': {'media': 'all', 'year': 'all', 'month': 'all',
                                                         'extension': 'all', 'deviceType': 'all', 'device': 'all',
                                                         'camera': 'all', 'lens': 'all', 'size': 'all',
                                                         'problem': 'all', 'query': '', **filters}})
        assert result['filteredTotal'] > 0
        assert result['items'], filters

    combo = bridge.gallery({'limit': 10, 'filter': {'media': 'photo', 'month': '2026-06', 'device': 'DJI FC7303'}})
    assert combo['filteredTotal'] == 2
    assert {item['extension'] for item in combo['items']} == {'jpg', 'dng'}
