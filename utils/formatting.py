from datetime import datetime, timedelta


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


def format_date(dt: datetime | None) -> str:
    """Format datetime to display string."""
    if dt is None:
        return "Desconhecida"
    return dt.strftime("%d/%m/%Y %H:%M")


def format_date_short(dt: datetime | None) -> str:
    """Format datetime to short display string."""
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y")


def format_duration(seconds: float) -> str:
    """Format seconds to human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}min"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_speed(files_per_second: float) -> str:
    """Format processing speed."""
    if files_per_second < 1:
        return f"{files_per_second:.2f} arq/s"
    return f"{files_per_second:.1f} arq/s"


def format_eta(remaining_files: int, files_per_second: float) -> str:
    """Format estimated time to arrival."""
    if files_per_second <= 0:
        return "calculando..."
    seconds = remaining_files / files_per_second
    return f"ETA: {format_duration(seconds)}"


def format_count(n: int) -> str:
    """Format large numbers with separators."""
    return f"{n:,}".replace(',', '.')


def truncate_path(path_str: str, max_len: int = 60) -> str:
    """Truncate long paths for display."""
    if len(path_str) <= max_len:
        return path_str
    parts = path_str.split('/')
    if len(parts) <= 2:
        return path_str[:max_len] + '...'
    return f"{parts[0]}/.../{parts[-1]}"
