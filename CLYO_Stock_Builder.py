from __future__ import annotations
import argparse, os, shutil, subprocess, sys
from pathlib import Path

APP_NAME = "CLYO_Stock"

def run(cmd: list[str], cwd: Path) -> None:
    print("+", subprocess.list2cmdline(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-dir", default=".")
    args = ap.parse_args()
    root = Path(args.app_dir).resolve()
    dist = root / "dist"
    work = root / "dist_build_tmp"
    spec = root / f"{APP_NAME}.spec"
    for p in (dist / "CLYO_Stock_PORTABLE", work):
        if p.exists(): shutil.rmtree(p, ignore_errors=True)
    if spec.exists(): spec.unlink()

    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
           "--name", APP_NAME, "--distpath", str(dist), "--workpath", str(work), "--specpath", str(root),
           "--hidden-import", "app", "--hidden-import", "pymysql", "--hidden-import", "python_multipart",
           "--collect-all", "webview", "--collect-all", "uvicorn", "--collect-all", "fastapi",
           "--collect-all", "docx", "--collect-all", "qrcode"]
    icon = root / "assets" / "app_icon.ico"
    if icon.exists(): cmd += ["--icon", str(icon)]
    for folder in ("assets", "templates"):
        p = root / folder
        if p.exists(): cmd += ["--add-data", f"{p}{sep}{folder}"]
    for f in ("app.py", "CLYO_Stock_Updater.py"):
        p = root / f
        if p.exists(): cmd += ["--add-data", f"{p}{sep}."]
    cmd.append(str(root / "run_app.py"))
    run(cmd, root)

    produced = dist / APP_NAME
    target = dist / "CLYO_Stock_PORTABLE"
    if not produced.exists(): raise FileNotFoundError(produced)
    if target.exists(): shutil.rmtree(target)
    produced.rename(target)
    exe = target / "CLYO_Stock.exe"
    if not exe.exists(): raise FileNotFoundError(exe)
    print(f"Build OK: {exe}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
