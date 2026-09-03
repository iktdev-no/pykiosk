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
import threading

class KioskApp:
    def __init__(self, initial_url: str|None):
        # 1. Kjernemoduler
        self.config = ConfigManager()
        self.override_url = initial_url
        self._display_change_job = None
        
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
        if layout is not None:
            self.root.geometry(f'{layout["bar_width"]}x{layout["bar_height"]}+{layout["bar_x"]}+{layout["bar_y"]}')

        # 4. Opprett Bunnbar (UI) med støtte for vanlig trykk og long-press (hard restart)
        self.bottom_bar = BottomBar(
            self.root,
            bar_height=self.config.bar_height,
            on_refresh=self.reload_main_browser,
            on_long_refresh=self.hard_restart_kiosk,
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
        time.sleep(0.3) # Gi X11 litt ekstra tid til å rydde opp vindusbufferet
        
        layout = self.display.get_layout_geometry()
        if layout is None:
            print("No display connected, waiting for display,")
            return

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
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, lambda: self.open_overlay(url))
            return

        if self.is_overlay_active():
            print(f"Overlay er allerede aktivt. Ignorerer forsøk på å åpne: {url}")
            return

        self.current_overlay_url = url
        
        self.root.update_idletasks()
        layout = self.display.get_layout_geometry()
        if layout is None:
            print("Can't start overlay when there is no display connected.")
            return

        self.root.after(50, lambda: self._create_overlay_window(url, layout))

    def _create_overlay_window(self, url: str, layout: dict):
        if self.current_overlay_url != url:
            return

        self.overlay_bar_window = tk.Toplevel(self.root)
        self.overlay_bar_window.overrideredirect(True)
        self.overlay_bar_window.attributes("-topmost", True)
        
        try:
            self.overlay_bar_window.transient(self.root)
        except Exception:
            pass
            
        self.overlay_bar_window.configure(bg="#111111")
        
        w = layout["overlay_top_width"]
        h = layout["overlay_top_height"]
        x = layout["overlay_top_x"]
        y = layout["overlay_top_y"]
        
        self.overlay_bar_window.geometry(f"{w}x{h}+{x}+{y}")
        
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
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, self.close_overlay)
            return

        if self.top_bar:
            try:
                self.top_bar.destroy()
            except Exception:
                pass
            self.top_bar = None

        if self.overlay_bar_window:
            try:
                self.overlay_bar_window.grab_release()
                self.overlay_bar_window.destroy()
            except Exception:
                pass
            self.overlay_bar_window = None

        self.current_overlay_url = None
        
        try:
            self.root.update_idletasks()
        except Exception:
            pass

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

    def hard_restart_kiosk(self):
        """River ned alt unntatt bunnbaren (tastatur, overlays, hovednettleser) og starter opp igjen."""
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, self.hard_restart_kiosk)
            return

        print("Hard omstart av kiosk-komponenter via long-press på refresh...")
        
        # 1. Stopp tastatur hvis synlig
        was_kb_visible = self.keyboard.is_visible()
        if was_kb_visible:
            self.keyboard.stop()

        # 2. Drep alt av nettlesere og overlays fullstendig
        self.close_overlay()
        self.stop_main_browser()

        # 3. Kort pause for at systemressurser frigjøres
        import time
        time.sleep(0.3)

        # 4. Start hovednettleseren opp igjen
        self.start_main_browser()

        # 5. Gjenopprett tastatur om det var aktivt
        if was_kb_visible:
            self.keyboard.start()

    def rotate_screen(self):
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
            time.sleep(0.4)
            
            layout = self.display.get_layout_geometry()
            self.root.geometry(f'{layout["bar_width"]}x{layout["bar_height"]}+{layout["bar_x"]}+{layout["bar_y"]}')
            self.root.update_idletasks()

        self.start_main_browser()
        
        if was_overlay_active and active_overlay_url:
            import time
            time.sleep(0.2)
            self.open_overlay(active_overlay_url)

        if was_kb_visible:
            self.keyboard.start()

    def monitor_processes(self):
        if self.main_browser_process is not None and self.main_browser_process.poll() is not None:
            print("Hovednettleser døde uventet. Starter på nytt...")
            self.start_main_browser()
        
        self.root.after(1000, self.monitor_processes)

    def monitor_display(self):
        if self.display.has_display_changed():
            print("Display changed, updating kiosk layout...")

            if self._display_change_job is not None:
                self.root.after_cancel(self._display_change_job)

            self._display_change_job = self.root.after(
                750,
                self.apply_display_layout
            )

        self.root.after(500, self.monitor_display)


    def apply_display_layout(self):
        self._display_change_job = None

        layout = self.display.get_layout_geometry()

        if layout is None:
            print("No display connected, stopping browser.")
            self.stop_main_browser()
            return

        self.root.geometry(
            f'{layout["bar_width"]}x{layout["bar_height"]}'
            f'+{layout["bar_x"]}+{layout["bar_y"]}'
        )

        self.root.update_idletasks()
        self.root.update()

        self.reload_main_browser()

    def run(self):
        self.api_server.start()
        self.root.after(1000, self.monitor_processes)
        self.root.after(500, self.monitor_display)
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