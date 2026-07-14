import json
from pathlib import Path


def test_tauri_bundle_does_not_embed_exiftool():
    config_path = Path("frontend/src-tauri/tauri.conf.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    resources = config["bundle"].get("resources", [])

    assert not any("exiftool" in resource.lower() for resource in resources)
