import tkinter as tk
from tkinter import ttk
import threading
import keyboard
import sys
from IG_actions.IG_multi_session import quit_all_sessions as quit_ig_sessions
from IG_actions.IG_user_behaviour import IG_user_behaviour
from FB_actions.FB_multi_session import quit_all_sessions as quit_fb_sessions
from FB_actions.FB_user_behaviour import FB_user_behaviour
from X_actions.X_multi_session import quit_all_sessions as quit_x_sessions
from X_actions.X_user_behaviour import X_user_behaviour
from tkinter import scrolledtext
from .widgets import LogPanel
from utils.log import Logger, log
import sys
import os
# Add current directory to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class SocialMediaAutomationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Social Media Multi-Platform Automation")
        self.geometry("600x1000")
        self.target_accounts = []
        self.tweet_count = 50
        
        # Initialize logger early
        self.log_panel = LogPanel(self)
        Logger.initialize(self, self.log_panel)
        
        # Track users and threads
        self.users = []  # List of tuples (user_id, platform)
        self.threads = []
        
        # Build GUI
        self._create_widgets()
        self._bind_hotkeys()
        self._setup_std_redirect()

    def _create_widgets(self):
        # User Input Section
        self.input_frame = ttk.LabelFrame(self, text="Add Users")
        self.input_frame.pack(pady=10, padx=10, fill=tk.X)

        # Platform Selection
        self.platform_var = tk.StringVar(value="Instagram")
        self.platform_combo = ttk.Combobox(
            self.input_frame,
            textvariable=self.platform_var,
            values=["Instagram", "Facebook (inactive)", "X"],
            state="readonly",
            width=10
        )
        self.platform_combo.pack(side=tk.LEFT, padx=5)

        # User ID Entry
        self.user_entry = ttk.Entry(self.input_frame, width=25)
        self.user_entry.pack(side=tk.LEFT, padx=5)
        
        # Add User Button
        self.btn_add = ttk.Button(
            self.input_frame,
            text="Add User",
            command=self._add_user_handler
        )
        self.btn_add.pack(side=tk.LEFT, padx=5)

        # Start/Stop Controls
        self.control_frame = ttk.Frame(self)
        self.control_frame.pack(pady=10)
        
        self.btn_start = ttk.Button(
            self.control_frame, 
            text="Start Automation", 
            command=self.start_automation
        )
        self.btn_stop = ttk.Button(
            self.control_frame, 
            text="Stop All Sessions (Ctrl+Q)", 
            command=self.stop_automation,
            state=tk.DISABLED
        )
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        # Logs
        self.log_panel.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.scrape_frame = ttk.LabelFrame(self, text="Scrape Settings (X only)")
        self.scrape_frame.pack(pady=10, padx=10, fill=tk.BOTH)
        
        # Target Accounts Input
        ttk.Label(self.scrape_frame, text="Target Accounts (one per line):").pack(anchor=tk.W)
        self.targets_entry = scrolledtext.ScrolledText(self.scrape_frame, height=4)
        self.targets_entry.pack(fill=tk.X, padx=5, pady=5)
        
        # Tweet Count Input
        ttk.Label(self.scrape_frame, text="Number of Tweets per Account:").pack(anchor=tk.W)
        self.tweet_count_var = tk.IntVar(value=50)
        self.tweet_spin = ttk.Spinbox(
            self.scrape_frame,
            from_=1,
            to=1000,
            textvariable=self.tweet_count_var,
            width=5
        )
        self.tweet_spin.pack(anchor=tk.W, padx=5, pady=5)

    def _bind_hotkeys(self):
        keyboard.add_hotkey("ctrl+q", self.stop_automation)

    def _setup_std_redirect(self):
        class LogRedirector:
            def __init__(self, original_stream):
                self.original_stream = original_stream

            def write(self, message):
                if message.strip():
                    log(message.strip(), tag="SYSTEM")
                self.original_stream.write(message)

            def flush(self):
                self.original_stream.flush()

        sys.stdout = LogRedirector(sys.stdout)
        sys.stderr = LogRedirector(sys.stderr)

    def _add_user_handler(self):
        user_id = self.user_entry.get()
        platform = self.platform_var.get()
        if user_id:
            try:
                user_id = int(user_id)
                self.add_user(user_id, platform)
                self.user_entry.delete(0, tk.END)
            except ValueError:
                log(f"Invalid user ID '{user_id}' - must be a number!", tag="ERROR")

    def add_user(self, user_id, platform):
        if (user_id, platform) not in self.users:
            self.users.append((user_id, platform))
            log(f"Added {platform} User: {user_id}", tag="USER MGMT")

    def start_automation(self):
        if not self.users:
            log("No users added!", tag="ERROR")
            return
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        
        for user_id, platform in self.users:
            thread = threading.Thread(
                target=self._run_user_automation,
                args=(user_id, platform),
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
            log(f"Started {platform} automation for: {user_id}", tag="SYSTEM")

    def _run_user_automation(self, user_id, platform):
        try:
            tag = f"{platform.upper()} - {user_id}"
            
            if platform == "Instagram":
                IG_user_behaviour(user_id)
            elif platform == "Facebook (inactive)":
                FB_user_behaviour(user_id)
            elif platform == "X":
                X_user_behaviour(user_id)
                
            log(f"Completed successfully", tag=tag)
        except Exception as e:
            log(f"Critical Error: {str(e)}", tag=f"ERROR/{tag}")

    def stop_automation(self):
        quit_ig_sessions()
        quit_fb_sessions()
        quit_x_sessions()
        
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        log("All sessions terminated", tag="SYSTEM")
        
        self.threads = []
        self.users = []

    def on_close(self):
        self.stop_automation()
        sys.stdout.flush()
        sys.stderr.flush()
        self.destroy()

if __name__ == "__main__":
    app = SocialMediaAutomationApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()