import subprocess
import re
from pykiosk.config import ConfigManager


class DisplayManager:
    def __init__(self, root_window=None, config_manager=None):
        self.root_window = root_window
        self.config = config_manager if config_manager else ConfigManager()
        self._last_geometry = self.get_screen_geometry()

    def has_display_changed(self) -> bool:
        current_geometry = self.get_screen_geometry()

        if current_geometry == self._last_geometry:
            return False

        print(
            f"Display geometry changed: "
            f"{self._last_geometry} -> {current_geometry}"
        )

        self._last_geometry = current_geometry
        return True

    def get_output_name(self):
        """Finner navnet på den aktive tilkoblede skjermen (f.eks. HDMI-1)."""
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True
        )

        for line in result.stdout.splitlines():
            if " connected" in line:
                return line.split()[0]
        return None

    def get_screen_geometry(self):
        """Henter aktiv XRandR-geometri direkte fra systemet."""

        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True
        )

        for line in result.stdout.splitlines():
            if " connected" not in line:
                continue

            match = re.search(
                r"\s(\d+)x(\d+)\+\-?\d+\+\-?\d+",
                line
            )

            if match:
                return int(match.group(1)), int(match.group(2))

        return None

    def get_layout_geometry(self):
        """Beregner nøyaktige dimensjoner og posisjoner for layouten basert på konfigurasjon."""

        geometry = self.get_screen_geometry()

        if geometry is None:
            return None

        width, height = geometry

        bar_height = self.config.bar_height
        keyboard_height = self.config.keyboard_height
        top_bar_height = 40

        web_height = max(1, height - bar_height)
        kb_height = min(keyboard_height, web_height)

        overlay_web_height = max(
            1,
            height - bar_height - top_bar_height
        )

        return {
            "width": width,
            "height": height,
            # Hovednettleser
            "web_x": 0,
            "web_y": 0,
            "web_width": width,
            "web_height": web_height,
            # Tastatur
            "keyboard_x": 0,
            "keyboard_y": height - bar_height - kb_height,
            "keyboard_width": width,
            "keyboard_height": kb_height,
            # Bunnbar
            "bar_x": 0,
            "bar_y": height - bar_height,
            "bar_width": width,
            "bar_height": bar_height,
            # Overlay: Toppbar (for lukkeknapp e.l.)
            "overlay_top_x": 0,
            "overlay_top_y": 0,
            "overlay_top_width": width,
            "overlay_top_height": top_bar_height,
            # Overlay: Nettleservindu (skjøvet ned under toppbaren)
            "overlay_web_x": 0,
            "overlay_web_y": top_bar_height,
            "overlay_web_width": width,
            "overlay_web_height": overlay_web_height,
        }