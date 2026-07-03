from datetime import datetime

from core.patterns import apply_pattern, preview_pattern, validate_pattern


def test_apply_pattern_formats_date_parts():
    dt = datetime(2024, 3, 15, 10, 30, 0)

    assert apply_pattern('{year}/{month:02d}/{day:02d}', dt, 'IMG_1.JPG') == (
        '2024/03/15/IMG_1.JPG'
    )


def test_apply_pattern_falls_back_to_year_for_invalid_pattern():
    dt = datetime(2024, 3, 15, 10, 30, 0)

    assert apply_pattern('{unknown}', dt, 'IMG_1.JPG') == '2024/IMG_1.JPG'


def test_validate_and_preview_pattern():
    assert validate_pattern('{year}/{month_name}')
    assert not validate_pattern('')
    assert preview_pattern('{year}/{month:02d}') == '2024/03/IMG_1234.jpg'
