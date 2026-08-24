#!/usr/bin/env python3

import os
import sys
import argparse
import subprocess
import tkinter as tk
from pykiosk.config import ConfigManager
from pykiosk.display import DisplayManager
from pykiosk.rotation import RotationManager
from pykiosk.keyboard import OnboardKeyboard
from pykiosk.api import KioskApiServer
from pykiosk.BottomBar import BottomBar

class KioskApp:
    def __init__(self, initial_url: str|None):
        # 1. Kjernemoduler
        self.config = ConfigManager()
        
        # Bruk medsendt URL hvis oppgitt, ellers fall tilbake til lagret konfigurasjon
        self.override_url = initial_url
        
        self.root = tk.Tk()
        
        self.display = DisplayManager(self.root, self.config)
        self.rotation_manager = RotationManager(self.root, self.config, self.display)
        self.keyboard = OnboardKeyboard(self.root)
        
        # Hent rotasjonsindeks fra lagring
        self.current_rot_idx = self.config.load_rotation_index()
        
        # Prosesser for nettlesere
        self.main_browser_process = None
        self.overlay_browser_process = None

        # 2. Tkinter vindusoppsett (Kiosk-modus)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.configure(bg="#111111")

        # 3. Opprett Bunnbar (UI)
        layout = self.display.get_layout_geometry()
        self.root.geometry(f'{layout["bar_width"]}x{layout["bar_height"]}+{layout["bar_x"]}+{layout["bar_y"]}')

        self.bottom_bar = BottomBar(
            self.root,
            bar_height=self.config.bar_height,
            on_refresh=self.reload_main_browser,
            on_toggle_keyboard=self.keyboard.toggle,
            on_rotate=self.rotate_screen
        )
        self.bottom_bar.pack(fill=tk.BOTH, expand=True)

        # 4. Sett opp API-server
        self.api_server = KioskApiServer(host="127.0.0.1", port=8081)
        self.api_server.register_callback("open_overlay", self.open_overlay)
        self.api_server.register_callback("close_overlay", self.close_overlay)

    def start_main_browser(self):
        """Starter hovednettleseren i en egen underprosess via webview_runner."""
        self.stop_main_browser()
        layout = self.display.get_layout_geometry()
        
        # Bruk overstyrt URL hvis den finnes, ellers hent fra config
        url = self.override_url if self.override_url else self.config.load_url()

        cmd = [
            sys.executable, "-m", "pykiosk.webview",
            url,
            str(layout["web_width"]),
            str(layout["web_height"]),
            str(layout["web_x"]),
            str(layout["web_y"])
        ]
        
        env = os.environ.copy()
        env["WEBKIT_DISABLE_COMPOSITING_MODE"] = "0"
        
        self.main_browser_process = subprocess.Popen(cmd, env=env)

    def stop_main_browser(self):
        if self.main_browser_process:
            try:
                self.main_browser_process.terminate()
                self.main_browser_process.wait(timeout=2)
            except Exception:
                self.main_browser_process.kill()
            self.main_browser_process = None

    def open_overlay(self, url: str):
        """Åpner overlay-nettleseren over hovednettleseren med angitt URL."""
        self.close_overlay()
        
        layout = self.display.get_layout_geometry()
        cmd = [
            sys.executable, "-m", "pykiosk.webview_runner",
            url,
            str(layout["web_width"]),
            str(layout["web_height"]),
            str(layout["web_x"]),
            str(layout["web_y"])
        ]
        
        env = os.environ.copy()
        self.overlay_browser_process = subprocess.Popen(cmd, env=env)
        print(f"Overlay åpnet med URL: {url}")

    def close_overlay(self):
        """Lukker overlay-nettleseren hvis den kjører."""
        if self.overlay_browser_process:
            try:
                self.overlay_browser_process.terminate()
                self.overlay_browser_process.wait(timeout=2)
            except Exception:
                self.overlay_browser_process.kill()
            self.overlay_browser_process = None
            print("Overlay lukket.")

    def reload_main_browser(self):
        """Starter hovednettleseren på nytt."""
        self.start_main_browser()

    def rotate_screen(self):
        """Roterer skjermen til neste indeks i rotasjonslisten."""
        self.current_rot_idx = (self.current_rot_idx + 1) % len(self.config.rotations)
        
        was_kb_visible = self.keyboard.is_visible()
        if was_kb_visible:
            self.keyboard.stop()
        
        self.stop_main_browser()
        self.close_overlay()

        success = self.rotation_manager.execute_rotation(self.current_rot_idx)
        
        if success:
            layout = self.display.get_layout_geometry()
            self.root.geometry(f'{layout["bar_width"]}x{layout["bar_height"]}+{layout["bar_x"]}+{layout["bar_y"]}')
            self.root.update_idletasks()

        self.start_main_browser()
        
        if was_kb_visible:
            self.keyboard.start()

    def monitor_processes(self):
        """Watchdog som sjekker om hovednettleseren har krasjet, og starter den på nytt."""
        if self.main_browser_process is not None and self.main_browser_process.poll() is not None:
            print("Hovednettleser døde uventet. Starter på nytt...")
            self.start_main_browser()
        
        self.root.after(1000, self.monitor_processes)

    def run(self):
        """Starter hele kioskløsningen."""
        self.rotation_manager.execute_rotation(self.current_rot_idx)
        self.start_main_browser()
        self.api_server.start()
        self.root.after(1000, self.monitor_processes)

        try:
            self.root.mainloop()
        finally:
            self.keyboard.stop()
            self.close_overlay()
            self.stop_main_browser()
            self.api_server.stop()

def main():
    parser = argparse.ArgumentParser(description="PyKiosk App")
    parser.add_argument("url", nargs="?", default=None, help="Valgfri URL som skal overstyre lagret standard-URL")
    args = parser.parse_args()

    app = KioskApp(initial_url=args.url)
    app.run()

if __name__ == "__main__":
    main()