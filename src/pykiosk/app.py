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
        
        self.current_rot_idx = self.config.load_rotation_index()
        self.rotation_manager.execute_rotation(self.current_rot_idx)
        import time
        time.sleep(0.2)
        
        self.main_browser_process = None
        self.overlay_browser_process = None
        self.top_bar = None
        self.overlay_bar_window = None
        self.current_overlay_url = None

        # 2. Tkinter vindusoppsett (Kiosk-modus)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.configure(bg="#111111")

        # 3. Opprett Hovedvinduets geometri
        layout = self.display.get_layout_geometry()
        self.root.geometry(f'{layout["bar_width"]}x{layout["bar_height"]}+{layout["bar_x"]}+{layout["bar_y"]}')

        # 4. Opprett Bunnbar (UI)
        self.bottom_bar = BottomBar(
            self.root,
            bar_height=self.config.bar_height,
            on_refresh=self.reload_main_browser,
            on_toggle_keyboard=self.keyboard.toggle,
            on_rotate=self.rotate_screen
        )
        self.bottom_bar.pack(side=tk.BOTTOM, fill=tk.BOTH)

        # 5. Sett opp API-server
        self.api_server = KioskApiServer(host="127.0.0.1", port=8081)
        self.api_server.register_callback("open_overlay", self.open_overlay)
        self.api_server.register_callback("close_overlay", self.close_overlay)
        self.api_server.register_callback("is_overlay_active", self.is_overlay_active)

    def start_main_browser(self):
        """Starter hovednettleseren i en egen underprosess via webview."""
        self.stop_main_browser()
        
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

    def is_overlay_active(self) -> bool:
        """Sjekker om overlay-vinduet eller prosessen er aktiv."""
        has_window = self.overlay_bar_window is not None
        has_process = self.overlay_browser_process is not None and self.overlay_browser_process.poll() is None
        return has_window or has_process

    def open_overlay(self, url: str):
        self.close_overlay()
        self.current_overlay_url = url
        
        self.root.update_idletasks()
        layout = self.display.get_layout_geometry()
        
        # Bruk en mikro-forsinkelse via Tkinter slik at X11 garantert har slettet det forrige vinduet
        self.root.after(50, lambda: self._create_overlay_window(url, layout))

    def _create_overlay_window(self, url: str, layout: dict):
        if self.current_overlay_url != url:
            return # Avbryt hvis en annen url ble åpnet i mellomtiden

        # 1. Lag et eget Toplevel-vindu for toppbaren
        self.overlay_bar_window = tk.Toplevel(self.root)
        self.overlay_bar_window.overrideredirect(True)
        self.overlay_bar_window.attributes("-topmost", True)
        
        try:
            self.overlay_bar_window.transient(self.root)
        except Exception:
            pass
            
        self.overlay_bar_window.configure(bg="#111111")
        
        # 2. Sett posisjon og størrelse eksplisitt
        w = layout["overlay_top_width"]
        h = layout["overlay_top_height"]
        x = layout["overlay_top_x"]
        y = layout["overlay_top_y"]
        
        self.overlay_bar_window.geometry(f"{w}x{h}+{x}+{y}")
        
        # 3. Legg TopBar inn i vinduet
        self.top_bar = TopBar(
            self.overlay_bar_window,
            bar_height=h,
            title=url,
            on_close=self.close_overlay
        )
        self.top_bar.pack(fill=tk.BOTH, expand=True)
        
        self.overlay_bar_window.update_idletasks()
        self.overlay_bar_window.deiconify()
        self.overlay_bar_window.lift()
        
        # 4. Start selve webview-overlayet under
        cmd = [
            sys.executable, "-m", "pykiosk.webview",
            url,
            str(layout["overlay_web_width"]),
            str(layout["overlay_web_height"]),
            str(layout["overlay_web_x"]),
            str(layout["overlay_web_y"])
        ]
        
        env = os.environ.copy()
        env["WEBKIT_DISABLE_COMPOSITING_MODE"] = "0"
        self.overlay_browser_process = subprocess.Popen(cmd, env=env)

    def close_overlay(self):
        # 1. Fjern og ødelegg TopBar-innholdet først
        if self.top_bar:
            try:
                self.top_bar.destroy()
            except Exception:
                pass
            self.top_bar = None

        # 2. Drep selve Toplevel-vinduet til toppbaren fullstendig
        if self.overlay_bar_window:
            try:
                self.overlay_bar_window.grab_release()
                self.overlay_bar_window.destroy()
            except Exception:
                pass
            self.overlay_bar_window = None

        self.current_overlay_url = None
        
        # Tving Tkinter til å prosessere alle ventende vindushendelser (sletter restene fra X11)
        try:
            self.root.update_idletasks()
        except Exception:
            pass

        # 3. Avslutt nettleserprosessen for overlayet
        if self.overlay_browser_process:
            try:
                self.overlay_browser_process.terminate()
                self.overlay_browser_process.wait(timeout=2)
            except Exception:
                try:
                    self.overlay_browser_process.kill()
                except Exception:
                    pass
            self.overlay_browser_process = None
   
    def stop_main_browser(self):
        if self.main_browser_process:
            try:
                self.main_browser_process.terminate()
                self.main_browser_process.wait(timeout=2)
            except Exception:
                self.main_browser_process.kill()
            self.main_browser_process = None

    def reload_main_browser(self):
        """Starter hovednettleseren på nytt, og oppdaterer overlayet hvis det er aktivt."""
        self.start_main_browser()
        
        # Hvis et overlay er åpent, må vi også starte selve overlay-webprosessen på nytt
        if self.current_overlay_url and self.overlay_bar_window:
            url = self.current_overlay_url
            
            if self.overlay_browser_process:
                try:
                    self.overlay_browser_process.terminate()
                    self.overlay_browser_process.wait(timeout=1)
                except Exception:
                    try:
                        self.overlay_browser_process.kill()
                    except Exception:
                        pass
                self.overlay_browser_process = None

            layout = self.display.get_layout_geometry()
            cmd = [
                sys.executable, "-m", "pykiosk.webview",
                url,
                str(layout["overlay_web_width"]),
                str(layout["overlay_web_height"]),
                str(layout["overlay_web_x"]),
                str(layout["overlay_web_y"])
            ]
            
            env = os.environ.copy()
            env["WEBKIT_DISABLE_COMPOSITING_MODE"] = "0"
            self.overlay_browser_process = subprocess.Popen(cmd, env=env)

    def rotate_screen(self):
        """Roterer skjermen til neste indeks i rotasjonslisten."""
        self.current_rot_idx = (self.current_rot_idx + 1) % len(self.config.rotations)
        
        was_kb_visible = self.keyboard.is_visible()
        if was_kb_visible:
            self.keyboard.stop()
        
        was_overlay_active = self.is_overlay_active()
        active_overlay_url = self.current_overlay_url

        self.stop_main_browser()
        self.close_overlay()

        success = self.rotation_manager.execute_rotation(self.current_rot_idx)
        
        if success:
            import time
            time.sleep(0.4) # Litt lengre pause for å la skjermdriveren rotere ordentlig
            
            layout = self.display.get_layout_geometry()
            self.root.geometry(f'{layout["bar_width"]}x{layout["bar_height"]}+{layout["bar_x"]}+{layout["bar_y"]}')
            self.root.update_idletasks()

        self.start_main_browser()
        
        # Gjenopprett overlay med en ørliten forsinkelse så skjermen har stabilisert seg
        if was_overlay_active and active_overlay_url:
            import time
            time.sleep(0.2)
            self.open_overlay(active_overlay_url)

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