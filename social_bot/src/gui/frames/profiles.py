# src/gui/frames/profiles.py
import customtkinter as ctk
import threading
import sqlite3
import tkinter as tk
from tkinter import Canvas
from src.gui.theme import COLORS
from src.gui.utils import AsyncImageLoader

class ProfilesFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.all_profiles_data = []
        self.image_loader = AsyncImageLoader()
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top Bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        ctk.CTkLabel(
            top_bar, text="Nalezené Profily",
            font=("Segoe UI", 24, "bold"),
            text_color=COLORS["text_main"]
        ).pack(side="left")

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self.filter_profiles)

        search_entry = ctk.CTkEntry(
            top_bar, textvariable=self.search_var, width=300, height=35,
            corner_radius=20, placeholder_text="🔍 Hledat jméno...",
            fg_color=COLORS["panel_bg"], border_color=COLORS["border"],
            text_color="white"
        )
        search_entry.pack(side="right")

        # Scrollable Area
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    def refresh_data(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not self.controller.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Načteme profily
            try:
                cur.execute("SELECT * FROM users ORDER BY last_scraped DESC")
            except Exception:
                cur.execute(
                    "SELECT id, platform, username, display_name, bio, "
                    "followers_count, profile_pic_url, last_scraped FROM users "
                    "ORDER BY last_scraped DESC"
                )
            self.all_profiles_data = [dict(row) for row in cur.fetchall()]

            # Načteme sentiment statistiky pro každý profil
            self._sentiment_cache = {}
            for user in self.all_profiles_data:
                try:
                    cur.execute("""
                        SELECT
                            COUNT(c.id)                  AS total,
                            AVG(c.sentiment_score)       AS avg_score,
                            SUM(CASE WHEN c.sentiment_label = 'positive' THEN 1 ELSE 0 END) AS pos,
                            SUM(CASE WHEN c.sentiment_label = 'neutral'  THEN 1 ELSE 0 END) AS neu,
                            SUM(CASE WHEN c.sentiment_label = 'negative' THEN 1 ELSE 0 END) AS neg
                        FROM comments c
                        JOIN posts p ON c.post_id = p.id
                        WHERE p.user_id = ? AND c.sentiment_score IS NOT NULL
                    """, (user["id"],))
                    row = cur.fetchone()
                    if row and row[0] and row[0] > 0:
                        self._sentiment_cache[user["id"]] = {
                            "total": row[0],
                            "avg":   round(row[1], 3) if row[1] else 0.0,
                            "pos":   row[2] or 0,
                            "neu":   row[3] or 0,
                            "neg":   row[4] or 0,
                        }
                except Exception:
                    pass

            conn.close()
            self.filter_profiles()
        except Exception as e:
            print(f"[GUI ERROR] Chyba profilů: {e}")

    def filter_profiles(self, *args):
        query = self.search_var.get().lower()
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        for user in self.all_profiles_data:
            u_name = (user.get("username") or "").lower()
            d_name = (user.get("display_name") or "").lower()
            if query in u_name or query in d_name:
                self.create_card(user)

    # ------------------------------------------------------------------
    # Karta profilu
    # ------------------------------------------------------------------
    def create_card(self, user):
        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=COLORS["panel_bg"],
            corner_radius=12,
            border_color=COLORS["border"],
            border_width=1
        )
        card.pack(fill="x", pady=6, padx=4)
        card.grid_columnconfigure(1, weight=1)

        # --- Avatar ---
        img_widget = ctk.CTkLabel(
            card, text="", width=80, height=80,
            corner_radius=10, fg_color="#333"
        )
        if user.get("profile_pic_url"):
            threading.Thread(
                target=self.image_loader.load_image,
                args=(user.get("profile_pic_url"), img_widget),
                daemon=True
            ).start()
        img_widget.grid(row=0, column=0, rowspan=4, padx=15, pady=15, sticky="n")

        # --- Jméno + verifikace + handle ---
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="nw", pady=(15, 0), padx=5)

        name_text = user.get("display_name") or user["username"]
        ctk.CTkLabel(
            info_frame, text=name_text,
            font=("Segoe UI", 16, "bold"), text_color="white"
        ).pack(side="left")

        if user.get("is_verified") == 1:
            ctk.CTkLabel(
                info_frame, text="☑",
                font=("Segoe UI", 16), text_color=COLORS["verified"]
            ).pack(side="left", padx=(5, 0))

        handle_txt = f"@{user['username']} • {str(user.get('platform')).upper()}"
        ctk.CTkLabel(
            info_frame, text=handle_txt,
            font=("Segoe UI", 13), text_color=COLORS["text_dim"]
        ).pack(side="left", padx=(10, 0))

        # --- Statistiky sledujících ---
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.grid(row=1, column=1, sticky="nw", pady=(4, 4), padx=5)

        def fmt(n):
            return f"{n:,}".replace(",", " ") if n is not None else "0"

        ctk.CTkLabel(
            stats_frame, text=fmt(user.get("followers_count", 0)),
            font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]
        ).pack(side="left")
        ctk.CTkLabel(
            stats_frame, text="Followers",
            font=("Segoe UI", 13), text_color=COLORS["text_dim"]
        ).pack(side="left", padx=(3, 15))

        ctk.CTkLabel(
            stats_frame, text=fmt(user.get("following_count", 0)),
            font=("Segoe UI", 13, "bold"), text_color=COLORS["text_main"]
        ).pack(side="left")
        ctk.CTkLabel(
            stats_frame, text="Following",
            font=("Segoe UI", 13), text_color=COLORS["text_dim"]
        ).pack(side="left", padx=(3, 0))

        # --- Bio ---
        bio = user.get("bio")
        if bio:
            clean_bio = " ".join(bio.split())
            short_bio = (clean_bio[:90] + "...") if len(clean_bio) > 90 else clean_bio
            ctk.CTkLabel(
                card, text=short_bio,
                font=("Segoe UI", 12, "italic"),
                text_color="#b0b0b0", anchor="w", justify="left"
            ).grid(row=2, column=1, sticky="w", padx=5, pady=(0, 4))

        # --- Metadata ---
        meta_frame = ctk.CTkFrame(card, fg_color="transparent")
        meta_frame.grid(row=3, column=1, sticky="nw", pady=(0, 12), padx=5)

        meta = []
        if user.get("location"):    meta.append(f"📍 {user['location']}")
        if user.get("website"):     meta.append(f"🔗 {user['website']}")
        if user.get("joined_date"): meta.append(f"📅 {user['joined_date']}")
        if meta:
            ctk.CTkLabel(
                meta_frame, text="   ".join(meta),
                font=("Segoe UI", 11), text_color=COLORS["text_dim"]
            ).pack(side="left")

        last_s = str(user.get("last_scraped", "")).split("T")[0] or "?"
        ctk.CTkLabel(
            card, text=f"Upd: {last_s}",
            font=("Segoe UI", 10), text_color="#555"
        ).grid(row=3, column=1, sticky="e", padx=15, pady=(0, 12))

        # --- Sentiment vizualizace ---
        sentiment_data = getattr(self, "_sentiment_cache", {}).get(user["id"])
        if sentiment_data:
            self._add_sentiment_widget(card, sentiment_data)

    # ------------------------------------------------------------------
    # Sentiment widget
    # ------------------------------------------------------------------
    def _add_sentiment_widget(self, card, s: dict):
        """
        Přidá sentiment panel ke kartě:
          - stacked bar (pos / neu / neg)
          - průměrné skóre + label
          - počty komentářů
        """
        SEP_COLOR   = COLORS["border"]
        POS_COLOR   = "#2eb85c"   # zelená
        NEU_COLOR   = "#5a6370"   # šedá
        NEG_COLOR   = "#e05252"   # červená
        TEXT_DIM    = COLORS["text_dim"]
        TEXT_MAIN   = COLORS["text_main"]

        total = s["total"]
        pos   = s["pos"]
        neu   = s["neu"]
        neg   = s["neg"]
        avg   = s["avg"]

        # Oddělovač
        ctk.CTkFrame(card, height=1, fg_color=SEP_COLOR).grid(
            row=4, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 10)
        )

        sentiment_row = ctk.CTkFrame(card, fg_color="transparent")
        sentiment_row.grid(row=5, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 12))
        sentiment_row.grid_columnconfigure(1, weight=1)

        # -- Levý panel: skóre + label --
        score_panel = ctk.CTkFrame(sentiment_row, fg_color="transparent", width=90)
        score_panel.grid(row=0, column=0, sticky="nw", padx=(0, 15))
        score_panel.grid_propagate(False)

        ctk.CTkLabel(
            score_panel, text="SENTIMENT",
            font=("Segoe UI", 9, "bold"), text_color=TEXT_DIM
        ).pack(anchor="w")

        # Barva a label průměrného skóre
        if avg >= 0.05:
            score_color = POS_COLOR
            score_label = "pozitivní"
        elif avg <= -0.05:
            score_color = NEG_COLOR
            score_label = "negativní"
        else:
            score_color = NEU_COLOR
            score_label = "neutrální"

        ctk.CTkLabel(
            score_panel, text=f"{avg:+.3f}",
            font=("Segoe UI", 20, "bold"), text_color=score_color
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(
            score_panel, text=score_label,
            font=("Segoe UI", 11), text_color=score_color
        ).pack(anchor="w")

        ctk.CTkLabel(
            score_panel, text=f"{total} komentářů",
            font=("Segoe UI", 10), text_color=TEXT_DIM
        ).pack(anchor="w", pady=(4, 0))

        # -- Pravý panel: stacked bar + legenda --
        bar_panel = ctk.CTkFrame(sentiment_row, fg_color="transparent")
        bar_panel.grid(row=0, column=1, sticky="nsew")
        bar_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bar_panel, text="ROZLOŽENÍ KOMENTÁŘŮ",
            font=("Segoe UI", 9, "bold"), text_color=TEXT_DIM
        ).pack(anchor="w")

        # Stacked bar pomocí Canvas
        bar_height = 22
        canvas = Canvas(
            bar_panel,
            height=bar_height,
            bg=COLORS["panel_bg"],
            highlightthickness=0,
            bd=0
        )
        canvas.pack(fill="x", pady=(4, 6))

        # Kreslíme po načtení — canvas musí být viditelný
        def draw_bar(event=None):
            canvas.delete("all")
            w = canvas.winfo_width()
            if w <= 1:
                canvas.after(50, draw_bar)
                return

            radius = 6

            segments = [
                (pos, POS_COLOR),
                (neu, NEU_COLOR),
                (neg, NEG_COLOR),
            ]

            x = 0
            drawn = []
            for count, color in segments:
                if total > 0 and count > 0:
                    seg_w = max(int((count / total) * w), 1)
                    drawn.append((x, seg_w, color, count))
                    x += seg_w

            # Zaokrouhlené rohy jen na krajích
            for i, (sx, sw, color, _) in enumerate(drawn):
                x0, y0 = sx, 0
                x1, y1 = sx + sw, bar_height
                is_first = (i == 0)
                is_last  = (i == len(drawn) - 1)

                if is_first and is_last:
                    _rounded_rect(canvas, x0, y0, x1, y1, radius, color)
                elif is_first:
                    _rounded_rect_left(canvas, x0, y0, x1, y1, radius, color)
                elif is_last:
                    _rounded_rect_right(canvas, x0, y0, x1, y1, radius, color)
                else:
                    canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

        canvas.bind("<Configure>", draw_bar)
        canvas.after(100, draw_bar)

        # Legenda
        legend_frame = ctk.CTkFrame(bar_panel, fg_color="transparent")
        legend_frame.pack(fill="x")

        for label_text, count, color in [
            ("Pozitivní", pos, POS_COLOR),
            ("Neutrální", neu, NEU_COLOR),
            ("Negativní", neg, NEG_COLOR),
        ]:
            pct = round((count / total) * 100) if total > 0 else 0
            item = ctk.CTkFrame(legend_frame, fg_color="transparent")
            item.pack(side="left", padx=(0, 18))

            dot_canvas = Canvas(item, width=8, height=8,
                                bg=COLORS["panel_bg"], highlightthickness=0)
            dot_canvas.pack(side="left", padx=(0, 4))
            dot_canvas.create_oval(0, 0, 8, 8, fill=color, outline="")

            ctk.CTkLabel(
                item, text=f"{label_text} {pct}% ({count})",
                font=("Segoe UI", 10), text_color=TEXT_DIM
            ).pack(side="left")


# ------------------------------------------------------------------
# Pomocné funkce pro zaokrouhlené obdélníky na Canvas
# ------------------------------------------------------------------
def _rounded_rect(canvas, x0, y0, x1, y1, r, color):
    """Plně zaokrouhlený obdélník."""
    canvas.create_arc(x0, y0, x0+2*r, y0+2*r, start=90,  extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y0, x1, y0+2*r, start=0,   extent=90,  fill=color, outline="")
    canvas.create_arc(x0, y1-2*r, x0+2*r, y1, start=180, extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y1-2*r, x1, y1, start=270, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=color, outline="")
    canvas.create_rectangle(x0, y0+r, x1, y1-r, fill=color, outline="")

def _rounded_rect_left(canvas, x0, y0, x1, y1, r, color):
    """Zaokrouhlené pouze levé rohy."""
    canvas.create_arc(x0, y0, x0+2*r, y0+2*r, start=90,  extent=90,  fill=color, outline="")
    canvas.create_arc(x0, y1-2*r, x0+2*r, y1, start=180, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0+r, y0, x1, y1, fill=color, outline="")
    canvas.create_rectangle(x0, y0+r, x0+r, y1-r, fill=color, outline="")

def _rounded_rect_right(canvas, x0, y0, x1, y1, r, color):
    """Zaokrouhlené pouze pravé rohy."""
    canvas.create_arc(x1-2*r, y0, x1, y0+2*r, start=0,   extent=90,  fill=color, outline="")
    canvas.create_arc(x1-2*r, y1-2*r, x1, y1, start=270, extent=90,  fill=color, outline="")
    canvas.create_rectangle(x0, y0, x1-r, y1, fill=color, outline="")
    canvas.create_rectangle(x1-r, y0+r, x1, y1-r, fill=color, outline="")