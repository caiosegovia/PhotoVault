from core.deduplicator import find_exact_duplicates, hash_file_full, hash_file_partial


def test_find_exact_duplicates_groups_only_identical_files(tmp_path):
    a = tmp_path / 'a.jpg'
    b = tmp_path / 'b.jpg'
    c = tmp_path / 'c.jpg'
    a.write_bytes(b'same-content')
    b.write_bytes(b'same-content')
    c.write_bytes(b'other-content')

    duplicates = find_exact_duplicates([a, b, c])

    assert len(duplicates) == 1
    assert {p.name for group in duplicates.values() for p in group} == {'a.jpg', 'b.jpg'}


def test_hash_helpers_return_none_for_missing_files(tmp_path):
    missing = tmp_path / 'missing.jpg'

    assert hash_file_partial(missing) is None
    assert hash_file_full(missing) is None
