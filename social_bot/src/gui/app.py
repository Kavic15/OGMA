import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk
import threading
import json
import os
import time
import sys
import sqlite3
from pathlib import Path
from src.bots.instagram.bot import InstagramBot
from src.bots.x.bot import XBot

ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("blue") 

class PrintLogger:
    def __init__(self, textbox, tk_app):
        self.textbox = textbox
        self.tk_app = tk_app

    def write(self, text):
        self.tk_app.after(0, self._insert_text, text)

    def _insert_text(self, text):
        self.textbox.insert(tk.END, text)
        self.textbox.see(tk.END) 

    def flush(self):
        pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ogma 0.0")
        
        self.geometry("1440x900+2560+0")
        self.after(1500, self._maximize_window)
        
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        icon_path = project_root / 'src' / 'gui' / 'ogma_ai_logo.ico'
        if icon_path.exists():
            self.iconbitmap(str(icon_path))
            
        self.data_path = project_root / 'data' / 'users.json'
        self.db_path = project_root / 'data' / 'osint.db'
        
        self.current_bot = None 
        self.is_running = False

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.users_map = {}
        self.load_users()

        self.main_tabview = ctk.CTkTabview(self, command=self.on_tab_change)
        self.main_tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tab_control = self.main_tabview.add("Ovládání bota")
        self.tab_database = self.main_tabview.add("Databáze")

        self.setup_control_tab()
        self.setup_database_tab()

    def _maximize_window(self):
        try:
            self.state('zoomed')
        except Exception as e:
            print(f"[WARNING] Nelze maximalizovat okno: {e}")

    def setup_control_tab(self):
        top_frame = ctk.CTkFrame(self.tab_control, fg_color="transparent")
        top_frame.pack(side="top", fill="x", pady=5, padx=20)
        
        log_frame = ctk.CTkFrame(self.tab_control)
        log_frame.pack(side="bottom", fill="both", expand=True, padx=20, pady=(0, 20))

        # SEKCE 1
        identity_frame = ctk.CTkFrame(top_frame)
        identity_frame.pack(fill="x", pady=5, ipadx=10, ipady=10)

        ctk.CTkLabel(identity_frame, text="1. Identita a Přihlášení", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            identity_frame, variable=self.user_var, state="readonly", 
            font=("Arial", 14), dropdown_font=("Arial", 14), width=350, height=40
        )
        self.user_combo.configure(values=list(self.users_map.keys()))
        if self.users_map:
            self.user_combo.set(list(self.users_map.keys())[0])
        self.user_combo.pack(pady=5)

        btn_login_frame = ctk.CTkFrame(identity_frame, fg_color="transparent")
        btn_login_frame.pack(pady=10)

        self.btn_ig_login = ctk.CTkButton(
            btn_login_frame, text="Pouze Přihlásit IG", 
            command=lambda: self.start_thread("instagram", action="login"), 
            width=180, height=40, font=("Arial", 13, "bold"), fg_color="#405DE6"
        )
        self.btn_ig_login.grid(row=0, column=0, padx=10)

        self.btn_x_login = ctk.CTkButton(
            btn_login_frame, text="Pouze Přihlásit X", 
            command=lambda: self.start_thread("X", action="login"), 
            width=180, height=40, font=("Arial", 13, "bold"), fg_color="#000000", hover_color="#333333"
        )
        self.btn_x_login.grid(row=0, column=1, padx=10)

        # SEKCE 2
        scrape_frame = ctk.CTkFrame(top_frame)
        scrape_frame.pack(fill="x", pady=10, ipadx=10, ipady=10)

        ctk.CTkLabel(scrape_frame, text="2. Těžba dat (Scraping)", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.target_var = ctk.StringVar()
        self.target_entry = ctk.CTkEntry(
            scrape_frame, textvariable=self.target_var, width=350, height=40, 
            font=("Arial", 14), placeholder_text="Cílový účet (např. elon musk)"
        )
        self.target_entry.pack(pady=5)

        btn_scrape_frame = ctk.CTkFrame(scrape_frame, fg_color="transparent")
        btn_scrape_frame.pack(pady=10)

        self.btn_ig_scrape = ctk.CTkButton(
            btn_scrape_frame, text="Těžit profil IG", 
            command=lambda: self.start_thread("instagram", action="scrape"), 
            width=180, height=40, font=("Arial", 13, "bold"), fg_color="#E1306C"
        )
        self.btn_ig_scrape.grid(row=0, column=0, padx=10)

        self.btn_x_scrape = ctk.CTkButton(
            btn_scrape_frame, text="Těžit profil X", 
            command=lambda: self.start_thread("X", action="scrape"), 
            width=180, height=40, font=("Arial", 13, "bold"), fg_color="#1DA1F2", text_color="white"
        )
        self.btn_x_scrape.grid(row=0, column=1, padx=10)

        # NOVÉ TLAČÍTKO PRO TRENDY
        self.btn_x_trending = ctk.CTkButton(
            scrape_frame, text="Těžit Trendy (X)", 
            command=lambda: self.start_thread("X", action="scrape_trending"), 
            width=380, height=40, font=("Arial", 13, "bold"), fg_color="#107C10", hover_color="#0B5A0B", text_color="white"
        )
        self.btn_x_trending.pack(pady=(0, 10))

        # SEKCE 3
        self.btn_stop = ctk.CTkButton(
            top_frame, text="STOP A ULOŽIT SESSION", 
            fg_color="#CC0000", hover_color="#990000", font=("Arial", 14, "bold"), 
            command=self.stop_bot, width=300, height=45
        )
        self.btn_stop.pack(pady=15)

        self.status_label = ctk.CTkLabel(top_frame, text="Připraveno", text_color="gray", font=("Arial", 14))
        self.status_label.pack(pady=0)

        # LOGY
        ctk.CTkLabel(log_frame, text="Real-time Bot Logs:", font=("Consolas", 14, "bold")).pack(anchor="w", padx=15, pady=(10, 5))
        self.log_text = ctk.CTkTextbox(log_frame, fg_color="#121212", text_color="#00ff00", font=("Consolas", 13), wrap="word")
        self.log_text.pack(side="bottom", fill="both", expand=True, padx=15, pady=(0, 15))

        sys.stdout = PrintLogger(self.log_text, self)
        sys.stderr = PrintLogger(self.log_text, self)

        print("=== OGMA 0.0 INICIALIZOVÁNO ===")
        print("Aplikace připravena.")

    def setup_database_tab(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=25, fieldbackground="#2b2b2b", bordercolor="#343638", borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])

        btn_refresh = ctk.CTkButton(self.tab_database, text="Obnovit data", command=self.load_db_data, width=150)
        btn_refresh.pack(pady=10)

        self.db_subtabs = ctk.CTkTabview(self.tab_database)
        self.db_subtabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.db_subtabs.add("Uživatelé")
        self.db_subtabs.add("Příspěvky")
        self.db_subtabs.add("Trendy") # NOVÁ TABULKA

        self.users_tree = self.create_treeview(self.db_subtabs.tab("Uživatelé"))
        self.posts_tree = self.create_treeview(self.db_subtabs.tab("Příspěvky"))
        self.trends_tree = self.create_treeview(self.db_subtabs.tab("Trendy"))

    def create_treeview(self, parent_frame):
        tree_scroll_y = ctk.CTkScrollbar(parent_frame, orientation="vertical")
        tree_scroll_y.pack(side="right", fill="y")
        
        tree_scroll_x = ctk.CTkScrollbar(parent_frame, orientation="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")

        tree = ttk.Treeview(parent_frame, yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        tree.pack(fill="both", expand=True)
        
        tree_scroll_y.configure(command=tree.yview)
        tree_scroll_x.configure(command=tree.xview)
        
        return tree

    def on_tab_change(self):
        if self.main_tabview.get() == "Databáze":
            self.load_db_data()

    def load_db_data(self):
        if not self.db_path.exists():
            return

        for item in self.users_tree.get_children(): self.users_tree.delete(item)
        for item in self.posts_tree.get_children(): self.posts_tree.delete(item)
        for item in self.trends_tree.get_children(): self.trends_tree.delete(item)

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # NAČTENÍ UŽIVATELŮ
            cursor.execute("SELECT id, platform, username, display_name, followers_count, last_scraped FROM users")
            self.users_tree['columns'] = ("ID", "Platform", "Username", "Display Name", "Followers", "Last Scraped")
            self.users_tree.column("#0", width=0, stretch="no")
            for col in self.users_tree['columns']:
                self.users_tree.column(col, anchor="w", width=150)
                self.users_tree.heading(col, text=col, anchor="w")
                
            for row in cursor.fetchall():
                row_list = list(row)
                row_list[0] = str(row_list[0])[:8] # Oříznutí zobrazení UUID
                self.users_tree.insert("", "end", values=row_list)

            # NAČTENÍ PŘÍSPĚVKŮ
            cursor.execute("SELECT id, platform, platform_post_id, text_content, likes_count, timestamp_posted, scraped_at FROM posts")
            self.posts_tree['columns'] = ("ID", "Platform", "Post ID", "Text", "Likes", "Posted At", "Scraped At")
            self.posts_tree.column("#0", width=0, stretch="no")
            for col in self.posts_tree['columns']:
                self.posts_tree.column(col, anchor="w", width=150)
                self.posts_tree.heading(col, text=col, anchor="w")
                
            for row in cursor.fetchall():
                row_list = list(row)
                row_list[0] = str(row_list[0])[:8] # Oříznutí zobrazení UUID
                if row_list[3] and len(row_list[3]) > 60: 
                    row_list[3] = row_list[3][:57] + "..."
                self.posts_tree.insert("", "end", values=row_list)

            # NAČTENÍ TRENDŮ
            try:
                cursor.execute("SELECT id, platform, rank, category, topic_name, post_count, scraped_at FROM trending ORDER BY rank ASC")
                self.trends_tree['columns'] = ("ID", "Platform", "Rank", "Category", "Topic", "Posts Count")
                self.trends_tree.column("#0", width=0, stretch="no")
                for col in self.trends_tree['columns']:
                    self.trends_tree.column(col, anchor="w", width=150)
                    self.trends_tree.heading(col, text=col, anchor="w")
                    
                for row in cursor.fetchall():
                    row_list = list(row)
                    row_list[0] = str(row_list[0])[:8] # Oříznutí zobrazení UUID
                    self.trends_tree.insert("", "end", values=row_list[:-1])
            except Exception as e:
                pass 

            conn.close()
        except Exception as e:
            print(f"[ERROR] Chyba při načítání databáze: {e}")

    def load_users(self):
        if not os.path.exists(self.data_path):
            return
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for user in data.get("users", []):
                self.users_map[f"{user['ID']} - {user['name']} {user['surname']}"] = user
        except Exception as e:
            print(f"[ERROR] Chyba při čtení users.json: {e}")

    def get_credentials(self, platform_key):
        selected_key = self.user_var.get()
        if not selected_key:
            messagebox.showwarning("Pozor", "Nevybral jsi žádného uživatele!")
            return None, None
        user_data = self.users_map.get(selected_key)
        social_data = user_data.get('social_media', {}).get(platform_key)
        if not social_data:
            messagebox.showerror("Chyba", f"Uživatel nemá údaje pro {platform_key}!")
            return None, None
        return social_data.get('username'), social_data.get('password')

    def start_thread(self, platform, action="login"):
        if self.is_running:
            messagebox.showwarning("Běží", "Bot už běží. Použij STOP tlačítko.")
            return

        username, password = self.get_credentials(platform)
        if not username: return

        target = self.target_var.get().strip()
        # ZMĚNA: Pro těžbu trendů nevyžadujeme vyplněný Target
        if action == "scrape" and not target:
            messagebox.showwarning("Pozor", "Pro spuštění těžby profilu musíš zadat Cílový účet!")
            return

        user_id = self.user_var.get().split(" - ")[0]

        self.update_status(f"Spouštím {platform} ({action}) pro ID {user_id}...")
        self.is_running = True
        
        self.log_text.delete(1.0, tk.END)
        print(f"=== STARTING {platform.upper()} BOT ({action.upper()}) ===")
        
        threading.Thread(target=self.run_bot, args=(platform, username, password, user_id, action, target), daemon=True).start()

    def run_bot(self, platform, username, password, user_id, action, target):
        try:
            if platform == "instagram":
                self.current_bot = InstagramBot(username, password, user_id=user_id)
            elif platform == "X":
                self.current_bot = XBot(username, password, user_id=user_id)
            
            self.current_bot.login()
            
            # ZMĚNA: Rozdělení akcí
            if action == "scrape":
                self.current_bot.scraper.scrape_profile(target)
                self.update_status(f"Těžba @{target} na {platform} byla dokončena.")
            elif action == "scrape_trending":
                self.current_bot.scraper.scrape_trending()
                self.update_status(f"Těžba trendů na {platform} byla dokončena.")
            else:
                self.update_status("Login hotový. Čekám. Klikni na STOP pro uložení.")
                
            print("\n[INFO] Bot dokončil zadanou úlohu. Čeká na tvůj příkaz STOP...")
            while self.is_running:
                time.sleep(1)

        except Exception as e:
            err_msg = str(e)
            ignored_errors = ["Connection closed", "Target closed", "页面的连接已断开", "disconnected"]
            if any(err in err_msg for err in ignored_errors):
                self.update_status("Bot byl bezpečně ukončen.")
            else:
                print(f"\n[CRITICAL ERROR]: {e}")
                self.update_status("Chyba: V logu")
        finally:
            if self.current_bot:
                self.current_bot.close()
                self.current_bot = None
            self.is_running = False

    def stop_bot(self, silent=False):
        if self.is_running:
            self.update_status("Zastavuji bota a ukládám data...")
            print("\n--- PŘIJAT PŘÍKAZ K UKONČENÍ A ULOŽENÍ ---")
            self.is_running = False 
            if self.current_bot:
                self.current_bot.close()
        else:
            if not silent:
                messagebox.showinfo("Info", "Žádný bot neběží.")

    def update_status(self, text):
        try:
            if self.winfo_exists():
                self.after(0, lambda: self.status_label.configure(text=text))
        except Exception:
            pass

    def on_closing(self):
        self.stop_bot(silent=True)
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        self.after(500, self.destroy)