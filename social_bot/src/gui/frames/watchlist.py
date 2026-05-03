"""
src/gui/frames/watchlist.py
"""

import customtkinter as ctk
from datetime import datetime
from src.core.database import DatabaseManager


COLORS = {
    "bg":        "#1a1a2e",
    "surface":   "#16213e",
    "border":    "#2a2a4a",
    "accent":    "#175DDC",
    "text_main": "#e0e0e0",
    "text_dim":  "#888",
    "danger":    "#e05252",
    "success":   "#2eb85c",
}


class WatchlistFrame(ctk.CTkFrame):
    def __init__(self, parent, scheduler, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], **kwargs)
        self.scheduler = scheduler
        self.db = DatabaseManager()
        self._build_ui()
        self._refresh_list()

        # Pravidelný refresh statusu
        self._tick()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # ---- Horní panel: přidání účtu ----
        add_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                                 corner_radius=10)
        add_frame.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(add_frame, text="Přidat účet do watchlistu",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_main"]).pack(anchor="w", padx=14, pady=(10, 6))

        fields = ctk.CTkFrame(add_frame, fg_color="transparent")
        fields.pack(fill="x", padx=14, pady=(0, 10))

        # Username
        ctk.CTkLabel(fields, text="Uživatelské jméno:",
                     text_color=COLORS["text_dim"],
                     font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=(0,8))
        self._entry_username = ctk.CTkEntry(fields, width=180,
                                            placeholder_text="např. nasa")
        self._entry_username.grid(row=0, column=1, padx=(0, 16))

        # Interval
        ctk.CTkLabel(fields, text="Interval (min):",
                     text_color=COLORS["text_dim"],
                     font=("Segoe UI", 12)).grid(row=0, column=2, sticky="w", padx=(0,8))
        self._entry_interval = ctk.CTkEntry(fields, width=70)
        self._entry_interval.insert(0, "20")
        self._entry_interval.grid(row=0, column=3, padx=(0, 16))

        # Limity
        for col, (label, default, attr) in enumerate([
            ("Příspěvky", "10",  "_entry_lp"),
            ("Komentáře", "50",  "_entry_lc"),
            ("Sledující",  "0",  "_entry_lf"),
            ("Sledovaní",  "0",  "_entry_lfol"),
        ], start=4):
            ctk.CTkLabel(fields, text=f"{label}:",
                         text_color=COLORS["text_dim"],
                         font=("Segoe UI", 12)).grid(row=0, column=col*2, sticky="w", padx=(0,4))
            e = ctk.CTkEntry(fields, width=55)
            e.insert(0, default)
            e.grid(row=0, column=col*2+1, padx=(0, 12))
            setattr(self, attr, e)

        ctk.CTkButton(fields, text="+ Přidat", width=90,
                      fg_color=COLORS["accent"],
                      command=self._add_entry).grid(row=0, column=13, padx=(8, 0))

        # ---- Scheduler controls ----
        ctrl_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                                  corner_radius=10)
        ctrl_frame.pack(fill="x", padx=16, pady=(0, 8))

        inner = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        self._btn_start = ctk.CTkButton(
            inner, text="▶  Spustit scheduler", width=160,
            fg_color=COLORS["success"], command=self._toggle_scheduler)
        self._btn_start.pack(side="left", padx=(0, 12))

        self._lbl_status = ctk.CTkLabel(
            inner, text="Scheduler: zastaven",
            text_color=COLORS["text_dim"], font=("Segoe UI", 12))
        self._lbl_status.pack(side="left")

        # ---- Tabulka watchlistu ----
        list_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                                  corner_radius=10)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        ctk.CTkLabel(list_frame, text="Sledované účty",
                     font=("Segoe UI", 14, "bold"),
                     text_color=COLORS["text_main"]).pack(anchor="w", padx=14, pady=(10, 4))

        # Scrollable list
        self._scroll = ctk.CTkScrollableFrame(
            list_frame, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._rows = []  # seznam widgetů

    # ------------------------------------------------------------------
    # Logika
    # ------------------------------------------------------------------
    def _add_entry(self):
        username = self._entry_username.get().strip().lstrip("@")
        if not username:
            return

        try:
            interval = int(self._entry_interval.get())
            lp   = int(self._entry_lp.get())
            lc   = int(self._entry_lc.get())
            lf   = int(self._entry_lf.get())
            lfol = int(self._entry_lfol.get())
        except ValueError:
            return

        try:
            self.db.cursor.execute('''
                INSERT OR IGNORE INTO watchlist
                    (platform, username, interval_min,
                     limit_posts, limit_comments, limit_followers, limit_following)
                VALUES ('IG', ?, ?, ?, ?, ?, ?)
            ''', (username, interval, lp, lc, lf, lfol))
            self.db.conn.commit()
            self._entry_username.delete(0, "end")
            self._refresh_list()
        except Exception as e:
            print(f"[WATCHLIST] Chyba přidávání: {e}")

    def _toggle_scheduler(self):
        if self.scheduler.is_running():
            self.scheduler.stop()
        else:
            self.scheduler.start()
        self._update_status()

    def _toggle_entry(self, row_id, enabled):
        self.db.cursor.execute(
            "UPDATE watchlist SET enabled=? WHERE id=?",
            (0 if enabled else 1, row_id))
        self.db.conn.commit()
        self._refresh_list()

    def _delete_entry(self, row_id):
        self.db.cursor.execute("DELETE FROM watchlist WHERE id=?", (row_id,))
        self.db.conn.commit()
        self._refresh_list()

    def _update_interval(self, row_id, value):
        try:
            self.db.cursor.execute(
                "UPDATE watchlist SET interval_min=?, next_scrape_at=NULL WHERE id=?",
                (int(value), row_id))
            self.db.conn.commit()
        except:
            pass

    # ------------------------------------------------------------------
    # Refresh GUI
    # ------------------------------------------------------------------
    def _refresh_list(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        self.db.cursor.execute('''
            SELECT id, username, interval_min, enabled,
                   last_scraped_at, next_scrape_at,
                   limit_posts, limit_comments, limit_followers, limit_following
            FROM watchlist ORDER BY added_at DESC
        ''')
        rows = self.db.cursor.fetchall()

        if not rows:
            ctk.CTkLabel(self._scroll, text="Žádné sledované účty.",
                         text_color=COLORS["text_dim"]).pack(pady=20)
            return

        # Hlavička
        hdr = ctk.CTkFrame(self._scroll, fg_color=COLORS["border"], corner_radius=6)
        hdr.pack(fill="x", pady=(0, 4))
        for col, (text, w) in enumerate([
            ("Uživatel", 160), ("Interval", 90), ("P/K/S/Sl", 120),
            ("Poslední scrape", 140), ("Další scrape", 140),
            ("Stav", 60), ("", 120)
        ]):
            ctk.CTkLabel(hdr, text=text, width=w,
                         font=("Segoe UI", 11, "bold"),
                         text_color=COLORS["text_dim"]).grid(
                row=0, column=col, padx=6, pady=4, sticky="w")

        for row in rows:
            row_id, username, interval, enabled, last_at, next_at, lp, lc, lf, lfol = row
            self._build_row(row_id, username, interval, enabled,
                            last_at, next_at, lp, lc, lf, lfol)

    def _build_row(self, row_id, username, interval, enabled,
                   last_at, next_at, lp, lc, lf, lfol):
        frame = ctk.CTkFrame(self._scroll, fg_color=COLORS["surface"],
                             corner_radius=6)
        frame.pack(fill="x", pady=2)

        # Username
        ctk.CTkLabel(frame, text=f"@{username}", width=160,
                     font=("Segoe UI", 12, "bold"),
                     text_color=COLORS["text_main"],
                     anchor="w").grid(row=0, column=0, padx=8, pady=6, sticky="w")

        # Interval (editovatelný)
        interval_var = ctk.StringVar(value=str(interval))
        interval_entry = ctk.CTkEntry(frame, textvariable=interval_var,
                                      width=60, justify="center")
        interval_entry.grid(row=0, column=1, padx=4)
        ctk.CTkLabel(frame, text="min", text_color=COLORS["text_dim"],
                     font=("Segoe UI", 11)).grid(row=0, column=1, padx=(68, 0))
        interval_entry.bind("<FocusOut>",
            lambda e, rid=row_id, v=interval_var: self._update_interval(rid, v.get()))

        # Limity
        ctk.CTkLabel(frame, text=f"{lp} / {lc} / {lf} / {lfol}",
                     width=120, text_color=COLORS["text_dim"],
                     font=("Segoe UI", 11)).grid(row=0, column=2, padx=4)

        # Časy
        last_str = last_at[11:16] if last_at else "nikdy"
        next_str = next_at[11:16] if next_at else "ihned"
        ctk.CTkLabel(frame, text=last_str, width=140,
                     text_color=COLORS["text_dim"],
                     font=("Segoe UI", 11)).grid(row=0, column=3, padx=4)
        ctk.CTkLabel(frame, text=next_str, width=140,
                     text_color=COLORS["accent"] if next_at else COLORS["success"],
                     font=("Segoe UI", 11)).grid(row=0, column=4, padx=4)

        # Enable/disable
        state_color = COLORS["success"] if enabled else COLORS["text_dim"]
        state_text  = "ON" if enabled else "OFF"
        ctk.CTkLabel(frame, text=state_text, width=60,
                     text_color=state_color,
                     font=("Segoe UI", 11, "bold")).grid(row=0, column=5, padx=4)

        # Akce
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=0, column=6, padx=8)

        ctk.CTkButton(btn_frame,
                      text="Pause" if enabled else "Resume",
                      width=60, height=26,
                      fg_color=COLORS["border"],
                      command=lambda rid=row_id, en=enabled:
                          self._toggle_entry(rid, en)).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame, text="✕", width=30, height=26,
                      fg_color=COLORS["danger"],
                      command=lambda rid=row_id:
                          self._delete_entry(rid)).pack(side="left", padx=2)

    def _update_status(self):
        if self.scheduler.is_running():
            target = self.scheduler.get_current_target()
            status = f"Scheduler: běží  |  Právě: @{target}" if target else "Scheduler: běží  |  Čeká na další cíl"
            self._btn_start.configure(text="⏹  Zastavit", fg_color=COLORS["danger"])
            self._lbl_status.configure(text=status, text_color=COLORS["success"])
        else:
            self._btn_start.configure(text="▶  Spustit scheduler", fg_color=COLORS["success"])
            self._lbl_status.configure(text="Scheduler: zastaven", text_color=COLORS["text_dim"])

    def _tick(self):
        self._update_status()
        self.after(5000, self._tick)  # refresh statusu každých 5s