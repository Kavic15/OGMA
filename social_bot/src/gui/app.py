import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk
import threading
import json
import os
import time
import sys
import sqlite3
import requests
from io import BytesIO
from PIL import Image
from pathlib import Path
from datetime import datetime
from src.bots.instagram.bot import InstagramBot
from src.bots.x.bot import XBot

# --- BITWARDEN THEME PALETTE (Dark Mode) ---
c_sidebar_bg = "#171b1e"       
c_main_bg = "#222529"          
c_panel_bg = "#2c3035"         
c_primary = "#175DDC"          
c_primary_hover = "#144eb8"    
c_text_main = "#ffffff"        
c_text_dim = "#9eaab5"         
c_border = "#3b4047"           
c_danger = "#ab1818"           

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class PrintLogger:
    def __init__(self, textbox, tk_app):
        self.textbox = textbox
        self.tk_app = tk_app

    def write(self, text):
        self.tk_app.after(0, self._insert_text, text)

    def _insert_text(self, text):
        self.textbox.configure(state="normal")
        
        # Pokud text obsahuje obsah (není to jen prázdný řádek/odřádkování), přidej čas
        if text.strip():
            current_time = datetime.now().strftime("[%H:%M:%S]")
            self.textbox.insert(tk.END, f"{current_time} {text}")
        else:
            self.textbox.insert(tk.END, text)
            
        self.textbox.see(tk.END)
        self.textbox.configure(state="disabled")

    def flush(self):
        pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # --- ZÁKLADNÍ KONFIGURACE ---
        self.title("Ogma 0.0") 
        self.geometry("1200x800")
        self.minsize(1000, 700)
        
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.data_path = project_root / 'data' / 'users.json'
        self.db_path = project_root / 'data' / 'osint.db'
        
        icon_path = project_root / 'src' / 'gui' / 'ogma_ai_logo.ico'
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        self.users_map = {}
        self.image_cache = {} # Cache pro obrázky
        self.load_users()
        self.current_bot = None 
        self.is_running = False
        self.all_profiles_data = []

        # --- HLAVNÍ LAYOUT (2 Sloupce) ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. SIDEBAR
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=c_sidebar_bg)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # 2. MAIN CONTENT
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color=c_main_bg)
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # FRAMES PRO OBRAZOVKY
        self.frame_dashboard = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.frame_profiles = ctk.CTkFrame(self.main_area, fg_color="transparent") 
        self.frame_database = ctk.CTkFrame(self.main_area, fg_color="transparent")

        self.setup_dashboard()
        self.setup_profiles_view()
        self.setup_database()

        # Logger
        sys.stdout = PrintLogger(self.log_box, self)
        sys.stderr = PrintLogger(self.log_box, self)

        self.show_frame("dashboard")

    # =========================================================================
    # SIDEBAR
    # =========================================================================
    def setup_sidebar(self):
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(25, 20), padx=20, fill="x")
        
        ctk.CTkLabel(logo_frame, text="Ogma 0.0", font=("Segoe UI", 22, "bold"), text_color=c_text_main, anchor="w").pack(fill="x")
        ctk.CTkLabel(logo_frame, text="OSINT Automation Tool", font=("Segoe UI", 12), text_color=c_text_dim, anchor="w").pack(fill="x")

        ctk.CTkFrame(self.sidebar, height=1, fg_color=c_border).pack(fill="x", padx=0, pady=10)

        # MENU
        self.btn_nav_dash = self.create_nav_btn("Přehled (Dashboard)", "dashboard")
        self.btn_nav_prof = self.create_nav_btn("Scrapnuté Profily", "profiles") 
        self.btn_nav_db = self.create_nav_btn("Databáze (Vault)", "database")
        
        self.sidebar_spacer = ctk.CTkLabel(self.sidebar, text="", height=50)
        self.sidebar_spacer.pack(side="bottom")

        # STATUS LABEL
        self.status_label = ctk.CTkLabel(self.sidebar, text="● Připraveno", text_color="#2eb85c", font=("Segoe UI", 12))
        self.status_label.pack(side="bottom", pady=(5, 20), padx=20, anchor="w")

        # PROGRESS BAR
        self.progress_bar = ctk.CTkProgressBar(self.sidebar, width=200, height=8, corner_radius=4, progress_color=c_primary)
        self.progress_bar.set(0)

    def create_nav_btn(self, text, view_name):
        btn = ctk.CTkButton(
            self.sidebar, text=text, command=lambda: self.show_frame(view_name),
            fg_color="transparent", text_color=c_text_dim, hover_color=c_panel_bg,
            anchor="w", height=45, font=("Segoe UI", 14), corner_radius=4
        )
        btn.pack(fill="x", padx=10, pady=2)
        return btn

    def show_frame(self, name):
        # Reset barev
        self.btn_nav_dash.configure(fg_color="transparent", text_color=c_text_dim)
        self.btn_nav_prof.configure(fg_color="transparent", text_color=c_text_dim)
        self.btn_nav_db.configure(fg_color="transparent", text_color=c_text_dim)
        
        self.frame_dashboard.grid_forget()
        self.frame_profiles.grid_forget()
        self.frame_database.grid_forget()

        if name == "dashboard":
            self.frame_dashboard.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_dash.configure(fg_color=c_panel_bg, text_color=c_primary)
        elif name == "profiles":
            self.frame_profiles.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_prof.configure(fg_color=c_panel_bg, text_color=c_primary)
            self.refresh_profiles_view()
        elif name == "database":
            self.frame_database.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_db.configure(fg_color=c_panel_bg, text_color=c_primary)
            self.refresh_db()

    # =========================================================================
    # PROFILES VIEW (KARTY)
    # =========================================================================
    def setup_profiles_view(self):
        self.frame_profiles.grid_columnconfigure(0, weight=1)
        self.frame_profiles.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(self.frame_profiles, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        ctk.CTkLabel(top_bar, text="Nalezené Profily", font=("Segoe UI", 24, "bold"), text_color=c_text_main).pack(side="left")

        self.profile_search_var = ctk.StringVar()
        self.profile_search_var.trace("w", self.filter_profiles)
        
        search_entry = ctk.CTkEntry(
            top_bar, textvariable=self.profile_search_var, 
            width=300, height=35, corner_radius=20,
            placeholder_text="🔍 Hledat jméno nebo handle...",
            fg_color=c_panel_bg, border_color=c_border, text_color="white"
        )
        search_entry.pack(side="right")

        self.profiles_scroll = ctk.CTkScrollableFrame(self.frame_profiles, fg_color="transparent", corner_radius=0)
        self.profiles_scroll.grid(row=1, column=0, sticky="nsew")
        self.profiles_scroll.grid_columnconfigure(0, weight=1)

    def refresh_profiles_view(self):
        for widget in self.profiles_scroll.winfo_children(): widget.destroy()
        if not self.db_path.exists(): return
        try:
            conn = sqlite3.connect(str(self.db_path)); conn.row_factory = sqlite3.Row; cur = conn.cursor()
            # Načteme vše (*) abychom měli přístup k novým sloupcům (location, following_count atd.)
            try: 
                cur.execute("SELECT * FROM users ORDER BY last_scraped DESC")
            except sqlite3.OperationalError: 
                cur.execute("SELECT id, platform, username, display_name, bio, followers_count, profile_pic_url, last_scraped FROM users ORDER BY last_scraped DESC")
            
            self.all_profiles_data = [dict(row) for row in cur.fetchall()]; conn.close()
            self.filter_profiles()
        except Exception as e: print(f"[GUI ERROR] Nelze načíst profily: {e}")

    def filter_profiles(self, *args):
        query = self.profile_search_var.get().lower()
        for widget in self.profiles_scroll.winfo_children(): widget.destroy()
        for user in self.all_profiles_data:
            if query in (user['username'] or "").lower() or query in (user.get('display_name') or "").lower():
                self.create_profile_card(user)

    def create_profile_card(self, user):
        card = ctk.CTkFrame(self.profiles_scroll, fg_color=c_panel_bg, corner_radius=10, border_color=c_border, border_width=1)
        card.pack(fill="x", pady=5, padx=5)
        card.grid_columnconfigure(1, weight=1) 
        
        # 1. Avatar
        img_widget = ctk.CTkLabel(card, text="", width=80, height=80, corner_radius=10, fg_color="#444")
        if user.get('profile_pic_url'): 
            threading.Thread(target=self.load_image_async, args=(user.get('profile_pic_url'), img_widget), daemon=True).start()
        img_widget.grid(row=0, column=0, rowspan=4, padx=15, pady=15, sticky="n")

        # 2. Hlavička (Jméno + Verifikace + Handle)
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="nw", pady=(15, 0), padx=5)
        
        # Jméno
        name_text = user.get('display_name') or user['username']
        lbl_name = ctk.CTkLabel(info_frame, text=name_text, font=("Segoe UI", 16, "bold"), text_color="white")
        lbl_name.pack(side="left")

        # Verifikace
        if user.get('is_verified') == 1:
            lbl_ver = ctk.CTkLabel(info_frame, text="☑", font=("Segoe UI", 16), text_color="#1DA1F2")
            lbl_ver.pack(side="left", padx=(5, 0))

        # Handle a Platforma
        handle_text = f"@{user['username']} • {str(user.get('platform')).upper()}"
        ctk.CTkLabel(info_frame, text=handle_text, font=("Segoe UI", 13), text_color=c_text_dim).pack(side="left", padx=(10, 0))

        # 3. Statistiky (Followers / Following)
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.grid(row=1, column=1, sticky="nw", pady=(5, 5), padx=5)
        
        f_count = user.get('followers_count', 0)
        fol_count = user.get('following_count', 0)
        
        def fmt(num): return f"{num:,}".replace(",", " ") if num is not None else "0"

        # Followers
        ctk.CTkLabel(stats_frame, text=fmt(f_count), font=("Segoe UI", 13, "bold"), text_color=c_text_main).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Followers", font=("Segoe UI", 13), text_color=c_text_dim).pack(side="left", padx=(3, 15))
        
        # Following
        ctk.CTkLabel(stats_frame, text=fmt(fol_count), font=("Segoe UI", 13, "bold"), text_color=c_text_main).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Following", font=("Segoe UI", 13), text_color=c_text_dim).pack(side="left", padx=(3, 0))

        # 4. Bio
        bio = user.get('bio')
        if bio: 
            short_bio = (bio.replace('\n', ' ')[:90] + "...") if len(bio)>90 else bio
            ctk.CTkLabel(card, text=short_bio, font=("Segoe UI", 12, "italic"), text_color="#b0b0b0", anchor="w").grid(row=2, column=1, sticky="w", padx=5, pady=(0, 5))

        # 5. Metadata řádek (Lokace, Web, Joined)
        meta_frame = ctk.CTkFrame(card, fg_color="transparent")
        meta_frame.grid(row=3, column=1, sticky="nw", pady=(0, 15), padx=5)
        
        meta_items = []
        if user.get('location'): meta_items.append(f"📍 {user['location']}")
        if user.get('website'): meta_items.append(f"🔗 {user['website']}")
        if user.get('joined_date'): meta_items.append(f"📅 {user['joined_date']}")
        
        meta_text = "   ".join(meta_items)
        if meta_text:
            ctk.CTkLabel(meta_frame, text=meta_text, font=("Segoe UI", 11), text_color=c_text_dim).pack(side="left")

        # Datum stažení vpravo dole
        last_s = str(user.get('last_scraped')).split('T')[0] if user.get('last_scraped') else "?"
        ctk.CTkLabel(card, text=f"Upd: {last_s}", font=("Segoe UI", 10), text_color="#555").grid(row=3, column=1, sticky="e", padx=15, pady=(0, 15))

    def load_image_async(self, url, label_widget):
        if url in self.image_cache:
            ctk_image = self.image_cache[url]
        else:
            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    img_data = BytesIO(response.content)
                    pil_img = Image.open(img_data)
                    
                    # Center Crop na čtverec
                    width, height = pil_img.size
                    if width != height:
                        new_size = min(width, height)
                        left = (width - new_size) / 2
                        top = (height - new_size) / 2
                        right = (width + new_size) / 2
                        bottom = (height + new_size) / 2
                        pil_img = pil_img.crop((left, top, right, bottom))
                    
                    pil_img = pil_img.resize((80, 80), Image.Resampling.LANCZOS)
                    ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(80, 80))
                    self.image_cache[url] = ctk_image
                else:
                    return
            except:
                return

        self.after(0, lambda: label_widget.configure(image=ctk_image, text="", fg_color="transparent"))

    # =========================================================================
    # DASHBOARD & LOGIC
    # =========================================================================
    def setup_dashboard(self):
        self.frame_dashboard.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.frame_dashboard, text="Ovládací panel", font=("Segoe UI", 24, "bold"), text_color=c_text_main).pack(anchor="w", pady=(0, 20))

        input_container = ctk.CTkFrame(self.frame_dashboard, fg_color="transparent")
        input_container.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(input_container, text="IDENTITA BOTA", font=("Segoe UI", 11, "bold"), text_color=c_text_dim).pack(anchor="w", pady=(0, 5))
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(input_container, variable=self.user_var, height=35, font=("Segoe UI", 13), border_color=c_border, fg_color=c_panel_bg, button_color=c_panel_bg, dropdown_hover_color=c_primary, text_color=c_text_main, state="readonly")
        if self.users_map: self.user_combo.set(list(self.users_map.keys())[0])
        self.user_combo.configure(values=list(self.users_map.keys()))
        self.user_combo.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(input_container, text="CÍLOVÉ ÚČTY (odděl čárkou)", font=("Segoe UI", 11, "bold"), text_color=c_text_dim).pack(anchor="w", pady=(0, 5))
        self.target_var = ctk.StringVar()
        self.target_entry = ctk.CTkEntry(
            input_container, textvariable=self.target_var, height=40, font=("Segoe UI", 14), 
            border_color=c_border, fg_color=c_panel_bg, text_color=c_text_main, placeholder_text="např. elonmusk, taylorswift13, nasa"
        )
        self.target_entry.pack(fill="x", pady=(0, 15))

        limit_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        limit_frame.pack(fill="x")
        ctk.CTkLabel(limit_frame, text="LIMIT PŘÍSPĚVKŮ (PRO KAŽDÝ PROFIL)", font=("Segoe UI", 11, "bold"), text_color=c_text_dim).pack(anchor="w", pady=(0, 5))
        limit_inner = ctk.CTkFrame(limit_frame, fg_color="transparent")
        limit_inner.pack(fill="x")
        self.scrape_all_var = ctk.BooleanVar(value=False)
        self.chk_all = ctk.CTkCheckBox(limit_inner, text="Stáhnout vše", variable=self.scrape_all_var, command=self.toggle_limit_entry, fg_color=c_primary, hover_color=c_primary_hover, border_color=c_border, font=("Segoe UI", 13))
        self.chk_all.pack(side="left", padx=(0, 20))
        self.limit_var = ctk.StringVar(value="10")
        self.limit_entry = ctk.CTkEntry(limit_inner, textvariable=self.limit_var, width=100, height=35, font=("Segoe UI", 13), border_color=c_border, fg_color=c_panel_bg, text_color=c_text_main)
        self.limit_entry.pack(side="left")

        ctk.CTkLabel(self.frame_dashboard, text="AKCE", font=("Segoe UI", 11, "bold"), text_color=c_text_dim).pack(anchor="w", pady=(10, 5))
        actions_frame = ctk.CTkFrame(self.frame_dashboard, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 20))
        actions_frame.grid_columnconfigure((0, 1), weight=1)
        self.btn_ig_login = self.create_action_btn(actions_frame, "Instagram Login", 0, 0, lambda: self.start_thread("instagram", "login"), outline=True)
        self.btn_ig_scrape = self.create_action_btn(actions_frame, "Těžit Instagram", 0, 1, lambda: self.start_thread("instagram", "scrape"))
        self.btn_x_login = self.create_action_btn(actions_frame, "X Login", 1, 0, lambda: self.start_thread("X", "login"), outline=True)
        self.btn_x_scrape = self.create_action_btn(actions_frame, "Těžit X", 1, 1, lambda: self.start_thread("X", "scrape"))
        self.btn_trend = ctk.CTkButton(actions_frame, text="Těžit Trendy (X)", command=lambda: self.start_thread("X", "scrape_trending"), height=35, fg_color=c_panel_bg, hover_color=c_border, text_color=c_text_main, font=("Segoe UI", 13))
        self.btn_trend.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.btn_stop = ctk.CTkButton(self.frame_dashboard, text="UKONČIT OPERACI", command=self.stop_bot, fg_color=c_danger, hover_color="#8a1212", height=40, font=("Segoe UI", 13, "bold"))
        self.btn_stop.pack(fill="x", pady=(10, 20))

        ctk.CTkLabel(self.frame_dashboard, text="LOG", font=("Segoe UI", 11, "bold"), text_color=c_text_dim).pack(anchor="w", pady=(0, 5))
        self.log_box = ctk.CTkTextbox(self.frame_dashboard, fg_color="#121416", text_color="#00ff41", font=("Consolas", 12), corner_radius=4, border_color=c_border, border_width=1)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def toggle_limit_entry(self):
        if self.scrape_all_var.get(): self.limit_entry.configure(state="disabled", fg_color=c_sidebar_bg)
        else: self.limit_entry.configure(state="normal", fg_color=c_panel_bg)

    def create_action_btn(self, parent, text, r, c, cmd, outline=False):
        if outline: fg, border, text_c, hover = "transparent", 1, c_primary, c_panel_bg
        else: fg, border, text_c, hover = c_primary, 0, "white", c_primary_hover
        btn = ctk.CTkButton(parent, text=text, command=cmd, height=35, fg_color=fg, text_color=text_c, border_width=border, border_color=c_primary, hover_color=hover, font=("Segoe UI", 13, "bold"))
        btn.grid(row=r, column=c, sticky="ew", padx=5, pady=5)
        return btn

    def setup_database(self):
        header = ctk.CTkFrame(self.frame_database, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header, text="Uložená data", font=("Segoe UI", 24, "bold"), text_color=c_text_main).pack(side="left")
        ctk.CTkButton(header, text="Obnovit", width=80, height=30, fg_color=c_panel_bg, hover_color=c_border, text_color=c_text_main, command=self.refresh_db).pack(side="right")
        self.tab_db = ctk.CTkTabview(self.frame_database, fg_color="transparent", segmented_button_fg_color=c_panel_bg, segmented_button_selected_color=c_primary, segmented_button_selected_hover_color=c_primary_hover, segmented_button_unselected_color=c_panel_bg, segmented_button_unselected_hover_color=c_border)
        self.tab_db.pack(fill="both", expand=True)
        self.tab_db.add("Uživatelé")
        self.tab_db.add("Příspěvky")
        self.tab_db.add("Trendy")
        self.tree_users = self.create_bitwarden_tree(self.tab_db.tab("Uživatelé"))
        self.tree_posts = self.create_bitwarden_tree(self.tab_db.tab("Příspěvky"))
        self.tree_trends = self.create_bitwarden_tree(self.tab_db.tab("Trendy"))

    def create_bitwarden_tree(self, parent):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=c_main_bg, foreground=c_text_main, rowheight=30, fieldbackground=c_main_bg, borderwidth=0, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", background=c_panel_bg, foreground=c_text_main, relief="flat", font=("Segoe UI", 12, "bold"), padding=(10, 5))
        style.map('Treeview', background=[('selected', c_primary)], foreground=[('selected', 'white')])
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        scroll_y = ctk.CTkScrollbar(frame, button_color=c_panel_bg, button_hover_color=c_border)
        scroll_y.pack(side="right", fill="y")
        tree = ttk.Treeview(frame, yscrollcommand=scroll_y.set, show="headings", selectmode="browse")
        tree.pack(fill="both", expand=True)
        scroll_y.configure(command=tree.yview)
        return tree

    def refresh_db(self):
        if not self.db_path.exists(): return
        for t in [self.tree_users, self.tree_posts, self.tree_trends]:
            for i in t.get_children(): t.delete(i)
        try:
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.cursor()
            cur.execute("SELECT platform, username, followers_count FROM users")
            self.tree_users['columns'] = ("Platform", "Username", "Followers")
            for c in self.tree_users['columns']: self.tree_users.heading(c, text=c, anchor="w"); self.tree_users.column(c, width=150)
            for r in cur.fetchall(): self.tree_users.insert("", "end", values=r)
            cur.execute("SELECT platform, text_content, likes_count FROM posts ORDER BY scraped_at DESC LIMIT 50")
            self.tree_posts['columns'] = ("Plat.", "Text", "Likes")
            self.tree_posts.heading("Plat.", text="Plat."); self.tree_posts.column("Plat.", width=50)
            self.tree_posts.heading("Text", text="Text"); self.tree_posts.column("Text", width=400)
            self.tree_posts.heading("Likes", text="Likes"); self.tree_posts.column("Likes", width=80)
            for r in cur.fetchall():
                tx = r[1][:60] + "..." if r[1] and len(r[1]) > 60 else r[1]
                self.tree_posts.insert("", "end", values=(r[0], tx, r[2]))
            cur.execute("SELECT rank, topic_name, post_count FROM trending ORDER BY rank ASC")
            self.tree_trends['columns'] = ("#", "Téma", "Objem")
            for c in self.tree_trends['columns']: self.tree_trends.heading(c, text=c, anchor="w")
            for r in cur.fetchall(): self.tree_trends.insert("", "end", values=r)
            conn.close()
        except Exception as e: print(f"[DB ERROR] {e}")

    def load_users(self):
        if not os.path.exists(self.data_path): return
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for user in data.get("users", []):
                self.users_map[f"{user['ID']} - {user['name']}"] = user
        except: pass

    def start_thread(self, platform, action):
        if self.is_running: messagebox.showwarning("Busy", "Bot již běží."); return
        key = self.user_var.get()
        if not key: messagebox.showerror("Chyba", "Vyber identitu."); return
        user_data = self.users_map[key]
        social = user_data.get('social_media', {}).get(platform)
        if not social: messagebox.showerror("Chyba", f"Identita nemá {platform}."); return
        
        target_input = self.target_var.get().strip()
        if action == "scrape" and not target_input: messagebox.showwarning("Chyba", "Zadej cíl."); return
        
        limit = 10
        if self.scrape_all_var.get(): limit = -1
        else:
            try: limit = int(self.limit_var.get())
            except ValueError: messagebox.showerror("Chyba", "Limit musí být číslo."); return
        
        self.is_running = True
        txt_limit = "VŠE" if limit == -1 else str(limit)
        self.status_label.configure(text=f"● Běží: {platform} {action} (Limit: {txt_limit})", text_color=c_primary)
        self.log_box.configure(state="normal"); self.log_box.delete(1.0, tk.END); self.log_box.configure(state="disabled")
        
        threading.Thread(target=self.run_bot, args=(platform, social['username'], social['password'], key.split()[0], action, target_input, limit), daemon=True).start()

    def run_bot(self, platform, u, p, uid, action, target_input, limit):
        try:
            if platform == "instagram": bot = InstagramBot(u, p, uid)
            else: bot = XBot(u, p, uid)
            self.current_bot = bot
            bot.login()
            
            if action == "scrape": 
                # BATCH LOGIKA S PROGRESS BAREM
                targets = [t.strip() for t in target_input.replace('\n', ',').split(',') if t.strip()]
                total = len(targets)
                
                # Zobrazíme progress bar
                self.after(0, lambda: self.progress_bar.pack(side="bottom", padx=20, pady=(0, 10), before=self.status_label))
                
                print(f"[BATCH] Nalezeno {total} cílů ke zpracování: {targets}")

                for i, target in enumerate(targets):
                    if not self.is_running:
                        print("[STOP] Hromadný sběr přerušen uživatelem.")
                        break

                    # Aktualizace GUI (Progress Bar a Text)
                    progress_percent = i / total
                    self.after(0, lambda p=progress_percent, t=target, idx=i, tot=total: [
                        self.progress_bar.set(p),
                        self.status_label.configure(text=f"● Těžím {idx+1}/{tot}: {t}", text_color=c_primary)
                    ])
                    
                    print(f"\n==========================================")
                    print(f"=== ZPRACOVÁVÁM CÍL {i+1}/{total}: {target} ===")
                    print(f"==========================================")
                    
                    try:
                        bot.scraper.scrape_profile(target, limit)
                    except Exception as e:
                        print(f"[ERROR] Chyba u cíle {target}: {e}")
                    
                    # Update po dokončení cíle
                    self.after(0, lambda p=((i + 1) / total): self.progress_bar.set(p))

                    if i < total - 1:
                        print(f"[INFO] Čekám 3 sekundy před dalším profilem...")
                        time.sleep(3)

            elif action == "scrape_trending": 
                bot.scraper.scrape_trending()
            
            print("--- HOTOVO ---")
            print("[INFO] Prohlížeč zůstává otevřený. Pro ukončení stiskni 'UKONČIT OPERACI'.")
            self.status_label.configure(text=f"● Hotovo (Čekám na STOP)", text_color="#2eb85c")
            
            while self.is_running: time.sleep(1)

        except Exception as e: print(f"CHYBA: {e}")
        finally:
            # Skryjeme progress bar
            self.after(0, lambda: self.progress_bar.pack_forget())
            self.after(0, lambda: self.progress_bar.set(0))
            
            if self.current_bot: self.current_bot.close()
            self.current_bot = None
            self.is_running = False
            self.status_label.configure(text="● Připraveno", text_color="#2eb85c")

    def stop_bot(self):
        if self.is_running:
            self.is_running = False
            if self.current_bot: self.current_bot.close()
            print("--- ZASTAVENO UŽIVATELEM ---")

if __name__ == "__main__":
    app = App()
    app.mainloop()