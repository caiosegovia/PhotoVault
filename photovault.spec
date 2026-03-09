# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('utils', 'utils'),
        ('core', 'core'),
        ('gui', 'gui'),
        ('integrations', 'integrations'),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ExifTags',
        'exifread',
        'hachoir', 'hachoir.parser', 'hachoir.metadata',
        'imagehash',
        'matplotlib', 'matplotlib.backends.backend_tkagg',
        'matplotlib.backends._backend_tk',
        'scipy', 'scipy.fft', 'scipy.ndimage',
        'numpy',
        'google.auth', 'google.oauth2', 'google_auth_oauthlib',
        'requests', 'urllib3', 'certifi',
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog',
        'sqlite3', 'hashlib', 'pathlib', 'shutil',
        'threading', 'json', 'subprocess', 'platform',
        'darkdetect',
    ],
    excludes=[
        'IPython', 'jupyter', 'notebook', 'pytest',
        'PyQt5', 'PyQt6', 'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PhotoVault',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # sem janela de console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # coloque aqui o path de um .ico se quiser
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PhotoVault',
)
