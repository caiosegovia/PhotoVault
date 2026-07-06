import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.device_detector import classify_device
from core.runtime_tools import exiftool_path, exiftool_version
from utils.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


log = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    total: int = 0
    enriched: int = 0
    skipped: int = 0
    errors: int = 0
    unavailable: bool = False

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "enriched": self.enriched,
            "skipped": self.skipped,
            "errors": self.errors,
            "unavailable": self.unavailable,
            "exiftoolVersion": exiftool_version(),
        }


def _clean_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first(raw: dict, *keys: str) -> object:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_date(value: object) -> Optional[datetime]:
    text = _clean_text(value)
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    candidates = [text]
    if len(text) >= 19 and text[4] == ":" and text[7] == ":":
        candidates.append(f"{text[:4]}-{text[5:7]}-{text[8:]}")
    for candidate in candidates:
        for fmt in (
            "%Y:%m:%d %H:%M:%S",
            "%Y:%m:%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed.replace(tzinfo=None)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(candidate).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _parse_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().split(" ")[0].replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: object) -> Optional[int]:
    number = _parse_float(value)
    return int(number) if number is not None else None


def _media_type(path: Path, raw: dict) -> str:
    ext = path.suffix.lower()
    if ext in PHOTO_EXTENSIONS:
        return "photo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    mime = _clean_text(raw.get("MIMEType")) or ""
    if mime.startswith("image/"):
        return "photo"
    if mime.startswith("video/"):
        return "video"
    return "other"


def normalize_exiftool_metadata(path: Path, raw: dict) -> dict:
    date_taken = _parse_date(
        _first(
            raw,
            "DateTimeOriginal",
            "SubSecDateTimeOriginal",
            "CreateDate",
            "MediaCreateDate",
            "TrackCreateDate",
            "CreationDate",
            "FileModifyDate",
        )
    )
    make = _clean_text(_first(raw, "Make", "CameraMake", "QuickTime:Make"))
    model = _clean_text(_first(raw, "Model", "CameraModelName", "QuickTime:Model"))
    software = _clean_text(_first(raw, "Software", "Encoder", "CompressorName"))
    lens_model = _clean_text(_first(raw, "LensModel", "LensID", "Lens"))
    width = _parse_int(_first(raw, "ImageWidth", "ExifImageWidth", "SourceImageWidth"))
    height = _parse_int(_first(raw, "ImageHeight", "ExifImageHeight", "SourceImageHeight"))
    duration = _parse_float(_first(raw, "Duration", "MediaDuration", "TrackDuration"))
    device = classify_device(
        path=path,
        make=make,
        model=model,
        software=software,
        lens_model=lens_model,
    )
    gps_lat = _parse_float(raw.get("GPSLatitude"))
    gps_lon = _parse_float(raw.get("GPSLongitude"))

    normalized = {
        "date_taken": date_taken,
        "media_type": _media_type(path, raw),
        "extension": path.suffix.lower(),
        "camera_make": device.make,
        "camera_model": device.model,
        "lens_model": device.lens_model,
        "software": device.software,
        "device_type": device.device_type,
        "device_name": device.normalized_name,
        "origin_hint": device.origin_hint,
        "width": width,
        "height": height,
        "duration": duration,
        "gps_latitude": gps_lat,
        "gps_longitude": gps_lon,
        "has_exif": bool(date_taken or make or model or lens_model or gps_lat or gps_lon),
        "exiftool": {
            "file_type": _clean_text(raw.get("FileType")),
            "mime_type": _clean_text(raw.get("MIMEType")),
            "codec": _clean_text(_first(raw, "CompressorID", "CompressorName", "VideoCodec")),
            "bitrate": _clean_text(_first(raw, "AvgBitrate", "VideoBitrate")),
            "frame_rate": _parse_float(_first(raw, "VideoFrameRate", "FrameRate")),
        },
        "raw_exiftool": raw,
    }
    return normalized


def extract_exiftool_metadata(path: Path) -> dict:
    tool = exiftool_path()
    if not tool:
        raise RuntimeError("ExifTool nao encontrado no PATH")
    result = subprocess.run(
        [tool, "-j", "-n", "-api", "largefilesupport=1", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"ExifTool falhou com codigo {result.returncode}")
    payload = json.loads(result.stdout or "[]")
    if not payload:
        raise RuntimeError("ExifTool nao retornou metadados")
    return normalize_exiftool_metadata(path, payload[0])


def enrich_gallery_metadata(limit: int = 1000, callback: Optional[Callable[[int, int, Path], None]] = None) -> EnrichmentResult:
    from core.database import apply_asset_metadata_enrichment, list_destination_assets_for_enrichment

    result = EnrichmentResult()
    if not exiftool_path():
        result.unavailable = True
        return result

    rows = list_destination_assets_for_enrichment(limit)
    result.total = len(rows)
    version = exiftool_version() or "unknown"
    for index, row in enumerate(rows, start=1):
        path = Path(row["path"])
        if callback:
            callback(index, result.total, path)
        if not path.exists():
            result.skipped += 1
            apply_asset_metadata_enrichment(
                asset_id=int(row["asset_id"]),
                path=str(path),
                extractor="exiftool",
                extractor_version=version,
                status="missing",
                raw={"error": "Arquivo nao encontrado"},
                normalized={},
            )
            continue
        try:
            metadata = extract_exiftool_metadata(path)
            apply_asset_metadata_enrichment(
                asset_id=int(row["asset_id"]),
                path=str(path),
                extractor="exiftool",
                extractor_version=version,
                status="ok",
                raw=metadata,
                normalized=metadata,
                mtime=path.stat().st_mtime,
            )
            result.enriched += 1
        except Exception as exc:
            log.warning("exiftool enrichment failed path=%s error=%s", path, exc)
            result.errors += 1
            apply_asset_metadata_enrichment(
                asset_id=int(row["asset_id"]),
                path=str(path),
                extractor="exiftool",
                extractor_version=version,
                status="error",
                raw={"error": str(exc)},
                normalized={},
                mtime=path.stat().st_mtime if path.exists() else None,
            )
    return result
