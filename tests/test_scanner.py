from core.scanner import count_files, scan_directory


def test_scan_directory_filters_media_extensions(tmp_path):
    (tmp_path / 'a.jpg').write_bytes(b'photo')
    (tmp_path / 'b.mp4').write_bytes(b'video')
    (tmp_path / 'notes.txt').write_text('ignore', encoding='utf-8')

    found = {p.name for p in scan_directory(tmp_path)}

    assert found == {'a.jpg', 'b.mp4'}


def test_count_files_by_type_and_size(tmp_path):
    (tmp_path / 'a.jpg').write_bytes(b'123')
    (tmp_path / 'b.mp4').write_bytes(b'12345')
    (tmp_path / 'notes.txt').write_text('ignore', encoding='utf-8')

    counts = count_files(tmp_path)

    assert counts['total'] == 2
    assert counts['photos'] == 1
    assert counts['videos'] == 1
    assert counts['size_bytes'] == 8
