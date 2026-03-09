import customtkinter as ctk
from utils.constants import APP_NAME, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT

# Theme settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLOR_BG = "#1a1a2e"
COLOR_SIDEBAR = "#16213e"
COLOR_CARD = "#0f3460"
COLOR_ACCENT = "#0d7377"
COLOR_ACCENT2 = "#14a085"
COLOR_TEXT = "#e0e0e0"
COLOR_TEXT_DIM = "#888888"
COLOR_SUCCESS = "#2ecc71"
COLOR_WARNING = "#f39c12"
COLOR_ERROR = "#e74c3c"
COLOR_BORDER = "#2a2a4a"

FONT_FAMILY = "Segoe UI" if __import__('platform').system() == 'Windows' else "Inter"
FONT_SIZE_TITLE = 20
FONT_SIZE_HEADER = 16
FONT_SIZE_BODY = 13
FONT_SIZE_SMALL = 11


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
