import customtkinter as ctk
from utils.constants import APP_NAME, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
from gui.theme import (
    ACCENT,
    ACCENT_HOVER,
    APP_BG,
    BORDER,
    ERROR,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_HEADER,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    SIDEBAR_BG,
    SUCCESS,
    SURFACE,
    TEXT,
    TEXT_MUTED,
    WARNING,
)

# Theme settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

COLOR_BG = APP_BG
COLOR_SIDEBAR = SIDEBAR_BG
COLOR_CARD = SURFACE
COLOR_ACCENT = ACCENT
COLOR_ACCENT2 = ACCENT_HOVER
COLOR_TEXT = TEXT
COLOR_TEXT_DIM = TEXT_MUTED
COLOR_SUCCESS = SUCCESS
COLOR_WARNING = WARNING
COLOR_ERROR = ERROR
COLOR_BORDER = BORDER


class PhotoVaultApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry(f"{WINDOW_MIN_WIDTH}x{WINDOW_MIN_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=COLOR_BG)

        # App state shared across views
        self.app_state = {
            'sources': [],          # list of source dicts
            'destination': None,    # Path
            'pattern': '{year}/{month:02d}',
            'mode': 'copy',
            'scan_results': None,   # count_files result
            'plan': None,           # OrganizationPlan
            'dup_result': None,     # DuplicateResult
            'session': {},
            'phash_threshold': 10,
            'include_no_date': True,
            'skip_existing': True,  # skip files already at destination
            'extensions': None,     # None = all
            'google_client': None,  # authenticated GooglePhotosClient
        }
