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
    monkeypatch.setattr(bridge, 'get_cached_thumbnail', lambda _path: None)
    monkeypatch.setattr(bridge, 'has_ffmpeg', lambda: False)
    monkeypatch.setattr(bridge, 'has_exiftool', lambda: False)
    monkeypatch.setattr(bridge, 'exiftool_version', lambda: '')
    monkeypatch.setattr(bridge, 'exiftool_status', lambda: {'available': False})
    monkeypatch.setattr(bridge, 'processing_summary', lambda _processor: {'total': 0})
    monkeypatch.setattr(bridge, 'environment_diagnostics', lambda: {'status': 'ok'})
    monkeypatch.setattr(bridge, 'gallery_health', lambda: {'total': 0})

    def list_assets(limit):
        calls.append(f'assets:{limit}')
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

    result = bridge.gallery({'limit': 10})

    assert calls == ['backfill', 'assets:10']
    assert result['timings']['backfillCount'] == 2
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
    monkeypatch.setattr(bridge, 'list_gallery_assets', lambda _limit: (_ for _ in ()).throw(AssertionError('assets should not load')))
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
    monkeypatch.setattr(bridge, 'list_gallery_assets', lambda _limit: [{
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

    result = bridge.gallery({'limit': 10, 'ensureThumbnails': True})

    assert str(photo) in hydrated
    assert result['items'][0]['thumbnail'] == str(thumb)
    assert result['items'][0]['previewStatus'] == 'ready'


def test_search_gallery_uses_search_assets(monkeypatch):
    import bridge

    monkeypatch.setattr(bridge, 'init_db', lambda: None)
    monkeypatch.setattr(bridge, '_gallery_payload', lambda _limit, include_items=False: {
        'items': [],
        'total': 2,
        'breakdowns': {'media': [], 'years': [], 'months': [], 'extensions': []},
    })
    monkeypatch.setattr(bridge, 'search_gallery_assets', lambda query, limit: [{
        'instance_id': 9,
        'asset_id': 13,
        'path': 'D:/Vault/drone-shot.mp4',
        'media_type': 'video',
        'extension': '.mp4',
        'size': 20,
        'tags': 'drone',
        'note_count': 1,
        'latest_note': 'Bom take',
    }] if query == 'drone' and limit == 25 else [])
    monkeypatch.setattr(bridge, 'get_cached_thumbnail', lambda _path: None)
    monkeypatch.setattr(bridge, 'has_ffmpeg', lambda: True)

    result = bridge.search_gallery({'query': 'drone', 'limit': 25})

    assert result['search']['count'] == 1
    assert result['items'][0]['tags'] == 'drone'
    assert result['items'][0]['latestNote'] == 'Bom take'
