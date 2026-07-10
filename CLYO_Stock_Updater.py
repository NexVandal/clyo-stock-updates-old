# -*- coding: utf-8 -*-
"""
CLYO Stock Atelier - Updater Python natif V8.3.11
Runner propre / anti-fichiers verrouillés / anti-processus bloquants.

Objectif : ne plus dépendre de PowerShell/CMD et éviter les mises à jour bloquées
par un service, un ancien EXE, un python.exe, ou un fichier encore ouvert.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as _dt
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import webbrowser
import zipfile
from pathlib import Path

APP_URL = "http://127.0.0.1:8080/"
APP_HOST = "127.0.0.1"
APP_PORT = 8080
UPDATER_VERSION = "8.3.11"

PROTECTED_NAMES = {
    "NexVandal", "data", "backups", "archives", "qr_codes", "product_images",
    "generated_documents", "documents_clients", "document_templates", "update_backups",
    "nexvandal_active_data.json", "setup_choice.json", "stock_assets.db", "stock_assets.db-wal",
    "stock_assets.db-shm", "referentiel_stock.xlsx", "activity_log.jsonl", "ui_settings.json",
    "deleted_status_values.json", "update_history.jsonl", "connection_schema_images",
    "connection_schemas.json", "dist", "build", "dist_build_tmp", "__pycache__", ".venv", "venv",
}
SKIP_FILE_SUFFIXES = {".pyc", ".pyo"}
CLYO_PROCESS_NAMES = {
    "clyo_stock.exe", "clyo_stock_atelier.exe", "clyo stock atelier.exe", "clyo_stock_portable.exe",
    "run_app.exe", "uvicorn.exe", "python.exe", "pythonw.exe", "py.exe",
}
SELF_NAMES = {"clyo_stock_updater.exe", "clyo_stock_updater.py"}

# Windows access constants
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102
MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004
MAX_PATH_BUF = 32768


def now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Ui:
    def __init__(self) -> None:
        self.root = None
        self.text = None
        self.bar = None
        self.status = None
        self.percent_var = None
        self.has_tk = False
        try:
            import tkinter as tk
            from tkinter import ttk
            self.tk = tk
            self.ttk = ttk
            self.root = tk.Tk()
            self.root.title("Mise à jour CLYO Stock Atelier - Updater V8.3.11")
            self.root.geometry("820x560")
            self.root.configure(bg="#0f172a")
            self.root.protocol("WM_DELETE_WINDOW", lambda: None)

            frame = tk.Frame(self.root, bg="#0f172a", padx=24, pady=22)
            frame.pack(fill="both", expand=True)
            tk.Label(frame, text="Mise à jour CLYO Stock Atelier", fg="#ffffff", bg="#0f172a", font=("Segoe UI", 20, "bold")).pack(anchor="w")
            tk.Label(frame, text="Updater Python natif V8.3.11 — runner propre", fg="#93c5fd", bg="#0f172a", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 16))
            self.status = tk.Label(frame, text="Préparation...", fg="#e5e7eb", bg="#0f172a", font=("Segoe UI", 11, "bold"))
            self.status.pack(anchor="w", pady=(0, 8))
            self.percent_var = tk.DoubleVar(value=0)
            self.bar = ttk.Progressbar(frame, variable=self.percent_var, maximum=100, length=740)
            self.bar.pack(fill="x", pady=(0, 14))
            self.text = tk.Text(frame, height=20, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", relief="flat", font=("Consolas", 9))
            self.text.pack(fill="both", expand=True)
            self.has_tk = True
        except Exception:
            self.has_tk = False

    def set(self, pct: int, msg: str) -> None:
        pct = max(0, min(100, int(pct)))
        line = f"[{now()}] {msg}"
        print(line, flush=True)
        if self.has_tk:
            def _do() -> None:
                try:
                    self.percent_var.set(pct)
                    self.status.config(text=f"{pct}% - {msg}")
                    self.text.insert("end", line + "\n")
                    self.text.see("end")
                    self.root.update_idletasks()
                except Exception:
                    pass
            try:
                self.root.after(0, _do)
                self.root.update()
            except Exception:
                pass

    def loop_tick(self) -> None:
        if self.has_tk:
            try:
                self.root.update()
            except Exception:
                pass

    def finish(self, ok: bool, msg: str) -> None:
        self.set(100 if ok else 99, msg)
        if self.has_tk:
            def _buttons() -> None:
                try:
                    frame = self.tk.Frame(self.root, bg="#0f172a")
                    frame.pack(fill="x", padx=24, pady=(0, 18))
                    self.tk.Button(frame, text="Ouvrir CLYO Stock Atelier", command=lambda: webbrowser.open(APP_URL), padx=18, pady=8).pack(side="left")
                    self.tk.Button(frame, text="Fermer", command=self.root.destroy, padx=18, pady=8).pack(side="right")
                except Exception:
                    pass
            self.root.after(0, _buttons)
            try:
                self.root.mainloop()
            except Exception:
                pass
        else:
            # En mode service/test sans console interactive, ne bloque pas indéfiniment.
            try:
                if getattr(sys.stdin, "isatty", lambda: False)():
                    input("Appuie sur Entrée pour fermer...")
                else:
                    time.sleep(3)
            except Exception:
                time.sleep(3)


def safe_log(log_path: Path, message: str) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write(f"[{now()}] {message}\n")
    except Exception:
        pass


def is_windows() -> bool:
    return os.name == "nt"


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if is_windows():
        try:
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
            if not handle:
                return False
            ret = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
            return ret == WAIT_TIMEOUT
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def terminate_pid(pid: int, ui: Ui, log_path: Path, reason: str = "") -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    if is_windows():
        try:
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, int(pid))
            if not handle:
                safe_log(log_path, f"Impossible OpenProcess terminate PID {pid}")
                return False
            ok = bool(ctypes.windll.kernel32.TerminateProcess(handle, 0))
            ctypes.windll.kernel32.CloseHandle(handle)
            if ok:
                ui.set(22, f"Processus arrêté PID {pid} {reason}".strip())
                safe_log(log_path, f"Processus arrêté PID {pid} {reason}")
            return ok
        except Exception as exc:
            safe_log(log_path, f"Terminate PID {pid} impossible : {exc}")
            return False
    try:
        os.kill(pid, 15)
        return True
    except Exception:
        try:
            os.kill(pid, 9)
            return True
        except Exception as exc:
            safe_log(log_path, f"Kill PID {pid} impossible : {exc}")
            return False


def wait_for_pid(pid: int, seconds: int, ui: Ui, log_path: Path, force_after: bool = False) -> None:
    if pid <= 0:
        time.sleep(1)
        return
    ui.set(18, f"Attente fermeture application PID {pid}...")
    end = time.time() + max(1, seconds)
    while time.time() < end:
        ui.loop_tick()
        if not is_pid_alive(pid):
            safe_log(log_path, f"PID {pid} fermé")
            return
        time.sleep(0.35)
    if force_after and is_pid_alive(pid):
        ui.set(21, f"Application encore ouverte, arrêt forcé PID {pid}...")
        terminate_pid(pid, ui, log_path, "ancien processus application")
        time.sleep(1.5)


# -------- Processus Windows liés à l'application --------
class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def iter_windows_processes(log_path: Path):
    if not is_windows():
        return
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        safe_log(log_path, "CreateToolhelp32Snapshot impossible")
        return
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            pid = int(entry.th32ProcessID)
            exe = str(entry.szExeFile or "")
            path = query_process_path(pid)
            yield {"pid": pid, "exe": exe, "path": path}
            success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)


def query_process_path(pid: int) -> str:
    if not is_windows() or pid <= 0:
        return ""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        buf = ctypes.create_unicode_buffer(MAX_PATH_BUF)
        size = ctypes.c_ulong(MAX_PATH_BUF)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        kernel32.CloseHandle(handle)
        return buf.value if ok else ""
    except Exception:
        return ""


def path_is_under(path_text: str, folder: Path) -> bool:
    if not path_text:
        return False
    try:
        p = Path(path_text).resolve()
        f = folder.resolve()
        return str(p).lower().startswith(str(f).lower())
    except Exception:
        return False


def stop_related_processes(app_dir: Path, old_pid: int, current_exe: str, ui: Ui, log_path: Path) -> None:
    ui.set(17, "Fermeture des processus CLYO encore actifs...")
    wait_for_pid(old_pid, 10, ui, log_path, force_after=True)
    if not is_windows():
        safe_log(log_path, "Détection processus avancée ignorée hors Windows")
        return
    current_pid = os.getpid()
    current_exe_path = str(Path(current_exe).resolve()).lower() if current_exe else ""
    targets: list[dict] = []
    for proc in iter_windows_processes(log_path) or []:
        pid = int(proc.get("pid") or 0)
        exe = str(proc.get("exe") or "").lower()
        ppath = str(proc.get("path") or "")
        if pid in (0, current_pid):
            continue
        if exe in SELF_NAMES:
            continue
        by_name = exe in CLYO_PROCESS_NAMES or exe.startswith("clyo_stock") or exe.startswith("cl yo")
        by_path = path_is_under(ppath, app_dir)
        by_current_exe = bool(current_exe_path and ppath.lower() == current_exe_path)
        # Ne tue pas un python système au hasard sauf s'il est dans le dossier app ou correspond explicitement à l'ancien PID.
        if by_current_exe or (by_name and by_path) or (pid == old_pid):
            targets.append(proc)
    if not targets:
        safe_log(log_path, "Aucun processus CLYO supplémentaire détecté")
        return
    for proc in targets:
        pid = int(proc["pid"])
        ui.set(21, f"Arrêt processus bloquant : {proc.get('exe')} PID {pid}")
        terminate_pid(pid, ui, log_path, f"{proc.get('exe')} {proc.get('path')}")
    end = time.time() + 8
    while time.time() < end:
        ui.loop_tick()
        alive = [p for p in targets if is_pid_alive(int(p["pid"]))]
        if not alive:
            return
        time.sleep(0.5)


def wait_port_closed(ui: Ui, log_path: Path, seconds: int = 15) -> None:
    ui.set(23, "Vérification libération du serveur local...")
    end = time.time() + seconds
    while time.time() < end:
        ui.loop_tick()
        try:
            with socket.create_connection((APP_HOST, APP_PORT), timeout=0.5):
                time.sleep(0.5)
                continue
        except OSError:
            safe_log(log_path, "Port local libéré")
            return
    safe_log(log_path, "Port local encore occupé après attente, tentative de copie quand même")


def copytree_safe(src: Path, dst: Path, ignore_names: set[str] | None = None) -> None:
    ignore_names = ignore_names or set()
    if not src.exists():
        return
    for root, dirs, files in os.walk(src):
        root_p = Path(root)
        rel = root_p.relative_to(src)
        if any(part in ignore_names for part in rel.parts):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in ignore_names]
        target_root = dst / rel
        target_root.mkdir(parents=True, exist_ok=True)
        for name in files:
            if name in ignore_names:
                continue
            s = root_p / name
            d = target_root / name
            try:
                shutil.copy2(s, d)
            except Exception:
                shutil.copyfile(s, d)


def normalize_zip_root(extract_dir: Path) -> Path:
    children = [p for p in extract_dir.iterdir() if p.name != "__MACOSX"]
    dirs = [p for p in children if p.is_dir()]
    files = [p for p in children if p.is_file()]
    if len(dirs) == 1 and not files and (dirs[0] / "app.py").exists():
        return dirs[0]
    return extract_dir


def backup_current(app_dir: Path, data_dir: Path, backup_root: Path, ui: Ui, log_path: Path) -> None:
    ui.set(25, "Sauvegarde des données utilisateur...")
    data_backup = backup_root / "data"
    if data_dir.exists():
        copytree_safe(data_dir, data_backup, ignore_names={"update_backups", "__pycache__"})
    ui.set(32, "Sauvegarde du code actuel...")
    code_backup = backup_root / "code"
    copytree_safe(app_dir, code_backup, ignore_names=PROTECTED_NAMES)
    safe_log(log_path, f"Sauvegarde créée : {backup_root}")


def schedule_replace_on_reboot(src: Path, dst: Path, log_path: Path) -> bool:
    if not is_windows():
        return False
    try:
        ok = bool(ctypes.windll.kernel32.MoveFileExW(str(src), str(dst), MOVEFILE_DELAY_UNTIL_REBOOT))
        safe_log(log_path, f"Planification remplacement reboot {src} -> {dst}: {ok}")
        return ok
    except Exception as exc:
        safe_log(log_path, f"MoveFileExW impossible : {exc}")
        return False


def copy_with_retry(src: Path, dst: Path, log_path: Path, attempts: int = 18) -> tuple[bool, str]:
    """Copie un fichier via fichier temporaire + os.replace, avec retries.
    Retourne (ok, message). Si le fichier est verrouillé, on tente un remplacement au redémarrage.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.parent / f".{dst.name}.update_tmp_{os.getpid()}"
    last_err = ""
    for i in range(1, attempts + 1):
        try:
            if tmp.exists():
                try: tmp.unlink()
                except Exception: pass
            shutil.copy2(src, tmp)
            try:
                os.replace(tmp, dst)
            except PermissionError:
                # Fallback : rename ancien puis replace. Peut échouer si fichier verrouillé.
                old = dst.parent / f".{dst.name}.old_{int(time.time())}"
                try:
                    if dst.exists():
                        os.replace(dst, old)
                    os.replace(tmp, dst)
                except Exception:
                    raise
            return True, "copié"
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            safe_log(log_path, f"Copie tentative {i}/{attempts} échouée {src} -> {dst}: {last_err}")
            time.sleep(min(0.25 + i * 0.15, 2.0))
    # Dernier recours : planifie au reboot si temp existe.
    try:
        if not tmp.exists():
            shutil.copy2(src, tmp)
        if schedule_replace_on_reboot(tmp, dst, log_path):
            return False, f"fichier verrouillé, remplacement planifié au prochain redémarrage Windows : {dst.name}"
    except Exception as exc:
        last_err += f" / schedule failed: {exc}"
    return False, last_err


def restore_code_backup(app_dir: Path, backup_root: Path, ui: Ui, log_path: Path) -> None:
    code_backup = backup_root / "code"
    if not code_backup.exists():
        safe_log(log_path, "Rollback impossible : backup code absent")
        return
    ui.set(94, "Rollback : restauration de l'ancien code...")
    restored = 0
    for root, dirs, files in os.walk(code_backup):
        root_p = Path(root)
        rel = root_p.relative_to(code_backup)
        for name in files:
            src = root_p / name
            dst = app_dir / rel / name
            ok, msg = copy_with_retry(src, dst, log_path, attempts=8)
            if ok:
                restored += 1
            else:
                safe_log(log_path, f"Rollback fichier non restauré {dst}: {msg}")
    safe_log(log_path, f"Rollback terminé, fichiers restaurés : {restored}")


def install_files(src_root: Path, app_dir: Path, ui: Ui, log_path: Path) -> tuple[int, int, list[str]]:
    installed = 0
    skipped = 0
    blocked: list[str] = []
    ui.set(48, "Remplacement sécurisé des fichiers applicatifs...")
    app_dir_resolved = app_dir.resolve()
    self_path = Path(sys.argv[0]).resolve()
    for root, dirs, files in os.walk(src_root):
        root_p = Path(root)
        rel = root_p.relative_to(src_root)
        if any(part in PROTECTED_NAMES for part in rel.parts):
            dirs[:] = []
            skipped += 1
            continue
        dirs[:] = [d for d in dirs if d not in PROTECTED_NAMES]
        for name in files:
            lower_name = name.lower()
            if name in PROTECTED_NAMES or Path(name).suffix.lower() in SKIP_FILE_SUFFIXES:
                skipped += 1
                continue
            rel_path = rel / name
            if any(part in PROTECTED_NAMES for part in rel_path.parts):
                skipped += 1
                continue
            src = root_p / name
            dst = (app_dir / rel_path).resolve()
            if not str(dst).lower().startswith(str(app_dir_resolved).lower()):
                skipped += 1
                continue
            # Ne remplace jamais l'exécutable/script updater actuellement lancé en direct.
            if dst == self_path:
                ok, msg = copy_with_retry(src, dst.with_suffix(dst.suffix + ".next"), log_path, attempts=4)
                blocked.append(f"{rel_path} -> updater actif mis de côté en .next ({msg})")
                skipped += 1
                continue
            ok, msg = copy_with_retry(src, dst, log_path)
            if ok:
                installed += 1
            else:
                blocked.append(f"{rel_path}: {msg}")
                skipped += 1
            if installed % 15 == 0:
                ui.set(48 + min(10, installed // 15), f"Fichiers installés : {installed}")
    safe_log(log_path, f"Installation fichiers terminée : {installed} installés, {skipped} ignorés, {len(blocked)} bloqués")
    for b in blocked[:50]:
        safe_log(log_path, "BLOQUE: " + b)
    return installed, skipped, blocked


def find_python(app_dir: Path) -> str | None:
    candidates = [app_dir / ".venv" / "Scripts" / "python.exe", Path(sys.executable)]
    for c in candidates:
        try:
            if c.exists() and c.name.lower().startswith("python"):
                return str(c)
        except Exception:
            pass
    for name in ("py.exe", "python.exe", "pythonw.exe", "python"):
        found = shutil.which(name)
        if found:
            return found
    return None


def run_builder_if_possible(app_dir: Path, ui: Ui, log_path: Path) -> None:
    builder = app_dir / "CLYO_Stock_Builder.py"
    if not builder.exists():
        ui.set(65, "Aucun builder Python trouvé, build EXE ignoré.")
        safe_log(log_path, "CLYO_Stock_Builder.py introuvable, build ignoré")
        return
    py = find_python(app_dir)
    if not py:
        ui.set(65, "Python introuvable, build EXE ignoré.")
        safe_log(log_path, "Python introuvable, build ignoré")
        return
    ui.set(66, "Build EXE Python direct en cours...")
    safe_log(log_path, f"Lancement builder : {py} {builder}")
    try:
        proc = subprocess.Popen([py, str(builder), "--app-dir", str(app_dir)], cwd=str(app_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout or []:
            line = line.rstrip()
            if line:
                safe_log(log_path, "BUILDER: " + line)
        code = proc.wait(timeout=900)
    except Exception as exc:
        ui.set(72, f"Build EXE ignoré / erreur : {exc}")
        safe_log(log_path, f"Builder exception : {exc}")
        return
    if code != 0:
        ui.set(72, f"Build EXE en erreur code {code}. La source a quand même été mise à jour.")
        safe_log(log_path, f"Builder terminé en erreur : {code}")
    else:
        ui.set(78, "Build EXE terminé.")
        safe_log(log_path, "Builder terminé avec succès")


def find_launch_target(app_dir: Path, current_exe: str | None = None) -> tuple[str | None, list[str] | None, Path | None]:
    candidates: list[Path] = []
    build_root = app_dir / "dist_build_tmp"
    if build_root.exists():
        try:
            for d in sorted(build_root.glob("build_*"), key=lambda p: p.stat().st_mtime, reverse=True):
                candidates.append(d / "CLYO_Stock" / "CLYO_Stock.exe")
        except Exception:
            pass
    candidates.extend([app_dir / "dist" / "CLYO_Stock_PORTABLE" / "CLYO_Stock.exe", app_dir / "CLYO_Stock.exe"])
    if current_exe:
        candidates.append(Path(current_exe))
    for exe in candidates:
        try:
            if exe.exists() and exe.is_file():
                return str(exe), [str(exe)], exe.parent
        except Exception:
            pass
    py = find_python(app_dir)
    run_app = app_dir / "run_app.py"
    if py and run_app.exists():
        return str(run_app), [py, str(run_app)], app_dir
    return None, None, None


def relaunch(app_dir: Path, current_exe: str | None, ui: Ui, log_path: Path) -> None:
    ui.set(86, "Relance de CLYO Stock Atelier...")
    target, cmd, cwd = find_launch_target(app_dir, current_exe)
    if not cmd or not cwd:
        ui.set(95, "Impossible de relancer automatiquement : cible introuvable.")
        safe_log(log_path, "Relance impossible : aucune cible trouvée")
        return
    try:
        subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        safe_log(log_path, f"Relance demandée : {cmd}")
    except Exception as exc:
        ui.set(95, f"Relance impossible : {exc}")
        safe_log(log_path, f"Relance impossible : {exc}")
        return
    ui.set(92, "Vérification du serveur local...")
    import urllib.request
    end = time.time() + 50
    while time.time() < end:
        ui.loop_tick()
        try:
            with urllib.request.urlopen(APP_URL, timeout=2) as resp:
                if getattr(resp, "status", 200) < 500:
                    ui.set(100, "Application relancée avec succès.")
                    try: webbrowser.open(APP_URL)
                    except Exception: pass
                    return
        except Exception:
            time.sleep(1)
    ui.set(96, "Mise à jour installée, mais serveur local non détecté. Relance manuelle possible.")


def write_history(app_dir: Path, data_dir: Path, event: dict) -> None:
    """Écrit l’historique dans le vrai dossier de données actif.

    Ancien comportement corrigé : l’Updater écrivait toujours dans app_dir/NexVandal,
    ce qui perdait l’historique quand l’utilisateur avait choisi une base externe.
    """
    event = dict(event or {})
    event["created_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    targets = []
    try:
        targets.append(data_dir / "update_history.jsonl")
    except Exception:
        pass
    try:
        fallback = app_dir / "NexVandal" / "update_history.jsonl"
        if not targets or fallback.resolve() != targets[0].resolve():
            targets.append(fallback)
    except Exception:
        pass
    for path in targets:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--zip-path", required=True)
    parser.add_argument("--old-pid", type=int, default=0)
    parser.add_argument("--current-version", default="")
    parser.add_argument("--current-exe", default="")
    parser.add_argument("--create-desktop-shortcut", default="0")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).resolve()
    data_dir = Path(args.data_dir).resolve()
    zip_path = Path(args.zip_path).resolve()
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = app_dir / "update_autobuild.log"
    backup_root = app_dir / "update_backups" / f"native_update_{stamp}"
    ui = Ui()
    installed = skipped = 0
    blocked: list[str] = []

    try:
        safe_log(log_path, f"=== Updater V{UPDATER_VERSION} runner propre démarré ===")
        ui.set(5, f"Updater V{UPDATER_VERSION} démarré depuis runner propre.")
        safe_log(log_path, f"updater_version={UPDATER_VERSION}")
        safe_log(log_path, f"runner_self={Path(sys.argv[0]).resolve()}")
        safe_log(log_path, f"app_dir={app_dir}")
        safe_log(log_path, f"data_dir={data_dir}")
        safe_log(log_path, f"zip_path={zip_path}")
        safe_log(log_path, f"old_pid={args.old_pid} current_exe={args.current_exe}")
        if not zip_path.exists():
            raise RuntimeError(f"ZIP introuvable : {zip_path}")

        stop_related_processes(app_dir, args.old_pid, args.current_exe, ui, log_path)
        wait_port_closed(ui, log_path, seconds=12)
        backup_current(app_dir, data_dir, backup_root, ui, log_path)

        ui.set(40, "Extraction du ZIP...")
        extract_dir = app_dir / "update_backups" / f"extract_{stamp}"
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
            if bad:
                raise RuntimeError(f"ZIP corrompu : {bad}")
            zf.extractall(extract_dir)
        source_root = normalize_zip_root(extract_dir)

        installed, skipped, blocked = install_files(source_root, app_dir, ui, log_path)
        if blocked:
            ui.set(61, f"{len(blocked)} fichier(s) bloqué(s). Voir log. Certains remplacements peuvent être planifiés au redémarrage.")
        run_builder_if_possible(app_dir, ui, log_path)
        write_history(app_dir, data_dir, {
            "event": "native_python_update_installed_v7730",
            "version_before": args.current_version,
            "zip_path": str(zip_path),
            "installed_files": installed,
            "skipped_files": skipped,
            "blocked_files": blocked[:80],
            "backup_folder": str(backup_root),
            "message": "Mise à jour installée via Updater Python natif V8.3.11 runner propre anti-fichiers verrouillés.",
        })
        relaunch(app_dir, args.current_exe, ui, log_path)
        final_msg = "Mise à jour terminée."
        if blocked:
            final_msg += " Certains fichiers étaient verrouillés : vérifie update_autobuild.log, puis redémarre Windows si demandé."
        ui.finish(True, final_msg)
        return 0
    except Exception as exc:
        safe_log(log_path, "ECHEC Updater anti-verrouillage : " + repr(exc))
        safe_log(log_path, traceback.format_exc())
        try:
            restore_code_backup(app_dir, backup_root, ui, log_path)
        except Exception as rb_exc:
            safe_log(log_path, f"Rollback exception : {rb_exc}")
        write_history(app_dir, data_dir, {
            "event": "native_python_update_failed_v7730",
            "version_before": args.current_version,
            "zip_path": str(zip_path),
            "backup_folder": str(backup_root),
            "installed_files_before_error": installed,
            "blocked_files": blocked[:80],
            "error": f"{type(exc).__name__}: {exc}",
        })
        ui.finish(False, f"Erreur mise à jour : {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
