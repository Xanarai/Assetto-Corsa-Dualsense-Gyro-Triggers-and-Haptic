"""
PyInstaller build launcher for DualSense AC Bridge.
Compiles the application into a onedir distribution via DualSenseACBridge.spec.
"""
import os
import sys
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC_FILE = os.path.join(BASE_DIR, "DualSenseACBridge.spec")
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CONFIG_JSON = os.path.join(BASE_DIR, "config.json")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    f"--distpath={DIST_DIR}",
    f"--workpath={BUILD_DIR}",
    SPEC_FILE
]

print("Starting optimized PyInstaller build using spec...")
print(" ".join(cmd))
res = subprocess.run(cmd, cwd=BASE_DIR)

if res.returncode == 0:
    out_dir = os.path.join(DIST_DIR, "DualSenseACBridge")
    # Copy default config and assets into output distribution
    shutil.copy2(CONFIG_JSON, os.path.join(out_dir, "config.json"))
    out_assets = os.path.join(out_dir, "assets")
    os.makedirs(out_assets, exist_ok=True)
    for f in os.listdir(ASSETS_DIR):
        shutil.copy2(os.path.join(ASSETS_DIR, f), os.path.join(out_assets, f))
    print("\n[SUCCESS] Build completed successfully!")
    print(f"Output folder: {out_dir}")
else:
    print(f"\n[ERROR] Build failed with exit code {res.returncode}")
    sys.exit(res.returncode)
