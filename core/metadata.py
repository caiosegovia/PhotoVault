import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from core.device_detector import classify_device
from utils.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


def _parse_exif_date(date_str: str) -> Optional[datetime]:
    """Parse EXIF date format YYYY:MM:DD HH:MM:SS."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in ('%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _extract_photo_date(path: Path) -> Optional[datetime]:
    """Extract date from photo using exifread → Pillow fallback."""
    # Try exifread first
    try:
        import exifread
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal', details=False)
        for tag in ('EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime'):
            if tag in tags:
                dt = _parse_exif_date(str(tags[tag]))
                if dt:
                    return dt
    except Exception:
        pass

    # Try Pillow
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        with Image.open(path) as img:
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, '')
                    if tag in ('DateTimeOriginal', 'DateTimeDigitized', 'DateTime'):
                        dt = _parse_exif_date(value)
                        if dt:
                            return dt
    except Exception:
        pass

    return None


def _extract_photo_device(path: Path) -> dict:
    """Extract camera/device fields from EXIF with Pillow fallback."""
    fields = {'make': None, 'model': None, 'software': None, 'lens_model': None}

    try:
        import exifread
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        mapping = {
            'Image Make': 'make',
            'Image Model': 'model',
            'Image Software': 'software',
            'EXIF LensModel': 'lens_model',
        }
        for tag_name, field in mapping.items():
            if tag_name in tags:
                fields[field] = str(tags[tag_name])
    except Exception:
        pass

    if any(fields.values()):
        return fields

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        with Image.open(path) as img:
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, '')
                    if tag == 'Make':
                        fields['make'] = value
                    elif tag == 'Model':
                        fields['model'] = value
                    elif tag == 'Software':
                        fields['software'] = value
                    elif tag == 'LensModel':
                        fields['lens_model'] = value
    except Exception:
        pass

    return fields


def _extract_video_date(path: Path) -> Optional[datetime]:
    """Extract date from video using hachoir → ffprobe fallback."""
    # Try hachoir
    try:
        from hachoir.parser import createParser
        from hachoir.metadata import extractMetadata
        parser = createParser(str(path))
        if parser:
            with parser:
                metadata = extractMetadata(parser)
            if metadata:
                for attr in ('creation_date', 'date_time_original', 'date'):
                    try:
                        val = metadata.get(attr)
                        if val:
                            if isinstance(val, datetime):
                                return val
                            dt = _parse_exif_date(str(val))
                            if dt:
                                return dt
                    except Exception:
                        continue
    except Exception:
        pass

    # Try ffprobe
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', str(path)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            tags = data.get('format', {}).get('tags', {})
            for key in ('creation_time', 'date', 'com.apple.quicktime.creationdate'):
                if key in tags:
                    val = tags[key]
                    try:
                        return datetime.fromisoformat(val.replace('Z', '+00:00')).replace(tzinfo=None)
                    except Exception:
                        dt = _parse_exif_date(val)
                        if dt:
                            return dt
    except Exception:
        pass

    return None


def _extract_video_metadata(path: Path) -> dict:
    fields = {'make': None, 'model': None, 'software': None, 'lens_model': None}
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', str(path)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            tags = data.get('format', {}).get('tags', {}) or {}
            stream_tags = {}
            for stream in data.get('streams', []) or []:
                stream_tags.update(stream.get('tags', {}) or {})
            tags = {**stream_tags, **tags}
            fields['make'] = tags.get('make') or tags.get('com.apple.quicktime.make')
            fields['model'] = tags.get('model') or tags.get('com.apple.quicktime.model')
            fields['software'] = tags.get('encoder') or tags.get('software') or tags.get('com.apple.quicktime.software')
    except Exception:
        pass
    return fields


def get_media_date(path: Path) -> Optional[datetime]:
    """Get media date with full fallback chain ending at mtime."""
    ext = path.suffix.lower()

    if ext in PHOTO_EXTENSIONS:
        dt = _extract_photo_date(path)
    elif ext in VIDEO_EXTENSIONS:
        dt = _extract_video_date(path)
    else:
        dt = None

    if dt is None:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime)
        except Exception:
            return None
    return dt


def get_media_info(path: Path) -> dict:
    """Return full info dict for a media file."""
    ext = path.suffix.lower()
    stat = path.stat()

    if ext in PHOTO_EXTENSIONS:
        media_type = 'photo'
    elif ext in VIDEO_EXTENSIONS:
        media_type = 'video'
    else:
        media_type = 'other'

    info = {
        'date': None,
        'width': None,
        'height': None,
        'duration': None,
        'size': stat.st_size,
        'type': media_type,
        'has_exif': False,
        'extension': ext,
        'camera_make': None,
        'camera_model': None,
        'lens_model': None,
        'software': None,
        'device_type': 'unknown',
        'device_name': 'Desconhecido',
        'origin_hint': 'metadata',
    }

    if media_type == 'photo':
        info['date'] = _extract_photo_date(path)
        if info['date']:
            info['has_exif'] = True
        else:
            info['date'] = datetime.fromtimestamp(stat.st_mtime)
        try:
            from PIL import Image
            with Image.open(path) as img:
                info['width'], info['height'] = img.size
        except Exception:
            pass
        device_fields = _extract_photo_device(path)
        device = classify_device(path=path, **device_fields)
        info.update({
            'camera_make': device.make,
            'camera_model': device.model,
            'lens_model': device.lens_model,
            'software': device.software,
            'device_type': device.device_type,
            'device_name': device.normalized_name,
            'origin_hint': device.origin_hint,
        })

    elif media_type == 'video':
        info['date'] = _extract_video_date(path)
        if info['date']:
            info['has_exif'] = True
        else:
            info['date'] = datetime.fromtimestamp(stat.st_mtime)
        try:
            from hachoir.parser import createParser
            from hachoir.metadata import extractMetadata
            parser = createParser(str(path))
            if parser:
                with parser:
                    metadata = extractMetadata(parser)
                if metadata:
                    try:
                        info['duration'] = metadata.get('duration').seconds if metadata.get('duration') else None
                    except Exception:
                        pass
                    try:
                        info['width'] = metadata.get('width')
                        info['height'] = metadata.get('height')
                    except Exception:
                        pass
        except Exception:
            pass
        device_fields = _extract_video_metadata(path)
        device = classify_device(path=path, **device_fields)
        info.update({
            'camera_make': device.make,
            'camera_model': device.model,
            'lens_model': device.lens_model,
            'software': device.software,
            'device_type': device.device_type,
            'device_name': device.normalized_name,
            'origin_hint': device.origin_hint,
        })
    else:
        info['date'] = datetime.fromtimestamp(stat.st_mtime)
        device = classify_device(path=path)
        info.update({
            'device_type': device.device_type,
            'device_name': device.normalized_name,
            'origin_hint': device.origin_hint,
        })

    return info
