import customtkinter as ctk
from concurrent.futures import ThreadPoolExecutor
from utils.constants import APP_NAME, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
import logging

# Theme settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Modernized Color Palette
COLOR_BG = "#0f111a"      # Deeper, richer background
COLOR_SIDEBAR = "#1a1c26" # Distinct sidebar
COLOR_CARD = "#1f2233"    # Elevated cards
COLOR_ACCENT = "#3d5afe"  # Vibrant blue
COLOR_ACCENT2 = "#00b0ff" # Secondary bright blue
COLOR_TEXT = "#f8f9fa"    # Clean white
COLOR_TEXT_DIM = "#9ca3af" # Subdued text
COLOR_SUCCESS = "#10b981" # Modern emerald
COLOR_WARNING = "#f59e0b" # Warm amber
COLOR_ERROR = "#ef4444"   # Bright red
COLOR_BORDER = "#2e324a"  # Subtle borders

FONT_FAMILY = "Segoe UI" if __import__('platform').system() == 'Windows' else "Inter"
FONT_SIZE_TITLE = 24
FONT_SIZE_HEADER = 18
FONT_SIZE_BODY = 14
FONT_SIZE_SMALL = 12


class PhotoVaultApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry(f"{WINDOW_MIN_WIDTH}x{WINDOW_MIN_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=COLOR_BG)

        # Global thread pool for I/O and CPU-bound tasks (thumb loading, hashing, etc.)
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="PhotoVaultThread")
        
        # Override the protocol for closing the app to ensure thread pool shutdown
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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

    def _on_close(self):
        """Clean up resources before closing."""
        logging.info("Shutting down PhotoVault...")
        self.executor.shutdown(wait=False)
        self.destroy()
