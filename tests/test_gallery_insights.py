from datetime import datetime
from pathlib import Path


def test_gallery_item_flags_low_resolution_and_missing_exif(tmp_path):
    from core.gallery_insights import item_from_info

    path = tmp_path / "small.jpg"
    path.write_bytes(b"fake")

    item = item_from_info(
        path,
        {
            "type": "photo",
            "extension": ".jpg",
            "size": 1024,
            "date": datetime(2023, 1, 2, 3, 4, 5),
            "width": 640,
            "height": 480,
            "has_exif": False,
            "device_name": "Apple iPhone",
            "device_type": "phone",
        },
        "Camera Roll",
    )

    assert item.media_type == "photo"
    assert "Sem EXIF" in item.flags
    assert "Baixa resolucao" in item.flags
    assert "Celular" in item.flags
    assert "Celular" in item.chips
    assert item.source_label == "Camera Roll"


def test_summarize_gallery_counts_duplicate_and_actions(tmp_path):
    from core.gallery_insights import item_from_info, summarize_gallery

    path = tmp_path / "video.mp4"
    path.write_bytes(b"fake")
    item = item_from_info(
        path,
        {
            "type": "video",
            "extension": ".mp4",
            "size": 60 * 1024 * 1024,
            "date": None,
            "has_exif": False,
            "device_name": "DJI Mini",
            "device_type": "drone",
        },
        "Drone",
    )

    summary = summarize_gallery([item], duplicate_paths={str(path)})

    assert summary["videos"] == 1
    assert summary["large_files"] == 1
    assert summary["duplicates"] == 1
    assert summary["devices"]["DJI Mini"] == 1
    assert any(title == "Duplicatas" for title, _text in summary["actions"])
