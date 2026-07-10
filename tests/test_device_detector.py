from pathlib import Path

from core.device_detector import classify_device


def test_classify_iphone_from_metadata():
    device = classify_device(make='Apple', model='iPhone 14 Pro')

    assert device.device_type == 'phone'
    assert device.normalized_name == 'Apple iPhone 14 Pro'


def test_classify_drone_from_dji_metadata():
    device = classify_device(make='DJI', model='FC3582')

    assert device.device_type == 'drone'
    assert device.make == 'DJI'
    assert device.model == 'FC3582'
    assert device.normalized_name == 'DJI FC3582'


def test_classify_drone_normalizes_fc_without_make():
    device = classify_device(model='FC3582')

    assert device.device_type == 'drone'
    assert device.make == 'DJI'
    assert device.normalized_name == 'DJI FC3582'


def test_classify_social_export_from_software():
    device = classify_device(software='WhatsApp')

    assert device.device_type == 'app'
    assert device.normalized_name == 'WhatsApp'


def test_classify_origin_from_path_fallback():
    device = classify_device(path=Path('E:/Backups/Drone/DJI_0001.JPG'))

    assert device.device_type == 'drone'
    assert device.origin_hint == 'path'
