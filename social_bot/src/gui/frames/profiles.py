# src/gui/frames/profiles.py
import customtkinter as ctk
import threading
import sqlite3
import tkinter as tk
from tkinter import Canvas
from src.gui.theme import COLORS
from src.gui.utils import AsyncImageLoader

PAGE_SIZE = 10  # Počet karet na stránku

# Možnosti řazení: (popisek, klíč v dict, reverse)
SORT_OPTIONS = [
    ("Sledující ↓",       "followers_count",  True),
    ("Sledující ↑",       "followers_count",  False),
    ("Sleduje ↓",         "following_count",  True),
    ("Sleduje ↑",         "following_count",  False),
    ("Naposledy scraped", "last_scraped",      True),
    ("Přidáno nejdřív",   "last_scraped",      False),
]


class ProfilesFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.all_profiles_data = []
        self._rendered_count   = 0
        self.image_loader      = AsyncImageLoader()
        self._sentiment_cache  = {}
        self._stats_cache      = {}
        self._active_platform  = "Vše"
        self._active_sort_idx  = 0
        self.filtered_data     = []
        self._platform_buttons = {}
        self._show_more_btn    = None
        self.setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Řádek 0: Nadpis + počítadlo + vyhledávání ──────────────────
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(
            top_bar, text="Nalezené Profily",
            font=("Segoe UI", 24, "bold"), text_color=COLORS["text_main"]
        ).pack(side="left")

        self.counter_label = ctk.CTkLabel(
            top_bar, text="", font=("Segoe UI", 13), text_color=COLORS["text_dim"]
        )
        self.counter_label.pack(side="left", padx=(15, 0))

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self._on_filter_change)

        ctk.CTkEntry(
            top_bar, textvariable=self.search_var, width=280, height=34,
            corner_radius=20, placeholder_text="🔍 Hledat jméno nebo @handle...",
            fg_color=COLORS["panel_bg"], border_color=COLORS["border"],
            text_color="white"
        ).pack(side="right")

        # ── Řádek 1: Filtr platforma + řazení ──────────────────────────
        self.filter_bar = ctk.CTkFrame(self, fg_color=COLORS["panel_bg"],
                                        corner_radius=8, height=44)
        self.filter_bar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.filter_bar.grid_propagate(False)

        # Platforma — label
        ctk.CTkLabel(
            self.filter_bar, text="Platforma:",
            font=("Segoe UI", 11), text_color=COLORS["text_dim"]
        ).pack(side="left", padx=(14, 6), pady=10)

        # Tlačítko "Vše"
        btn_vse = ctk.CTkButton(
            self.filter_bar, text="Vše",
            width=46, height=26, corner_radius=6,
            font=("Segoe UI", 11, "bold"),
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            border_width=1, border_color=COLORS["border"], text_color="white",
            command=lambda: self._set_platform("Vše")
        )
        btn_vse.pack(side="left", padx=3, pady=9)
        self._platform_buttons["Vše"] = btn_vse

        # Oddělovač
        ctk.CTkFrame(self.filter_bar, width=1, height=24,
                     fg_color=COLORS["border"]).pack(side="left", padx=12, pady=10)

        # Řazení — label
        ctk.CTkLabel(
            self.filter_bar, text="Řadit:",
            font=("Segoe UI", 11), text_color=COLORS["text_dim"]
        ).pack(side="left", padx=(0, 6))

        self.sort_var = ctk.StringVar(value=SORT_OPTIONS[0][0])
        ctk.CTkOptionMenu(
            self.filter_bar,
            variable=self.sort_var,
            values=[o[0] for o in SORT_OPTIONS],
            width=190, height=28, corner_radius=6,
            fg_color=COLORS["panel_bg"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["primary"],
            dropdown_fg_color=COLORS["panel_bg"],
            dropdown_hover_color=COLORS["border"],
            text_color="white",
            font=("Segoe UI", 11),
            command=self._on_sort_change
        ).pack(side="left", padx=3, pady=8)

        # ── Řádek 2: Scrollovatelný seznam ──────────────────────────────
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self.scroll_frame.grid(row=2, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Načtení dat z DB
    # ------------------------------------------------------------------
    def refresh_data(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._rendered_count  = 0
        self._sentiment_cache = {}
        self._stats_cache     = {}

        if not self.controller.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            try:
                cur.execute("SELECT * FROM users ORDER BY last_scraped DESC")
            except Exception:
                cur.execute(
                    "SELECT id, platform, username, display_name, bio, "
                    "followers_count, following_count, profile_pic_url, last_scraped "
                    "FROM users ORDER BY last_scraped DESC"
                )
            self.all_profiles_data = [dict(row) for row in cur.fetchall()]

            # Dynamicky přidáme tlačítka platform které jsou v DB
            self._refresh_platform_buttons()

            # Sentiment cache
            for user in self.all_profiles_data:
                try:
                    cur.execute("""
                        SELECT COUNT(c.id), AVG(c.sentiment_score),
                               SUM(CASE WHEN c.sentiment_label='positive' THEN 1 ELSE 0 END),
                               SUM(CASE WHEN c.sentiment_label='neutral'  THEN 1 ELSE 0 END),
                               SUM(CASE WHEN c.sentiment_label='negative' THEN 1 ELSE 0 END)
                        FROM comments c JOIN posts p ON c.post_id = p.id
                        WHERE p.user_id = ? AND c.sentiment_score IS NOT NULL
                    """, (user["id"],))
                    row = cur.fetchone()
                    if row and row[0] and row[0] > 0:
                        self._sentiment_cache[user["id"]] = {
                            "total": row[0], "avg": round(row[1], 3) if row[1] else 0.0,
                            "pos": row[2] or 0, "neu": row[3] or 0, "neg": row[4] or 0,
                        }
                except Exception:
                    pass

            conn.close()
            self._on_filter_change()

        except Exception as e:
            print(f"[GUI ERROR] Chyba profilů: {e}")

    def _refresh_platform_buttons(self):
        """Zjistí platformy v DB; přidá tlačítka pro nové, odstraní prázdné."""
        seen  = {(str(u.get("platform") or "")).upper() for u in self.all_profiles_data}
        seen.discard("")
        known = set(self._platform_buttons.keys()) - {"Vše"}

        for plat in sorted(seen - known):
            btn = ctk.CTkButton(
                self.filter_bar, text=plat,
                width=46, height=26, corner_radius=6,
                font=("Segoe UI", 11, "bold"),
                fg_color="transparent", hover_color=COLORS["primary_hover"],
                border_width=1, border_color=COLORS["border"], text_color="white",
                command=lambda p=plat: self._set_platform(p)
            )
            # Vložit PŘED oddělovač (oddělovač je 3. widget od konce)
            btn.pack(side="left", padx=3, pady=9)
            self._platform_buttons[plat] = btn

        # Reset výběru pokud aktuální platforma zmizela z DB
        if self._active_platform not in ({"Vše"} | seen):
            self._active_platform = "Vše"

    # ------------------------------------------------------------------
    # Filtrování a řazení
    # ------------------------------------------------------------------
    def _set_platform(self, plat: str):
        self._active_platform = plat
        for p, btn in self._platform_buttons.items():
            btn.configure(
                fg_color=COLORS["primary"] if p == plat else "transparent"
            )
        self._on_filter_change()

    def _on_sort_change(self, _=None):
        label = self.sort_var.get()
        self._active_sort_idx = next(
            (i for i, o in enumerate(SORT_OPTIONS) if o[0] == label), 0
        )
        self._on_filter_change()

    def _on_filter_change(self, *args):
        query = self.search_var.get().lower()
        plat  = self._active_platform

        data = self.all_profiles_data

        # Filtr platformy
        if plat != "Vše":
            data = [u for u in data
                    if (str(u.get("platform") or "")).upper() == plat]

        # Fulltextové vyhledávání
        if query:
            data = [u for u in data
                    if query in (u.get("username") or "").lower()
                    or query in (u.get("display_name") or "").lower()]

        # Řazení
        _, field, reverse = SORT_OPTIONS[self._active_sort_idx]
        data = sorted(
            data,
            key=lambda u: (u.get(field) or 0) if field != "last_scraped"
                          else (u.get(field) or ""),
            reverse=reverse
        )

        self.filtered_data    = data
        self._rendered_count  = 0
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._render_next_page()

    # ------------------------------------------------------------------
    # Paginace
    # ------------------------------------------------------------------
    def _render_next_page(self):
        total = len(self.filtered_data)
        start = self._rendered_count
        end   = min(start + PAGE_SIZE, total)

        for user in self.filtered_data[start:end]:
            self.create_card(user)

        self._rendered_count = end
        self.counter_label.configure(text=f"Zobrazeno {self._rendered_count} z {total}")

        if self._show_more_btn:
            try: self._show_more_btn.destroy()
            except Exception: pass
            self._show_more_btn = None

        if self._rendered_count < total:
            remaining = total - self._rendered_count
            self._show_more_btn = ctk.CTkButton(
                self.scroll_frame,
                text=f"Načíst dalších {min(PAGE_SIZE, remaining)}  ↓",
                fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
                border_width=1, border_color=COLORS["border"],
                text_color=COLORS["text_dim"], font=("Segoe UI", 13),
                height=40, corner_radius=8, command=self._render_next_page
            )
            self._show_more_btn.pack(fill="x", pady=(8, 4), padx=4)
        else:
            if total > PAGE_SIZE:
                ctk.CTkLabel(
                    self.scroll_frame,
                    text=f"— Všechny profily načteny ({total}) —",
                    font=("Segoe UI", 11), text_color="#444"
                ).pack(pady=(8, 4))

    # ------------------------------------------------------------------
    # Karta profilu
    # ------------------------------------------------------------------
    def create_card(self, user):
        card = ctk.CTkFrame(
            self.scroll_frame, fg_color=COLORS["panel_bg"],
            corner_radius=12, border_color=COLORS["border"], border_width=1
        )
        card.pack(fill="x", pady=6, padx=4)
        card.grid_columnconfigure(1, weight=1)

        # Avatar
        img_widget = ctk.CTkLabel(card, text="", width=80, height=80,
                                   corner_radius=10, fg_color="#333")
        if user.get("profile_pic_url"):
            threading.Thread(
                target=self.image_loader.load_image,
                args=(user.get("profile_pic_url"), img_widget),
                daemon=True
            ).start()
        img_widget.grid(row=0, column=0, rowspan=2, padx=15, pady=(15, 5), sticky="n")

        # Jméno + verifikace + handle
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="nw", pady=(15, 0), padx=5)

        name_text = user.get("display_name") or user["username"]
        ctk.CTkLabel(info_frame, text=name_text,
                     font=("Segoe UI", 16, "bold"), text_color="white").pack(side="left")

        if user.get("is_verified") == 1:
            ctk.CTkLabel(info_frame, text="☑",
                         font=("Segoe UI", 16), text_color=COLORS["verified"]).pack(side="left", padx=(5, 0))

        handle_txt = f"@{user['username']} • {str(user.get('platform') or '').upper()}"
        ctk.CTkLabel(info_frame, text=handle_txt,
                     font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(10, 0))

        # Followers / Following
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.grid(row=1, column=1, sticky="nw", pady=(2, 0), padx=5)

        def fmt(n): return f"{n:,}".replace(",", " ") if n is not None else "0"

        ctk.CTkLabel(stats_frame, text=fmt(user.get("followers_count", 0)),
                     font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Followers",
                     font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(3, 15))
        ctk.CTkLabel(stats_frame, text=fmt(user.get("following_count", 0)),
                     font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]).pack(side="left")
        ctk.CTkLabel(stats_frame, text="Following",
                     font=("Segoe UI", 13), text_color=COLORS["text_dim"]).pack(side="left", padx=(3, 0))

        # Bio + metadata + last_scraped (dynamický blok bez prázdných řádků)
        bottom_parts = []
        bio = user.get("bio")
        if bio:
            bottom_parts.append(("bio", " ".join(bio.split())))
        meta = []
        if user.get("location"):    meta.append(f"📍 {user['location']}")
        if user.get("website"):     meta.append(f"🔗 {user['website']}")
        if user.get("joined_date"): meta.append(f"📅 {user['joined_date']}")
        if meta:
            bottom_parts.append(("meta", "   ".join(meta)))

        last_s = str(user.get("last_scraped", "")).split("T")[0] or "?"

        bottom_frame = ctk.CTkFrame(card, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, columnspan=3, sticky="ew",
                          padx=(110, 15), pady=(2, 10))
        bottom_frame.grid_columnconfigure(0, weight=1)

        r = 0
        for kind, text in bottom_parts:
            if kind == "bio":
                short = (text[:120] + "...") if len(text) > 120 else text
                ctk.CTkLabel(bottom_frame, text=short,
                             font=("Segoe UI", 12, "italic"), text_color="#b0b0b0",
                             anchor="w", justify="left", wraplength=800).grid(
                    row=r, column=0, columnspan=2, sticky="w", pady=(0, 2))
            else:
                ctk.CTkLabel(bottom_frame, text=text,
                             font=("Segoe UI", 11), text_color=COLORS["text_dim"],
                             anchor="w").grid(row=r, column=0, sticky="w")
            r += 1

        ctk.CTkLabel(bottom_frame, text=f"Upd: {last_s}",
                     font=("Segoe UI", 10), text_color="#555",
                     anchor="e").grid(row=max(r - 1, 0), column=1, sticky="e")

        # Sentiment widget
        sentiment_data = self._sentiment_cache.get(user["id"])
        if sentiment_data:
            self._add_sentiment_widget(card, sentiment_data)

        # Textová analytika (bez word cloud)
        self._add_expandable_stats(card, user)

    # ------------------------------------------------------------------
    # Rozbalitelná sekce — Textová analytika
    # ------------------------------------------------------------------
    def _add_expandable_stats(self, card, user):
        user_id = user["id"]

        ctk.CTkFrame(card, height=1, fg_color=COLORS["border"]).grid(
            row=6, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 0)
        )

        toggle_var    = tk.BooleanVar(value=False)
        content_frame = ctk.CTkFrame(card, fg_color=COLORS["main_bg"], corner_radius=8)

        toggle_btn = ctk.CTkButton(
            card,
            text="▶  Textová analytika  (hashtagy · zmínky · top slova)",
            fg_color="transparent", hover_color=COLORS["border"],
            text_color=COLORS["text_dim"], anchor="w",
            font=("Segoe UI", 12), height=34,
            command=lambda: self._toggle_stats(card, user_id, toggle_var, toggle_btn, content_frame)
        )
        toggle_btn.grid(row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=2)

    def _toggle_stats(self, card, user_id, toggle_var, toggle_btn, content_frame):
        if not toggle_var.get():
            toggle_var.set(True)
            toggle_btn.configure(text="▼  Textová analytika  (hashtagy · zmínky · top slova)")
            content_frame.grid(row=8, column=0, columnspan=3, sticky="ew", padx=15, pady=(4, 12))
            content_frame.grid_columnconfigure((0, 1, 2), weight=1)
            if user_id not in self._stats_cache:
                self._load_stats_async(user_id, content_frame)
            else:
                self._render_stats(content_frame, user_id)
        else:
            toggle_var.set(False)
            toggle_btn.configure(text="▶  Textová analytika  (hashtagy · zmínky · top slova)")
            content_frame.grid_forget()

    def _load_stats_async(self, user_id, content_frame):
        loading = ctk.CTkLabel(content_frame, text="⏳  Načítám data...",
                               font=("Segoe UI", 12), text_color=COLORS["text_dim"])
        loading.grid(row=0, column=0, columnspan=3, pady=15)

        def worker():
            try:
                from src.analysis.text_stats import TextStatsAnalyzer
                analyzer = TextStatsAnalyzer()
                stats    = analyzer.get_profile_stats(user_id, posts_limit=100, top_n=10)
                self._stats_cache[user_id] = stats
                self.after(0, lambda: self._render_stats(content_frame, user_id, "commenters"))
            except Exception as e:
                self.after(0, lambda err=e: loading.configure(text=f"Chyba: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def _render_stats(self, content_frame, user_id, active_tab="commenters"):
        for w in content_frame.winfo_children():
            w.destroy()

        stats = self._stats_cache.get(user_id, {})
        if not stats:
            ctk.CTkLabel(content_frame, text="Žádná data k zobrazení.",
                         font=("Segoe UI", 12), text_color=COLORS["text_dim"]).grid(
                row=0, column=0, columnspan=3, pady=10)
            return

        section = stats.get(active_tab, {})

        # Záložky
        tab_bar = ctk.CTkFrame(content_frame, fg_color="transparent")
        tab_bar.grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 4))

        owner_count   = stats.get("owner", {}).get("total_posts", 0)
        comment_count = stats.get("commenters", {}).get("total_comments", 0)

        for tab_key, tab_label in [
            ("owner",      f"Vlastník  ({owner_count} příspěvků)"),
            ("commenters", f"Komentující  ({comment_count} komentářů)"),
        ]:
            is_active = tab_key == active_tab
            ctk.CTkButton(
                tab_bar, text=tab_label, height=28,
                font=("Segoe UI", 11, "bold" if is_active else "normal"),
                fg_color=COLORS["border"] if is_active else "transparent",
                hover_color=COLORS["border"],
                text_color=COLORS["text_main"] if is_active else COLORS["text_dim"],
                corner_radius=6,
                command=lambda k=tab_key: self._render_stats(content_frame, user_id, k)
            ).pack(side="left", padx=(0, 6))

        # Tři sloupce
        data_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        data_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        data_frame.grid_columnconfigure((0, 1, 2), weight=1)

        for col_idx, (title, key, color) in enumerate([
            ("# HASHTAGY", "top_hashtags", "#175DDC"),
            ("@ ZMÍNKY",   "top_mentions", "#2eb85c"),
            ("TOP SLOVA",  "top_words",    "#9b59b6"),
        ]):
            frame = ctk.CTkFrame(data_frame, fg_color="transparent")
            frame.grid(row=0, column=col_idx, sticky="nw", padx=15, pady=(4, 12))
            ctk.CTkLabel(frame, text=title, font=("Segoe UI", 10, "bold"),
                         text_color=COLORS["text_dim"]).pack(anchor="w")
            items = section.get(key, [])
            if items:
                max_c = items[0][1]
                for label, count in items:
                    self._bar_row(frame, label, count, max_c, color)
            else:
                ctk.CTkLabel(frame, text="—", font=("Segoe UI", 11),
                             text_color=COLORS["text_dim"]).pack(anchor="w")

    def _bar_row(self, parent, label, count, max_count, color):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)
        short = label if len(label) <= 18 else label[:17] + "…"
        ctk.CTkLabel(row, text=short, font=("Segoe UI", 11),
                     text_color=COLORS["text_main"], width=130, anchor="w").pack(side="left")
        bar_width  = 60
        fill_width = max(2, int((count / max_count) * bar_width))
        bar_bg = Canvas(row, width=bar_width, height=10,
                        bg=COLORS["main_bg"], highlightthickness=0)
        bar_bg.pack(side="left", padx=(4, 4))
        bar_bg.create_rectangle(0, 2, fill_width, 8, fill=color, outline="")
        ctk.CTkLabel(row, text=str(count), font=("Segoe UI", 10),
                     text_color=COLORS["text_dim"]).pack(side="left")

    # ------------------------------------------------------------------
    # Sentiment widget
    # ------------------------------------------------------------------
    def _add_sentiment_widget(self, card, s):
        POS_COLOR = "#2eb85c"; NEU_COLOR = "#5a6370"; NEG_COLOR = "#e05252"
        total = s["total"]; pos = s["pos"]; neu = s["neu"]
        neg   = s["neg"];   avg = s["avg"]

        ctk.CTkFrame(card, height=1, fg_color=COLORS["border"]).grid(
            row=4, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 10))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.grid(row=5, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 8))
        row.grid_columnconfigure(1, weight=1)

        score_panel = ctk.CTkFrame(row, fg_color="transparent", width=90)
        score_panel.grid(row=0, column=0, sticky="nw", padx=(0, 15))
        score_panel.grid_propagate(False)

        ctk.CTkLabel(score_panel, text="SENTIMENT", font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w")

        if avg >= 0.05:    sc, sl = POS_COLOR, "pozitivní"
        elif avg <= -0.05: sc, sl = NEG_COLOR, "negativní"
        else:              sc, sl = NEU_COLOR, "neutrální"

        ctk.CTkLabel(score_panel, text=f"{avg:+.3f}", font=("Segoe UI", 20, "bold"),
                     text_color=sc).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(score_panel, text=sl, font=("Segoe UI", 11),
                     text_color=sc).pack(anchor="w")
        ctk.CTkLabel(score_panel, text=f"{total} komentářů", font=("Segoe UI", 10),
                     text_color=COLORS["text_dim"]).pack(anchor="w", pady=(4, 0))

        bar_panel = ctk.CTkFrame(row, fg_color="transparent")
        bar_panel.grid(row=0, column=1, sticky="nsew")
        bar_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(bar_panel, text="ROZLOŽENÍ KOMENTÁŘŮ", font=("Segoe UI", 9, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w")

        canvas = Canvas(bar_panel, height=22, bg=COLORS["panel_bg"],
                        highlightthickness=0, bd=0)
        canvas.pack(fill="x", pady=(4, 6))

        def draw_bar(event=None):
            canvas.delete("all")
            w = canvas.winfo_width()
            if w <= 1: canvas.after(50, draw_bar); return
            r = 6
            segments = [(pos, POS_COLOR), (neu, NEU_COLOR), (neg, NEG_COLOR)]
            x = 0; drawn = []
            for cnt, color in segments:
                if total > 0 and cnt > 0:
                    sw = max(int((cnt / total) * w), 1)
                    drawn.append((x, sw, color)); x += sw
            for i, (sx, sw, color) in enumerate(drawn):
                x0, y0, x1, y1 = sx, 0, sx + sw, 22
                fl = i == 0; la = i == len(drawn) - 1
                if fl and la:  _rounded_rect(canvas, x0, y0, x1, y1, r, color)
                elif fl:       _rounded_rect_left(canvas, x0, y0, x1, y1, r, color)
                elif la:       _rounded_rect_right(canvas, x0, y0, x1, y1, r, color)
                else:          canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

        canvas.bind("<Configure>", draw_bar)
        canvas.after(100, draw_bar)

        legend = ctk.CTkFrame(bar_panel, fg_color="transparent")
        legend.pack(fill="x")
        for lbl, cnt, color in [("Pozitivní", pos, POS_COLOR),
                                 ("Neutrální", neu, NEU_COLOR),
                                 ("Negativní", neg, NEG_COLOR)]:
            pct = round((cnt / total) * 100) if total > 0 else 0
            item = ctk.CTkFrame(legend, fg_color="transparent")
            item.pack(side="left", padx=(0, 18))
            dot = Canvas(item, width=8, height=8, bg=COLORS["panel_bg"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 4))
            dot.create_oval(0, 0, 8, 8, fill=color, outline="")
            ctk.CTkLabel(item, text=f"{lbl} {pct}% ({cnt})", font=("Segoe UI", 10),
                         text_color=COLORS["text_dim"]).pack(side="left")


# ------------------------------------------------------------------
# Canvas helpers
# ------------------------------------------------------------------
def _rounded_rect(canvas, x0, y0, x1, y1, r, color):
    canvas.create_arc(x0, y0, x0+2*r, y0+2*r, start=90,  extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y0, x1, y0+2*r, start=0,   extent=90,  fill=color, outline="")
    canvas.create_arc(x0, y1-2*r, x0+2*r, y1, start=180, extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y1-2*r, x1, y1, start=270, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=color, outline="")
    canvas.create_rectangle(x0, y0+r, x1, y1-r, fill=color, outline="")

def _rounded_rect_left(canvas, x0, y0, x1, y1, r, color):
    canvas.create_arc(x0, y0, x0+2*r, y0+2*r, start=90,  extent=90,  fill=color, outline="")
    canvas.create_arc(x0, y1-2*r, x0+2*r, y1, start=180, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0+r, y0, x1, y1,     fill=color, outline="")
    canvas.create_rectangle(x0, y0+r, x0+r, y1-r, fill=color, outline="")

def _rounded_rect_right(canvas, x0, y0, x1, y1, r, color):
    canvas.create_arc(x1-2*r, y0, x1, y0+2*r, start=0,   extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y1-2*r, x1, y1, start=270, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0, y0, x1-r, y1,     fill=color, outline="")
    canvas.create_rectangle(x1-r, y0+r, x1, y1-r, fill=color, outline="")