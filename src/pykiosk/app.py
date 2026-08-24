#!/usr/bin/env python3

import os
import sys
import argparse
import subprocess
import tkinter as tk
from pykiosk.TopBar import TopBar
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
        self.override_url = initial_url
        
        self.root = tk.Tk()
        
        self.display = DisplayManager(self.root, self.config)
        self.rotation_manager = RotationManager(self.root, self.config, self.display)
        self.keyboard = OnboardKeyboard(self.root)
        
        # Hent rotasjonsindeks og roter FØR vi lager noen elementer
        self.current_rot_idx = self.config.load_rotation_index()
        
        # Utfør rotasjon med en gang slik at X-serveren er i riktig modus
        self.rotation_manager.execute_rotation(self.current_rot_idx)
        import time
        time.sleep(0.2) # Gi X-serveren et lite øyeblikk til å sette oppløsningen
        
        # Prosesser for nettlesere
        self.main_browser_process = None
        self.overlay_browser_process = None

        # 2. Tkinter vindusoppsett (Kiosk-modus)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.configure(bg="#111111")

        # 3. Opprett Bunnbar (UI) med NØYAKTIG geometri for gjeldende rotasjon
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
        """Starter hovednettleseren i en egen underprosess via webview."""
        self.stop_main_browser()
        
        # Gi X-serveren et øyeblikk til å lande hvis den kalles rett etter rotasjon
        import time
        time.sleep(0.1)
        
        layout = self.display.get_layout_geometry()
        
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

    def open_overlay(self, url: str):
        self.close_overlay()
        layout = self.display.get_layout_geometry()
        
        # 1. Lag et eget lite Tkinter-vindu for toppbaren
        self.overlay_bar_window = tk.Toplevel(self.root)
        self.overlay_bar_window.overrideredirect(True)
        self.overlay_bar_window.attributes("-topmost", True)
        self.overlay_bar_window.geometry(
            f'{layout["overlay_top_width"]}x{layout["overlay_top_height"]}+'
            f'{layout["overlay_top_x"]}+{layout["overlay_top_y"]}'
        )
        
        # Legg til TopBar-komponenten i dette vinduet
        self.top_bar = TopBar(
            self.overlay_bar_window,
            bar_height=layout["overlay_top_height"],
            title=url,
            on_close=self.close_overlay
        )
        self.top_bar.pack(fill=tk.BOTH, expand=True)

        # 2. Start selve webview-overlayet skjøvet ned under toppbaren
        cmd = [
            sys.executable, "-m", "pykiosk.webview",
            url,
            str(layout["overlay_web_width"]),
            str(layout["overlay_web_height"]),
            str(layout["overlay_web_x"]),
            str(layout["overlay_web_y"])
        ]
        
        env = os.environ.copy()
        self.overlay_browser_process = subprocess.Popen(cmd, env=env)

    def stop_main_browser(self):
        if self.main_browser_process:
            try:
                self.main_browser_process.terminate()
                self.main_browser_process.wait(timeout=2)
            except Exception:
                self.main_browser_process.kill()
            self.main_browser_process = None

    def close_overlay(self):
        if hasattr(self, 'overlay_bar_window') and self.overlay_bar_window:
            try:
                self.overlay_bar_window.destroy()
            except Exception:
                pass
            self.overlay_bar_window = None

        if self.overlay_browser_process:
            try:
                self.overlay_browser_process.terminate()
                self.overlay_browser_process.wait(timeout=2)
            except Exception:
                self.overlay_browser_process.kill()
            self.overlay_browser_process = None

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

        # 1. Utfør selve rotasjonen
        success = self.rotation_manager.execute_rotation(self.current_rot_idx)
        
        if success:
            # Gi X-serveren et lite øyeblikk til å oppdatere skrivebordsbufferen og oppløsningen
            import time
            time.sleep(0.3)
            
            # Hent fersk layout *etter* at rotasjonen har satt seg
            layout = self.display.get_layout_geometry()
            
            # Tving Tkinter til å oppdatere geometri med de nye sidene (Landscape/Portrait byttet om)
            self.root.geometry(f'{layout["bar_width"]}x{layout["bar_height"]}+{layout["bar_x"]}+{layout["bar_y"]}')
            self.root.update_idletasks()

        # 2. Start nettleseren med de nøyaktig oppdaterte målene
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
        self.api_server.start()
        self.root.after(1000, self.monitor_processes)
        
        # Start hovednettleseren direkte ettersom rotasjon og geometri allerede er på plass
        self.start_main_browser()

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