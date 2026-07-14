from pathlib import Path
from types import SimpleNamespace

import pytest


def test_build_ingest_plan_skips_exact_duplicates_in_same_run(tmp_path, monkeypatch):
    import core.database as database
    import core.ingestion as ingestion

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    src = tmp_path / 'src'
    vault = tmp_path / 'vault'
    src.mkdir()
    vault.mkdir()
    (src / 'a.jpg').write_bytes(b'same-content')
    (src / 'b.jpg').write_bytes(b'same-content')

    plan = ingestion.build_ingest_plan([src], vault)
    operations = database.get_ingest_operations(plan.plan_id)

    assert plan.scanned == 2
    assert [row['action'] for row in operations].count('copy') == 1
    assert [row['action'] for row in operations].count('skip') == 1
    assert {row['reason'] for row in operations} == {'new_asset', 'exact_duplicate_in_plan'}


def test_execute_ingest_plan_copies_with_verification_and_registers_destination(tmp_path, monkeypatch):
    import core.database as database
    import core.ingestion as ingestion

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    src = tmp_path / 'src'
    vault = tmp_path / 'vault'
    src.mkdir()
    vault.mkdir()
    source = src / 'photo.jpg'
    source.write_bytes(b'original bytes')

    plan = ingestion.build_ingest_plan([src], vault, pattern='{year}/{month:02d}')
    stats = ingestion.execute_ingest_plan(plan.plan_id)
    operations = database.get_ingest_operations(plan.plan_id)

    copied = [row for row in operations if row['action'] == 'copy'][0]
    dst = Path(copied['dst_path'])
    instances = database.get_asset_instances(copied['asset_id'])

    assert stats['processed'] == 1
    assert stats['errors'] == 0
    assert dst.exists()
    assert dst.read_bytes() == b'original bytes'
    assert any(row['role'] == 'destination' and row['path'] == str(dst) for row in instances)


def test_execute_ingest_plan_rejects_plan_larger_than_free_space(tmp_path, monkeypatch):
    import core.database as database
    import core.ingestion as ingestion

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    src = tmp_path / 'src'
    vault = tmp_path / 'vault'
    src.mkdir()
    vault.mkdir()
    source = src / 'large.jpg'
    source.write_bytes(b'large bytes')

    plan = ingestion.build_ingest_plan([src], vault)
    monkeypatch.setattr(
        ingestion.shutil,
        'disk_usage',
        lambda _path: SimpleNamespace(total=100, used=95, free=5),
    )

    with pytest.raises(RuntimeError, match='Espaco insuficiente no destino'):
        ingestion.execute_ingest_plan(plan.plan_id)

    operations = database.get_ingest_operations(plan.plan_id)
    assert [row['status'] for row in operations if row['action'] == 'copy'] == ['planned']


def test_execute_ingest_plan_rejects_new_assets_marked_as_skip(tmp_path, monkeypatch):
    import core.database as database
    import core.ingestion as ingestion

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    src = tmp_path / 'src'
    vault = tmp_path / 'vault'
    src.mkdir()
    vault.mkdir()
    (src / 'photo.jpg').write_bytes(b'original bytes')

    plan = ingestion.build_ingest_plan([src], vault)
    op = database.get_ingest_operations(plan.plan_id)[0]
    database.update_ingest_operation_status(op['id'], 'skipped')
    with database._get_conn() as conn:
        conn.execute("UPDATE ingest_operations SET action='skip' WHERE id=?", (op['id'],))

    with pytest.raises(ValueError, match='arquivos novos estao marcados para ignorar'):
        ingestion.execute_ingest_plan(plan.plan_id)

    assert not any(vault.rglob('*.jpg'))


def test_build_ingest_plan_skips_asset_already_present_in_vault(tmp_path, monkeypatch):
    import core.database as database
    import core.ingestion as ingestion

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    vault = tmp_path / 'vault'
    src = tmp_path / 'src'
    vault.mkdir()
    src.mkdir()
    (vault / 'existing.jpg').write_bytes(b'known bytes')
    (src / 'copy.jpg').write_bytes(b'known bytes')

    plan = ingestion.build_ingest_plan([vault, src], vault)
    operations = database.get_ingest_operations(plan.plan_id)
    source_ops = [row for row in operations if row['src_path'].endswith('copy.jpg')]

    assert len(source_ops) == 1
    assert source_ops[0]['action'] == 'skip'
    assert source_ops[0]['reason'] == 'exact_duplicate_in_vault'


def test_build_ingest_plan_rejects_vault_inside_origin(tmp_path, monkeypatch):
    import core.database as database
    import core.ingestion as ingestion

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    src = tmp_path / 'src'
    vault = src / 'vault'
    vault.mkdir(parents=True)
    (src / 'photo.jpg').write_bytes(b'photo')

    with pytest.raises(ValueError, match='vault esta dentro da origem'):
        ingestion.build_ingest_plan([src], vault)
