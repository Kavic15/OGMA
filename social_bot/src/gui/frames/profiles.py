# src/gui/frames/profiles.py
import customtkinter as ctk
import threading
import sqlite3
from src.gui.theme import COLORS
from src.gui.utils import AsyncImageLoader

class ProfilesFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.all_profiles_data = []
        self.image_loader = AsyncImageLoader()
        
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top Bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        ctk.CTkLabel(top_bar, text="Nalezené Profily", font=("Segoe UI", 24, "bold"), 
                     text_color=COLORS["text_main"]).pack(side="left")

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self.filter_profiles)
        
        search_entry = ctk.CTkEntry(
            top_bar, textvariable=self.search_var, width=300, height=35, 
            corner_radius=20, placeholder_text="🔍 Hledat jméno...",
            fg_color=COLORS["panel_bg"], border_color=COLORS["border"], text_color="white"
        )
        search_entry.pack(side="right")

        # Scrollable Area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    def refresh_data(self):
        # Vyčistit
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        
        if not self.controller.db_path.exists(): return
        
        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            try:
                cur.execute("SELECT * FROM users ORDER BY last_scraped DESC")
            except:
                # Fallback pro starou DB
                cur.execute("SELECT id, platform, username, display_name, bio, followers_count, profile_pic_url, last_scraped FROM users ORDER BY last_scraped DESC")
            
            self.all_profiles_data = [dict(row) for row in cur.fetchall()]
            conn.close()
            self.filter_profiles()
        except Exception as e:
            print(f"[GUI ERROR] Chyba profilů: {e}")

    def filter_profiles(self, *args):
        query = self.search_var.get().lower()
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        
        for user in self.all_profiles_data:
            u_name = (user['username'] or "").lower()
            d_name = (user.get('display_name') or "").lower()
            
            if query in u_name or query in d_name:
                self.create_card(user)

    def create_card(self, user):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["panel_bg"], corner_radius=10, 
                            border_color=COLORS["border"], border_width=1)
        card.pack(fill="x", pady=5, padx=5)
        card.grid_columnconfigure(1, weight=1) 
        
        # 1. Avatar
        img_widget = ctk.CTkLabel(card, text="", width=80, height=80, corner_radius=10, fg_color="#444")
        if user.get('profile_pic_url'):
            # Spustit načítání v threadu
            threading.Thread(
                target=self.image_loader.load_image, 
                args=(user.get('profile_pic_url'), img_widget), 
                daemon=True
            ).start()
            
        img_widget.grid(row=0, column=0, rowspan=4, padx=15, pady=15, sticky="n")

        # 2. Info Frame
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="nw", pady=(15, 0), padx=5)
        
        # Jméno
        name_text = user.get('display_name') or user['username']
        ctk.CTkLabel(info_frame, text=name_text, font=("Segoe UI", 16, "bold"), 
                     text_color="white").pack(side="left")

        # Verifikace
        if user.get('is_verified') == 1:
            ctk.CTkLabel(info_frame, text="☑", font=("Segoe UI", 16), 
                         text_color=COLORS["verified"]).pack(side="left", padx=(5, 0))

        # Handle
        handle_txt = f"@{user['username']} • {str(user.get('platform')).upper()}"
        ctk.CTkLabel(info_frame, text=handle_txt, font=("Segoe UI", 13), 
                     text_color=COLORS["text_dim"]).pack(side="left", padx=(10, 0))

        # 3. Stats
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.grid(row=1, column=1, sticky="nw", pady=(5, 5), padx=5)
        
        def fmt(n): return f"{n:,}".replace(",", " ") if n is not None else "0"
        
        # Followers
        ctk.CTkLabel(stats_frame, text=fmt(user.get('followers_count', 0)), font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Followers", font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(3, 15))
        
        # Following
        ctk.CTkLabel(stats_frame, text=fmt(user.get('following_count', 0)), font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Following", font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(3, 0))

        # 4. Bio
        bio = user.get('bio')
        if bio:
            # Bezpečné odstranění všech nových řádků a přebytečných mezer pro kompaktní UI kartu
            clean_bio = " ".join(bio.split())
            short_bio = (clean_bio[:90] + "...") if len(clean_bio) > 90 else clean_bio
            
            # Přidán parametr justify="left" pro správné zarovnání textu
            ctk.CTkLabel(card, text=short_bio, font=("Segoe UI", 12, "italic"), 
                         text_color="#b0b0b0", anchor="w", justify="left").grid(row=2, column=1, sticky="w", padx=5, pady=(0, 5))

        # 5. Metadata
        meta_frame = ctk.CTkFrame(card, fg_color="transparent")
        meta_frame.grid(row=3, column=1, sticky="nw", pady=(0, 15), padx=5)
        
        meta = []
        if user.get('location'): meta.append(f"📍 {user['location']}")
        if user.get('website'): meta.append(f"🔗 {user['website']}")
        if user.get('joined_date'): meta.append(f"📅 {user['joined_date']}")
        
        if meta:
            ctk.CTkLabel(meta_frame, text="   ".join(meta), font=("Segoe UI", 11), 
                         text_color=COLORS["text_dim"]).pack(side="left")

        # Date
        last_s = str(user.get('last_scraped')).split('T')[0] if user.get('last_scraped') else "?"
        ctk.CTkLabel(card, text=f"Upd: {last_s}", font=("Segoe UI", 10), 
                     text_color="#555").grid(row=3, column=1, sticky="e", padx=15, pady=(0, 15))