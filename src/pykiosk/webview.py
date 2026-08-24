#!/usr/bin/env python3

import sys
import webview

def main():
    if len(sys.argv) < 6:
        print("Bruk: webview_runner.py <url> <width> <height> <x> <y>")
        sys.exit(1)

    url = sys.argv[1]
    width = int(sys.argv[2])
    height = int(sys.argv[3])
    x = int(sys.argv[4])
    y = int(sys.argv[5])

    webview.create_window(
        'Kammich Kiosk',
        url,
        width=width,
        height=height,
        x=x,
        y=y,
        frameless=True,
        easy_drag=False,
        resizable=False,
        background_color='#111111'
    )

    webview.start()

if __name__ == "__main__":
    main()