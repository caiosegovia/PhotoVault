from datetime import datetime

from core.organizer import apply_duplicate_decisions, execute_plan, plan_organization


def test_plan_organization_uses_pattern_and_resolves_collisions(tmp_path, monkeypatch):
    src_dir = tmp_path / 'src'
    dst_dir = tmp_path / 'dst'
    src_dir.mkdir()
    dst_dir.mkdir()
    source = src_dir / 'photo.jpg'
    source.write_bytes(b'new')
    existing_dir = dst_dir / '2024' / '03'
    existing_dir.mkdir(parents=True)
    (existing_dir / 'photo.jpg').write_bytes(b'existing')

    monkeypatch.setattr(
        'core.organizer.get_media_date',
        lambda path: datetime(2024, 3, 15, 10, 30, 0),
    )

    plan = plan_organization([src_dir], dst_dir, '{year}/{month:02d}')

    assert plan.total == 1
    assert plan.operations[0].dst == existing_dir / 'photo_001.jpg'


def test_plan_organization_can_skip_files_without_dates(tmp_path, monkeypatch):
    src_dir = tmp_path / 'src'
    dst_dir = tmp_path / 'dst'
    src_dir.mkdir()
    dst_dir.mkdir()
    source = src_dir / 'photo.jpg'
    source.write_bytes(b'new')

    monkeypatch.setattr('core.organizer.get_media_date', lambda path: None)

    plan = plan_organization(
        [src_dir],
        dst_dir,
        '{year}/{month:02d}',
        include_no_date=False,
    )

    assert plan.operations[0].action == 'skip'
    assert plan.operations[0].status == 'skipped'


def test_execute_plan_copies_files(tmp_path, monkeypatch):
    src_dir = tmp_path / 'src'
    dst_dir = tmp_path / 'dst'
    src_dir.mkdir()
    dst_dir.mkdir()
    source = src_dir / 'photo.jpg'
    source.write_bytes(b'content')

    monkeypatch.setattr(
        'core.organizer.get_media_date',
        lambda path: datetime(2024, 3, 15, 10, 30, 0),
    )

    plan = plan_organization([src_dir], dst_dir, '{year}/{month:02d}')
    result = execute_plan(plan, verify=True)

    assert result.processed == 1
    assert result.errors == 0
    assert (dst_dir / '2024' / '03' / 'photo.jpg').read_bytes() == b'content'


def test_apply_duplicate_decisions_marks_non_keeper_operations_as_skip(tmp_path, monkeypatch):
    src_dir = tmp_path / 'src'
    dst_dir = tmp_path / 'dst'
    src_dir.mkdir()
    dst_dir.mkdir()
    keeper = src_dir / 'keeper.jpg'
    duplicate = src_dir / 'duplicate.jpg'
    keeper.write_bytes(b'same')
    duplicate.write_bytes(b'same')

    monkeypatch.setattr(
        'core.organizer.get_media_date',
        lambda path: datetime(2024, 3, 15, 10, 30, 0),
    )

    plan = plan_organization([src_dir], dst_dir, '{year}/{month:02d}')
    changed = apply_duplicate_decisions(
        plan,
        {'group': [keeper, duplicate]},
        {'group': str(keeper)},
    )

    skipped = [op for op in plan.operations if op.action == 'skip']
    active = [op for op in plan.operations if op.action != 'skip']

    assert changed == 1
    assert skipped[0].src == duplicate
    assert active[0].src == keeper
