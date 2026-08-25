#!/usr/bin/env python3

import tkinter as tk

class TopBar(tk.Frame):
    def __init__(self, parent, bar_height=40, title="Overlay", on_close=None, **kwargs):
        super().__init__(parent, bg="#111111", bd=0, highlightthickness=0, **kwargs)
        
        self.bar_height = bar_height
        self.on_close = on_close
        self.title_text = title

        self._create_widgets()

    def _create_widgets(self):
        # Hovedcontainer for elementer i toppbaren
        container = tk.Frame(
            self,
            bg="#111111",
            bd=0,
            highlightthickness=0
        )
        container.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=0
        )

        # 1. Tittel / Infotekst for overlayet
        lbl_title = tk.Label(
            container,
            text=self.title_text,
            bg="#111111",
            fg="#aaaaaa",
            font=("Arial", 12, "bold"),
            anchor="w"
        )
        lbl_title.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 2. Lukk-knapp (X)
        btn_close = tk.Button(
            container,
            text="✕ LUKK",
            bg="#cc0000",
            fg="white",
            font=("Arial", 11, "bold"),
            bd=0,
            borderwidth=0,
            highlightthickness=0,
            relief=tk.FLAT,
            activebackground="#ff0000",
            activeforeground="white",
            padx=15,
            command=self._handle_close
        )
        # Pakker den til høyre, og lar den fylle høyden med litt padding i toppen/bunn
        btn_close.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

    def _handle_close(self):
        if self.on_close:
            # Bruk after(1) slik at knappen rekker å bli ferdig med klikk-hendelsen 
            # før vinduet og elementene destrueres underveis.
            self.after(1, self.on_close)