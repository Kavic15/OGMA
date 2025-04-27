import tkinter as tk
from tkinter import ttk, scrolledtext

class UserIDInput(ttk.Frame):
    """Input field for adding user IDs."""
    def __init__(self, master, on_add):
        super().__init__(master)
        self.on_add = on_add
        self.entry = ttk.Entry(self, width=15)
        self.btn_add = ttk.Button(self, text="Add User", command=self._add_user)
        self.entry.pack(side=tk.LEFT, padx=5)
        self.btn_add.pack(side=tk.LEFT)

    def _add_user(self):
        user_id = self.entry.get()
        if user_id.isdigit():
            self.on_add(int(user_id))
            self.entry.delete(0, tk.END)

class LogPanel(scrolledtext.ScrolledText):
    """Scrollable log display."""
    def __init__(self, master):
        super().__init__(master, wrap=tk.WORD, state=tk.DISABLED, height=10)
    
    def log(self, message):
        self.configure(state=tk.NORMAL)
        self.insert(tk.END, message + "\n")
        self.configure(state=tk.DISABLED)
        self.see(tk.END)  # Auto-scroll to bottom