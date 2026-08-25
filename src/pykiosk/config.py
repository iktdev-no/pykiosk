import os

class ConfigManager:
    def __init__(self, default_url="http://127.0.0.1:8080", rotation_file="/var/lib/kammich/rotation.idx", url_file="/var/lib/kammich/url.cfg"):
        self.default_url = default_url
        self.rotation_file = rotation_file
        self.url_file = url_file

        self.bar_height = 50
        self.keyboard_height = 300

        self.rotations = [
            ("normal",   "1 0 0 0 1 0 0 0 1"),
            ("right",    "0 1 0 -1 0 1 0 0 1"),
            ("inverted", "-1 0 1 0 -1 1 0 0 1"),
            ("left",     "0 -1 1 1 0 0 0 0 1")
        ]

    def load_rotation_index(self):
        """Henter lagret rotasjons-indeks fra fil, med fallback til 0 (normal)."""
        if os.path.exists(self.rotation_file):
            try:
                with open(self.rotation_file, "r") as f:
                    idx = int(f.read().strip())
                    if 0 <= idx < len(self.rotations):
                        return idx
            except Exception:
                pass
        return 0

    def save_rotation_index(self, idx):
        """Lagrer rotasjons-indeks til fil."""
        try:
            os.makedirs(os.path.dirname(self.rotation_file), exist_ok=True)
            with open(self.rotation_file, "w") as f:
                f.write(str(idx))
        except Exception as e:
            print(f"Klarte ikke å lagre rotasjon: {e}")

    def load_url(self):
        """Henter lagret URL fra fil, eller returnerer default hvis filen ikke finnes."""
        if os.path.exists(self.url_file):
            try:
                with open(self.url_file, "r") as f:
                    url = f.read().strip()
                    if url:
                        return url
            except Exception:
                pass
        return self.default_url

    def save_url(self, url):
        """Lagrer en ny hoved-URL til fil."""
        try:
            os.makedirs(os.path.dirname(self.url_file), exist_ok=True)
            with open(self.url_file, "w") as f:
                f.write(url.strip())
        except Exception as e:
            print(f"Klarte ikke å lagre URL: {e}")