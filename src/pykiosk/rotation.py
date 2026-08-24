import subprocess
import re
from pykiosk.display import DisplayManager
from pykiosk.config import ConfigManager

class RotationManager:
    def __init__(self, root_window=None, config_manager=None, display_manager=None):
        self.config = config_manager if config_manager else ConfigManager()
        self.display = display_manager if display_manager else DisplayManager(root_window, self.config)

    def detect_current_rotation_index(self):
        """
        Spør XRandR om hva skjermens faktiske rotasjon er akkurat nå.
        Returnerer indeksen basert på konfigurasjonens rotasjonsliste.
        """
        output = self.display.get_output_name()
        if not output:
            return 0

        result = subprocess.run(["xrandr", "--query"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if output in line:
                for idx, (rot_name, _) in enumerate(self.config.rotations):
                    if f" {rot_name}" in line or f"({rot_name})" in line:
                        return idx
        return 0

    def execute_rotation(self, idx):
        """Utfør selve xrandr-roteringen og oppdater xinput for touch-skjermer."""
        if not (0 <= idx < len(self.config.rotations)):
            print(f"Ugyldig rotasjonsindeks: {idx}")
            return False

        rot_name, matrix = self.config.rotations[idx]
        output = self.display.get_output_name()

        if not output:
            print("Fant ingen tilkoblet skjerm.")
            return False

        # Utfør xrandr rotasjon
        result = subprocess.run(["sudo", "xrandr", "--output", output, "--rotate", rot_name])
        if result.returncode != 0:
            print(f"Kunne ikke rotere skjermen til {rot_name}.")
            return False

        # Oppdater touch/digitizer-mapping (Coordinate Transformation Matrix)
        xinput_res = subprocess.run(["xinput", "list", "--name-only"], capture_output=True, text=True)
        for dev in xinput_res.stdout.splitlines():
            if any(k in dev.lower() for k in ["touch", "digitizer", "pen", "stylus", "ctp"]):
                subprocess.run([
                    "sudo", "xinput", "set-prop", dev, "Coordinate Transformation Matrix"
                ] + matrix.split())

        # Lagre indeksen i konfigurasjonen
        self.config.save_rotation_index(idx)
        return True