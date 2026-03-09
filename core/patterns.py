from datetime import datetime
from pathlib import Path
from typing import Optional

MONTH_NAMES_PT = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

MONTH_ABBR_PT = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr',
    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}

BUILTIN_PATTERNS = [
    {
        'id': 'year_month',
        'label': 'Ano/Mês numérico',
        'pattern': '{year}/{month:02d}',
        'example': '2024/03',
    },
    {
        'id': 'year_month_name',
        'label': 'Ano/Nome do mês',
        'pattern': '{year}/{month_name}',
        'example': '2024/Março',
    },
    {
        'id': 'year_month_abbr',
        'label': 'Ano/Mês abreviado',
        'pattern': '{year}/{month:02d}-{month_abbr}',
        'example': '2024/03-Mar',
    },
    {
        'id': 'year_month_day',
        'label': 'Ano/Mês/Dia',
        'pattern': '{year}/{month:02d}/{day:02d}',
        'example': '2024/03/15',
    },
    {
        'id': 'year_dash_month',
        'label': 'Ano-Mês (plano)',
        'pattern': '{year}-{month:02d}',
        'example': '2024-03',
    },
    {
        'id': 'year_only',
        'label': 'Apenas Ano',
        'pattern': '{year}',
        'example': '2024',
    },
]


def _build_context(date: datetime) -> dict:
    return {
        'year': date.year,
        'month': date.month,
        'day': date.day,
        'hour': date.hour,
        'minute': date.minute,
        'second': date.second,
        'month_name': MONTH_NAMES_PT[date.month],
        'month_abbr': MONTH_ABBR_PT[date.month],
    }


def apply_pattern(pattern: str, date: datetime, filename: str) -> str:
    """Generate relative path from pattern and date."""
    ctx = _build_context(date)
    try:
        folder = pattern.format(**ctx)
    except (KeyError, ValueError):
        folder = str(date.year)
    # Normalize path separators
    folder = folder.replace('\\', '/')
    return f"{folder}/{filename}"


def validate_pattern(pattern: str) -> bool:
    """Validate pattern syntax."""
    if not pattern or not pattern.strip():
        return False
    sample = datetime(2024, 3, 15, 10, 30, 0)
    try:
        result = apply_pattern(pattern, sample, 'test.jpg')
        return bool(result)
    except Exception:
        return False


def preview_pattern(pattern: str, sample_date: Optional[datetime] = None) -> str:
    """Return preview of pattern with sample date."""
    if sample_date is None:
        sample_date = datetime(2024, 3, 15, 10, 30, 0)
    if not validate_pattern(pattern):
        return "Padrão inválido"
    return apply_pattern(pattern, sample_date, 'IMG_1234.jpg')
