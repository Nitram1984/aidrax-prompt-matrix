#!/usr/bin/env python3
"""AIDRAX Neon GUI for Prompt Manager using Tkinter."""

from __future__ import annotations

import json
import sysconfig
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import ai
import db


AIDRAX_BG = "#050611"
AIDRAX_SURFACE = "#090d1d"
AIDRAX_SURFACE_ALT = "#11152c"
AIDRAX_TEXT = "#e9ecff"
AIDRAX_MUTED = "#adc2ff"
AIDRAX_PRIMARY = "#00f7ff"
AIDRAX_SECONDARY = "#ff00ea"
AIDRAX_OK = "#00ff96"
AIDRAX_WARN = "#ffd166"
AIDRAX_DANGER = "#ff6b8a"
AIDRAX_EDGE = "#22304f"
AIDRAX_INPUT = "#0d1326"
APP_DIR = Path(__file__).resolve().parent
INSTALL_DIR = Path.home() / ".local" / "share" / "prompt-manager"
SHARED_ASSET_DIR = Path(sysconfig.get_path("data")) / "share" / "aidrax-prompt-matrix" / "assets"
ASSET_DIRS = [
    APP_DIR / "assets",
    INSTALL_DIR / "assets",
    SHARED_ASSET_DIR,
]


def find_asset(filename: str) -> Path:
    for asset_dir in ASSET_DIRS:
        candidate = asset_dir / filename
        if candidate.exists():
            return candidate
    return ASSET_DIRS[0] / filename


APP_ICON_PNG = find_asset("aidrax-icon-neon-cyberpunk.png")
APP_ICON_ICO = find_asset("aidrax-icon-neon-cyberpunk.ico")


class PromptManagerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AIDRAX Prompt Matrix")
        self.root.geometry("1920x1080")
        self.root.minsize(1280, 720)
        self.root.configure(bg=AIDRAX_BG)
        self.icon_image: tk.PhotoImage | None = None
        self._apply_window_icon()
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

        db.init_db()

        self.prompt_map: dict[int, dict] = {}
        self.category_by_name: dict[str, int | None] = {"(Keine)": None}
        self.selected_prompt_id: int | None = None
        self.last_generated_prompt = ""
        self.busy = False
        self.action_buttons: list[tk.Button] = []

        self.prompt_count_var = tk.StringVar(value="0")
        self.active_count_var = tk.StringVar(value="0")
        self.favorite_count_var = tk.StringVar(value="0")
        self.category_count_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Bereit")
        self.signal_var = tk.StringVar(value="Kein Signal")

        self._setup_theme()
        self._build_ui()
        self._load_categories()
        self._refresh_prompt_list()
        self._new_prompt()

    def _apply_window_icon(self) -> None:
        try:
            if APP_ICON_PNG.exists():
                self.icon_image = tk.PhotoImage(file=str(APP_ICON_PNG))
                self.root.iconphoto(True, self.icon_image)
        except tk.TclError:
            self.icon_image = None

        try:
            if APP_ICON_ICO.exists():
                self.root.iconbitmap(default=str(APP_ICON_ICO))
        except tk.TclError:
            pass

    def _set_initial_split_layout(self) -> None:
        try:
            self.main_pane.sash_place(0, 390, 1)
        except tk.TclError:
            pass
        try:
            self.editor_pane.sash_place(0, 1, 500)
        except tk.TclError:
            pass

    def _setup_theme(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "AIDRAX.Treeview",
            background=AIDRAX_SURFACE,
            foreground=AIDRAX_TEXT,
            fieldbackground=AIDRAX_SURFACE,
            borderwidth=0,
            rowheight=30,
            relief="flat",
        )
        style.map(
            "AIDRAX.Treeview",
            background=[("selected", "#16213f")],
            foreground=[("selected", AIDRAX_PRIMARY)],
        )
        style.configure(
            "AIDRAX.Treeview.Heading",
            background=AIDRAX_SURFACE_ALT,
            foreground=AIDRAX_PRIMARY,
            relief="flat",
            borderwidth=0,
            padding=(8, 8),
            font=("Orbitron", 10, "bold"),
        )
        style.configure(
            "AIDRAX.Vertical.TScrollbar",
            gripcount=0,
            background=AIDRAX_SURFACE_ALT,
            darkcolor=AIDRAX_SURFACE_ALT,
            lightcolor=AIDRAX_SURFACE_ALT,
            troughcolor=AIDRAX_BG,
            bordercolor=AIDRAX_BG,
            arrowcolor=AIDRAX_PRIMARY,
        )
        style.configure(
            "AIDRAX.TCombobox",
            fieldbackground=AIDRAX_INPUT,
            background=AIDRAX_INPUT,
            foreground=AIDRAX_TEXT,
            arrowcolor=AIDRAX_PRIMARY,
            bordercolor=AIDRAX_EDGE,
            lightcolor=AIDRAX_EDGE,
            darkcolor=AIDRAX_EDGE,
            insertcolor=AIDRAX_PRIMARY,
        )
        style.map(
            "AIDRAX.TCombobox",
            fieldbackground=[("readonly", AIDRAX_INPUT)],
            foreground=[("readonly", AIDRAX_TEXT)],
            selectbackground=[("readonly", AIDRAX_SECONDARY)],
            selectforeground=[("readonly", AIDRAX_BG)],
        )

        self.root.option_add("*TCombobox*Listbox.background", AIDRAX_SURFACE_ALT)
        self.root.option_add("*TCombobox*Listbox.foreground", AIDRAX_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", AIDRAX_SECONDARY)
        self.root.option_add("*TCombobox*Listbox.selectForeground", AIDRAX_BG)

    def _make_card(
        self,
        parent: tk.Widget,
        *,
        title: str,
        subtitle: str = "",
        accent: str = AIDRAX_PRIMARY,
        body_bg: str = AIDRAX_SURFACE,
    ) -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(
            parent,
            bg=body_bg,
            highlightbackground=accent,
            highlightcolor=accent,
            highlightthickness=1,
            bd=0,
        )
        accent_bar = tk.Frame(outer, bg=accent, height=2)
        accent_bar.pack(fill=tk.X)

        header = tk.Frame(outer, bg=body_bg)
        header.pack(fill=tk.X, padx=12, pady=(10, 4))

        title_label = tk.Label(
            header,
            text=title,
            bg=body_bg,
            fg=accent,
            font=("Orbitron", 11, "bold"),
            anchor="w",
        )
        title_label.pack(anchor="w")

        if subtitle:
            subtitle_label = tk.Label(
                header,
                text=subtitle,
                bg=body_bg,
                fg=AIDRAX_MUTED,
                font=("JetBrains Mono", 8),
                anchor="w",
            )
            subtitle_label.pack(anchor="w", pady=(2, 0))

        body = tk.Frame(outer, bg=body_bg)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        return outer, body

    def _make_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        *,
        accent: str = AIDRAX_PRIMARY,
        width: int | None = None,
    ) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=AIDRAX_SURFACE_ALT,
            fg=accent,
            activebackground=accent,
            activeforeground=AIDRAX_BG,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            font=("Space Grotesk", 9, "bold"),
            highlightbackground=accent,
            highlightcolor=accent,
            highlightthickness=1,
            width=width,
        )
        self.action_buttons.append(button)
        return button

    def _style_entry(self, widget: tk.Entry) -> None:
        widget.configure(
            bg=AIDRAX_INPUT,
            fg=AIDRAX_TEXT,
            insertbackground=AIDRAX_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            highlightbackground=AIDRAX_EDGE,
            highlightcolor=AIDRAX_PRIMARY,
            highlightthickness=1,
            selectbackground=AIDRAX_SECONDARY,
            selectforeground=AIDRAX_BG,
            font=("Space Grotesk", 11),
        )

    def _style_text(self, widget: tk.Text, *, mono: bool = False) -> None:
        widget.configure(
            bg=AIDRAX_INPUT,
            fg=AIDRAX_TEXT,
            insertbackground=AIDRAX_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=12,
            highlightbackground=AIDRAX_EDGE,
            highlightcolor=AIDRAX_PRIMARY,
            highlightthickness=1,
            selectbackground=AIDRAX_SECONDARY,
            selectforeground=AIDRAX_BG,
            font=("JetBrains Mono", 10) if mono else ("Space Grotesk", 11),
        )

    def _build_metric_card(
        self,
        parent: tk.Widget,
        label: str,
        value_var: tk.StringVar,
        *,
        accent: str,
        note: str,
    ) -> tk.Frame:
        card = tk.Frame(
            parent,
            bg=AIDRAX_SURFACE_ALT,
            highlightbackground=accent,
            highlightcolor=accent,
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=10,
        )
        tk.Label(
            card,
            text=label,
            bg=AIDRAX_SURFACE_ALT,
            fg=AIDRAX_MUTED,
            font=("JetBrains Mono", 8),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            card,
            textvariable=value_var,
            bg=AIDRAX_SURFACE_ALT,
            fg=accent,
            font=("Orbitron", 18, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            card,
            text=note,
            bg=AIDRAX_SURFACE_ALT,
            fg=AIDRAX_MUTED,
            font=("Space Grotesk", 9),
            anchor="w",
        ).pack(anchor="w")
        return card

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=AIDRAX_BG)
        shell.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        hero, hero_body = self._make_card(
            shell,
            title="AIDRAX // PROMPT OPS",
            subtitle="Neon control surface fuer Prompt-, Skill- und KI-Operations",
            accent=AIDRAX_PRIMARY,
            body_bg=AIDRAX_SURFACE,
        )
        hero.pack(fill=tk.X, pady=(0, 10))

        top_line = tk.Frame(hero_body, bg=AIDRAX_SURFACE)
        top_line.pack(fill=tk.X)
        tk.Label(
            top_line,
            text="PROMPT MATRIX",
            bg=AIDRAX_SURFACE,
            fg=AIDRAX_TEXT,
            font=("Orbitron", 25, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            top_line,
            text="NEON GUI",
            bg=AIDRAX_SURFACE,
            fg=AIDRAX_SECONDARY,
            font=("Orbitron", 17, "bold"),
        ).pack(side=tk.LEFT, padx=(12, 0))
        tk.Label(
            top_line,
            text="LIVE",
            bg=AIDRAX_OK,
            fg=AIDRAX_BG,
            font=("JetBrains Mono", 8, "bold"),
            padx=12,
            pady=3,
        ).pack(side=tk.RIGHT)

        tk.Label(
            hero_body,
            textvariable=self.signal_var,
            bg=AIDRAX_SURFACE,
            fg=AIDRAX_MUTED,
            font=("Space Grotesk", 10),
            anchor="w",
        ).pack(fill=tk.X, pady=(6, 10))

        metrics = tk.Frame(hero_body, bg=AIDRAX_SURFACE)
        metrics.pack(fill=tk.X)
        for index, card in enumerate(
            [
                self._build_metric_card(metrics, "PROMPTS", self.prompt_count_var, accent=AIDRAX_PRIMARY, note="aktive Bibliothek"),
                self._build_metric_card(metrics, "LIVE", self.active_count_var, accent=AIDRAX_OK, note="aktive Records"),
                self._build_metric_card(metrics, "FAVORITES", self.favorite_count_var, accent=AIDRAX_SECONDARY, note="markierte Prompts"),
                self._build_metric_card(metrics, "KATEGORIEN", self.category_count_var, accent=AIDRAX_WARN, note="organisierte Slots"),
            ]
        ):
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 10 if index < 3 else 0))
            metrics.columnconfigure(index, weight=1)

        toolbar, toolbar_body = self._make_card(
            shell,
            title="CONTROL DECK",
            subtitle="Suche, Pflege und KI-Operationen",
            accent=AIDRAX_SECONDARY,
            body_bg=AIDRAX_SURFACE,
        )
        toolbar.pack(fill=tk.X, pady=(0, 10))

        self.search_var = tk.StringVar()
        search_row = tk.Frame(toolbar_body, bg=AIDRAX_SURFACE)
        search_row.pack(fill=tk.X)

        tk.Label(
            search_row,
            text="Suche",
            bg=AIDRAX_SURFACE,
            fg=AIDRAX_PRIMARY,
            font=("JetBrains Mono", 10, "bold"),
        ).pack(side=tk.LEFT)
        search_entry = tk.Entry(search_row, textvariable=self.search_var, width=42)
        self._style_entry(search_entry)
        search_entry.pack(side=tk.LEFT, padx=(10, 12))
        search_entry.bind("<Return>", lambda _e: self._refresh_prompt_list())

        self._make_button(search_row, "Suchen", self._refresh_prompt_list, accent=AIDRAX_PRIMARY).pack(side=tk.LEFT)
        self._make_button(search_row, "Neu", self._new_prompt, accent=AIDRAX_OK).pack(side=tk.LEFT, padx=(8, 0))
        self._make_button(search_row, "Speichern", self._save_prompt, accent=AIDRAX_PRIMARY).pack(side=tk.LEFT, padx=(8, 0))
        self._make_button(search_row, "Loeschen", self._delete_prompt, accent=AIDRAX_DANGER).pack(side=tk.LEFT, padx=(8, 0))
        self.generate_btn = self._make_button(search_row, "Prompt erzeugen", self._generate_prompt_with_ai, accent=AIDRAX_SECONDARY)
        self.generate_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.send_btn = self._make_button(search_row, "Prompt testen", self._send_to_ai, accent=AIDRAX_WARN)
        self.send_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._make_button(search_row, "Konfiguration", self._open_config_dialog, accent=AIDRAX_PRIMARY).pack(side=tk.RIGHT)

        main = tk.PanedWindow(
            shell,
            orient=tk.HORIZONTAL,
            bg=AIDRAX_BG,
            sashwidth=8,
            sashrelief=tk.FLAT,
            bd=0,
            relief=tk.FLAT,
        )
        main.pack(fill=tk.BOTH, expand=True)
        self.main_pane = main

        left_host = tk.Frame(main, bg=AIDRAX_BG)
        right_host = tk.Frame(main, bg=AIDRAX_BG)
        left_host.configure(width=390)
        right_host.configure(width=1110)
        main.add(left_host, minsize=320, stretch="never")
        main.add(right_host, minsize=900, stretch="always")

        left_card, left_body = self._make_card(
            left_host,
            title="PROMPT FLEET",
            subtitle="Live-Raster aller gespeicherten Eintraege",
            accent=AIDRAX_PRIMARY,
            body_bg=AIDRAX_SURFACE,
        )
        left_card.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "title", "category", "fav", "used")
        self.tree = ttk.Treeview(
            left_body,
            columns=cols,
            show="headings",
            selectmode="browse",
            style="AIDRAX.Treeview",
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("title", text="Prompt")
        self.tree.heading("category", text="Kategorie")
        self.tree.heading("fav", text="◆")
        self.tree.heading("used", text="Runs")
        self.tree.column("id", width=56, anchor=tk.E)
        self.tree.column("title", width=240, anchor=tk.W)
        self.tree.column("category", width=146, anchor=tk.W)
        self.tree.column("fav", width=42, anchor=tk.CENTER)
        self.tree.column("used", width=64, anchor=tk.E)
        self.tree.tag_configure("favorite", foreground=AIDRAX_SECONDARY)
        self.tree.tag_configure("inactive", foreground=AIDRAX_MUTED)

        y_scroll = ttk.Scrollbar(left_body, orient=tk.VERTICAL, command=self.tree.yview, style="AIDRAX.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=y_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        form_card, form_body = self._make_card(
            right_host,
            title="PROMPT DOSSIER",
            subtitle="Editiere Titel, Kategorien, Inhalt und Meta",
            accent=AIDRAX_SECONDARY,
            body_bg=AIDRAX_SURFACE,
        )
        form_card.pack(fill=tk.BOTH, expand=True)

        self.title_var = tk.StringVar()
        self.category_var = tk.StringVar(value="(Keine)")
        self.tags_var = tk.StringVar()
        self.favorite_var = tk.BooleanVar(value=False)

        title_row = tk.Frame(form_body, bg=AIDRAX_SURFACE)
        title_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(title_row, text="Titel", bg=AIDRAX_SURFACE, fg=AIDRAX_PRIMARY, font=("JetBrains Mono", 10, "bold"), width=12, anchor="w").pack(side=tk.LEFT)
        title_entry = tk.Entry(title_row, textvariable=self.title_var)
        self._style_entry(title_entry)
        title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        category_row = tk.Frame(form_body, bg=AIDRAX_SURFACE)
        category_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(category_row, text="Kategorie", bg=AIDRAX_SURFACE, fg=AIDRAX_PRIMARY, font=("JetBrains Mono", 10, "bold"), width=12, anchor="w").pack(side=tk.LEFT)
        self.category_combo = ttk.Combobox(
            category_row,
            textvariable=self.category_var,
            state="readonly",
            style="AIDRAX.TCombobox",
        )
        self.category_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._make_button(category_row, "+", self._add_category, accent=AIDRAX_OK, width=3).pack(side=tk.LEFT, padx=(8, 0))

        tags_row = tk.Frame(form_body, bg=AIDRAX_SURFACE)
        tags_row.pack(fill=tk.X, pady=(0, 10))
        tk.Label(tags_row, text="Tags", bg=AIDRAX_SURFACE, fg=AIDRAX_PRIMARY, font=("JetBrains Mono", 10, "bold"), width=12, anchor="w").pack(side=tk.LEFT)
        tags_entry = tk.Entry(tags_row, textvariable=self.tags_var)
        self._style_entry(tags_entry)
        tags_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        favorite_toggle = tk.Checkbutton(
            tags_row,
            text="Favorit",
            variable=self.favorite_var,
            bg=AIDRAX_SURFACE,
            fg=AIDRAX_WARN,
            activebackground=AIDRAX_SURFACE,
            activeforeground=AIDRAX_WARN,
            selectcolor=AIDRAX_INPUT,
            font=("Space Grotesk", 10, "bold"),
            highlightthickness=0,
            bd=0,
        )
        favorite_toggle.pack(side=tk.LEFT, padx=(12, 0))

        description_card, description_body = self._make_card(
            form_body,
            title="BESCHREIBUNG",
            subtitle="Kurzbeschreibung fuer Kontext und Wiederverwendung",
            accent=AIDRAX_WARN,
            body_bg=AIDRAX_SURFACE_ALT,
        )
        description_card.pack(fill=tk.X, pady=(0, 10))
        self.description_text = tk.Text(description_body, height=2, wrap=tk.WORD)
        self._style_text(self.description_text, mono=False)
        self.description_text.pack(fill=tk.X, expand=True)

        editor_pane = tk.PanedWindow(
            form_body,
            orient=tk.VERTICAL,
            bg=AIDRAX_SURFACE,
            sashwidth=10,
            sashrelief=tk.FLAT,
            bd=0,
            relief=tk.FLAT,
        )
        editor_pane.pack(fill=tk.BOTH, expand=True)
        self.editor_pane = editor_pane

        content_host = tk.Frame(editor_pane, bg=AIDRAX_SURFACE)
        response_host = tk.Frame(editor_pane, bg=AIDRAX_SURFACE)
        editor_pane.add(content_host, minsize=320, stretch="always")
        editor_pane.add(response_host, minsize=180, stretch="never")

        content_card, content_body = self._make_card(
            content_host,
            title="PROMPT-INHALT",
            subtitle="Primaerer Arbeitsbereich fuer Prompttext und Platzhalter",
            accent=AIDRAX_PRIMARY,
            body_bg=AIDRAX_SURFACE_ALT,
        )
        content_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        content_frame = tk.Frame(content_body, bg=AIDRAX_SURFACE_ALT)
        content_frame.pack(fill=tk.BOTH, expand=True)
        self.content_text = tk.Text(content_frame, height=24, wrap=tk.WORD)
        self._style_text(self.content_text, mono=True)
        content_scroll = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=self.content_text.yview, style="AIDRAX.Vertical.TScrollbar")
        self.content_text.configure(yscrollcommand=content_scroll.set)
        self.content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        response_card, response_body = self._make_card(
            response_host,
            title="KI-ANTWORT",
            subtitle="Generierter Prompt oder Testantwort",
            accent=AIDRAX_SECONDARY,
            body_bg=AIDRAX_SURFACE_ALT,
        )
        response_card.pack(fill=tk.BOTH, expand=True)

        response_actions = tk.Frame(response_body, bg=AIDRAX_SURFACE_ALT)
        response_actions.pack(fill=tk.X, pady=(0, 8))
        self.apply_btn = self._make_button(
            response_actions,
            "Als Inhalt uebernehmen",
            self._apply_ai_response_to_content,
            accent=AIDRAX_OK,
        )
        self.apply_btn.pack(side=tk.RIGHT)
        self.apply_btn.configure(state=tk.DISABLED)

        response_frame = tk.Frame(response_body, bg=AIDRAX_SURFACE_ALT)
        response_frame.pack(fill=tk.BOTH, expand=True)
        self.response_text = tk.Text(response_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        self._style_text(self.response_text, mono=False)
        response_scroll = ttk.Scrollbar(response_frame, orient=tk.VERTICAL, command=self.response_text.yview, style="AIDRAX.Vertical.TScrollbar")
        self.response_text.configure(yscrollcommand=response_scroll.set)
        self.response_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        response_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        status_bar = tk.Frame(
            self.root,
            bg=AIDRAX_SURFACE_ALT,
            highlightbackground=AIDRAX_EDGE,
            highlightcolor=AIDRAX_EDGE,
            highlightthickness=1,
            bd=0,
            padx=14,
            pady=8,
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=18, pady=(0, 18))
        tk.Label(
            status_bar,
            text="STATUS",
            bg=AIDRAX_SURFACE_ALT,
            fg=AIDRAX_PRIMARY,
            font=("JetBrains Mono", 9, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            status_bar,
            textvariable=self.status_var,
            bg=AIDRAX_SURFACE_ALT,
            fg=AIDRAX_TEXT,
            font=("Space Grotesk", 10),
        ).pack(side=tk.LEFT, padx=(10, 0))

        self.root.after(120, self._set_initial_split_layout)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.signal_var.set(f"Signal: {text}")

    def _update_metrics(self, rows: list[dict]) -> None:
        self.prompt_count_var.set(str(len(rows)))
        self.active_count_var.set(str(sum(1 for row in rows if row.get("is_active", 1))))
        self.favorite_count_var.set(str(sum(1 for row in rows if row.get("is_favorite"))))
        self.category_count_var.set(str(max(len(self.category_by_name) - 1, 0)))

    def _load_categories(self) -> None:
        categories = db.list_categories()
        self.category_by_name = {"(Keine)": None}
        for cat in categories:
            self.category_by_name[cat["name"]] = cat["id"]
        self.category_combo["values"] = list(self.category_by_name.keys())
        if self.category_var.get() not in self.category_by_name:
            self.category_var.set("(Keine)")
        self.category_count_var.set(str(len(categories)))

    def _refresh_prompt_list(self, keep_status: bool = False) -> None:
        search = self.search_var.get().strip()
        rows = db.list_prompts(search=search)
        self.prompt_map = {int(row["id"]): row for row in rows}

        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in rows:
            pid = int(row["id"])
            tags: tuple[str, ...] = ()
            if row.get("is_favorite"):
                tags += ("favorite",)
            if not row.get("is_active", 1):
                tags += ("inactive",)
            self.tree.insert(
                "",
                tk.END,
                iid=str(pid),
                tags=tags,
                values=(
                    pid,
                    row.get("title") or "",
                    row.get("category_name") or "—",
                    "◆" if row.get("is_favorite") else "",
                    row.get("use_count") or 0,
                ),
            )

        self._update_metrics(rows)
        if not keep_status:
            self._set_status(f"{len(rows)} Prompt(s) geladen")

    def _on_tree_select(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return

        prompt_id = int(selected[0])
        prompt = db.get_prompt(prompt_id)
        if not prompt:
            return

        self.selected_prompt_id = prompt_id
        self._fill_form(prompt)

    def _fill_form(self, prompt: dict) -> None:
        self.title_var.set(prompt.get("title") or "")

        cat_name = prompt.get("category_name") or "(Keine)"
        if cat_name not in self.category_by_name:
            self._load_categories()
        self.category_var.set(cat_name if cat_name in self.category_by_name else "(Keine)")

        try:
            tags = json.loads(prompt.get("tags") or "[]")
        except json.JSONDecodeError:
            tags = []
        self.tags_var.set(", ".join(tags))

        self.favorite_var.set(bool(prompt.get("is_favorite")))

        self.description_text.delete("1.0", tk.END)
        self.description_text.insert("1.0", prompt.get("description") or "")

        self.content_text.delete("1.0", tk.END)
        self.content_text.insert("1.0", prompt.get("content") or "")
        self._clear_ai_response()

        self._set_status(f"Prompt #{prompt.get('id')} geladen")

    def _new_prompt(self) -> None:
        self.selected_prompt_id = None
        self.title_var.set("")
        self.category_var.set("(Keine)")
        self.tags_var.set("")
        self.favorite_var.set(False)
        self.description_text.delete("1.0", tk.END)
        self.content_text.delete("1.0", tk.END)
        self._clear_ai_response()
        self._set_status("Neuer Prompt bereit")

    def _collect_form(self) -> tuple[str, str, str, int | None, list[str], bool]:
        title = self.title_var.get().strip()
        description = self.description_text.get("1.0", tk.END).strip()
        content = self.content_text.get("1.0", tk.END).strip()
        category_id = self.category_by_name.get(self.category_var.get(), None)
        tags = [tag.strip().lower() for tag in self.tags_var.get().split(",") if tag.strip()]
        is_favorite = bool(self.favorite_var.get())
        return title, description, content, category_id, tags, is_favorite

    def _save_prompt(self) -> None:
        title, description, content, category_id, tags, is_favorite = self._collect_form()

        if not title:
            messagebox.showerror("Fehler", "Titel darf nicht leer sein.")
            return
        if not content:
            messagebox.showerror("Fehler", "Prompt-Inhalt darf nicht leer sein.")
            return

        if self.selected_prompt_id is None:
            prompt_id = db.create_prompt(
                title=title,
                content=content,
                description=description,
                category_id=category_id,
                tags=tags,
                is_favorite=is_favorite,
            )
            self.selected_prompt_id = prompt_id
            self._set_status(f"Prompt #{prompt_id} erstellt")
        else:
            db.update_prompt(
                self.selected_prompt_id,
                title=title,
                content=content,
                description=description,
                category_id=category_id,
                tags=tags,
                is_favorite=is_favorite,
            )
            self._set_status(f"Prompt #{self.selected_prompt_id} gespeichert")

        self._refresh_prompt_list(keep_status=True)
        if self.selected_prompt_id is not None:
            prompt_iid = str(self.selected_prompt_id)
            if self.tree.exists(prompt_iid):
                self.tree.selection_set(prompt_iid)
                self.tree.see(prompt_iid)

    def _delete_prompt(self) -> None:
        if self.selected_prompt_id is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Prompt auswaehlen.")
            return

        if not messagebox.askyesno("Loeschen", f"Prompt #{self.selected_prompt_id} wirklich loeschen?"):
            return

        db.delete_prompt(self.selected_prompt_id)
        deleted_id = self.selected_prompt_id
        self._new_prompt()
        self._refresh_prompt_list(keep_status=True)
        self._set_status(f"Prompt #{deleted_id} geloescht")

    def _set_response(self, text: str) -> None:
        self.response_text.configure(state=tk.NORMAL)
        self.response_text.delete("1.0", tk.END)
        self.response_text.insert("1.0", text)
        self.response_text.configure(state=tk.DISABLED)

    def _clear_ai_response(self) -> None:
        self.last_generated_prompt = ""
        self.apply_btn.configure(state=tk.DISABLED)
        self._set_response("")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for button in self.action_buttons:
            button.configure(state=state)
        if busy or not self.last_generated_prompt:
            self.apply_btn.configure(state=tk.DISABLED)
        else:
            self.apply_btn.configure(state=tk.NORMAL)

    def _build_generation_brief(self, title: str, description: str, content: str) -> str:
        parts = [
            "Erstelle oder verbessere auf Basis dieser Angaben einen direkt nutzbaren Prompt.",
        ]
        if title:
            parts.append(f"Titel: {title}")
        if description:
            parts.append(f"Beschreibung: {description}")
        parts.append("Anforderung oder Entwurf:")
        parts.append(content)
        return "\n\n".join(parts)

    def _run_ai_request(
        self,
        *,
        prompt_content: str,
        system_prompt: str,
        prompt_title: str | None,
        status_text: str,
        done_mode: str,
        increment_use_count: bool = False,
    ) -> None:
        if self.busy:
            return

        self._set_busy(True)
        self._set_status(status_text)
        self._set_response("Bitte warten...")

        selected_id = self.selected_prompt_id

        def worker() -> None:
            try:
                response = ai.chat(
                    prompt_content=prompt_content,
                    system_prompt=system_prompt,
                    model=None,
                    stream=False,
                    prompt_id=selected_id,
                    prompt_title=prompt_title,
                )
                if increment_use_count and selected_id is not None:
                    db.increment_use_count(selected_id)
                self.root.after(0, lambda: self._on_ai_done(response, None, done_mode))
            except Exception as exc:
                self.root.after(0, lambda: self._on_ai_done("", str(exc), done_mode))

        threading.Thread(target=worker, daemon=True).start()

    def _add_category(self) -> None:
        name = simpledialog.askstring("Neue Kategorie", "Kategoriename:", parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return

        try:
            db.create_category(name)
        except Exception as exc:
            messagebox.showerror("Fehler", f"Kategorie konnte nicht erstellt werden:\n{exc}")
            return

        self._load_categories()
        self.category_var.set(name)
        self._set_status(f"Kategorie '{name}' erstellt")

    def _open_config_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("AIDRAX Konfiguration")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=AIDRAX_BG)

        card, body = self._make_card(
            dialog,
            title="CONFIG",
            subtitle="OpenAI / lokale API-Endpunkte",
            accent=AIDRAX_WARN,
            body_bg=AIDRAX_SURFACE,
        )
        card.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        api_key_var = tk.StringVar(value=db.get_config("openai_api_key"))
        model_var = tk.StringVar(value=db.get_config("default_model") or "gpt-4o-mini")
        url_var = tk.StringVar(value=db.get_config("api_base_url") or "https://api.openai.com/v1")

        for row_index, (label_text, var, secret) in enumerate(
            [
                ("API-Key", api_key_var, True),
                ("Modell", model_var, False),
                ("API-URL", url_var, False),
            ]
        ):
            row = tk.Frame(body, bg=AIDRAX_SURFACE)
            row.pack(fill=tk.X, pady=(0, 10))
            tk.Label(
                row,
                text=label_text,
                bg=AIDRAX_SURFACE,
                fg=AIDRAX_PRIMARY,
                font=("JetBrains Mono", 10, "bold"),
                width=12,
                anchor="w",
            ).pack(side=tk.LEFT)
            entry = tk.Entry(row, textvariable=var, show="*" if secret else "")
            self._style_entry(entry)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        button_row = tk.Frame(body, bg=AIDRAX_SURFACE)
        button_row.pack(fill=tk.X, pady=(8, 0))

        def save_config() -> None:
            db.set_config("openai_api_key", api_key_var.get().strip())
            db.set_config("default_model", model_var.get().strip())
            db.set_config("api_base_url", url_var.get().strip())
            self._set_status("Konfiguration gespeichert")
            dialog.destroy()

        cancel_btn = tk.Button(
            button_row,
            text="Abbrechen",
            command=dialog.destroy,
            bg=AIDRAX_SURFACE_ALT,
            fg=AIDRAX_MUTED,
            activebackground=AIDRAX_EDGE,
            activeforeground=AIDRAX_TEXT,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=8,
            font=("Space Grotesk", 10, "bold"),
        )
        cancel_btn.pack(side=tk.RIGHT)

        save_btn = tk.Button(
            button_row,
            text="Speichern",
            command=save_config,
            bg=AIDRAX_SURFACE_ALT,
            fg=AIDRAX_OK,
            activebackground=AIDRAX_OK,
            activeforeground=AIDRAX_BG,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=8,
            font=("Space Grotesk", 10, "bold"),
            highlightbackground=AIDRAX_OK,
            highlightcolor=AIDRAX_OK,
            highlightthickness=1,
        )
        save_btn.pack(side=tk.RIGHT, padx=(0, 8))

    def _generate_prompt_with_ai(self) -> None:
        title, description, content, _category_id, _tags, _favorite = self._collect_form()
        if not content:
            messagebox.showerror("Fehler", "Bitte zuerst den Prompt-Inhalt oder die Anforderung beschreiben.")
            return

        system_prompt = (
            "Du bist ein erfahrener Prompt-Engineer. "
            "Erstelle aus Anforderungen oder einem vorhandenen Entwurf genau einen finalen, direkt nutzbaren Prompt. "
            "Gib nur den finalen Prompttext zurück, ohne Einleitung, ohne Erklärungen, ohne Markdown-Codeblock. "
            "Behalte die Sprache der Anforderung bei, wenn nichts anderes verlangt wird. "
            "Wenn hilfreich, strukturiere den Prompt klar mit Rolle, Ziel, Kontext, Schritten, Regeln und Ausgabeformat. "
            "Wenn Variablen sinnvoll sind, verwende gut benannte Platzhalter im Format {{name}}."
        )
        self.last_generated_prompt = ""
        self._run_ai_request(
            prompt_content=self._build_generation_brief(title, description, content),
            system_prompt=system_prompt,
            prompt_title=(title or "Prompt Generator") + " (generate)",
            status_text="Erzeuge Prompt mit KI...",
            done_mode="generate",
        )

    def _send_to_ai(self) -> None:
        title, _description, content, _category_id, _tags, _favorite = self._collect_form()
        if not content:
            messagebox.showerror("Fehler", "Prompt-Inhalt darf nicht leer sein.")
            return

        self._run_ai_request(
            prompt_content=content,
            system_prompt=(
                "Du testest einen gespeicherten Prompt. "
                "Behandle den Benutzertext als Prompt, fuehre ihn so direkt wie moeglich aus "
                "und antworte mit dem Ergebnis statt mit einer Meta-Erklaerung."
            ),
            prompt_title=(title or "Prompt") + " (test)",
            status_text="Teste Prompt mit KI...",
            done_mode="test",
            increment_use_count=True,
        )

    def _apply_ai_response_to_content(self) -> None:
        generated = self.last_generated_prompt.strip()
        if not generated:
            return

        current = self.content_text.get("1.0", tk.END).strip()
        if current and current != generated:
            should_replace = messagebox.askyesno(
                "Prompt uebernehmen",
                "Den aktuellen Inhalt durch den erzeugten Prompt ersetzen?",
            )
            if not should_replace:
                return

        self.content_text.delete("1.0", tk.END)
        self.content_text.insert("1.0", generated)
        self._set_status("Erzeugten Prompt in den Inhalt uebernommen")

    def _on_ai_done(self, response: str, error: str | None, mode: str) -> None:
        self._set_busy(False)

        if error:
            if mode == "generate":
                self.last_generated_prompt = ""
            self._set_response("")
            self._set_status(f"Fehler: {error}")
            messagebox.showerror("KI-Fehler", error)
            return

        self._set_response(response)
        if mode == "generate":
            self.last_generated_prompt = response.strip()
            self.apply_btn.configure(state=tk.NORMAL if self.last_generated_prompt else tk.DISABLED)
            self._set_status("Prompt-Vorschlag erhalten")
        else:
            self.last_generated_prompt = ""
            self.apply_btn.configure(state=tk.DISABLED)
            self._set_status("Prompt-Testantwort erhalten")
        self._refresh_prompt_list(keep_status=True)


def main() -> None:
    root = tk.Tk()
    PromptManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
