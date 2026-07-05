from pathlib import Path


def resolve_existing_or_parent(path: Path) -> Path:
    """Resolve a path even when the final folder does not exist yet."""
    try:
        return path.resolve()
    except OSError:
        parent = path
        while not parent.exists() and parent.parent != parent:
            parent = parent.parent
        return parent.resolve() / path.relative_to(parent)


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_import_paths(source_path: Path, vault_root: Path) -> None:
    source = resolve_existing_or_parent(source_path)
    vault = resolve_existing_or_parent(vault_root)

    if source == vault:
        raise ValueError("A origem nao pode ser o proprio vault")
    if is_relative_to(source, vault):
        raise ValueError("A origem esta dentro do vault; escolha uma pasta externa")
    if is_relative_to(vault, source):
        raise ValueError("O vault esta dentro da origem; isso faria a importacao varrer o destino")


def validate_reset_root(config_dir: Path) -> Path:
    root = config_dir.resolve()
    expected = Path.home().resolve() / ".photovault"
    if root != expected:
        raise ValueError(f"Diretorio de configuracao inesperado: {root}")
    return root
