import json
import os
import runpy
import sys
import threading
import time
import traceback
from urllib import error as urllib_error
from urllib import request as urllib_request


APP_NAME = "FC Fantasy Local"
DEFAULT_UPDATE_URL = os.environ.get("FC_UPDATE_URL", "").strip()


def app_data_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    return os.path.dirname(os.path.abspath(__file__))


def load_settings():
    defaults = {
        "cloud_enabled": True,
        "cloud_api_url": os.environ.get("FC_CLOUD_API_URL", "http://127.0.0.1:8080"),
        "auto_update_enabled": bool(DEFAULT_UPDATE_URL),
        "update_manifest_url": DEFAULT_UPDATE_URL,
    }
    settings_file = os.path.join(app_data_dir(), "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                defaults.update({k: data[k] for k in defaults if k in data})
        except Exception:
            pass
    return defaults


def log_path():
    return os.path.join(app_data_dir(), "launcher.log")


def log_message(message):
    try:
        os.makedirs(app_data_dir(), exist_ok=True)
        with open(log_path(), "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def load_local_version(script_path):
    version_file = os.path.join(os.path.dirname(script_path), "version.json")
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"version": "0"}


def save_local_version(script_path, data):
    version_file = os.path.join(os.path.dirname(script_path), "version.json")
    try:
        with open(version_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def parse_version(value):
    text = str(value or "0").strip()
    parts = []
    for item in text.split("."):
        try:
            parts.append(int(item))
        except Exception:
            parts.append(0)
    return tuple(parts)


def fetch_json(url):
    req = urllib_request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib_request.urlopen(req, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bytes(url):
    req = urllib_request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib_request.urlopen(req, timeout=12) as response:
        return response.read()


def update_script_if_needed(script_path, settings):
    manifest_url = str(settings.get("update_manifest_url", "")).strip()
    if not settings.get("auto_update_enabled") or not manifest_url:
        log_message("Auto update disabled or manifest URL missing")
        return
    try:
        manifest = fetch_json(manifest_url)
    except Exception:
        log_message("Failed to fetch update manifest")
        return
    remote_version = str(manifest.get("version", "0"))
    script_url = str(manifest.get("script_url", "")).strip()
    if not script_url:
        return
    local_version = str(load_local_version(script_path).get("version", "0"))
    if parse_version(remote_version) <= parse_version(local_version):
        log_message(f"No update needed local={local_version} remote={remote_version}")
        return
    backup_path = script_path + ".bak"
    temp_path = script_path + ".download"
    try:
        payload = fetch_bytes(script_url)
        with open(temp_path, "wb") as fh:
            fh.write(payload)
        if os.path.exists(script_path):
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.replace(script_path, backup_path)
        os.replace(temp_path, script_path)
        save_local_version(
            script_path,
            {
                "version": remote_version,
                "manifest_url": manifest_url,
                "updated_at": int(time.time()),
            },
        )
        log_message(f"Updated script to version {remote_version}")
    except Exception:
        log_message("Update download failed; keeping existing script")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        if os.path.exists(backup_path) and not os.path.exists(script_path):
            try:
                os.replace(backup_path, script_path)
            except Exception:
                pass


def script_candidates():
    candidates = []
    env_path = os.environ.get("FC_GAME_SCRIPT", "").strip()
    if env_path:
        candidates.append(env_path)
    if getattr(sys, "frozen", False):
        app_bundle = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sys.executable))))
        parent = os.path.dirname(app_bundle)
        candidates.append(os.path.join(parent, "Football Game.py"))
        candidates.append(os.path.join(parent, "game", "Football Game.py"))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(base, "Football Game.py"))
    return candidates


def show_error(message):
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("FC Fantasy Launcher", message)
        root.destroy()
    except Exception:
        sys.stderr.write(message + "\n")


def launcher_exec_args():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, os.path.abspath(__file__)]


def restart_launcher(script_path):
    log_message(f"Restarting launcher for {script_path}")
    env = os.environ.copy()
    env["FC_GAME_SCRIPT"] = script_path
    os.execvpe(launcher_exec_args()[0], launcher_exec_args(), env)


def watch_script_for_changes(script_path):
    try:
        last_mtime = os.path.getmtime(script_path)
    except OSError:
        return

    while True:
        time.sleep(1.0)
        try:
            current_mtime = os.path.getmtime(script_path)
        except OSError:
            continue
        if current_mtime != last_mtime:
            restart_launcher(script_path)


def main():
    settings = load_settings()
    log_message(f"Launcher start frozen={getattr(sys, 'frozen', False)} cwd={os.getcwd()}")
    if settings.get("cloud_enabled") and settings.get("cloud_api_url"):
        os.environ["FC_CLOUD_API_URL"] = settings["cloud_api_url"].rstrip("/")
    for candidate in script_candidates():
        log_message(f"Checking script candidate {candidate}")
        if candidate and os.path.exists(candidate):
            script_path = os.path.abspath(candidate)
            log_message(f"Using script {script_path}")
            update_script_if_needed(script_path, settings)
            watcher = threading.Thread(target=watch_script_for_changes, args=(script_path,), daemon=True)
            watcher.start()
            os.chdir(os.path.dirname(script_path))
            sys.argv[0] = script_path
            runpy.run_path(script_path, run_name="__main__")
            return
    log_message("No script candidate found")
    show_error(
        "Could not find 'Football Game.py'.\n\n"
        "Put the editable game file next to the app, or set FC_GAME_SCRIPT."
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        log_message("Launcher exited via SystemExit")
        raise
    except Exception:
        log_message("Launcher exception:\n" + traceback.format_exc())
        show_error("Launcher failed:\n\n" + traceback.format_exc())
        raise
