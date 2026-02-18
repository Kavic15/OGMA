# src/gui/frames/database.py
import customtkinter as ctk
from tkinter import ttk
import sqlite3
from src.gui.theme import COLORS

class DatabaseFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header, text="Uložená data", font=("Segoe UI", 24, "bold"), 
                     text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkButton(header, text="Obnovit", width=80, height=30, 
                      fg_color=COLORS["panel_bg"], hover_color=COLORS["border"], 
                      text_color=COLORS["text_main"], command=self.refresh_data).pack(side="right")

        # Tabs
        self.tab_db = ctk.CTkTabview(
            self, fg_color="transparent", 
            segmented_button_fg_color=COLORS["panel_bg"], 
            segmented_button_selected_color=COLORS["primary"], 
            segmented_button_selected_hover_color=COLORS["primary_hover"], 
            segmented_button_unselected_color=COLORS["panel_bg"], 
            segmented_button_unselected_hover_color=COLORS["border"]
        )
        self.tab_db.pack(fill="both", expand=True)
        
        self.tab_db.add("Uživatelé")
        self.tab_db.add("Příspěvky")
        self.tab_db.add("Trendy")

        self.tree_users = self.create_tree(self.tab_db.tab("Uživatelé"))
        self.tree_posts = self.create_tree(self.tab_db.tab("Příspěvky"))
        self.tree_trends = self.create_tree(self.tab_db.tab("Trendy"))

    def create_tree(self, parent):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=COLORS["main_bg"], foreground=COLORS["text_main"], 
                        rowheight=30, fieldbackground=COLORS["main_bg"], borderwidth=0, font=("Segoe UI", 11))
        style.configure("Treeview.Heading", background=COLORS["panel_bg"], foreground=COLORS["text_main"], 
                        relief="flat", font=("Segoe UI", 12, "bold"), padding=(10, 5))
        style.map('Treeview', background=[('selected', COLORS["primary"])], foreground=[('selected', 'white')])
        
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        
        scroll_y = ctk.CTkScrollbar(frame, button_color=COLORS["panel_bg"], button_hover_color=COLORS["border"])
        scroll_y.pack(side="right", fill="y")
        
        tree = ttk.Treeview(frame, yscrollcommand=scroll_y.set, show="headings", selectmode="browse")
        tree.pack(fill="both", expand=True)
        scroll_y.configure(command=tree.yview)
        return tree

    def refresh_data(self):
        if not self.controller.db_path.exists(): return
        
        # Clear
        for t in [self.tree_users, self.tree_posts, self.tree_trends]:
            for i in t.get_children(): t.delete(i)
            
        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            cur = conn.cursor()
            
            # Users
            cur.execute("SELECT platform, username, followers_count FROM users")
            self.tree_users['columns'] = ("Platform", "Username", "Followers")
            for c in self.tree_users['columns']: 
                self.tree_users.heading(c, text=c, anchor="w")
                self.tree_users.column(c, width=150)
            for r in cur.fetchall(): self.tree_users.insert("", "end", values=r)
            
            # Posts
            cur.execute("SELECT platform, text_content, likes_count FROM posts ORDER BY scraped_at DESC LIMIT 50")
            self.tree_posts['columns'] = ("Plat.", "Text", "Likes")
            self.tree_posts.heading("Plat.", text="Plat."); self.tree_posts.column("Plat.", width=50)
            self.tree_posts.heading("Text", text="Text"); self.tree_posts.column("Text", width=400)
            self.tree_posts.heading("Likes", text="Likes"); self.tree_posts.column("Likes", width=80)
            for r in cur.fetchall():
                tx = r[1][:60] + "..." if r[1] and len(r[1]) > 60 else r[1]
                self.tree_posts.insert("", "end", values=(r[0], tx, r[2]))
                
            # Trends
            cur.execute("SELECT rank, topic_name, post_count FROM trending ORDER BY rank ASC")
            self.tree_trends['columns'] = ("#", "Téma", "Objem")
            for c in self.tree_trends['columns']: self.tree_trends.heading(c, text=c, anchor="w")
            for r in cur.fetchall(): self.tree_trends.insert("", "end", values=r)
            
            conn.close()
        except Exception as e:
            print(f"[DB ERROR] {e}")