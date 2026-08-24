import os
import subprocess
import time
from pykiosk.display import DisplayManager

class OnboardKeyboard:
    def __init__(self, root_window=None):
        self.display_manager = DisplayManager(root_window)
        self._visible = False

    def ensure_openbox_config(self):
        """Sjekker og oppretter Openbox-konfigurasjon for Onboard hvis den mangler."""
        config_dir = os.path.expanduser("~/.config/openbox")
        config_file = os.path.join(config_dir, "rc.xml")

        if not os.path.exists(config_file):
            try:
                os.makedirs(config_dir, exist_ok=True)
                openbox_xml = """<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://icculus.org/openbox/rdc" xmlns:xi="http://www.w3.org/2001/XInclude">
<applications>
  <!-- Regler for tastaturet -->
  <application name="onboard" class="Onboard">
    <layer>above</layer>
    <skip_pager>yes</skip_pager>
    <skip_taskbar>yes</skip_taskbar>
    <focus>no</focus>
    <decor>no</decor>
  </application>

  <!-- Regler for hovednettleser og overlay (pywebview) -->
  <application class="Python">
    <decor>no</decor>
    <focus>yes</focus>
  </application>
</applications>
</openbox_config>
"""
                with open(config_file, "w") as f:
                    f.write(openbox_xml)
                
                subprocess.run(["openbox", "--reconfigure"], capture_output=True)
            except Exception as e:
                print(f"Klarte ikke å opprette Openbox-konfigurasjon: {e}")

    def is_running(self):
        """Sjekker om Onboard-prosessen faktisk kjører på systemet."""
        result = subprocess.run(["pgrep", "-x", "onboard"], capture_output=True)
        return result.returncode == 0

    def start(self):
        """Starter tastaturet basert på gjeldende skjermgeometri med redusert høyde."""
        self.ensure_openbox_config()
        layout = self.display_manager.get_layout_geometry()

        if layout["keyboard_height"] <= 0:
            return

        self.stop()
        time.sleep(0.15)

        # Reduser høyden her (f.eks. til 75% av det DisplayManager ber om)
        reduced_height = int(layout["keyboard_height"] * 0.75)
        
        # Hvis du vil at det fremdeles skal ligge nederst på skjermen, 
        # må y-koordinaten skyves nedsvart tilsvarende differansen:
        height_diff = layout["keyboard_height"] - reduced_height
        adjusted_y = int(layout["keyboard_y"]) + height_diff

        subprocess.Popen([
            "onboard",
            "-x", str(int(layout["keyboard_x"])),
            "-y", str(adjusted_y),
            "-s", f'{int(layout["keyboard_width"])}x{reduced_height}',
            "--layout", "Phone"  # Holder på det kompakte mobil-oppsettet
        ])
        self._visible = True

    def stop(self):
        """Stopper tastaturet."""
        subprocess.run(["pkill", "-x", "onboard"], capture_output=True)
        self._visible = False

    def toggle(self):
        """Veksler tastaturets synlighet."""
        if self.is_visible():
            self.stop()
        else:
            self.start()

    def is_visible(self):
        """Returnerer om tastaturet er synlig."""
        return self._visible or self.is_running()