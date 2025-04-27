import tkinter as tk
from tkinter import ttk
import threading
import keyboard
from IG_actions.IG_multi_session import quit_all_sessions
from IG_actions.IG_user_behaviour import IG_user_behaviour
from .widgets import UserIDInput, LogPanel

class InstagramAutomationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Instagram Multi-User Automation")
        self.geometry("800x600")
        
        # Track user IDs and threads
        self.user_ids = []
        self.threads = []
        
        # Build GUI
        self._create_widgets()
        self._bind_hotkeys()

    def _create_widgets(self):
        # User ID Input
        self.input_frame = ttk.LabelFrame(self, text="Add Users")
        self.input_frame.pack(pady=10, padx=10, fill=tk.X)
        
        self.user_input = UserIDInput(self.input_frame, self.add_user)
        self.user_input.pack(pady=5)
        
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
        self.log_panel = LogPanel(self)
        self.log_panel.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    def _bind_hotkeys(self):
        keyboard.add_hotkey("ctrl+q", self.stop_automation)

    def add_user(self, user_id):
        if user_id not in self.user_ids:
            self.user_ids.append(user_id)
            self.log_panel.log(f"Added User ID: {user_id}")

    def start_automation(self):
        if not self.user_ids:
            self.log_panel.log("Error: No users added!")
            return
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        
        for uid in self.user_ids:
            thread = threading.Thread(target=self._run_user_automation, args=(uid,))
            thread.start()
            self.threads.append(thread)
            self.log_panel.log(f"Started automation for User ID: {uid}")

    def _run_user_automation(self, user_id):
        try:
            IG_user_behaviour(user_id)
        except Exception as e:
            self.log_panel.log(f"Error for User {user_id}: {str(e)}")

    def stop_automation(self):
        quit_all_sessions()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.log_panel.log("All sessions terminated.")
        
        # Clear threads
        self.threads = []
        self.user_ids = []

    def on_close(self):
        self.stop_automation()
        self.destroy()

if __name__ == "__main__":
    app = InstagramAutomationApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()