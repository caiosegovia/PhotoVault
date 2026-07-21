from pathlib import Path

import pytest


def test_create_import_analysis_persists_timeline_and_files(tmp_path, monkeypatch):
    import core.database as database
    import core.imports as imports

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    src = tmp_path / 'camera'
    vault = tmp_path / 'vault'
    src.mkdir()
    vault.mkdir()
    (src / 'a.jpg').write_bytes(b'one')
    (src / 'b.jpg').write_bytes(b'one')
    (src / 'c.jpg').write_bytes(b'two')

    analysis = imports.create_import_analysis(src, vault, name='Camera antiga')
    timeline = database.list_imports()
    files = database.get_import_files(analysis.import_id)

    assert analysis.files_found == 3
    assert analysis.files_new == 2
    assert analysis.files_duplicate == 1
    assert timeline[0]['name'] == 'Camera antiga'
    assert timeline[0]['status'] == 'analyzed'
    assert len(files) == 3
    assert {item['reason'] for item in files} == {'new_asset', 'exact_duplicate_in_plan'}


def test_execute_import_updates_import_status_and_copies_new_files(tmp_path, monkeypatch):
    import core.database as database
    import core.imports as imports
    import core.ingestion as ingestion

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    src = tmp_path / 'phone'
    vault = tmp_path / 'vault'
    src.mkdir()
    vault.mkdir()
    (src / 'photo.jpg').write_bytes(b'photo-bytes')

    analysis = imports.create_import_analysis(src, vault)
    stats = ingestion.execute_ingest_plan(analysis.plan_id)
    row = database.get_import(analysis.import_id)
    files = database.get_import_files(analysis.import_id)
    copied = Path(files[0]['dst_path'])

    assert stats['processed'] == 1
    assert row['status'] == 'completed'
    assert row['files_imported'] == 1
    assert row['bytes_imported'] == len(b'photo-bytes')
    assert files[0]['status'] == 'done'
    assert copied.exists()


def test_update_decision_group_updates_files_and_operations_atomically(tmp_path, monkeypatch):
    import core.database as database

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()
    vault_id = database.save_vault('Vault', str(tmp_path / 'vault'), '{year}/{month}')
    import_id = database.create_import(vault_id, 'Import', str(tmp_path / 'source'))
    plan_id = database.create_ingest_plan(vault_id)
    database.set_import_plan(import_id, plan_id)

    operation_ids = []
    for index in range(3):
        src = str(tmp_path / 'source' / f'{index}.jpg')
        dst = str(tmp_path / 'vault' / f'{index}.jpg')
        operation_id = database.add_ingest_operation(plan_id, {
            'src_path': src, 'dst_path': dst, 'action': 'copy', 'reason': 'duplicate',
        })
        operation_ids.append(operation_id)
        database.add_import_file(import_id, {
            'src_path': src, 'dst_path': dst, 'ingest_operation_id': operation_id,
            'decision': 'copy', 'reason': 'duplicate',
        })

    updated = database.update_import_file_decisions_by_reason(import_id, 'duplicate', 'skip')

    assert updated == 3
    assert {row['decision'] for row in database.get_import_files(import_id)} == {'skip'}
    operations = database.get_ingest_operations(plan_id)
    assert {row['action'] for row in operations} == {'skip'}
    assert {row['status'] for row in operations} == {'skipped'}


def test_create_import_analysis_rejects_source_inside_vault(tmp_path, monkeypatch):
    import core.database as database
    import core.imports as imports

    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'database.db')
    database.init_db()

    vault = tmp_path / 'vault'
    src = vault / 'camera'
    src.mkdir(parents=True)
    (src / 'photo.jpg').write_bytes(b'photo')

    with pytest.raises(ValueError, match='origem esta dentro do vault'):
        imports.create_import_analysis(src, vault)
