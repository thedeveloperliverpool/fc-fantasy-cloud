import json
import os
import runpy
import subprocess
import sys
import threading
import time
import traceback
from urllib import error as urllib_error
from urllib import request as urllib_request


APP_NAME = "FC Legends"
DEFAULT_UPDATE_URL = os.environ.get("FC_UPDATE_URL", "").strip()


class UpdateStatusWindow:
    def __init__(self):
        self.pygame = None
        self.screen = None
        self.clock = None
        self.font_title = None
        self.font_body = None
        self.font_small = None
        self.status = "Starting"
        self.detail = ""
        self.version_text = "Preparing launcher"
        self.progress = None
        self._pulse = 0.0
        self._active = False
        try:
            import pygame

            self.pygame = pygame
            if not pygame.get_init():
                pygame.init()
            self.screen = pygame.display.set_mode((520, 230))
            pygame.display.set_caption(f"{APP_NAME} Updater")
            self.clock = pygame.time.Clock()
            self.font_title = pygame.font.SysFont("Helvetica", 22, bold=True)
            self.font_body = pygame.font.SysFont("Helvetica", 16)
            self.font_small = pygame.font.SysFont("Helvetica", 12)
            self._active = True
            self.refresh()
        except Exception:
            self._active = False

    def refresh(self):
        if not self._active or not self.pygame or not self.screen:
            return
        try:
            pygame = self.pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pass

            self.screen.fill((7, 22, 45))
            pygame.draw.rect(self.screen, (11, 31, 63), (18, 18, 484, 194), border_radius=22)
            pygame.draw.rect(self.screen, (40, 149, 255), (18, 18, 484, 194), 2, border_radius=22)

            self.screen.blit(self.font_title.render("FC Legends Updater", True, (208, 247, 255)), (36, 34))
            self.screen.blit(self.font_small.render(self.version_text, True, (133, 217, 255)), (38, 68))
            self.screen.blit(self.font_body.render(self.status, True, (255, 255, 255)), (38, 98))

            detail_lines = []
            words = self.detail.split()
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                if self.font_small.size(test)[0] > 430 and current:
                    detail_lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                detail_lines.append(current)
            for idx, line in enumerate(detail_lines[:2]):
                self.screen.blit(self.font_small.render(line, True, (212, 220, 235)), (38, 126 + idx * 18))

            bar_rect = pygame.Rect(38, 172, 444, 18)
            pygame.draw.rect(self.screen, (10, 32, 60), bar_rect, border_radius=9)
            if self.progress is None:
                self._pulse = (self._pulse + 0.06) % 1.0
                pulse_x = bar_rect.x + int((bar_rect.w - 120) * self._pulse)
                pygame.draw.rect(self.screen, (42, 182, 255), (pulse_x, bar_rect.y, 120, bar_rect.h), border_radius=9)
            else:
                filled = max(0, min(bar_rect.w, int(bar_rect.w * (self.progress / 100.0))))
                pygame.draw.rect(self.screen, (42, 182, 255), (bar_rect.x, bar_rect.y, filled, bar_rect.h), border_radius=9)
                self.screen.blit(self.font_small.render(f"{int(self.progress)}%", True, (158, 180, 205)), (448, 196))

            pygame.display.flip()
            self.clock.tick(30)
        except Exception:
            self._active = False

    def set_status(self, status, detail="", progress=None, version_text=""):
        if not self._active:
            return
        if version_text:
            self.version_text = version_text
        self.status = status
        self.detail = detail
        self.progress = None if progress is None else max(0, min(100, progress))
        self.refresh()

    def close(self, delay=0.0):
        if delay > 0:
            end_time = time.time() + delay
            while time.time() < end_time:
                self.refresh()
                time.sleep(0.05)
        if not self._active or not self.pygame:
            return
        try:
            self.pygame.display.quit()
        except Exception:
            pass
        self._active = False


def app_data_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    return os.path.dirname(os.path.abspath(__file__))


def load_settings():
    defaults = {
        "cloud_enabled": True,
        "cloud_api_url": os.environ.get("FC_CLOUD_API_URL", "http://127.0.0.1:8080"),
        "auto_update_enabled": True,
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


def fetch_bytes(url, progress_callback=None):
    req = urllib_request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib_request.urlopen(req, timeout=12) as response:
        total = response.headers.get("Content-Length")
        try:
            total = int(total) if total else 0
        except Exception:
            total = 0
        chunks = []
        received = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
            received += len(chunk)
            if progress_callback:
                progress_callback(received, total)
        return b"".join(chunks)


def update_script_if_needed(script_path, settings, update_window=None):
    local_info = load_local_version(script_path)
    manifest_url = str(settings.get("update_manifest_url", "") or local_info.get("manifest_url", "")).strip()
    local_version = str(local_info.get("version", "0"))
    version_text = f"Current version {local_version}"
    if not settings.get("auto_update_enabled") or not manifest_url:
        log_message("Auto update disabled or manifest URL missing")
        if update_window:
            update_window.set_status("Starting game", "Auto update is off for this copy.", 100, version_text)
            update_window.close(0.4)
        return
    try:
        if update_window:
            update_window.set_status("Checking for updates", "Contacting update server...", None, version_text)
        manifest = fetch_json(manifest_url)
    except Exception:
        log_message("Failed to fetch update manifest")
        if update_window:
            update_window.set_status("Update check failed", "Could not reach update server. Launching current version.", 100, version_text)
            update_window.close(0.9)
        return
    remote_version = str(manifest.get("version", "0"))
    script_url = str(manifest.get("script_url", "")).strip()
    if not script_url:
        if update_window:
            update_window.set_status("Starting game", f"Version {local_version} is ready.", 100, version_text)
            update_window.close(0.35)
        return
    if parse_version(remote_version) <= parse_version(local_version):
        log_message(f"No update needed local={local_version} remote={remote_version}")
        if update_window:
            update_window.set_status("Up to date", f"Version {local_version} is current.", 100, f"Installed version {local_version}")
            update_window.close(0.6)
        return
    backup_path = script_path + ".bak"
    temp_path = script_path + ".download"
    try:
        if update_window:
            update_window.set_status(
                f"New version {remote_version} found",
                "Downloading update package...",
                0,
                f"Installed {local_version}  Available {remote_version}",
            )

        def report_progress(received, total):
            if not update_window:
                return
            if total > 0:
                detail = f"Downloading {received // 1024} KB of {total // 1024} KB"
                update_window.set_status("Downloading update", detail, received * 100 / total, f"Updating to {remote_version}")
            else:
                detail = f"Downloading {received // 1024} KB"
                update_window.set_status("Downloading update", detail, None, f"Updating to {remote_version}")

        payload = fetch_bytes(script_url, progress_callback=report_progress)
        if update_window:
            update_window.set_status("Installing update", "Applying the new version...", 100, f"Updating to {remote_version}")
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
        if update_window:
            update_window.set_status("Update complete", f"FC Legends {remote_version} is ready.", 100, f"Installed version {remote_version}")
            update_window.close(0.8)
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
        if update_window:
            update_window.set_status("Update failed", "Keeping the current installed version.", 100, version_text)
            update_window.close(1.0)


def script_candidates():
    candidates = []
    env_path = os.environ.get("FC_GAME_SCRIPT", "").strip()
    if env_path:
        candidates.append(env_path)
    if getattr(sys, "frozen", False):
        app_bundle = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sys.executable))))
        resources = os.path.join(app_bundle, "Contents", "Resources")
        parent = os.path.dirname(app_bundle)
        candidates.append(os.path.join(resources, "Football Game.py"))
        candidates.append(os.path.join(parent, "Football Game.py"))
        candidates.append(os.path.join(parent, "game", "Football Game.py"))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(base, "Football Game.py"))
    return candidates


def show_error(message):
    try:
        subprocess.run(
            ["osascript", "-e", f'display dialog {json.dumps(message)} with title "FC Legends" buttons {{"OK"}} default button "OK"'],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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
            update_window = UpdateStatusWindow()
            update_script_if_needed(script_path, settings, update_window=update_window)
            local_version = str(load_local_version(script_path).get("version", "0"))
            os.environ["FC_APP_VERSION"] = local_version
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
