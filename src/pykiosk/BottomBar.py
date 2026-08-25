#!/usr/bin/env python3

import tkinter as tk
import base64
from PIL import ImageTk
from pykiosk.icons import get_refresh_icon, get_keyboard_icon, get_rotate_icon

class BottomBar(tk.Frame):
    def __init__(self, parent, bar_height=50, on_refresh=None, on_long_refresh=None, on_toggle_keyboard=None, on_rotate=None, **kwargs):
        super().__init__(parent, bg="#000000", bd=0, highlightthickness=0, **kwargs)
        
        self.bar_height = bar_height
        
        # Callbacks for actions
        self.on_refresh = on_refresh
        self.on_long_refresh = on_long_refresh
        self.on_toggle_keyboard = on_toggle_keyboard
        self.on_rotate = on_rotate

        self.img_refresh = get_refresh_icon()
        self.img_keyboard = get_keyboard_icon()
        self.img_rotate = get_rotate_icon()

        self._long_press_timer = None

        self._create_widgets()

    def _create_widgets(self):
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

        # 1. Oppdater-knapp med Long Press-støtte
        self.btn_refresh = tk.Button(
            btn_container,
            image=self.img_refresh,
            command=self._handle_refresh_click,
            **btn_config
        )
        self.btn_refresh.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind trykk ned og slipp for å oppdage hold / long press (1 sekund)
        self.btn_refresh.bind("<Button-1>", self._start_long_press)
        self.btn_refresh.bind("<ButtonRelease-1>", self._cancel_long_press)
        self.btn_refresh.bind("<Leave>", self._cancel_long_press)

        separator_height = int(self.bar_height * 0.70)
        self._create_separator(btn_container, separator_height)

        # 2. Tastatur-knapp
        btn_kb = tk.Button(
            btn_container,
            image=self.img_keyboard,
            command=self._handle_toggle_keyboard,
            **btn_config
        )
        btn_kb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._create_separator(btn_container, separator_height)

        # 3. Roter-knapp
        btn_rotate = tk.Button(
            btn_container,
            image=self.img_rotate,
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

    # --- Long Press Logikk for Refresh ---
    def _start_long_press(self, event):
        self._clear_timer()
        # Hvis brukeren holder knappen i 1000ms (1 sekund), utløs long press
        self._long_press_timer = self.after(1000, self._trigger_long_refresh)

    def _cancel_long_press(self, event=None):
        self._clear_timer()

    def _clear_timer(self):
        if self._long_press_timer:
            try:
                self.after_cancel(self._long_press_timer)
            except Exception:
                pass
            self._long_press_timer = None

    def _trigger_long_refresh(self):
        self._long_press_timer = None
        if self.on_long_refresh:
            self.on_long_refresh()

    # --- Vanlige Handlinger ---
    def _handle_refresh_click(self):
        # Hvis long press allerede har fyrt av, ignorerer vi standard klikk
        if self._long_press_timer is None:
            return 
        self._clear_timer()
        if self.on_refresh:
            self.on_refresh()

    def _handle_toggle_keyboard(self):
        if self.on_toggle_keyboard:
            self.on_toggle_keyboard()

    def _handle_rotate(self):
        if self.on_rotate:
            self.on_rotate()