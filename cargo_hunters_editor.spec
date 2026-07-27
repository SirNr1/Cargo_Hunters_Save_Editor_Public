# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

import os

# UnityPy ships a typetree database and loads submodules dynamically; without both the
# frozen app cannot read the game bundles and every item falls back to its raw GUID.
unitypy_datas = collect_data_files('UnityPy')
unitypy_hiddenimports = collect_submodules('UnityPy')

block_cipher = None

a = Analysis(
    ['CH_Editor/gui_editor.py'],
    pathex=['CH_Editor', 'Scripts'],
    binaries=[],
    datas=[
        ('Scripts/template_aliases.json', '.'),
        ('CH_Editor/music.wav', '.'),
        ('CH_Editor/hackerman.png', '.'),
    ] + ([('Scripts/generated/template_mapping_report.json', 'generated')] if os.path.exists('Scripts/generated/template_mapping_report.json') else []) + unitypy_datas,
    hiddenimports=['UnityPy', 'extract_template_mapping'] + unitypy_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='CargoHuntersEditor',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CargoHuntersEditor',
)
