# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

BASE_DIR = os.path.dirname(os.path.abspath(SPEC))

datas = [
    (os.path.join(BASE_DIR, 'assets'), 'assets'),
    (os.path.join(BASE_DIR, 'DualSenseACBridge', 'ui', 'web'), os.path.join('DualSenseACBridge', 'ui', 'web')),
    (os.path.join(BASE_DIR, 'config.json'), '.')
]
binaries = []
hiddenimports = [
    'webview',
    'clr_loader',
    'pythonnet',
    'bottle',
    'proxy_tools',
    'sounddevice',
    '_sounddevice_data',
    'numpy',
    'pystray',
    'vgamepad',
    'hid',
    'psutil',
    'PIL',
    'PIL.Image'
]

ret_wv = collect_all('webview')
datas += ret_wv[0]; binaries += ret_wv[1]; hiddenimports += ret_wv[2]

ret_clr = collect_all('clr_loader')
datas += ret_clr[0]; binaries += ret_clr[1]; hiddenimports += ret_clr[2]

ret_pn = collect_all('pythonnet')
datas += ret_pn[0]; binaries += ret_pn[1]; hiddenimports += ret_pn[2]

ret_vg = collect_all('vgamepad')
datas += ret_vg[0]; binaries += ret_vg[1]; hiddenimports += ret_vg[2]

ret_sd = collect_all('_sounddevice_data')
datas += ret_sd[0]; binaries += ret_sd[1]; hiddenimports += ret_sd[2]

ret_stray = collect_all('pystray')
datas += ret_stray[0]; binaries += ret_stray[1]; hiddenimports += ret_stray[2]

# Exclude heavy scientific and unused GUI/web framework packages to reduce bundle size
excludes = [
    'customtkinter', 'tkinter', 'torch', 'torchaudio', 'torchvision', 'scipy', 'matplotlib', 'pandas',
    'cv2', 'opencv', 'PyQt6', 'PyQt5', 'PySide6', 'PySide2', 'shiboken6',
    'pygame', 'qt_material', 'transformers', 'onnx', 'onnxruntime',
    'fastapi', 'starlette', 'uvicorn', 'streamlit', 'gradio', 'librosa',
    'numba', 'llvmlite', 'sqlalchemy', 'alembic', 'playwright', 'selenium',
    'moviepy', 'diffusers', 'sympy', 'openpyxl', 'xlsxwriter', 'IPython',
    'jupyter', 'notebook', 'pytest', 'setuptools', 'pip', 'wheel',
    'Cython', 'google', 'anthropic', 'av', 'borb', 'celery', 'dulwich',
    'easyocr', 'faster_whisper', 'flet', 'lxml', 'mediapipe', 'rembg'
]

a = Analysis(
    [os.path.join(BASE_DIR, 'main.py')],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DualSenseACBridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(BASE_DIR, 'assets', 'icon.ico')],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DualSenseACBridge',
)
