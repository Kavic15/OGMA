import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import time  # Přidán import time
from src.bots.instagram import InstagramBot
from src.bots.x import XBot

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Social Bot 2.0 (IG & X)")
        self.geometry("450x400")
        
        self.current_bot = None 
        self.is_running = False

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_path = os.path.join(base_dir, 'data', 'users.json')
        
        self.users_map = {}
        self.load_users()

        # --- UI Prvky ---
        ttk.Label(self, text="Vyber bota (Identita):").pack(pady=5)
        
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(self, textvariable=self.user_var, state="readonly")
        self.user_combo['values'] = list(self.users_map.keys())
        if self.users_map:
            self.user_combo.current(0)
        self.user_combo.pack(pady=5, fill='x', padx=20)

        ttk.Label(self, text="Cíl (Target Username):").pack(pady=5)
        self.entry_target = ttk.Entry(self)
        self.entry_target.insert(0, "realDonaldTrump")
        self.entry_target.pack(pady=5, fill='x', padx=20)

        # Frame pro tlačítka
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=20)

        self.btn_ig = ttk.Button(btn_frame, text="Spustit Instagram", command=lambda: self.start_thread("instagram"))
        self.btn_ig.grid(row=0, column=0, padx=10)

        self.btn_x = ttk.Button(btn_frame, text="Spustit X (Twitter)", command=lambda: self.start_thread("X"))
        self.btn_x.grid(row=0, column=1, padx=10)

        # Tlačítko STOP
        self.btn_stop = tk.Button(self, text="STOP / UKONČIT BOTA", bg="#ffcccc", fg="red", command=self.stop_bot)
        self.btn_stop.pack(pady=10, fill='x', padx=50)

        self.status_label = ttk.Label(self, text="Připraveno", foreground="gray")
        self.status_label.pack(side="bottom", pady=5)

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

        target = self.entry_target.get()
        user_id = self.user_var.get().split(" - ")[0]

        self.status_label.config(text=f"Spouštím {platform} pro ID {user_id}...")
        self.is_running = True
        
        threading.Thread(target=self.run_bot, args=(platform, username, password, target, user_id)).start()

    def run_bot(self, platform, username, password, target, user_id):
        try:
            if platform == "instagram":
                self.current_bot = InstagramBot(username, password, user_id=user_id)
                self.current_bot.login()
                if target:
                    self.current_bot.scrape_profile(target)
            elif platform == "X":
                self.current_bot = XBot(username, password, user_id=user_id)
                self.current_bot.login()
            
            # --- DŮLEŽITÁ ZMĚNA: NEKONČIT, DOKUD NENÍ STISKNUTO STOP ---
            self.update_status("Bot běží a čeká. Klikni na STOP pro uložení.")
            while self.is_running:
                time.sleep(1) # Čekáme ve smyčce, aby se bot nevypnul
            # -----------------------------------------------------------

        except Exception as e:
            if "Connection closed" not in str(e) and "Target closed" not in str(e):
                print(f"ERROR: {e}")
                self.update_status(f"Chyba: {e}")
            else:
                self.update_status("Bot byl ukončen.")
        finally:
            # Tento blok se provede až když self.is_running nastaveno na False (tlačítkem STOP)
            if self.current_bot:
                self.current_bot.close() # Tady se uloží data!
                self.current_bot = None
            self.is_running = False

    def stop_bot(self):
        """Bezpečné ukončení bota."""
        if self.is_running:
            self.status_label.config(text="Zastavuji bota a ukládám data...")
            print("--- STOP BUTTON PRESSED ---")
            # Nastavením na False se přeruší smyčka while v run_bot
            self.is_running = False 
        else:
            messagebox.showinfo("Info", "Žádný bot neběží.")

    def update_status(self, text):
        self.after(0, lambda: self.status_label.config(text=text))

    def on_closing(self):
        self.stop_bot()
        # Malá pauza, aby se stihlo zavolat close() ve vlákně
        self.after(1000, self.destroy)

if __name__ == "__main__":
    try:
        app = App()
        # update() pomáhá stabilizovat okno před spuštěním smyčky
        app.update() 
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[INFO] Aplikace byla ukončena uživatelem (CTRL+C).")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Aplikace spadla: {e}")