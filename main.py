"""
PhotoVault — Desktop photo/video organizer
Entry point: initializes DB, builds GUI, starts event loop.
"""
import sys
import os
from pathlib import Path

# Fix for visual artifacts on some Windows systems (disable hardware acceleration for Tkinter/Matplotlib)
if sys.platform == 'win32':
    os.environ['TKDND_LIBRARY'] = '' # dummy
    # Force software rendering for some drivers if needed,
    # but more importantly, handle DPI awareness to prevent multi-monitor glitches
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# Ensure project root is on sys.path (dev mode and PyInstaller onedir mode)
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    _base = Path(sys._MEIPASS)
else:
    _base = Path(__file__).parent

sys.path.insert(0, str(_base))

from core.database import init_db
from gui.app import PhotoVaultApp
from gui.main_window import MainWindow


def main():
    # Initialize persistent database
    init_db()

    # Create and run application
    app = PhotoVaultApp()
    MainWindow(app)
    app.mainloop()


if __name__ == '__main__':
    main()
