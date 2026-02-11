import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import json
import os
import time
import sys
from pathlib import Path
from src.bots.instagram import InstagramBot
from src.bots.x import XBot

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
        self.title("Social Bot - Command Center")
        self.geometry("1200x800")
        
        # --- DYNAMICKÉ CESTY ---
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        icon_path = project_root / 'src' / 'gui' / 'ogma_ai_logo.ico'
        if icon_path.exists():
            self.iconbitmap(str(icon_path))
        else:
            print(f"[WARNING] Ikona nenalezena na cestě: {icon_path}")
            
        self.data_path = project_root / 'data' / 'users.json'
        # ----------------------
        
        self.current_bot = None 
        self.is_running = False

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.users_map = {}
        self.load_users()

        # --- OVLÁDÁNÍ A LOGY ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(side="top", fill="x", pady=20, padx=40)
        
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(side="bottom", fill="both", expand=True, padx=40, pady=(0, 40))

        # --- PRVKY ---
        ctk.CTkLabel(top_frame, text="Vyber bota (Identita):", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            top_frame, 
            variable=self.user_var, 
            state="readonly", 
            font=("Arial", 14), 
            dropdown_font=("Arial", 14),
            width=350,
            height=40
        )
        self.user_combo.configure(values=list(self.users_map.keys()))
        if self.users_map:
            self.user_combo.set(list(self.users_map.keys())[0])
        self.user_combo.pack(pady=5)

        btn_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        btn_frame.pack(pady=20)

        self.btn_ig = ctk.CTkButton(
            btn_frame, 
            text="Přihlásit IG", 
            command=lambda: self.start_thread("instagram"), 
            width=200, 
            height=45,
            font=("Arial", 14, "bold")
        )
        self.btn_ig.grid(row=0, column=0, padx=15)

        self.btn_x = ctk.CTkButton(
            btn_frame, 
            text="Přihlásit X", 
            command=lambda: self.start_thread("X"), 
            width=200, 
            height=45,
            font=("Arial", 14, "bold")
        )
        self.btn_x.grid(row=0, column=1, padx=15)

        self.btn_stop = ctk.CTkButton(
            top_frame, 
            text="STOP A ULOŽIT SESSION", 
            fg_color="#CC0000", 
            hover_color="#990000", 
            font=("Arial", 14, "bold"), 
            command=self.stop_bot,
            width=300,
            height=45
        )
        self.btn_stop.pack(pady=15)

        self.status_label = ctk.CTkLabel(top_frame, text="Připraveno", text_color="gray", font=("Arial", 14))
        self.status_label.pack(pady=5)

        # --- LOGY ---
        ctk.CTkLabel(log_frame, text="Real-time Bot Logs:", font=("Consolas", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        self.log_text = ctk.CTkTextbox(
            log_frame, 
            fg_color="#121212", 
            text_color="#00ff00", 
            font=("Consolas", 13), 
            wrap="word"
        )
        self.log_text.pack(side="bottom", fill="both", expand=True, padx=15, pady=(0, 15))

        sys.stdout = PrintLogger(self.log_text, self)
        sys.stderr = PrintLogger(self.log_text, self)

        print("=== COMMAND CENTER INICIALIZOVÁNO ===")
        print("Grafické rozhraní přepnuto do režimu CustomTkinter.")
        print("Přesunut okno na sekundární monitor a můžeš začít...")

    def load_users(self):
        if not os.path.exists(self.data_path):
            messagebox.showerror("Chyba", f"Nenalezen soubor: {self.data_path}")
            return
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for user in data.get("users", []):
                display_name = f"{user['ID']} - {user['name']} {user['surname']}"
                self.users_map[display_name] = user
        except Exception as e:
            messagebox.showerror("Chyba JSON", f"Chyba při čtení users.json:\n{e}")

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

    def start_thread(self, platform):
        if self.is_running:
            messagebox.showwarning("Běží", "Bot už běží. Použij STOP tlačítko.")
            return

        username, password = self.get_credentials(platform)
        if not username: return

        user_id = self.user_var.get().split(" - ")[0]

        self.update_status(f"Spouštím {platform} pro ID {user_id}...")
        self.is_running = True
        
        self.log_text.delete(1.0, tk.END)
        print(f"=== STARTING {platform.upper()} BOT ===")
        
        threading.Thread(target=self.run_bot, args=(platform, username, password, user_id), daemon=True).start()

    def run_bot(self, platform, username, password, user_id):
        try:
            if platform == "instagram":
                self.current_bot = InstagramBot(username, password, user_id=user_id)
                self.current_bot.login()
            elif platform == "X":
                self.current_bot = XBot(username, password, user_id=user_id)
                self.current_bot.login()
            
            self.update_status("Login hotový. Čekám. Klikni na STOP pro uložení.")
            print("\n[INFO] Bot dokončil úlohu. Čeká na tvůj příkaz STOP...")
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