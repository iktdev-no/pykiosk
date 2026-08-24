#!/usr/bin/env python3

import tkinter as tk
import subprocess
import os
import re
import time
import base64
from PIL import ImageTk


# ==========================================
# KONFIGURASJON
# ==========================================

START_URL = "http://192.168.2.20:5173"

ROTATION_FILE = "/var/lib/kammich/rotation.idx"

BAR_HEIGHT = 50

# Høyden på Onboard.
# Endre denne hvis du ønsker større/mindre tastatur.
KEYBOARD_HEIGHT = 300


rotations = [
    ("normal",   "1 0 0 0 1 0 0 0 1"),
    ("right",    "0 1 0 -1 0 1 0 0 1"),
    ("inverted", "-1 0 1 0 -1 1 0 0 1"),
    ("left",     "0 -1 1 1 0 0 0 0 1")
]


# ==========================================
# LAST INN LAGRET ROTASJON
# ==========================================

current_rot_idx = 0

if os.path.exists(ROTATION_FILE):
    try:
        with open(ROTATION_FILE, "r") as f:
            current_rot_idx = int(f.read().strip())

        if current_rot_idx < 0 or current_rot_idx >= len(rotations):
            current_rot_idx = 0

    except Exception:
        current_rot_idx = 0


browser_process = None


# ==========================================
# SKJERM / LAYOUT
# ==========================================

def get_output_name():
    result = subprocess.run(
        ["xrandr", "--query"],
        capture_output=True,
        text=True
    )

    for line in result.stdout.splitlines():
        if " connected" in line:
            return line.split()[0]

    return None


def get_screen_geometry():
    """
    Get the actual active XRandR geometry.

    Do not rely on Tk's screen geometry here. After xrandr rotation,
    Tk can temporarily report the old dimensions.
    """
    result = subprocess.run(
        ["xrandr", "--query"],
        capture_output=True,
        text=True
    )

    for line in result.stdout.splitlines():
        if " connected" not in line:
            continue

        # Example:
        # HDMI-1 connected primary 1920x1080+0+0
        match = re.search(r"\s(\d+)x(\d+)\+\-?\d+\+\-?\d+", line)
        if match:
            return int(match.group(1)), int(match.group(2))

    # Fallback to Tk.
    root.update_idletasks()
    return root.winfo_screenwidth(), root.winfo_screenheight()


def get_layout_geometry():
    width, height = get_screen_geometry()

    # The bottom bar is always 50 px high.
    web_height = max(1, height - BAR_HEIGHT)

    # Keyboard is an overlay. It must never extend outside the screen.
    keyboard_height = min(
        KEYBOARD_HEIGHT,
        web_height
    )

    return {
        "width": width,
        "height": height,

        # WebView occupies the complete available area above the bar.
        "web_x": 0,
        "web_y": 0,
        "web_width": width,
        "web_height": web_height,

        # Onboard is an overlay directly above the bottom bar.
        "keyboard_x": 0,
        "keyboard_y": height - BAR_HEIGHT - keyboard_height,
        "keyboard_width": width,
        "keyboard_height": keyboard_height,

        # Bottom bar.
        "bar_x": 0,
        "bar_y": height - BAR_HEIGHT,
        "bar_width": width,
        "bar_height": BAR_HEIGHT,
    }


# ==========================================
# ONBOARD
# ==========================================

keyboard_visible = False


def is_keyboard_running():
    result = subprocess.run(
        ["pgrep", "-x", "onboard"],
        capture_output=True
    )

    return result.returncode == 0


def stop_keyboard():
    global keyboard_visible

    subprocess.run(
        ["pkill", "-x", "onboard"],
        capture_output=True
    )

    keyboard_visible = False


def start_keyboard():
    global keyboard_visible

    layout = get_layout_geometry()

    if layout["keyboard_height"] <= 0:
        return

    # Kill any old instance so its saved geometry cannot interfere.
    subprocess.run(
        ["pkill", "-x", "onboard"],
        capture_output=True
    )

    time.sleep(0.15)

    subprocess.Popen([
        "onboard",
        "-x", str(layout["keyboard_x"]),
        "-y", str(layout["keyboard_y"]),
        "-s",
        f'{layout["keyboard_width"]}x{layout["keyboard_height"]}'
    ])

    keyboard_visible = True


def toggle_keyboard():
    global keyboard_visible

    if keyboard_visible or is_keyboard_running():
        stop_keyboard()
    else:
        start_keyboard()


# ==========================================
# BROWSER
# ==========================================

def stop_browser():
    global browser_process

    if browser_process is None:
        return

    try:
        browser_process.terminate()
        browser_process.wait(timeout=2)
    except Exception:
        try:
            browser_process.kill()
        except Exception:
            pass

    browser_process = None


def start_browser():
    global browser_process

    stop_browser()

    layout = get_layout_geometry()

    env = os.environ.copy()
    env["WEBKIT_DISABLE_COMPOSITING_MODE"] = "0"

    cmd = [
        "/home/kammich/kiosk-env/bin/python3",
        "-c",
        f"""
import webview

webview.create_window(
    'Kammich Kiosk',
    '{START_URL}',
    width={layout["web_width"]},
    height={layout["web_height"]},
    x={layout["web_x"]},
    y={layout["web_y"]},
    frameless=True,
    easy_drag=False,
    resizable=False,
    background_color='#111111'
)

webview.start()
"""
    ]

    browser_process = subprocess.Popen(
        cmd,
        env=env
    )


def reload_app():
    # Restart only the browser.
    # Keyboard state is intentionally left untouched.
    start_browser()


# ==========================================
# ROTASJON
# ==========================================

def apply_rotation(idx):
    global current_rot_idx

    rot_name, matrix = rotations[idx]

    output = get_output_name()

    if not output:
        print("Fant ingen tilkoblet skjerm.")
        return

    # Preserve the user's keyboard state.
    was_keyboard_visible = keyboard_visible or is_keyboard_running()

    # Nothing should be moving while XRandR changes geometry.
    if was_keyboard_visible:
        stop_keyboard()

    stop_browser()

    result = subprocess.run([
        "sudo",
        "xrandr",
        "--output",
        output,
        "--rotate",
        rot_name
    ])

    if result.returncode != 0:
        print(f"Kunne ikke rotere skjermen til {rot_name}.")
        start_browser()
        if was_keyboard_visible:
            start_keyboard()
        return

    # Update touch/digitizer mapping.
    xinput_res = subprocess.run(
        ["xinput", "list", "--name-only"],
        capture_output=True,
        text=True
    )

    for dev in xinput_res.stdout.splitlines():
        if any(
            k in dev.lower()
            for k in [
                "touch",
                "digitizer",
                "pen",
                "stylus",
                "ctp"
            ]
        ):
            subprocess.run([
                "sudo",
                "xinput",
                "set-prop",
                dev,
                "Coordinate Transformation Matrix"
            ] + matrix.split())

    # Give XRandR/XInput time to settle.
    time.sleep(0.8)

    layout = get_layout_geometry()

    # Keep the Tk bottom bar exactly at the bottom of the actual screen.
    root.geometry(
        f'{layout["bar_width"]}x{layout["bar_height"]}'
        f'+{layout["bar_x"]}+{layout["bar_y"]}'
    )
    root.update_idletasks()

    # Start the browser using the NEW geometry.
    start_browser()

    # Only restore Onboard if it was visible before rotation.
    if was_keyboard_visible:
        start_keyboard()


def rotate_screen():
    global current_rot_idx

    current_rot_idx = (
        current_rot_idx + 1
    ) % len(rotations)

    try:
        os.makedirs(
            os.path.dirname(ROTATION_FILE),
            exist_ok=True
        )

        with open(ROTATION_FILE, "w") as f:
            f.write(str(current_rot_idx))

    except Exception as e:
        print(f"Klarte ikke å lagre rotasjon: {e}")

    apply_rotation(current_rot_idx)


# ==========================================
# TKINTER
# ==========================================

root = tk.Tk()

root.overrideredirect(True)
root.attributes("-topmost", True)
root.focus_force()

root.configure(bg="#111111")


# ==========================================
# IKONER
# ==========================================

rotate_icon_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAEsWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS41LjAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgeG1sbnM6ZXhpZj0iaHR0cDovL25zLmFkb2JlLmNvbS9leGlmLzEuMC8iCiAgICB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyIKICAgIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIKICAgIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIKICAgIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIgogICAgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZUV2ZW50IyIKICAgZXhpZjpQaXhlbFhEaW1lbnNpb249IjMyIgogICBleGlmOlBpeGVsWURpbWVuc2lvbj0iMzIiCiAgIGV4aWY6Q29sb3JTcGFjZT0iMSIKICAgdGlmZjpJbWFnZVdpZHRoPSIzMiIKICAgdGlmZjpJbWFnZUxlbmd0aD0iMzIiCiAgIHRpZmY6UmVzb2x1dGlvblVuaXQ9IjIiCiAgIHRpZmY6WFJlc29sdXRpb249IjcyLzEiCiAgIHRpZmY6WVJlc29sdXRpb249IjcyLzEiCiAgIHBob3Rvc2hvcDpDb2xvck1vZGU9IjMiCiAgIHBob3Rvc2hvcDpJQ0NQcm9maWxlPSJzUkdCIElFQzYxOTY2LTIuMSIKICAgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDgtMDhUMDM6NDU6MzArMDI6MDAiCiAgIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDgtMDhUMDM6NDU6MzArMDI6MDAiPgogICA8eG1wTU06SGlzdG9yeT4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgc3RFdnQ6YWN0aW9uPSJwcm9kdWNlZCIKICAgICAgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWZmaW5pdHkgUGhvdG8gMiAyLjYuNSIKICAgICAgc3RFdnQ6d2hlbj0iMjAyNi0wOC0wOFQwMzo0NTozMCswMjowMCIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rvcnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+tfO9uQAAAYBpQ0NQc1JHQiBJRUM2MTk2Ni0yLjEAACiRdZHPK0RRFMc/ZogYUSQLi5eGFfKjJjYWI4bCYuYpvzYzz3szama83nuTJltlqyix8WvBX8BWWStFpGQtS2KDnvOMGsmc0733c7/3nNO954JPTWsZu7wbMlnHikbCyvTMrFL5RJV4GQGa4pptTsRGVEra241Eil11erVKx/1rNQu6rUFZlfCgZlqO8Kjw+LJjerwp3Kil4gvCx8IdllxQ+NrTEwV+9DhZ4A+PLTU6BL56YSX5ixO/WEtZGWF5OcFMOqf93Md7SUDPTsVkbZXRgk2UCGEUxhhmiBA9DMgcopNeumRHifzu7/xJliRXk9kkj8UiSVI4dIiak+q6rIbouniavNf/v321jb7eQvVAGCoeXPelDSo34HPddd/3XffzAPz3cJYt5i/tQf+r6OtFLbgLdatwcl7UEltwugbNd2bcin9Lfhk+w4DnI6idgYZLqJ4r9OznnMNbUFfkqy5gewfaJb5u/gsNFme9rCn+aQAAAAlwSFlzAAALEwAACxMBAJqcGAAAAXdJREFUWIXtlkFKw0AYRr8R607XatttRTyB4qJbD9ALeAFBcKU3kIKX0E2FVl24VMSCV9B2aXsBdxV8LpxiGJNxmk4jqB8EksnM/14mmTDSf3IE2ABWfgK8BtzxkVfgDFgqEj7ka7ozl0iBXwH9qBJAFWjYo+qBt4EFoBJVwoLHafjgiTHxJFyBFHgnCXckelNLOAJHIfCoEo5AMl54NIkMgYsQeKJGObeEZwbGac1CYi7w4YJjjBlIqkvq26YtSddZEvOJ82dJ557aD5NIAHVJx5JKtnlX0klojb8Tk9YI7EnatpcjSQfGmGFoUWBf0qanS9MYk/1KgUXgPvElPwKrEwi0vllRjXHf1FVgjHmRtCOpa5tqkm4mkYiSCDNRsj+zzBnII/EUIpECf8slkEfCwjuJ/gPgMLeAR6IcCK+Rst+ILmHhbRdu700v4JPwwe24Cp9bvkpugQyJHnCZBZ9JUiSKgzsSp8DIwm8Lgzsiy8B64eBfkXfrw9rdARZg2gAAAABJRU5ErkJggg==")
keyboard_icon_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAEsWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS41LjAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgeG1sbnM6ZXhpZj0iaHR0cDovL25zLmFkb2JlLmNvbS9leGlmLzEuMC8iCiAgICB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyIKICAgIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIKICAgIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIKICAgIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIgogICAgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZUV2ZW50IyIKICAgZXhpZjpQaXhlbFhEaW1lbnNpb249IjMyIgogICBleGlmOlBpeGVsWURpbWVuc2lvbj0iMzIiCiAgIGV4aWY6Q29sb3JTcGFjZT0iMSIKICAgdGlmZjpJbWFnZVdpZHRoPSIzMiIKICAgdGlmZjpJbWFnZUxlbmd0aD0iMzIiCiAgIHRpZmY6UmVzb2x1dGlvblVuaXQ9IjIiCiAgIHRpZmY6WFJlc29sdXRpb249IjcyLzEiCiAgIHRpZmY6WVJlc29sdXRpb249IjcyLzEiCiAgIHBob3Rvc2hvcDpDb2xvck1vZGU9IjMiCiAgIHBob3Rvc2hvcDpJQ0NQcm9maWxlPSJzUkdCIElFQzYxOTY2LTIuMSIKICAgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDgtMDhUMDM6NDQ6MjQrMDI6MDAiCiAgIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDgtMDhUMDM6NDQ6MjQrMDI6MDAiPgogICA8eG1wTU06SGlzdG9yeT4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgc3RFdnQ6YWN0aW9uPSJwcm9kdWNlZCIKICAgICAgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWZmaW5pdHkgUGhvdG8gMiAyLjYuNSIKICAgICAgc3RFdnQ6d2hlbj0iMjAyNi0wOC0wOFQwMzo0NDoyNCswMjowMCIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rvcnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8++IFw1gAAAYBpQ0NQc1JHQiBJRUM2MTk2Ni0yLjEAACiRdZHPK0RRFMc/ZogYUSQLi5eGFfKjJjYWI4bCYuYpvzYzz3szama83nuTJltlqyix8WvBX8BWWStFpGQtS2KDnvOMGsmc0733c7/3nNO954JPTWsZu7wbMlnHikbCyvTMrFL5RJV4GQGa4pptTsRGVEra241Eil11erVKx/1rNQu6rUFZlfCgZlqO8Kjw+LJjerwp3Kil4gvCx8IdllxQ+NrTEwV+9DhZ4A+PLTU6BL56YSX5ixO/WEtZGWF5OcFMOqf93Md7SUDPTsVkbZXRgk2UCGEUxhhmiBA9DMgcopNeumRHifzu7/xJliRXk9kkj8UiSVI4dIiak+q6rIbouniavNf/v321jb7eQvVAGCoeXPelDSo34HPddd/3XffzAPz3cJYt5i/tQf+r6OtFLbgLdatwcl7UEltwugbNd2bcin9Lfhk+w4DnI6idgYZLqJ4r9OznnMNbUFfkqy5gewfaJb5u/gsNFme9rCn+aQAAAAlwSFlzAAALEwAACxMBAJqcGAAAAPtJREFUWIXtlk1uwjAQRt+gikpFKgeAg7CuOALcor1BeyI4Auw5COq6SO2GzddFnWjkGgIEhwV+m2R+lM+ejDyGQuHesdghaQBMgf6VtfbA2sy+D2ZIepX0pXzsJL0lKyDpCfgEhlfeecwOGJnZD0DPBV46ECdoTCvjwQUeo8QtsAnvk/BsY4/dt+v+8guI2ZjZHEDSAqClPUuJ9FLOLjlWgUm1E0JJ29opfAX+nQldUHrg5j1QI2mW8QiOmVe6N2/Cc3pgaScCLHMsIAu+CfcNuWP/75pyG+K1lh/HA/7G8fOJIpeSHsfB8R4Scop/VOLQ/ZVs5cULhQLALyy4ULFojsCNAAAAAElFTkSuQmCC")
restart_icon_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAEsWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS41LjAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgeG1sbnM6ZXhpZj0iaHR0cDovL25zLmFkb2JlLmNvbS9leGlmLzEuMC8iCiAgICB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyIKICAgIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIKICAgIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIKICAgIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIgogICAgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZUV2ZW50IyIKICAgZXhpZjpQaXhlbFhEaW1lbnNpb249IjMyIgogICBleGlmOlBpeGVsWURpbWVuc2lvbj0iMzIiCiAgIGV4aWY6Q29sb3JTcGFjZT0iMSIKICAgdGlmZjpJbWFnZVdpZHRoPSIzMiIKICAgdGlmZjpJbWFnZUxlbmd0aD0iMzIiCiAgIHRpZmY6UmVzb2x1dGlvblVuaXQ9IjIiCiAgIHRpZmY6WFJlc29sdXRpb249IjcyLzEiCiAgIHRpZmY6WVJlc29sdXRpb249IjcyLzEiCiAgIHBob3Rvc2hvcDpDb2xvck1vZGU9IjMiCiAgIHBob3Rvc2hvcDpJQ0NQcm9maWxlPSJzUkdCIElFQzYxOTY2LTIuMSIKICAgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDgtMDhUMDM6NDU6MDMrMDI6MDAiCiAgIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDgtMDhUMDM6NDU6MDMrMDI6MDAiPgogICA8eG1wTU06SGlzdG9yeT4KICAgIDxyZGY6U2VxPgogICAgIDxyZGY6bGkKICAgICAgc3RFdnQ6YWN0aW9uPSJwcm9kdWNlZCIKICAgICAgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWZmaW5pdHkgUGhvdG8gMiAyLjYuNSIKICAgICAgc3RFdnQ6d2hlbj0iMjAyNi0wOC0wOFQwMzo0NTowMyswMjowMCIvPgogICAgPC9yZGY6U2VxPgogICA8L3htcE1NOkhpc3Rvcnk+CiAgPC9yZGY6RGVzY3JpcHRpb24+CiA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgo8P3hwYWNrZXQgZW5kPSJyIj8+tGW9jAAAAYBpQ0NQc1JHQiBJRUM2MTk2Ni0yLjEAACiRdZHPK0RRFMc/ZogYUSQLi5eGFfKjJjYWI4bCYuYpvzYzz3szama83nuTJltlqyix8WvBX8BWWStFpGQtS2KDnvOMGsmc0733c7/3nNO954JPTWsZu7wbMlnHikbCyvTMrFL5RJV4GQGa4pptTsRGVEra241Eil11erVKx/1rNQu6rUFZlfCgZlqO8Kjw+LJjerwp3Kil4gvCx8IdllxQ+NrTEwV+9DhZ4A+PLTU6BL56YSX5ixO/WEtZGWF5OcFMOqf93Md7SUDPTsVkbZXRgk2UCGEUxhhmiBA9DMgcopNeumRHifzu7/xJliRXk9kkj8UiSVI4dIiak+q6rIbouniavNf/v321jb7eQvVAGCoeXPelDSo34HPddd/3XffzAPz3cJYt5i/tQf+r6OtFLbgLdatwcl7UEltwugbNd2bcin9Lfhk+w4DnI6idgYZLqJ4r9OznnMNbUFfkqy5gewfaJb5u/gsNFme9rCn+aQAAAAlwSFlzAAALEwAACxMBAJqcGAAAAapJREFUWIXtljEvQ1EYhr+r6aBNLAzahEVCVMJQInTzC3Qm4heY/QS2ktRQE2sHERMLgxCNwaIGiUoTo8HSoQmP5dzkc92rzr3SG0nf6UvPed/36T23JxXpKYKAgVjLgatYywFiLe86gLfcqACk4yp39Q7cAwfAUhwAWh/A3p89FaC/A8QGcAjUTbmrJ2AxankGaAALQRCe/QXgUUG8AsNRAE5M0Bsw5gfh40kB+wriOGz5ugq5BhKe9cCLCEgYj6u1MABNY24B4wF7Aq9iYMJ4AZq25RlFX7Zk1zllleP7LvQFeGfVfBMWQERqAZkdAfJqvo0AoL15vw1BACNqtju/r9LeURuABzVPRgDIqbluA3Cn5pkIANMBmT8LGFJv72nYduBM5Qzami+UeTlEeVH5z239AkwBbRPQALIW3izwbLxtINfZ5R+0rb7FC+D7W/Z45sxeV1uhyk1YGrhUYS2g5Adiikvq+sV4U6EBTHAS2OW7KmpPxWd9B0hGKveArHoebVWtVT1HtfLbXMcSwhGReREpigiO42yaz91zPhKRmuM43f+73tO/1SfCqbVMj9ut5AAAAABJRU5ErkJggg==")



# NB:
# De tre base64-strengene over må erstattes med de komplette
# strengene fra originalfilen din dersom de ikke allerede
# ligger i filen du kjører.


img_refresh = ImageTk.PhotoImage(
    data=restart_icon_bytes
)

img_keyboard = ImageTk.PhotoImage(
    data=keyboard_icon_bytes
)

img_rotate = ImageTk.PhotoImage(
    data=rotate_icon_bytes
)


# ==========================================
# BOTTOM BAR
# ==========================================

btn_container = tk.Frame(
    root,
    bg="#000000",
    bd=0,
    highlightthickness=0
)

btn_container.pack(
    fill=tk.BOTH,
    expand=True,
    padx=0,
    pady=0
)


btn_config = {
    "bg": "#000000",
    "fg": "white",
    "font": ("Arial", 14, "bold"),

    # Ingen border
    "bd": 0,
    "borderwidth": 0,
    "highlightthickness": 0,
    "relief": tk.FLAT,

    "activebackground": "#444444",
    "activeforeground": "white",

    "compound": tk.LEFT,
    "padx": 10,
}


# ==========================================
# KNAPPER
# ==========================================

btn_refresh = tk.Button(
    btn_container,
    image=img_refresh,
    **btn_config
)

btn_refresh.bind(
    "<ButtonPress-1>",
    lambda e: reload_app()
)

btn_refresh.pack(
    side=tk.LEFT,
    fill=tk.BOTH,
    expand=True
)


# 70 % av 50 px = 35 px
SEPARATOR_HEIGHT = int(BAR_HEIGHT * 0.70)


separator1 = tk.Frame(
    btn_container,
    bg="white",
    width=1,
    height=SEPARATOR_HEIGHT
)

separator1.pack(
    side=tk.LEFT,
    fill=tk.Y,
    pady=(
        (BAR_HEIGHT - SEPARATOR_HEIGHT) // 2,
        (BAR_HEIGHT - SEPARATOR_HEIGHT + 1) // 2
    )
)


btn_kb = tk.Button(
    btn_container,
    image=img_keyboard,
    **btn_config
)

btn_kb.bind(
    "<ButtonPress-1>",
    lambda e: toggle_keyboard()
)

btn_kb.pack(
    side=tk.LEFT,
    fill=tk.BOTH,
    expand=True
)


separator2 = tk.Frame(
    btn_container,
    bg="white",
    width=1,
    height=SEPARATOR_HEIGHT
)

separator2.pack(
    side=tk.LEFT,
    fill=tk.Y,
    pady=(
        (BAR_HEIGHT - SEPARATOR_HEIGHT) // 2,
        (BAR_HEIGHT - SEPARATOR_HEIGHT + 1) // 2
    )
)


btn_rotate = tk.Button(
    btn_container,
    image=img_rotate,
    **btn_config
)

btn_rotate.bind(
    "<ButtonPress-1>",
    lambda e: rotate_screen()
)

btn_rotate.pack(
    side=tk.LEFT,
    fill=tk.BOTH,
    expand=True
)


# ==========================================
# START
# ==========================================

def initial_start():
    """
    Restore the saved screen rotation and start the browser.

    Onboard is deliberately NOT started here.
    It only appears after pressing the keyboard button.
    """

    # Make absolutely sure a stale Onboard instance from a previous
    # process cannot remain visible.
    stop_keyboard()

    apply_rotation(current_rot_idx)


# ==========================================
# WATCHDOG
# ==========================================

def monitor_app():
    if (
        browser_process is not None
        and browser_process.poll() is not None
    ):
        print("Browser-prosessen døde. Starter på nytt...")
        start_browser()

        # Do not start Onboard here.
        # If it was visible, it remains visible independently.

    root.after(
        1000,
        monitor_app
    )


# Start kiosk
initial_start()

root.after(
    1000,
    monitor_app
)


# ==========================================
# SHUTDOWN
# ==========================================

try:
    root.mainloop()

finally:

    stop_keyboard()

    if browser_process:
        try:
            browser_process.terminate()
        except Exception:
            pass
