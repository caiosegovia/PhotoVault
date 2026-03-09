from pathlib import Path

PHOTO_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.heic', '.heif',
    '.tiff', '.tif', '.raw', '.cr2', '.cr3',
    '.nef', '.arw', '.dng', '.orf', '.rw2'
}
VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.m4v',
    '.3gp', '.wmv', '.mts', '.m2ts'
}
ALL_MEDIA_EXTENSIONS = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS

DB_PATH = Path.home() / '.photovault' / 'database.db'
TOKEN_PATH = Path.home() / '.photovault' / 'google_token.json'
CONFIG_DIR = Path.home() / '.photovault'

GOOGLE_PHOTOS_SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.readonly'
]

APP_NAME = 'PhotoVault'
APP_VERSION = '1.0.0'
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 800

PHASH_THRESHOLD_DEFAULT = 10
PARTIAL_HASH_CHUNK = 65536  # 64KB
