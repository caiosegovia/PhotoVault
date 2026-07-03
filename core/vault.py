import re
from dataclasses import dataclass
from pathlib import Path

from core.identity import MediaIdentity
from core.patterns import apply_pattern


@dataclass(frozen=True)
class VaultConfig:
    id: int
    label: str
    root_path: Path
    pattern: str


def _clean_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned or 'media'


def canonical_filename(identity: MediaIdentity) -> str:
    """Build a stable, inspectable filename for the vault."""
    original_stem = _clean_name(identity.path.stem)
    suffix = identity.extension or identity.path.suffix.lower()
    digest = identity.sha256[:12]

    if identity.date_taken and hasattr(identity.date_taken, 'strftime'):
        prefix = identity.date_taken.strftime('%Y-%m-%d_%H-%M-%S')
    else:
        prefix = 'sem-data'

    device = ''
    if identity.device_name and identity.device_name != 'Desconhecido':
        device = '_' + _clean_name(identity.device_name).replace(' ', '')

    return f"{prefix}{device}_{original_stem}_{digest}{suffix.lower()}"


def canonical_path(vault: VaultConfig, identity: MediaIdentity) -> Path:
    """Return the canonical destination path for an asset inside a vault."""
    filename = canonical_filename(identity)
    if identity.date_taken and hasattr(identity.date_taken, 'strftime'):
        relative = apply_pattern(vault.pattern, identity.date_taken, filename)
        return vault.root_path / relative
    return vault.root_path / 'sem-data' / filename
