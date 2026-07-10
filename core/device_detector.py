from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional


@dataclass(frozen=True)
class DeviceInfo:
    make: Optional[str] = None
    model: Optional[str] = None
    software: Optional[str] = None
    lens_model: Optional[str] = None
    normalized_name: str = "Desconhecido"
    device_type: str = "unknown"
    origin_hint: str = "metadata"


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().strip("\x00")
    text = re.sub(r"\s+", " ", text)
    return text or None


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(n in low for n in needles)


def _normalize_dji_model(model: Optional[str]) -> Optional[str]:
    if not model:
        return None
    text = _clean(model)
    if not text:
        return None
    upper = text.upper()
    if upper.startswith("DJI "):
        text = text[4:].strip()
        upper = text.upper()
    if upper == "DJI":
        return None
    return text


def classify_device(
    make: str | None = None,
    model: str | None = None,
    software: str | None = None,
    lens_model: str | None = None,
    path: Path | None = None,
) -> DeviceInfo:
    make = _clean(make)
    model = _clean(model)
    software = _clean(software)
    lens_model = _clean(lens_model)

    combined = " ".join(v for v in (make, model, software, lens_model) if v)
    low = combined.lower()
    origin_hint = "metadata" if combined else "path"

    if _contains_any(low, ("whatsapp", "instagram", "facebook", "snapseed", "lightroom")):
        return DeviceInfo(make, model, software, lens_model, software or "App/exportacao", "app", origin_hint)

    is_dji = (make and "dji" in make.lower()) or (model and model.upper().startswith(("FC", "DJI")))
    if is_dji:
        normalized_model = _normalize_dji_model(model)
        name = " ".join(v for v in ("DJI", normalized_model) if v)
        return DeviceInfo("DJI", normalized_model, software, lens_model, name or "DJI", "drone", origin_hint)

    phone_makers = {
        "apple": "Apple",
        "samsung": "Samsung",
        "xiaomi": "Xiaomi",
        "google": "Google",
        "motorola": "Motorola",
        "huawei": "Huawei",
        "oneplus": "OnePlus",
    }
    if make and make.lower() in phone_makers:
        maker = phone_makers[make.lower()]
        dtype = "phone" if model and _contains_any(model, ("iphone", "pixel", "sm-", "moto", "redmi", "mi ")) else "camera"
        return DeviceInfo(make, model, software, lens_model, " ".join(v for v in (maker, model) if v), dtype, origin_hint)

    camera_makers = ("canon", "nikon", "sony", "fujifilm", "olympus", "panasonic", "leica", "gopro")
    if make and make.lower() in camera_makers:
        dtype = "action_camera" if make.lower() == "gopro" else "camera"
        return DeviceInfo(make, model, software, lens_model, " ".join(v for v in (make, model) if v), dtype, origin_hint)

    if path:
        name = path.name.lower()
        parts = [p.lower() for p in path.parts]
        if name.startswith("dji_") or any("dji" in p or "drone" in p for p in parts):
            return DeviceInfo(make, model, software, lens_model, "DJI/Drone", "drone", "path")
        if name.startswith(("gopr", "gh")) or any("gopro" in p for p in parts):
            return DeviceInfo(make, model, software, lens_model, "GoPro", "action_camera", "path")
        if "whatsapp" in name or any("whatsapp" in p for p in parts):
            return DeviceInfo(make, model, software, lens_model, "WhatsApp", "app", "path")
        if any(p in ("dcim", "camera") for p in parts):
            return DeviceInfo(make, model, software, lens_model, "Camera/DCIM", "camera", "path")

    normalized = " ".join(v for v in (make, model) if v) or "Desconhecido"
    return DeviceInfo(make, model, software, lens_model, normalized, "unknown", origin_hint)
