import tkinter as tk
from tkinter import ttk
import threading
import keyboard
from IG_actions.IG_multi_session import quit_all_sessions as quit_ig_sessions
from IG_actions.IG_user_behaviour import IG_user_behaviour
from FB_actions.FB_multi_session import quit_all_sessions as quit_fb_sessions
from FB_actions.FB_user_behaviour import FB_user_behaviour
from .widgets import LogPanel

class SocialMediaAutomationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Social Media Multi-Platform Automation")
        self.geometry("800x600")
        
        # Track users and threads
        self.users = []  # List of tuples (user_id, platform)
        self.threads = []
        
        # Build GUI
        self._create_widgets()
        self._bind_hotkeys()

    def _create_widgets(self):
        # User Input Section
        self.input_frame = ttk.LabelFrame(self, text="Add Users")
        self.input_frame.pack(pady=10, padx=10, fill=tk.X)

        # Platform Selection
        self.platform_var = tk.StringVar(value="Instagram")
        self.platform_combo = ttk.Combobox(
            self.input_frame,
            textvariable=self.platform_var,
            values=["Instagram", "Facebook", "X (in progress)"],
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
        self.log_panel = LogPanel(self)
        self.log_panel.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    def _bind_hotkeys(self):
        keyboard.add_hotkey("ctrl+q", self.stop_automation)

    def _add_user_handler(self):
        user_id = self.user_entry.get()
        platform = self.platform_var.get()
        if user_id:
            try:
                # Convert to integer and validate
                user_id = int(user_id)
                self.add_user(user_id, platform)
                self.user_entry.delete(0, tk.END)
            except ValueError:
                self.log_panel.log(f"Error: Invalid user ID '{user_id}' - must be a number!")

    def add_user(self, user_id, platform):
        if (user_id, platform) not in self.users:
            self.users.append((user_id, platform))
            self.log_panel.log(f"Added {platform} User: {user_id}")

    def start_automation(self):
        if not self.users:
            self.log_panel.log("Error: No users added!")
            return
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        
        for user_id, platform in self.users:
            thread = threading.Thread(
                target=self._run_user_automation,
                args=(user_id, platform)
            )
            thread.start()
            self.threads.append(thread)
            self.log_panel.log(f"Started {platform} automation for: {user_id}")

    def _run_user_automation(self, user_id, platform):
        try:
            if platform == "Instagram":
                IG_user_behaviour(user_id)
            elif platform == "Facebook":
                FB_user_behaviour(user_id)
            elif platform == "X (in progress)":
                self.log_panel.log(f"X platform automation is in progress.")
        except Exception as e:
            self.log_panel.log(f"Error ({platform} - {user_id}): {str(e)}")

    def stop_automation(self):
        # Terminate all sessions for both platforms
        quit_ig_sessions()
        quit_fb_sessions()
        
        # Update UI
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.log_panel.log("All sessions terminated across both platforms")
        
        # Clear queues
        self.threads = []
        self.users = []

    def on_close(self):
        self.stop_automation()
        self.destroy()

if __name__ == "__main__":
    app = SocialMediaAutomationApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()