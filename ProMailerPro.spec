# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# Application source directories (strictly preserved and never filtered)
app_datas = [('backend', 'backend'), ('ui_new', 'ui_new'), ('graph', 'graph'), ('services', 'services')]

hiddenimports = [
    'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'msal', 'requests', 'dotenv', 'openpyxl', 'PIL', 'loguru',
    'backend.database', 'backend.license_validator',
    'backend.task_worker', 'backend.html_renderer', 'backend.template_manager',
    'backend.graph_api', 'backend.tag_processor', 'graph.auth'
]

# Collect PySide6 core components
tmp_ret = collect_all('PySide6')
pyside_datas = tmp_ret[0]
binaries = tmp_ret[1]
hiddenimports += tmp_ret[2]

# Remove only massive unused Qt subsystems (WebEngine ~125MB, Quick ~35MB, QML ~30MB, 3D, Multimedia)
unwanted_keywords = [
    'webengine', 'quick', 'qml', 'qt3d', 'multimedia', 'designer', 
    'bluetooth', 'sensors', 'positioning', 'nfc', 'serialport', 
    'spatialaudio', 'virtualkeyboard'
]

# Filter binaries and PySide6 data assets (protecting all app files)
binaries = [b for b in binaries if not any(k in b[0].lower() for k in unwanted_keywords)]
pyside_datas = [d for d in pyside_datas if not any(k in d[0].lower() for k in unwanted_keywords)]
datas = app_datas + pyside_datas

a = Analysis(
    ['run_pro.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pandas', 'numpy', 'matplotlib', 'scipy', 'tkinter', 'pytest',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
        'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQml',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtTest',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning',
        'PySide6.QtSensors', 'PySide6.QtSerialPort', 'PySide6.QtSpatialAudio',
        'PySide6.QtVirtualKeyboard'
    ],
    noarchive=False,
    optimize=2,
)

# Safety check: keep only non-unwanted binaries while preserving core Qt & app files
a.binaries = [b for b in a.binaries if not any(k in b[0].lower() for k in unwanted_keywords)]

pyz = PYZ(a.pure, optimize=2)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ProMailerPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
