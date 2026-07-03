"""
PhotoVault — Desktop photo/video organizer
Entry point: initializes DB, builds GUI, starts event loop.
"""
import sys
from pathlib import Path

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
from utils.logging import setup_logging


def main():
    setup_logging()
    # Initialize persistent database
    init_db()

    # Create and run application
    app = PhotoVaultApp()
    MainWindow(app)
    app.mainloop()


if __name__ == '__main__':
    main()
