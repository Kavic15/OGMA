# src/gui/frames/sessions.py
"""
SessionsFrame — přehled a porovnání jednotlivých běhů scrapingu.

Záložky:
  Historie    — tabulka všech sessionů, řaditelná, s barevným kódováním
  Porovnání   — sloupcový graf pro vybrané metriky (výběr ze seznamu)
  Export      — export do CSV pro použití v diplomové práci
"""

import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from src.gui.theme import COLORS


# ── Helpers ────────────────────────────────────────────────────────────

def _fmt_bytes(b):
    if b is None: return "—"
    b = float(b)
    if b < 1024:       return f"{b:.0f} B"
    elif b < 1024**2:  return f"{b/1024:.1f} KB"
    else:              return f"{b/1024**2:.1f} MB"

def _fmt_dur(s):
    if s is None: return "—"
    s = int(s)
    m, sec = divmod(s, 60)
    return f"{m}m {sec:02d}s"

def _db_path():
    return Path(__file__).resolve().parent.parent.parent.parent / "data" / "osint.db"


# ── Hlavní frame ───────────────────────────────────────────────────────

class SessionsFrame(ctk.CTkFrame):

    COLUMNS = [
        # (db_col,            header,           width, fmt)
        ("started_at",        "Datum",           115,  lambda v: v[:16].replace("T"," ") if v else "—"),
        ("platform",          "Platforma",        75,  None),
        ("target_username",   "Cíl",             120,  None),
        ("duration_s",        "Délka",            70,  _fmt_dur),
        ("posts_scraped",     "Příspěvky",        80,  None),
        ("comments_scraped",  "Komentáře",        80,  None),
        ("followers_scraped", "Sledující",        80,  None),
        ("posts_per_min",     "P/min",            60,  lambda v: f"{v:.1f}" if v else "0"),
        ("comments_per_min",  "K/min",            60,  lambda v: f"{v:.1f}" if v else "0"),
        ("rx_bytes_total",    "Staženo",          80,  _fmt_bytes),
        ("tx_bytes_total",    "Odesláno",         80,  _fmt_bytes),
        ("rx_bytes_per_post", "B/příspěvek",      90,  _fmt_bytes),
        ("search_method",     "Metoda hledání",  110,  None),
        ("error_count",       "Chyby",            55,  None),
        ("was_interrupted",   "Přerušeno",        75,  lambda v: "Ano" if v else "Ne"),
    ]

    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self._all_rows  = []   # surová data z DB
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Nadpis + tlačítka
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text="Historie běhů", font=("Segoe UI", 24, "bold"),
                     text_color=COLORS["text_main"]).pack(side="left")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="Obnovit", width=80, height=30,
                      fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
                      text_color=COLORS["text_dim"], font=("Segoe UI", 12),
                      command=self.refresh_data).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_frame, text="Export CSV", width=95, height=30,
                      fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                      text_color="white", font=("Segoe UI", 12),
                      command=self._export_csv).pack(side="left")

        # Záložky
        self._tabs = ctk.CTkTabview(
            self, fg_color="transparent",
            segmented_button_fg_color=COLORS["panel_bg"],
            segmented_button_selected_color=COLORS["primary"],
            segmented_button_selected_hover_color=COLORS["primary_hover"],
            segmented_button_unselected_color=COLORS["panel_bg"],
            segmented_button_unselected_hover_color=COLORS["border"],
        )
        self._tabs.pack(fill="both", expand=True)
        self._tabs.add("Historie")
        self._tabs.add("Porovnání")
        self._tabs.add("Souhrn")

        self._build_history_tab(self._tabs.tab("Historie"))
        self._build_compare_tab(self._tabs.tab("Porovnání"))
        self._build_summary_tab(self._tabs.tab("Souhrn"))

    # ------------------------------------------------------------------
    # Záložka: Historie
    # ------------------------------------------------------------------
    def _build_history_tab(self, tab):
        # Ttk styl pro tmavé pozadí
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Sessions.Treeview",
                        background=COLORS["panel_bg"],
                        foreground=COLORS["text_main"],
                        fieldbackground=COLORS["panel_bg"],
                        rowheight=26,
                        font=("Segoe UI", 11))
        style.configure("Sessions.Treeview.Heading",
                        background=COLORS["main_bg"],
                        foreground=COLORS["text_dim"],
                        font=("Segoe UI", 10, "bold"),
                        relief="flat")
        style.map("Sessions.Treeview",
                  background=[("selected", COLORS["primary"])],
                  foreground=[("selected", "white")])

        cols = [c[0] for c in self.COLUMNS]
        self._tree = ttk.Treeview(tab, columns=cols, show="headings",
                                  style="Sessions.Treeview")

        for db_col, header, width, _ in self.COLUMNS:
            self._tree.heading(db_col, text=header,
                               command=lambda c=db_col: self._sort(c))
            self._tree.column(db_col, width=width, minwidth=40, anchor="center")

        # Scrollbary
        vsb = ttk.Scrollbar(tab, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tab, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Barevné tagy
        self._tree.tag_configure("ok",          background="#1a2a1a")
        self._tree.tag_configure("interrupted",  background="#2a1a1a")
        self._tree.tag_configure("errors",       background="#2a2a1a")

        # Detail při kliknutí
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail panel pod tabulkou
        self._detail_var = ctk.StringVar(value="Klikni na řádek pro detail.")
        ctk.CTkLabel(tab, textvariable=self._detail_var,
                     font=("Consolas", 11), text_color=COLORS["text_dim"],
                     wraplength=900, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------
    # Záložka: Porovnání (sloupcový graf přes tk.Canvas)
    # ------------------------------------------------------------------
    def _build_compare_tab(self, tab):
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        ctrl = ctk.CTkFrame(tab, fg_color="transparent")
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(ctrl, text="Metrika:", font=("Segoe UI", 12),
                     text_color=COLORS["text_dim"]).pack(side="left", padx=(0, 8))

        self._metric_var = ctk.StringVar(value="posts_per_min")
        metrics = [
            ("Příspěvky/min",   "posts_per_min"),
            ("Komentáře/min",   "comments_per_min"),
            ("Sledující/min",   "followers_per_min"),
            ("Staženo (KB)",    "rx_bytes_total"),
            ("Délka (s)",       "duration_s"),
            ("Chyby",           "error_count"),
            ("B/příspěvek",     "rx_bytes_per_post"),
        ]
        metric_labels = [m[0] for m in metrics]
        self._metric_map = {m[0]: m[1] for m in metrics}

        combo = ctk.CTkComboBox(ctrl, values=metric_labels,
                                variable=ctk.StringVar(value="Příspěvky/min"),
                                width=180, height=30,
                                fg_color=COLORS["panel_bg"],
                                border_color=COLORS["border"],
                                text_color=COLORS["text_main"],
                                command=lambda v: self._draw_chart())
        combo.pack(side="left")
        self._metric_combo = combo

        ctk.CTkButton(ctrl, text="Překreslit", width=90, height=30,
                      fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
                      text_color=COLORS["text_dim"], font=("Segoe UI", 12),
                      command=self._draw_chart).pack(side="left", padx=8)

        self._chart = tk.Canvas(tab, bg=COLORS["main_bg"],
                                highlightthickness=0, bd=0)
        self._chart.grid(row=1, column=0, sticky="nsew")
        self._chart.bind("<Configure>", lambda e: self._draw_chart())

    # ------------------------------------------------------------------
    # Záložka: Souhrn
    # ------------------------------------------------------------------
    def _build_summary_tab(self, tab):
        self._summary_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self._summary_frame.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def refresh_data(self):
        try:
            conn = sqlite3.connect(str(_db_path()), timeout=5)
            cur  = conn.cursor()
            cur.execute("""
                SELECT session_id, platform, bot_identity, target_username,
                       started_at, finished_at, duration_s,
                       posts_scraped, comments_scraped,
                       followers_scraped, following_scraped,
                       posts_per_min, comments_per_min, followers_per_min,
                       rx_bytes_total, tx_bytes_total,
                       rx_bytes_per_post, bytes_per_comment,
                       search_method, profile_found, error_count,
                       was_interrupted, headless,
                       limit_posts, limit_comments,
                       limit_followers, limit_following, notes
                FROM scrape_sessions
                ORDER BY started_at DESC
            """)
            self._all_rows = cur.fetchall()
            conn.close()
        except Exception as e:
            self._all_rows = []
            print(f"[SESSIONS] Chyba načítání: {e}")

        self._populate_tree()
        self._draw_chart()
        self._populate_summary()

    def _populate_tree(self):
        self._tree.delete(*self._tree.get_children())

        col_indices = {
            "session_id": 0, "platform": 1, "bot_identity": 2,
            "target_username": 3, "started_at": 4, "finished_at": 5,
            "duration_s": 6, "posts_scraped": 7, "comments_scraped": 8,
            "followers_scraped": 9, "following_scraped": 10,
            "posts_per_min": 11, "comments_per_min": 12, "followers_per_min": 13,
            "rx_bytes_total": 14, "tx_bytes_total": 15,
            "rx_bytes_per_post": 16, "bytes_per_comment": 17,
            "search_method": 18, "profile_found": 19, "error_count": 20,
            "was_interrupted": 21, "headless": 22,
            "limit_posts": 23, "limit_comments": 24,
            "limit_followers": 25, "limit_following": 26, "notes": 27,
        }

        for row in self._all_rows:
            values = []
            for db_col, _, _, fmt in self.COLUMNS:
                raw = row[col_indices[db_col]]
                values.append(fmt(raw) if fmt else (raw if raw is not None else "—"))

            interrupted = row[col_indices["was_interrupted"]]
            errors      = row[col_indices["error_count"]]
            tag = "interrupted" if interrupted else ("errors" if errors > 0 else "ok")
            self._tree.insert("", "end", values=values, tags=(tag,),
                              iid=row[0])  # session_id jako iid

    def _on_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        sid = sel[0]
        row = next((r for r in self._all_rows if r[0] == sid), None)
        if not row:
            return

        dur  = _fmt_dur(row[6])
        rx   = _fmt_bytes(row[14])
        tx   = _fmt_bytes(row[15])
        note = row[27] or "—"

        self._detail_var.set(
            f"Session: {sid[:8]}…  |  Bot: {row[2]}  |  Cíl: {row[3]}  |  "
            f"Platforma: {row[1]}  |  Délka: {dur}  |  "
            f"P:{row[7]} K:{row[8]} Sl:{row[9]}  |  "
            f"P/min: {row[11]:.1f}  K/min: {row[12]:.1f}  |  "
            f"RX: {rx}  TX: {tx}  |  "
            f"Metoda: {row[18]}  |  Chyby: {row[20]}  |  Poznámka: {note}"
        )

    # ------------------------------------------------------------------
    # Graf
    # ------------------------------------------------------------------
    def _draw_chart(self):
        c = self._chart
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1 or not self._all_rows:
            return

        label_str = self._metric_combo.get()
        db_col    = self._metric_map.get(label_str, "posts_per_min")

        col_idx = {
            "posts_per_min": 11, "comments_per_min": 12, "followers_per_min": 13,
            "rx_bytes_total": 14, "duration_s": 6, "error_count": 20,
            "rx_bytes_per_post": 16,
        }
        idx = col_idx.get(db_col, 11)

        # Posledních 20 sessionů (chronologicky)
        rows = list(reversed(self._all_rows[:20]))
        values = [float(r[idx] or 0) for r in rows]
        peak   = max(values) or 1

        pad_l, pad_r, pad_t, pad_b = 40, 20, 20, 50
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b
        bar_w   = max(4, chart_w // max(len(rows), 1) - 4)

        COLORS_BAR = ["#175DDC", "#2eb85c", "#e0a040", "#9b59b6",
                      "#5a9bd4", "#e05252", "#175DDC"]

        for i, (row, val) in enumerate(zip(rows, values)):
            x0 = pad_l + i * (chart_w // len(rows))
            bar_h = int((val / peak) * chart_h)
            y0 = pad_t + chart_h - bar_h
            y1 = pad_t + chart_h

            color = "#e05252" if row[21] else COLORS_BAR[i % len(COLORS_BAR)]
            c.create_rectangle(x0, y0, x0 + bar_w, y1,
                               fill=color, outline="", width=0)

            # Hodnota nad sloupcem
            display = f"{val/1024:.0f}KB" if "bytes" in db_col and val > 1024 else f"{val:.1f}"
            c.create_text(x0 + bar_w // 2, y0 - 4,
                          text=display, fill=COLORS["text_dim"],
                          font=("Segoe UI", 8), anchor="s")

            # Popisek pod (datum + cíl)
            label = f"{row[4][5:10]}\n{row[3][:10]}"
            c.create_text(x0 + bar_w // 2, y1 + 6,
                          text=label, fill=COLORS["text_dim"],
                          font=("Segoe UI", 8), anchor="n")

        # Y osa
        c.create_line(pad_l, pad_t, pad_l, pad_t + chart_h,
                      fill=COLORS["border"], width=1)
        for pct in [0, 0.25, 0.5, 0.75, 1.0]:
            y = pad_t + chart_h - int(pct * chart_h)
            val_label = f"{peak * pct:.1f}"
            c.create_text(pad_l - 4, y, text=val_label,
                          fill=COLORS["text_dim"], font=("Segoe UI", 8), anchor="e")
            c.create_line(pad_l, y, pad_l + chart_w, y,
                          fill=COLORS["border"], width=1, dash=(2, 4))

    # ------------------------------------------------------------------
    # Souhrn
    # ------------------------------------------------------------------
    def _populate_summary(self):
        for w in self._summary_frame.winfo_children():
            w.destroy()

        if not self._all_rows:
            ctk.CTkLabel(self._summary_frame, text="Žádné session.",
                         text_color=COLORS["text_dim"]).pack()
            return

        total   = len(self._all_rows)
        ok      = sum(1 for r in self._all_rows if not r[21])
        inter   = total - ok
        avg_dur = sum(r[6] or 0 for r in self._all_rows) / total
        avg_ppm = sum(r[11] or 0 for r in self._all_rows) / total
        avg_kpm = sum(r[12] or 0 for r in self._all_rows) / total
        tot_rx  = sum(r[14] or 0 for r in self._all_rows)
        tot_err = sum(r[20] or 0 for r in self._all_rows)

        # Nejrychlejší session
        best_p  = max(self._all_rows, key=lambda r: r[11] or 0)
        best_k  = max(self._all_rows, key=lambda r: r[12] or 0)

        stats = [
            ("Celkem běhů",              str(total)),
            ("Dokončeno / přerušeno",    f"{ok} / {inter}"),
            ("Průměrná délka",           _fmt_dur(avg_dur)),
            ("Průměrně příspěvků/min",   f"{avg_ppm:.2f}"),
            ("Průměrně komentářů/min",   f"{avg_kpm:.2f}"),
            ("Celkem staženo",           _fmt_bytes(tot_rx)),
            ("Celkem chyb",              str(tot_err)),
            ("Nejrychlejší P/min",       f"{best_p[11]:.2f}  ({best_p[3]} @ {best_p[4][:10]})"),
            ("Nejrychlejší K/min",       f"{best_k[12]:.2f}  ({best_k[3]} @ {best_k[4][:10]})"),
        ]

        # Skupiny podle platformy
        platforms = sorted(set(r[1] for r in self._all_rows))
        for plat in platforms:
            plat_rows = [r for r in self._all_rows if r[1] == plat]
            avg_p = sum(r[11] or 0 for r in plat_rows) / len(plat_rows)
            avg_k = sum(r[12] or 0 for r in plat_rows) / len(plat_rows)
            stats.append((f"{plat} — průměr P/min", f"{avg_p:.2f}"))
            stats.append((f"{plat} — průměr K/min", f"{avg_k:.2f}"))
            stats.append((f"{plat} — počet běhů",   str(len(plat_rows))))

        for label, value in stats:
            row = ctk.CTkFrame(self._summary_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 12),
                         text_color=COLORS["text_dim"], width=260,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=("Segoe UI", 12, "bold"),
                         text_color=COLORS["text_main"], anchor="w").pack(side="left")

    # ------------------------------------------------------------------
    # Export CSV
    # ------------------------------------------------------------------
    def _export_csv(self):
        if not self._all_rows:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"ogma_sessions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        )
        if not path:
            return

        all_cols = [
            "session_id", "platform", "bot_identity", "target_username",
            "started_at", "finished_at", "duration_s",
            "posts_scraped", "comments_scraped",
            "followers_scraped", "following_scraped",
            "posts_per_min", "comments_per_min", "followers_per_min",
            "rx_bytes_total", "tx_bytes_total",
            "rx_bytes_per_post", "bytes_per_comment",
            "search_method", "profile_found", "error_count",
            "was_interrupted", "headless",
            "limit_posts", "limit_comments",
            "limit_followers", "limit_following", "notes",
        ]

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(all_cols)
                writer.writerows(self._all_rows)
            print(f"[SESSIONS] Export dokončen: {path}")
        except Exception as e:
            print(f"[SESSIONS] Export selhal: {e}")

    # ------------------------------------------------------------------
    def _sort(self, col):
        """Řazení po kliknutí na hlavičku sloupce."""
        col_idx = {c[0]: i for i, c in enumerate(self.COLUMNS)}
        idx = col_idx.get(col, 0)
        self._all_rows.sort(
            key=lambda r: (r[idx] is None, r[idx]),
            reverse=getattr(self, f"_sort_rev_{col}", False)
        )
        setattr(self, f"_sort_rev_{col}",
                not getattr(self, f"_sort_rev_{col}", False))
        self._populate_tree()
