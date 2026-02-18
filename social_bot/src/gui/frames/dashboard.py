# src/gui/frames/dashboard.py
import customtkinter as ctk
from src.gui.theme import COLORS

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller # Reference na hlavní App
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        
        # Nadpis
        ctk.CTkLabel(self, text="Ovládací panel", font=("Segoe UI", 24, "bold"), 
                     text_color=COLORS["text_main"]).pack(anchor="w", pady=(0, 20))

        # 1. INPUTY
        input_container = ctk.CTkFrame(self, fg_color="transparent")
        input_container.pack(fill="x", pady=(0, 20))
        
        # Identita
        ctk.CTkLabel(input_container, text="IDENTITA BOTA", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            input_container, variable=self.user_var, height=35, font=("Segoe UI", 13),
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"], 
            button_color=COLORS["panel_bg"], dropdown_hover_color=COLORS["primary"],
            text_color=COLORS["text_main"], state="readonly"
        )
        self.user_combo.pack(fill="x", pady=(0, 15))
        self.refresh_users_combo()

        # Cíle
        ctk.CTkLabel(input_container, text="CÍLOVÉ ÚČTY (odděl čárkou)", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.target_var = ctk.StringVar()
        self.target_entry = ctk.CTkEntry(
            input_container, textvariable=self.target_var, height=40, font=("Segoe UI", 14), 
            border_color=COLORS["border"], fg_color=COLORS["panel_bg"], 
            text_color=COLORS["text_main"], placeholder_text="např. elonmusk, taylorswift13"
        )
        self.target_entry.pack(fill="x", pady=(0, 15))

        # Limity
        limit_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        limit_frame.pack(fill="x")
        ctk.CTkLabel(limit_frame, text="LIMIT PŘÍSPĚVKŮ", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        
        limit_inner = ctk.CTkFrame(limit_frame, fg_color="transparent")
        limit_inner.pack(fill="x")
        
        self.scrape_all_var = ctk.BooleanVar(value=False)
        self.chk_all = ctk.CTkCheckBox(
            limit_inner, text="Stáhnout vše", variable=self.scrape_all_var, 
            command=self.toggle_limit_entry, fg_color=COLORS["primary"], 
            hover_color=COLORS["primary_hover"], border_color=COLORS["border"], font=("Segoe UI", 13)
        )
        self.chk_all.pack(side="left", padx=(0, 20))
        
        self.limit_var = ctk.StringVar(value="10")
        self.limit_entry = ctk.CTkEntry(
            limit_inner, textvariable=self.limit_var, width=100, height=35, 
            font=("Segoe UI", 13), border_color=COLORS["border"], 
            fg_color=COLORS["panel_bg"], text_color=COLORS["text_main"]
        )
        self.limit_entry.pack(side="left")

        # 2. AKCE
        ctk.CTkLabel(self, text="AKCE", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(10, 5))
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 20))
        actions_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.create_action_btn(actions_frame, "Instagram Login", 0, 0, lambda: self.controller.start_thread("instagram", "login"), outline=True)
        self.create_action_btn(actions_frame, "Těžit Instagram", 0, 1, lambda: self.controller.start_thread("instagram", "scrape"))
        self.create_action_btn(actions_frame, "X Login", 1, 0, lambda: self.controller.start_thread("X", "login"), outline=True)
        self.create_action_btn(actions_frame, "Těžit X", 1, 1, lambda: self.controller.start_thread("X", "scrape"))
        
        btn_trend = ctk.CTkButton(
            actions_frame, text="Těžit Trendy (X)", command=lambda: self.controller.start_thread("X", "scrape_trending"), 
            height=35, fg_color=COLORS["panel_bg"], hover_color=COLORS["border"], 
            text_color=COLORS["text_main"], font=("Segoe UI", 13)
        )
        btn_trend.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        btn_stop = ctk.CTkButton(
            self, text="UKONČIT OPERACI", command=self.controller.stop_bot, 
            fg_color=COLORS["danger"], hover_color="#8a1212", height=40, font=("Segoe UI", 13, "bold")
        )
        btn_stop.pack(fill="x", pady=(10, 20))

        # 3. LOG
        ctk.CTkLabel(self, text="LOG", font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.log_box = ctk.CTkTextbox(
            self, fg_color="#121416", text_color="#00ff41", font=("Consolas", 12), 
            corner_radius=4, border_color=COLORS["border"], border_width=1
        )
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def toggle_limit_entry(self):
        if self.scrape_all_var.get(): 
            self.limit_entry.configure(state="disabled", fg_color=COLORS["sidebar_bg"])
        else: 
            self.limit_entry.configure(state="normal", fg_color=COLORS["panel_bg"])

    def create_action_btn(self, parent, text, r, c, cmd, outline=False):
        if outline: fg, border, text_c, hover = "transparent", 1, COLORS["primary"], COLORS["panel_bg"]
        else: fg, border, text_c, hover = COLORS["primary"], 0, "white", COLORS["primary_hover"]
        
        btn = ctk.CTkButton(
            parent, text=text, command=cmd, height=35, fg_color=fg, 
            text_color=text_c, border_width=border, border_color=COLORS["primary"], 
            hover_color=hover, font=("Segoe UI", 13, "bold")
        )
        btn.grid(row=r, column=c, sticky="ew", padx=5, pady=5)

    def refresh_users_combo(self):
        if self.controller.users_map:
            users = list(self.controller.users_map.keys())
            self.user_combo.configure(values=users)
            self.user_combo.set(users[0])