#!/usr/bin/env python3

import tkinter as tk
import base64
from PIL import ImageTk
from pykiosk.icons import img_refresh as refreshIcon, img_keyboard as keyboardIcon, img_rotate as rotateIcon


class BottomBar(tk.Frame):
    def __init__(self, parent, bar_height=50, on_refresh=None, on_toggle_keyboard=None, on_rotate=None, **kwargs):
        super().__init__(parent, bg="#000000", bd=0, highlightthickness=0, **kwargs)
        
        self.bar_height = bar_height
        
        # Callbacks for actions
        self.on_refresh = on_refresh
        self.on_toggle_keyboard = on_toggle_keyboard
        self.on_rotate = on_rotate

        # Last inn ikoner

        self._create_widgets()

    def _create_widgets(self):
        # Hovedcontainer for knapper
        btn_container = tk.Frame(
            self,
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
            "bd": 0,
            "borderwidth": 0,
            "highlightthickness": 0,
            "relief": tk.FLAT,
            "activebackground": "#444444",
            "activeforeground": "white",
            "compound": tk.LEFT,
            "padx": 10,
        }

        # 1. Oppdater-knapp
        btn_refresh = tk.Button(
            btn_container,
            image=refreshIcon,
            command=self._handle_refresh,
            **btn_config
        )
        btn_refresh.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Skillelinje 1
        separator_height = int(self.bar_height * 0.70)
        self._create_separator(btn_container, separator_height)

        # 2. Tastatur-knapp
        btn_kb = tk.Button(
            btn_container,
            image=keyboardIcon,
            command=self._handle_toggle_keyboard,
            **btn_config
        )
        btn_kb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Skillelinje 2
        self._create_separator(btn_container, separator_height)

        # 3. Roter-knapp
        btn_rotate = tk.Button(
            btn_container,
            image=rotateIcon,
            command=self._handle_rotate,
            **btn_config
        )
        btn_rotate.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _create_separator(self, parent, separator_height):
        sep = tk.Frame(
            parent,
            bg="white",
            width=1,
            height=separator_height
        )
        sep.pack(
            side=tk.LEFT,
            fill=tk.Y,
            pady=(
                (self.bar_height - separator_height) // 2,
                (self.bar_height - separator_height + 1) // 2
            )
        )

    # --- Handlinger ---
    def _handle_refresh(self):
        if self.on_refresh:
            self.on_refresh()

    def _handle_toggle_keyboard(self):
        if self.on_toggle_keyboard:
            self.on_toggle_keyboard()

    def _handle_rotate(self):
        if self.on_rotate:
            self.on_rotate()