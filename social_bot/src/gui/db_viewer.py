import customtkinter as ctk
from tkinter import ttk
import sqlite3
from pathlib import Path

class DatabaseViewer(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Prohlížeč Databáze - osint.db")
        self.geometry("1000x600")
        
        # Stylování standardního Tkinter Treeview do tmavého režimu
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        rowheight=25, 
                        fieldbackground="#2b2b2b",
                        bordercolor="#343638",
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", 
                        background="#565b5e", 
                        foreground="white", 
                        relief="flat")
        style.map("Treeview.Heading", background=[('active', '#343638')])

        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.db_path = project_root / 'data' / 'osint.db'

        # Přepínání tabulek
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        self.tabview.add("Uživatelé (Users)")
        self.tabview.add("Příspěvky (Posts)")

        self.users_tree = self.create_treeview(self.tabview.tab("Uživatelé (Users)"))
        self.posts_tree = self.create_treeview(self.tabview.tab("Příspěvky (Posts)"))

        self.load_data()

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

    def load_data(self):
        if not self.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Načtení uživatelů
            cursor.execute("SELECT id, platform, username, display_name, followers_count, last_scraped FROM users")
            users_rows = cursor.fetchall()
            
            self.users_tree['columns'] = ("ID", "Platform", "Username", "Display Name", "Followers", "Last Scraped")
            self.users_tree.column("#0", width=0, stretch="no")
            for col in self.users_tree['columns']:
                self.users_tree.column(col, anchor="w", width=150)
                self.users_tree.heading(col, text=col, anchor="w")

            for row in users_rows:
                self.users_tree.insert("", "end", values=row)

            # Načtení příspěvků
            cursor.execute("SELECT id, platform_post_id, text_content, likes_count, timestamp_posted, scraped_at FROM posts")
            posts_rows = cursor.fetchall()

            self.posts_tree['columns'] = ("ID", "Post ID", "Text", "Likes", "Posted At", "Scraped At")
            self.posts_tree.column("#0", width=0, stretch="no")
            for col in self.posts_tree['columns']:
                self.posts_tree.column(col, anchor="w", width=150)
                self.posts_tree.heading(col, text=col, anchor="w")

            for row in posts_rows:
                # Oříznutí textu, aby tabulka nebyla moc široká
                row_list = list(row)
                if row_list[2] and len(row_list[2]) > 50:
                    row_list[2] = row_list[2][:47] + "..."
                self.posts_tree.insert("", "end", values=row_list)

            conn.close()
        except Exception as e:
            print(f"Chyba při načítání databáze: {e}")