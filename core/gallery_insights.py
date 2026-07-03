from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from core.metadata import get_media_info
from utils.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


@dataclass
class GalleryItem:
    path: Path
    name: str
    source_label: str = "Fonte desconhecida"
    media_type: str = "other"
    extension: str = ""
    size: int = 0
    date_taken: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None
    has_exif: bool = False
    device_name: str = "Desconhecido"
    device_type: str = "unknown"
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    lens_model: Optional[str] = None
    software: Optional[str] = None
    origin_hint: str = "metadata"
    flags: list[str] = field(default_factory=list)
    chips: list[str] = field(default_factory=list)
    score: int = 50

    @property
    def megapixels(self) -> float:
        if not self.width or not self.height:
            return 0.0
        return (self.width * self.height) / 1_000_000

    @property
    def year(self) -> str:
        return str(self.date_taken.year) if self.date_taken else "Sem data"

    @property
    def resolution_label(self) -> str:
        if not self.width or not self.height:
            return "sem dimensoes"
        return f"{self.width}x{self.height}"

    @property
    def date_group_label(self) -> str:
        if not self.date_taken:
            return "Sem data"
        return self.date_taken.strftime("%Y-%m")


def _parse_date(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def source_label_for_path(path: Path, sources: Iterable[dict]) -> str:
    p = str(path).lower()
    matches: list[tuple[str, str]] = []
    for source in sources:
        if source.get("type") == "cloud":
            continue
        root = str(source.get("path", ""))
        if root and p.startswith(root.lower()):
            label = source.get("label") or Path(root).name or root
            matches.append((root, label))
    if not matches:
        return "Fonte desconhecida"
    return max(matches, key=lambda item: len(item[0]))[1]


def item_from_path(path: Path, sources: Iterable[dict]) -> Optional[GalleryItem]:
    try:
        info = get_media_info(path)
    except Exception:
        return None
    return item_from_info(path, info, source_label_for_path(path, sources))


def item_from_record(record, sources: Iterable[dict]) -> Optional[GalleryItem]:
    try:
        path = Path(record["path"])
    except Exception:
        return None
    if not path.exists():
        return None
    info = {
        "type": record["media_type"],
        "extension": record["extension"],
        "size": record["size"],
        "date": _parse_date(record["date_taken"]),
        "has_exif": bool(record["has_exif"]) if "has_exif" in record.keys() else bool(record["date_taken"]),
        "camera_make": record["camera_make"],
        "camera_model": record["camera_model"],
        "lens_model": record["lens_model"],
        "software": record["software"],
        "device_type": record["device_type"],
        "device_name": record["device_name"],
        "origin_hint": record["origin_hint"],
        "width": record["width"] if "width" in record.keys() else None,
        "height": record["height"] if "height" in record.keys() else None,
        "duration": record["duration"] if "duration" in record.keys() else None,
    }
    source_label = None
    try:
        source_label = record["source_label"]
    except Exception:
        source_label = None
    return item_from_info(path, info, source_label or source_label_for_path(path, sources))


def item_from_info(path: Path, info: dict, source_label: str) -> GalleryItem:
    flags: list[str] = []
    chips: list[str] = []
    ext = (info.get("extension") or path.suffix).lower()
    media_type = info.get("type") or ("photo" if ext in PHOTO_EXTENSIONS else "video" if ext in VIDEO_EXTENSIONS else "other")
    size = int(info.get("size") or 0)
    width = info.get("width")
    height = info.get("height")
    has_exif = bool(info.get("has_exif"))
    score = 50

    if media_type == "video":
        flags.append("Video")
        chips.append("Video")
        score += 5
    if not has_exif:
        flags.append("Sem EXIF")
        score -= 12
    if width and height:
        mp = (width * height) / 1_000_000
        if mp < 1.0:
            flags.append("Baixa resolucao")
            chips.append("Baixa res")
            score -= 15
        elif mp >= 12:
            flags.append("Alta resolucao")
            chips.append("12MP+")
            score += 10
        elif mp >= 8:
            chips.append("8MP+")
        if width >= 3840 or height >= 2160:
            chips.append("4K")
        elif width >= 1920 or height >= 1080:
            chips.append("Full HD")
        ratio = max(width, height) / max(min(width, height), 1)
        if ratio > 2.2:
            flags.append("Panorama")
            chips.append("Panorama")
    else:
        flags.append("Sem dimensoes")
        chips.append("Sem dimensoes")
        score -= 8
    if size >= 250 * 1024 * 1024:
        flags.append("Muito pesado")
        chips.append("Muito pesado")
        score -= 8
    elif size >= 50 * 1024 * 1024:
        flags.append("Pesado")
        chips.append("Pesado")
    device_type = info.get("device_type") or "unknown"
    device_label = {
        "drone": "Drone",
        "phone": "Celular",
        "camera": "Camera",
        "action_camera": "Action cam",
        "screen": "Captura",
        "unknown": "Origem incerta",
    }.get(device_type, device_type.title())
    if device_type in {"drone", "phone", "camera", "action_camera", "screen"}:
        flags.append(device_label)
        chips.append(device_label)
        score += 4
    if not info.get("date"):
        flags.append("Sem data")
        chips.append("Sem data")
        score -= 10
    if not has_exif:
        chips.append("Sem EXIF")
    if info.get("lens_model"):
        chips.append("Lente")
    if info.get("software"):
        software = str(info.get("software"))
        if "lightroom" in software.lower():
            chips.append("Editada")
        elif "photoshop" in software.lower():
            chips.append("Editada")

    return GalleryItem(
        path=path,
        name=path.name,
        source_label=source_label,
        media_type=media_type,
        extension=ext,
        size=size,
        date_taken=info.get("date"),
        width=width,
        height=height,
        duration=info.get("duration"),
        has_exif=has_exif,
        device_name=info.get("device_name") or "Desconhecido",
        device_type=device_type,
        camera_make=info.get("camera_make"),
        camera_model=info.get("camera_model"),
        lens_model=info.get("lens_model"),
        software=info.get("software"),
        origin_hint=info.get("origin_hint") or "metadata",
        flags=flags[:5],
        chips=_dedupe(chips)[:6],
        score=max(0, min(100, score)),
    )


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def summarize_gallery(items: list[GalleryItem], duplicate_paths: set[str] | None = None) -> dict:
    duplicate_paths = duplicate_paths or set()
    summary = {
        "total": len(items),
        "photos": 0,
        "videos": 0,
        "missing_exif": 0,
        "large_files": 0,
        "low_resolution": 0,
        "duplicates": 0,
        "devices": {},
        "years": {},
        "sources": {},
        "date_groups": {},
        "quality": {},
        "actions": [],
    }
    for item in items:
        if item.media_type == "photo":
            summary["photos"] += 1
        elif item.media_type == "video":
            summary["videos"] += 1
        if not item.has_exif:
            summary["missing_exif"] += 1
        if item.size >= 50 * 1024 * 1024:
            summary["large_files"] += 1
        if "Baixa resolucao" in item.flags:
            summary["low_resolution"] += 1
        if str(item.path) in duplicate_paths:
            summary["duplicates"] += 1
        summary["devices"][item.device_name] = summary["devices"].get(item.device_name, 0) + 1
        summary["years"][item.year] = summary["years"].get(item.year, 0) + 1
        summary["date_groups"][item.date_group_label] = summary["date_groups"].get(item.date_group_label, 0) + 1
        summary["sources"][item.source_label] = summary["sources"].get(item.source_label, 0) + 1
        for chip in item.chips:
            summary["quality"][chip] = summary["quality"].get(chip, 0) + 1

    if summary["duplicates"]:
        summary["actions"].append(("Duplicatas", f"{summary['duplicates']} arquivos ja aparecem em grupos duplicados."))
    if summary["missing_exif"]:
        summary["actions"].append(("Metadados", f"{summary['missing_exif']} itens precisam de data/origem confiavel."))
    if summary["large_files"]:
        summary["actions"].append(("Espaco", f"{summary['large_files']} arquivos grandes merecem revisao primeiro."))
    if summary["low_resolution"]:
        summary["actions"].append(("Qualidade", f"{summary['low_resolution']} fotos parecem ter baixa resolucao."))
    if not summary["actions"]:
        summary["actions"].append(("Curadoria", "A amostra parece saudavel; avance para duplicatas ou organizacao."))
    return summary
