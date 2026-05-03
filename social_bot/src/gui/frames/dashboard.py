# src/gui/frames/dashboard.py
import customtkinter as ctk
from src.gui.theme import COLORS
from src.gui.browser_preview import BrowserPreview


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()

    # ------------------------------------------------------------------
    # Hlavní layout — grid na self (NIKDY pack na self)
    # ------------------------------------------------------------------
    def setup_ui(self):
        # self používá výhradně grid
        self.grid_columnconfigure(0, weight=2, minsize=340)  # levý panel
        self.grid_columnconfigure(1, weight=3)               # pravý panel (náhled + log)
        self.grid_rowconfigure(0, weight=1)

        # ── Levý sloupec — scrollovatelný ────────────────────────────
        left_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        left_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_left(left_scroll)

        # ── Pravý sloupec ────────────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=3)   # náhled — větší část
        right.grid_rowconfigure(2, weight=1)   # log — menší část
        right.grid_columnconfigure(0, weight=1)

        # Náhled prohlížeče
        self.browser_preview = BrowserPreview(right)
        self.browser_preview.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        # Oddělovač
        ctk.CTkFrame(right, height=1, fg_color=COLORS["border"]).grid(
            row=1, column=0, sticky="ew", pady=(0, 4))

        # Log panel
        log_header = ctk.CTkFrame(right, fg_color="transparent")
        log_header.grid(row=2, column=0, sticky="nsew")
        log_header.grid_rowconfigure(1, weight=1)
        log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_header, text="LOG", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).grid(
            row=0, column=0, sticky="w", pady=(0, 4))

        self.log_box = ctk.CTkTextbox(
            log_header, fg_color="#121416", text_color="#00ff41",
            font=("Consolas", 12), corner_radius=4,
            border_color=COLORS["border"], border_width=1
        )
        self.log_box.grid(row=1, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Levý sloupec — původní obsah beze změny (pack uvnitř left_scroll)
    # ------------------------------------------------------------------
    def _build_left(self, parent):
        """Celý původní obsah setup_ui — parent je CTkScrollableFrame."""

        # Nadpis
        ctk.CTkLabel(parent, text="Ovládací panel", font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["text_main"]).pack(anchor="w", pady=(0, 20))

        # 1. INPUTY
        input_container = ctk.CTkFrame(parent, fg_color="transparent")
        input_container.pack(fill="x", pady=(0, 20))

        # Identita
        ctk.CTkLabel(input_container, text="IDENTITA BOTA",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            input_container, variable=self.user_var, height=35,
            font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            button_color=COLORS["panel_bg"],
            dropdown_hover_color=COLORS["primary"],
            text_color=COLORS["text_main"], state="readonly"
        )
        self.user_combo.pack(fill="x", pady=(0, 15))
        self.refresh_users_combo()

        # Cíle
        ctk.CTkLabel(input_container, text="CÍLOVÉ ÚČTY (odděl čárkou)",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.target_var = ctk.StringVar()
        self.target_entry = ctk.CTkEntry(
            input_container, textvariable=self.target_var, height=40,
            font=("Segoe UI", 14),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            text_color=COLORS["text_main"],
            placeholder_text="např. elonmusk, taylorswift13"
        )
        self.target_entry.pack(fill="x", pady=(0, 15))

        # Limity
        limits_container = ctk.CTkFrame(input_container, fg_color="transparent")
        limits_container.pack(fill="x")
        limits_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        limit_frame.grid(row=0, column=0, sticky="nw", padx=(0, 5))
        ctk.CTkLabel(limit_frame, text="PŘÍSPĚVKY", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        limit_inner = ctk.CTkFrame(limit_frame, fg_color="transparent")
        limit_inner.pack(fill="x")
        self.scrape_all_var = ctk.BooleanVar(value=False)
        self.chk_all = ctk.CTkCheckBox(
            limit_inner, text="Vše", variable=self.scrape_all_var,
            command=self.toggle_limit_entry,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            border_color=COLORS["border"], font=("Segoe UI", 13), width=45
        )
        self.chk_all.pack(side="left", padx=(0, 5))
        self.limit_var = ctk.StringVar(value="10")
        self.limit_entry = ctk.CTkEntry(
            limit_inner, textvariable=self.limit_var, width=50, height=35,
            font=("Segoe UI", 13), border_color=COLORS["border"],
            fg_color=COLORS["panel_bg"], text_color=COLORS["text_main"]
        )
        self.limit_entry.pack(side="left")

        comm_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        comm_limit_frame.grid(row=0, column=1, sticky="nw", padx=5)
        ctk.CTkLabel(comm_limit_frame, text="KOMENTÁŘE",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.comments_limit_var = ctk.StringVar(value="50")
        self.comments_limit_entry = ctk.CTkEntry(
            comm_limit_frame, textvariable=self.comments_limit_var,
            width=70, height=35, font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            text_color=COLORS["text_main"]
        )
        self.comments_limit_entry.pack(side="left")

        fol_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        fol_limit_frame.grid(row=0, column=2, sticky="nw", padx=5)
        ctk.CTkLabel(fol_limit_frame, text="SLEDUJÍCÍ",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.followers_limit_var = ctk.StringVar(value="50")
        self.followers_limit_entry = ctk.CTkEntry(
            fol_limit_frame, textvariable=self.followers_limit_var,
            width=70, height=35, font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            text_color=COLORS["text_main"]
        )
        self.followers_limit_entry.pack(side="left")

        following_limit_frame = ctk.CTkFrame(limits_container, fg_color="transparent")
        following_limit_frame.grid(row=0, column=3, sticky="nw", padx=(5, 0))
        ctk.CTkLabel(following_limit_frame, text="SLEDUJE",
                     font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.following_limit_var = ctk.StringVar(value="50")
        self.following_limit_entry = ctk.CTkEntry(
            following_limit_frame, textvariable=self.following_limit_var,
            width=70, height=35, font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"],
            text_color=COLORS["text_main"]
        )
        self.following_limit_entry.pack(side="left")

        # 2. AKCE
        ctk.CTkLabel(parent, text="AKCE", font=("Segoe UI", 11, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(20, 5))
        actions_frame = ctk.CTkFrame(parent, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 20))
        actions_frame.grid_columnconfigure((0, 1), weight=1)

        self.create_action_btn(actions_frame, "Instagram Login", 0, 0,
                               lambda: self.controller.start_thread("instagram", "login"),
                               outline=True)
        self.create_action_btn(actions_frame, "Těžit Instagram", 0, 1,
                               lambda: self.controller.start_thread("instagram", "scrape"))
        self.create_action_btn(actions_frame, "X Login", 1, 0,
                               lambda: self.controller.start_thread("X", "login"),
                               outline=True)
        self.create_action_btn(actions_frame, "Těžit X", 1, 1,
                               lambda: self.controller.start_thread("X", "scrape"))
        self.create_action_btn(actions_frame, "Těžit YouTube", 2, 0,
                               lambda: self.controller.start_thread("youtube", "scrape"))

        btn_trend = ctk.CTkButton(
            actions_frame, text="Těžit Trendy (X)",
            command=lambda: self.controller.start_thread("X", "scrape_trending"),
            height=35, fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
            text_color=COLORS["text_main"], font=("Segoe UI", 13)
        )
        btn_trend.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        # 3. PO SCRAPU
        post_frame = ctk.CTkFrame(parent, fg_color=COLORS["panel_bg"],
                                  corner_radius=8, border_width=1,
                                  border_color=COLORS["border"])
        post_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(post_frame, text="PO SCRAPU", font=("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=12, pady=(8, 4))

        self.ocr_auto_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            post_frame,
            text="OCR obrázků  (Tesseract — zpomalí scraping)",
            variable=self.ocr_auto_var,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            border_color=COLORS["border"],
            font=("Segoe UI", 12),
            checkmark_color="white",
        ).pack(anchor="w", padx=12, pady=(0, 6))

        self.headless_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            post_frame,
            text="Pouze screencast  (bez viditelného okna prohlížeče)",
            variable=self.headless_var,
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            border_color=COLORS["border"],
            font=("Segoe UI", 12),
            checkmark_color="white",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # UKONČIT
        btn_stop = ctk.CTkButton(
            parent, text="UKONČIT OPERACI",
            command=self.controller.stop_bot,
            fg_color=COLORS["danger"], hover_color="#8a1212",
            height=40, font=("Segoe UI", 13, "bold")
        )
        btn_stop.pack(fill="x", pady=(10, 0))

    # ------------------------------------------------------------------
    # Pomocné metody — beze změny
    # ------------------------------------------------------------------
    def toggle_limit_entry(self):
        if self.scrape_all_var.get():
            self.limit_entry.configure(state="disabled",
                                       fg_color=COLORS["sidebar_bg"])
        else:
            self.limit_entry.configure(state="normal",
                                       fg_color=COLORS["panel_bg"])

    def create_action_btn(self, parent, text, r, c, cmd, outline=False):
        if outline:
            fg, border, text_c, hover = (
                "transparent", 1, COLORS["primary"], COLORS["panel_bg"])
        else:
            fg, border, text_c, hover = (
                COLORS["primary"], 0, "white", COLORS["primary_hover"])
        btn = ctk.CTkButton(
            parent, text=text, command=cmd, height=35,
            fg_color=fg, text_color=text_c,
            border_width=border, border_color=COLORS["primary"],
            hover_color=hover, font=("Segoe UI", 13, "bold")
        )
        btn.grid(row=r, column=c, sticky="ew", padx=5, pady=5)

    def refresh_users_combo(self):
        if self.controller.users_map:
            users = list(self.controller.users_map.keys())
            self.user_combo.configure(values=users)
            self.user_combo.set(users[0])