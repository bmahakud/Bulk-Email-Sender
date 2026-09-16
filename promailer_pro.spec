# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

BASE_DIR = Path(os.path.abspath(SPECPATH))

# Collect all PySide6 and shiboken6 binaries, plugins, and datas
ps6_datas, ps6_binaries, ps6_hidden = collect_all('PySide6')
shb_datas, shb_binaries, shb_hidden = collect_all('shiboken6')

datas = [
    (str(BASE_DIR / 'templates'), 'templates'),
] + ps6_datas + shb_datas

hidden_modules = list(set([
    'requests',
    'urllib3',
    'openpyxl',
    'pandas',
    'PIL',
    'PIL.Image',
    'PIL.PngImagePlugin',
    'dotenv',
    'sqlite3',
    'backend',
    'backend.database',
    'backend.license_validator',
    'backend.graph_api',
    'backend.tag_processor',
    'backend.task_worker',
    'backend.template_manager',
    'backend.html_renderer',
    'ui_new',
    'ui_new.activation_dialog',
    'ui_new.dashboard',
    'ui_new.main_window',
    'ui_new.task_panel',
    'ui_new.unsubscribed_dialog',
] + ps6_hidden + shb_hidden))

a = Analysis(
    ['run_pro.py'],
    pathex=[str(BASE_DIR)],
    binaries=ps6_binaries + shb_binaries,
    datas=datas,
    hiddenimports=hidden_modules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'IPython', 'notebook',
        'nbconvert', 'nbformat', 'tkinter', 'sphinx',
        'docutils', 'black', 'tornado', 'zmq', 'pytest',
        'numba', 'dask', 'llvmlite'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Crucial fix: strip out ONLY Anaconda's conflicting Qt5/old Qt DLLs that clash with PySide6.
# We PRESERVE Microsoft Visual C++ runtimes (vcruntime140, msvcp140), OpenSSL, and SQLite.
clean_binaries = []
for item in a.binaries:
    dest, src, kind = item
    src_lower = src.lower()
    if 'anaconda3\\library\\bin' in src_lower or 'anaconda3/library/bin' in src_lower:
        fname = os.path.basename(src_lower)
        if (fname.startswith('qt5') or 
            fname.startswith('qt6') or 
            'pyside' in fname or 
            'shiboken' in fname or 
            fname.startswith('icu')):
            continue
    clean_binaries.append(item)

# Ensure Microsoft Visual C++ runtime DLLs are explicitly present in binaries
# so python39.dll and PySide6 can load on any clean Windows machine
vc_dlls = [
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
]
existing_dests = {item[0].lower() for item in clean_binaries}
for dll in vc_dlls:
    if dll.lower() not in existing_dests:
        sys32_path = os.path.join(r'C:\Windows\System32', dll)
        if os.path.exists(sys32_path):
            clean_binaries.append((dll, sys32_path, 'BINARY'))
        else:
            conda_path = os.path.join(r'C:\Users\91986\anaconda3\Library\bin', dll)
            if os.path.exists(conda_path):
                clean_binaries.append((dll, conda_path, 'BINARY'))

a.binaries = clean_binaries

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
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
    contents_directory='.',
)
