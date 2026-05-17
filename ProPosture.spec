# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_dir = Path(SPECPATH)
build_icon_dir = project_dir / "build" / "icons"
windows_icon = build_icon_dir / "proposture.ico"
macos_icon = build_icon_dir / "proposture.icns"

datas = [
    (str(project_dir / "assets"), "assets"),
]
datas += collect_data_files("customtkinter")
datas += collect_data_files("mediapipe")

hiddenimports = []
hiddenimports += collect_submodules("mediapipe")
hiddenimports += collect_submodules("pyttsx3.drivers")

a = Analysis(
    [str(project_dir / "main.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="ProPosture",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
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
        name="ProPosture",
    )
    app = BUNDLE(
        coll,
        name="ProPosture.app",
        icon=str(macos_icon) if macos_icon.exists() else None,
        bundle_identifier="com.proposture.app",
        info_plist={
            "CFBundleName": "ProPosture",
            "CFBundleDisplayName": "ProPosture",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSCameraUsageDescription": (
                "ProPosture uses the camera to analyze posture locally."
            ),
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="ProPosture",
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
        icon=str(windows_icon) if windows_icon.exists() else None,
    )
