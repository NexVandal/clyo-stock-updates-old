from __future__ import annotations

import ctypes
import importlib
import importlib.util
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

import uvicorn

_FASTAPI_APP = None


def safe_print(message: str = "") -> None:
    try:
        if sys.stdout:
            print(message)
    except Exception:
        pass


def show_startup_error(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        safe_print(title)
        safe_print(message)


def _candidate_import_dirs() -> list[Path]:
    dirs: list[Path] = []
    try:
        dirs.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    try:
        dirs.append(Path(sys.executable).resolve().parent)
        dirs.append(Path(sys.executable).resolve().parent / "_internal")
    except Exception:
        pass
    try:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            dirs.append(Path(sys._MEIPASS).resolve())  # type: ignore[attr-defined]
    except Exception:
        pass

    unique: list[Path] = []
    for d in dirs:
        if d and d not in unique:
            unique.append(d)
    return unique


def _load_module_from_app_py(path: Path):
    """Charge app.py depuis un fichier physique quand PyInstaller ne l'a pas importé."""
    if not path.exists():
        raise FileNotFoundError(str(path))
    spec = importlib.util.spec_from_file_location("clyo_stock_embedded_app", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"spec_from_file_location impossible pour {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_fastapi_app():
    """Charge l'objet FastAPI depuis app.py de façon robuste.

    Correctif V8.1.0 : le build PyInstaller GitHub Actions doit embarquer le
    module app. On tente d'abord l'import Python normal, puis un fallback par
    fichier app.py si le module a été ajouté comme ressource.
    """
    global _FASTAPI_APP
    if _FASTAPI_APP is not None:
        return _FASTAPI_APP

    for d in reversed(_candidate_import_dirs()):
        ds = str(d)
        if ds and ds not in sys.path:
            sys.path.insert(0, ds)

    errors: list[str] = []
    module = None

    # Import statique volontaire : PyInstaller le détecte mieux qu'un importlib seul.
    try:
        from app import app as direct_fastapi_app  # type: ignore
        _FASTAPI_APP = direct_fastapi_app
        return _FASTAPI_APP
    except Exception as exc:
        errors.append("import direct from app : " + "".join(traceback.format_exception_only(type(exc), exc)).strip())
        sys.modules.pop("app", None)

    try:
        module = importlib.import_module("app")
    except Exception as exc:
        errors.append("importlib.import_module('app') : " + "".join(traceback.format_exception_only(type(exc), exc)).strip())
        sys.modules.pop("app", None)

    if module is None:
        for d in _candidate_import_dirs():
            candidate = d / "app.py"
            try:
                module = _load_module_from_app_py(candidate)
                break
            except Exception as exc:
                errors.append(f"chargement fichier {candidate} : " + "".join(traceback.format_exception_only(type(exc), exc)).strip())

    if module is None:
        details = "\n".join("- " + e for e in errors[-8:])
        raise RuntimeError(
            "Impossible de charger le module app.py de CLYO Stock Atelier.\n\n"
            "Le build doit contenir CLYO_Stock_Builder.py V8.1.0 avec --hidden-import app.\n\n"
            "Détails :\n" + details
        )

    fastapi_app = getattr(module, "app", None)
    if fastapi_app is None:
        module_path = getattr(module, "__file__", "emplacement inconnu")
        raise RuntimeError(
            "Le fichier app.py chargé ne contient pas l'objet FastAPI nommé 'app'.\n"
            f"Fichier chargé : {module_path}\n\n"
            "Il faut remplacer app.py par celui du patch actuel puis relancer le build GitHub Actions."
        )

    _FASTAPI_APP = fastapi_app
    return _FASTAPI_APP

def port_is_free(host: str, port: int) -> bool:
    """V8.2.9 : teste vraiment la possibilité de binder le port.

    L'ancien test connect_ex détectait seulement l'absence d'écoute. Sur Windows,
    un port peut rester indisponible même sans listener visible.
    """
    bind_host = "127.0.0.1" if host == "0.0.0.0" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((bind_host, int(port)))
            return True
        except OSError:
            return False



def wait_for_port(host: str, port: int, timeout_seconds: float = 12.0) -> bool:
    bind_host = "127.0.0.1" if host == "0.0.0.0" else host
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((bind_host, port)) == 0:
                return True
        time.sleep(0.15)
    return False


def find_free_port(host: str, start_port: int = 8080, end_port: int = 8090) -> int:
    for port in range(start_port, end_port + 1):
        if port_is_free(host, port):
            return port
    raise RuntimeError("Aucun port disponible entre 8080 et 8090.")


def open_browser_later(url: str) -> None:
    time.sleep(1.5)
    webbrowser.open(url)


def should_open_browser() -> bool:
    if os.environ.get("CLYO_STOCK_NO_BROWSER", "0") == "1":
        return False
    try:
        app_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        marker = app_dir / "no_auto_browser.once"
        if marker.exists():
            marker.unlink(missing_ok=True)
            return False
    except Exception:
        pass
    return True


def desktop_window_enabled() -> bool:
    """Mode normal : ouverture dans la fenêtre native de l'application.

    Depuis la V8.2.9, on ne bascule plus automatiquement dans le navigateur
    externe, car l'utilisateur attend une vraie fenêtre CLYO Stock Atelier.
    """
    return os.environ.get("CLYO_STOCK_DESKTOP_WINDOW", "1").strip().lower() not in {"0", "false", "no", "non"}


def browser_fallback_enabled() -> bool:
    """Fallback navigateur uniquement si explicitement demandé pour diagnostic."""
    return os.environ.get("CLYO_STOCK_ALLOW_BROWSER_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "oui"}


def run_uvicorn(host: str, port: int) -> None:
    uvicorn.run(
        load_fastapi_app(),
        host=host,
        port=port,
        log_level="critical",
        access_log=False,
        log_config=None,
        lifespan="off",  # V8.2.9 : pas de startup lourd bloquant avant ouverture du port local
    )


def run_uvicorn_captured(host: str, port: int, errors: list[str]) -> None:
    """Lance Uvicorn en capturant les erreurs invisibles en mode --windowed.

    Correctif V8.2.9 : auparavant le navigateur pouvait s'ouvrir alors que
    le serveur local n'était pas encore prêt, ou après un crash silencieux du
    thread serveur. Résultat : page 127.0.0.1 / ERR_CONNECTION_REFUSED.
    """
    try:
        run_uvicorn(host, port)
    except BaseException:
        errors.append(traceback.format_exc())


def wait_for_port_or_server_error(host: str, port: int, errors: list[str], timeout_seconds: float = 60.0) -> bool:
    bind_host = "127.0.0.1" if host == "0.0.0.0" else host
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if errors:
            return False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((bind_host, port)) == 0:
                return True
        time.sleep(0.20)
    return False



def wait_for_http_health_v825(host: str, port: int, errors: list[str], timeout_seconds: float = 90.0) -> bool:
    """Attend une vraie réponse HTTP locale, pas seulement l'ouverture du port."""
    import urllib.request
    bind_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{bind_host}:{port}/api/local-health"
    fallback_url = f"http://{bind_host}:{port}/api/health"
    deadline = time.monotonic() + timeout_seconds
    last_probe_error = ""
    while time.monotonic() < deadline:
        if errors:
            return False
        for target in (url, fallback_url):
            try:
                with urllib.request.urlopen(target, timeout=1.2) as resp:
                    if 200 <= int(getattr(resp, "status", 200)) < 500:
                        return True
            except Exception as exc:
                last_probe_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.25)
    if last_probe_error and not errors:
        errors.append("Aucune réponse HTTP du serveur local avant délai. Dernier test : " + last_probe_error)
    return False

def show_server_start_error(errors: list[str], host: str, port: int) -> None:
    detail = errors[-1] if errors else "Aucune réponse du serveur local dans le délai prévu."
    show_startup_error(
        "Erreur démarrage CLYO Stock Atelier",
        "Le serveur local CLYO Stock Atelier n'a pas démarré correctement.\n\n"
        f"Adresse attendue : http://127.0.0.1:{port}\n"
        f"Hôte : {host} / Port : {port}\n\n"
        "Détail :\n" + detail[-3500:],
    )


def run_browser_mode(url: str, host: str, port: int) -> None:
    errors: list[str] = []
    server_thread = threading.Thread(
        target=run_uvicorn_captured,
        args=(host, port, errors),
        daemon=False,
        name="clyo-stock-local-server",
    )
    server_thread.start()

    if wait_for_http_health_v825(host, port, errors, timeout_seconds=90.0):
        if should_open_browser():
            webbrowser.open(url)
        while server_thread.is_alive():
            time.sleep(0.5)
        if errors:
            show_server_start_error(errors, host, port)
        return

    show_server_start_error(errors, host, port)


def run_desktop_window(url: str, host: str, port: int) -> bool:
    if not desktop_window_enabled():
        return False
    try:
        import webview
    except Exception as exc:
        show_startup_error(
            "Erreur démarrage CLYO Stock Atelier",
            "La fenêtre native de CLYO Stock Atelier ne peut pas être chargée.\n\n"
            "Le logiciel ne doit pas s'ouvrir uniquement dans un navigateur externe.\n"
            "Relance le build avec le patch V8.2.9 qui embarque pywebview, pythonnet et WebView2.\n\n"
            f"Détail : {type(exc).__name__}: {exc}"
        )
        return True

    errors: list[str] = []
    server_thread = threading.Thread(
        target=run_uvicorn_captured,
        args=(host, port, errors),
        daemon=False,
        name="clyo-stock-local-server",
    )
    server_thread.start()
    if not wait_for_http_health_v825(host, port, errors, timeout_seconds=90.0):
        show_server_start_error(errors, host, port)
        return True

    try:
        # V8.2.9 : ouverture dans une vraie fenêtre applicative.
        # Le navigateur externe n'est plus utilisé par défaut.
        webview.create_window(
            "CLYO Stock Atelier",
            url,
            width=1440,
            height=920,
            min_size=(1100, 720),
        )
        webview.start(debug=False)
        os._exit(0)
    except Exception as exc:
        if browser_fallback_enabled() and should_open_browser():
            safe_print(f"Fenêtre native impossible, fallback navigateur explicitement autorisé : {exc}")
            webbrowser.open(url)
            try:
                server_thread.join()
            finally:
                os._exit(0)
        show_startup_error(
            "Erreur démarrage CLYO Stock Atelier",
            "Impossible d'ouvrir la fenêtre native de l'application.\n\n"
            "La page web externe a été désactivée volontairement.\n"
            "Vérifie que Microsoft Edge WebView2 Runtime est installé sur le poste, "
            "puis relance l'application.\n\n"
            f"Détail : {type(exc).__name__}: {exc}"
        )
        os._exit(1)
    return True


def main() -> None:
    # Force le chargement au démarrage pour détecter immédiatement un app.py incorrect.
    load_fastapi_app()

    host = os.environ.get("CLYO_STOCK_HOST", "127.0.0.1")
    start_port = int(os.environ.get("CLYO_STOCK_PORT", "8080"))
    port = find_free_port(host, start_port, start_port + 10)
    browser_url = f"http://127.0.0.1:{port}"

    safe_print("=" * 68)
    safe_print("CLYO Stock Atelier V9")
    safe_print("=" * 68)
    safe_print(f"Application locale : {browser_url}")
    if host == "0.0.0.0":
        safe_print("Mode réseau local actif : les autres postes peuvent accéder au PC serveur")
        safe_print(f"Adresse à utiliser depuis un autre poste : http://IP_DU_PC:{port}")
    safe_print("Service de maintien du port : actif tant que CLYO_Stock.exe reste lancé")
    safe_print("Mode affichage : fenêtre locale native quand WebView2 est disponible")
    safe_print("=" * 68)

    if run_desktop_window(browser_url, host, port):
        return

    # V8.2.9 : le navigateur n'est ouvert qu'après confirmation que
    # le serveur local répond vraiment, pour éviter ERR_CONNECTION_REFUSED.
    run_browser_mode(browser_url, host, port)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        show_startup_error("Erreur démarrage CLYO Stock Atelier", detail)
        raise SystemExit(1)
