# src/gui/app.py
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import json
import os
import time
import sys
from pathlib import Path

# Modulární importy
from src.gui.theme import COLORS
from src.gui.utils import PrintLogger
from src.gui.frames.dashboard import DashboardFrame
from src.gui.frames.profiles import ProfilesFrame
from src.gui.frames.database import DatabaseFrame

from src.bots.instagram.bot import InstagramBot
from src.bots.x.bot import XBot

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # --- KONFIGURACE ---
        self.title("Ogma 0.0") 
        self.geometry("1200x800")
        self.minsize(1000, 700)
        
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.data_path = project_root / 'data' / 'users.json'
        self.db_path = project_root / 'data' / 'osint.db'
        
        icon_path = project_root / 'src' / 'gui' / 'ogma_ai_logo.ico'
        if icon_path.exists(): self.iconbitmap(str(icon_path))

        self.users_map = {}
        self.load_users()
        self.current_bot = None 
        self.is_running = False

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=COLORS["sidebar_bg"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # 2. Main Content
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color=COLORS["main_bg"])
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # 3. Frames (Moduly)
        self.frame_dash = DashboardFrame(self.main_area, self)
        self.frame_prof = ProfilesFrame(self.main_area, self)
        self.frame_db = DatabaseFrame(self.main_area, self)

        # 4. Logger Hook
        # Přesměrujeme stdout do log boxu uvnitř DashboardFrame
        sys.stdout = PrintLogger(self.frame_dash.log_box, self)
        sys.stderr = PrintLogger(self.frame_dash.log_box, self)

        self.show_frame("dashboard")

    def setup_sidebar(self):
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(25, 20), padx=20, fill="x")
        
        ctk.CTkLabel(logo_frame, text="Ogma 0.0", font=("Segoe UI", 22, "bold"), text_color=COLORS["text_main"], anchor="w").pack(fill="x")
        ctk.CTkLabel(logo_frame, text="OSINT Automation Tool", font=("Segoe UI", 12), text_color=COLORS["text_dim"], anchor="w").pack(fill="x")

        ctk.CTkFrame(self.sidebar, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=0, pady=10)

        self.btn_nav_dash = self.create_nav_btn("Přehled (Dashboard)", "dashboard")
        self.btn_nav_prof = self.create_nav_btn("Scrapnuté Profily", "profiles") 
        self.btn_nav_db = self.create_nav_btn("Databáze (Vault)", "database")
        
        ctk.CTkLabel(self.sidebar, text="", height=50).pack(side="bottom") # Spacer

        self.status_label = ctk.CTkLabel(self.sidebar, text="● Připraveno", text_color="#2eb85c", font=("Segoe UI", 12))
        self.status_label.pack(side="bottom", pady=(5, 20), padx=20, anchor="w")

        self.progress_bar = ctk.CTkProgressBar(self.sidebar, width=200, height=8, corner_radius=4, progress_color=COLORS["primary"])
        self.progress_bar.set(0)

    def create_nav_btn(self, text, view_name):
        return ctk.CTkButton(
            self.sidebar, text=text, command=lambda: self.show_frame(view_name),
            fg_color="transparent", text_color=COLORS["text_dim"], hover_color=COLORS["panel_bg"],
            anchor="w", height=45, font=("Segoe UI", 14), corner_radius=4
        ).pack(fill="x", padx=10, pady=2) or self.sidebar.winfo_children()[-1]

    def show_frame(self, name):
        # Reset buttons (simple style reset)
        for btn in [self.btn_nav_dash, self.btn_nav_prof, self.btn_nav_db]:
            btn.configure(fg_color="transparent", text_color=COLORS["text_dim"])
        
        # Hide all
        self.frame_dash.grid_forget()
        self.frame_prof.grid_forget()
        self.frame_db.grid_forget()

        if name == "dashboard":
            self.frame_dash.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_dash.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
        elif name == "profiles":
            self.frame_prof.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_prof.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_prof.refresh_data()
        elif name == "database":
            self.frame_db.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
            self.btn_nav_db.configure(fg_color=COLORS["panel_bg"], text_color=COLORS["primary"])
            self.frame_db.refresh_data()

    def load_users(self):
        if not os.path.exists(self.data_path): return
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for user in data.get("users", []):
                self.users_map[f"{user['ID']} - {user['name']}"] = user
        except: pass

    # --- BOT LOGIC (Zůstává zde kvůli Threadingu a přístupu ke stavu) ---
    def start_thread(self, platform, action):
        if self.is_running: messagebox.showwarning("Busy", "Bot již běží."); return
        
        # Data taháme z DashboardFrame
        key = self.frame_dash.user_var.get()
        if not key: messagebox.showerror("Chyba", "Vyber identitu."); return
        
        user_data = self.users_map[key]
        social = user_data.get('social_media', {}).get(platform)
        if not social: messagebox.showerror("Chyba", f"Identita nemá {platform}."); return
        
        target_input = self.frame_dash.target_var.get().strip()
        if action == "scrape" and not target_input: messagebox.showwarning("Chyba", "Zadej cíl."); return
        
        limit = 10
        if self.frame_dash.scrape_all_var.get(): limit = -1
        else:
            try: limit = int(self.frame_dash.limit_var.get())
            except ValueError: messagebox.showerror("Chyba", "Limit musí být číslo."); return
        
        self.is_running = True
        txt_limit = "VŠE" if limit == -1 else str(limit)
        self.status_label.configure(text=f"● Běží: {platform} {action} (Limit: {txt_limit})", text_color=COLORS["primary"])
        
        # Vyčistit log
        self.frame_dash.log_box.configure(state="normal")
        self.frame_dash.log_box.delete(1.0, tk.END)
        self.frame_dash.log_box.configure(state="disabled")
        
        threading.Thread(target=self.run_bot, args=(platform, social['username'], social['password'], key.split()[0], action, target_input, limit), daemon=True).start()

    def run_bot(self, platform, u, p, uid, action, target_input, limit):
        try:
            if platform == "instagram": bot = InstagramBot(u, p, uid)
            else: bot = XBot(u, p, uid)
            self.current_bot = bot
            bot.login()
            
            if action == "scrape": 
                targets = [t.strip() for t in target_input.replace('\n', ',').split(',') if t.strip()]
                total = len(targets)
                
                self.after(0, lambda: self.progress_bar.pack(side="bottom", padx=20, pady=(0, 10), before=self.status_label))
                print(f"[BATCH] Nalezeno {total} cílů ke zpracování: {targets}")

                for i, target in enumerate(targets):
                    if not self.is_running:
                        print("[STOP] Přerušeno uživatelem.")
                        break

                    progress_percent = i / total
                    self.after(0, lambda p=progress_percent, t=target, idx=i, tot=total: [
                        self.progress_bar.set(p),
                        self.status_label.configure(text=f"● Těžím {idx+1}/{tot}: {t}", text_color=COLORS["primary"])
                    ])
                    
                    print(f"\n=== CÍL {i+1}/{total}: {target} ===")
                    try:
                        bot.scraper.scrape_profile(target, limit)
                    except Exception as e:
                        print(f"[ERROR] Chyba u cíle {target}: {e}")
                    
                    self.after(0, lambda p=((i + 1) / total): self.progress_bar.set(p))
                    if i < total - 1:
                        print(f"[INFO] Pauza 3s...")
                        time.sleep(3)

            elif action == "scrape_trending": 
                bot.scraper.scrape_trending()
            
            print("--- HOTOVO ---")
            self.status_label.configure(text=f"● Hotovo (Čekám na STOP)", text_color="#2eb85c")
            while self.is_running: time.sleep(1)

        except Exception as e: print(f"CHYBA: {e}")
        finally:
            self.after(0, lambda: self.progress_bar.pack_forget())
            self.after(0, lambda: self.progress_bar.set(0))
            if self.current_bot: self.current_bot.close()
            self.current_bot = None
            self.is_running = False
            self.status_label.configure(text="● Připraveno", text_color="#2eb85c")

    def stop_bot(self):
        if self.is_running:
            self.is_running = False
            # Změna: Záměrně zde nevoláme self.current_bot.close().
            # Vlákno (run_bot) si po změně is_running na False 
            # samo vyskočí ze smyček a zavře prohlížeč bezpečně ve svém bloku finally.
            print("--- ZASTAVENO UŽIVATELEM ---")

if __name__ == "__main__":
    app = App()
    app.mainloop()