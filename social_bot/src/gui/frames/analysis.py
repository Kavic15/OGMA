# src/gui/frames/analysis.py
"""
Záložka "Analýza" v hlavním okně aplikace.
Sekce:
  1. Sentiment analýza komentářů (VADER + kontextový slovník)
  2. OCR analýza obrázků (Tesseract)
  3. Výsledková tabulka sentimentu per uživatel
"""

import customtkinter as ctk
from tkinter import ttk
import threading
import sqlite3
from src.gui.theme import COLORS


class AnalysisFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- Nadpis ---
        ctk.CTkLabel(
            self, text="Analýza dat",
            font=("Segoe UI", 24, "bold"),
            text_color=COLORS["text_main"]
        ).grid(row=0, column=0, sticky="w", pady=(0, 20))

        # --- Sekce 1: Sentiment ---
        self._build_sentiment_panel()

        # --- Sekce 2: OCR ---
        self._build_ocr_panel()

        # --- Sekce 3: Výsledková tabulka ---
        self._build_results_table()

    # ------------------------------------------------------------------
    # Panel 1 — Sentiment analýza
    # ------------------------------------------------------------------
    def _build_sentiment_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["panel_bg"], corner_radius=10)
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        panel.grid_columnconfigure(1, weight=1)

        # Ikona + název
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(15, 4))

        ctk.CTkLabel(
            header, text="💬",
            font=("Segoe UI", 18)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header, text="Sentiment analýza komentářů",
            font=("Segoe UI", 15, "bold"), text_color=COLORS["text_main"]
        ).pack(side="left")

        ctk.CTkLabel(
            panel,
            text="Projde všechny nové komentáře a příspěvky v DB, přiřadí skóre "
                 "(-1.0 negativní → +1.0 pozitivní) pomocí kontextového slovníku + VADER.",
            font=("Segoe UI", 12), text_color=COLORS["text_dim"],
            wraplength=700, justify="left"
        ).grid(row=1, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="w")

        self.btn_sentiment = ctk.CTkButton(
            panel, text="▶  Spustit analýzu",
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=("Segoe UI", 13, "bold"), height=38, width=180,
            command=self.run_sentiment
        )
        self.btn_sentiment.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="w")

        self.sentiment_progress = ctk.CTkProgressBar(
            panel, height=8, corner_radius=4, progress_color=COLORS["primary"]
        )
        self.sentiment_progress.set(0)
        self.sentiment_progress.grid(row=2, column=1, padx=(10, 10), pady=(0, 15), sticky="ew")

        self.sentiment_label = ctk.CTkLabel(
            panel, text="", font=("Segoe UI", 12),
            text_color=COLORS["text_dim"], width=120, anchor="e"
        )
        self.sentiment_label.grid(row=2, column=2, padx=(0, 20), pady=(0, 15))

    # ------------------------------------------------------------------
    # Panel 2 — OCR analýza obrázků
    # ------------------------------------------------------------------
    def _build_ocr_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["panel_bg"], corner_radius=10)
        panel.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        panel.grid_columnconfigure(1, weight=1)

        # Ikona + název
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(15, 4))

        ctk.CTkLabel(
            header, text="🖼",
            font=("Segoe UI", 18)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header, text="OCR analýza obrázků",
            font=("Segoe UI", 15, "bold"), text_color=COLORS["text_main"]
        ).pack(side="left")

        ctk.CTkLabel(
            panel,
            text="Stáhne obrázky z příspěvků a komentářů, extrahuje text pomocí Tesseract OCR "
                 "a provede sentiment analýzu nalezeného textu. Podporuje: EN, CS, SK, ES.",
            font=("Segoe UI", 12), text_color=COLORS["text_dim"],
            wraplength=700, justify="left"
        ).grid(row=1, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="w")

        # Tlačítka — příspěvky a komentáře zvlášť
        btn_frame = ctk.CTkFrame(panel, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="w")

        self.btn_ocr_posts = ctk.CTkButton(
            btn_frame, text="▶  Příspěvky",
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=("Segoe UI", 13, "bold"), height=38, width=140,
            command=lambda: self.run_ocr("posts")
        )
        self.btn_ocr_posts.pack(side="left", padx=(0, 8))

        self.btn_ocr_comments = ctk.CTkButton(
            btn_frame, text="▶  Komentáře",
            fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
            font=("Segoe UI", 13, "bold"), height=38, width=140,
            command=lambda: self.run_ocr("comments")
        )
        self.btn_ocr_comments.pack(side="left", padx=(0, 8))

        self.btn_ocr_both = ctk.CTkButton(
            btn_frame, text="▶  Vše",
            fg_color=COLORS["panel_bg"], hover_color=COLORS["border"],
            border_width=1, border_color=COLORS["primary"],
            text_color=COLORS["primary"],
            font=("Segoe UI", 13, "bold"), height=38, width=90,
            command=lambda: self.run_ocr("both")
        )
        self.btn_ocr_both.pack(side="left")

        self.ocr_progress = ctk.CTkProgressBar(
            panel, height=8, corner_radius=4, progress_color="#e8a020"
        )
        self.ocr_progress.set(0)
        self.ocr_progress.grid(row=2, column=1, padx=(10, 10), pady=(0, 15), sticky="ew")

        self.ocr_label = ctk.CTkLabel(
            panel, text="", font=("Segoe UI", 12),
            text_color=COLORS["text_dim"], width=120, anchor="e"
        )
        self.ocr_label.grid(row=2, column=2, padx=(0, 20), pady=(0, 15))

        # Statistiky OCR
        self.ocr_stats_label = ctk.CTkLabel(
            panel, text="",
            font=("Segoe UI", 11), text_color=COLORS["text_dim"]
        )
        self.ocr_stats_label.grid(row=3, column=0, columnspan=3, padx=20, pady=(0, 12), sticky="w")
        self._refresh_ocr_stats()

    # ------------------------------------------------------------------
    # Výsledková tabulka
    # ------------------------------------------------------------------
    def _build_results_table(self):
        ctk.CTkLabel(
            self, text="VÝSLEDKY SENTIMENTU PER UŽIVATEL",
            font=("Segoe UI", 11, "bold"), text_color=COLORS["text_dim"]
        ).grid(row=3, column=0, sticky="w", pady=(0, 5))

        results_frame = ctk.CTkFrame(self, fg_color="transparent")
        results_frame.grid(row=4, column=0, sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Analysis.Treeview",
            background=COLORS["main_bg"], foreground=COLORS["text_main"],
            rowheight=30, fieldbackground=COLORS["main_bg"],
            borderwidth=0, font=("Segoe UI", 11)
        )
        style.configure(
            "Analysis.Treeview.Heading",
            background=COLORS["panel_bg"], foreground=COLORS["text_main"],
            relief="flat", font=("Segoe UI", 11, "bold"), padding=(10, 5)
        )
        style.map(
            "Analysis.Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", "white")]
        )

        scroll_y = ctk.CTkScrollbar(results_frame)
        scroll_y.grid(row=0, column=1, sticky="ns")

        columns = (
            "Platform", "Uživatel", "Komentářů",
            "Avg. skóre", "😊 Pozit.", "😐 Neutr.", "😠 Negat.",
            "🖼 OCR textů"
        )
        self.tree = ttk.Treeview(
            results_frame, columns=columns,
            show="headings", style="Analysis.Treeview",
            yscrollcommand=scroll_y.set
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.configure(command=self.tree.yview)

        col_widths = {
            "Platform": 80, "Uživatel": 150, "Komentářů": 100,
            "Avg. skóre": 110, "😊 Pozit.": 85, "😐 Neutr.": 85,
            "😠 Negat.": 85, "🖼 OCR textů": 100
        }
        for col in columns:
            self.tree.heading(col, text=col, anchor="w")
            self.tree.column(col, width=col_widths.get(col, 100), anchor="w")

        self.tree.tag_configure("positive", foreground="#2eb85c")
        self.tree.tag_configure("negative", foreground="#e05252")
        self.tree.tag_configure("neutral",  foreground=COLORS["text_main"])

    # ------------------------------------------------------------------
    # Akce — Sentiment
    # ------------------------------------------------------------------
    def run_sentiment(self):
        self.btn_sentiment.configure(state="disabled", text="⏳  Probíhá...")
        self.sentiment_progress.set(0)
        self.sentiment_label.configure(text="0 / ?")
        threading.Thread(target=self._sentiment_thread, daemon=True).start()

    def _sentiment_thread(self):
        try:
            from src.analysis.sentiment import SentimentAnalyzer
            analyzer = SentimentAnalyzer()

            def cb(current, total):
                pct = current / total if total > 0 else 0
                self.after(0, lambda c=current, t=total, p=pct: [
                    self.sentiment_progress.set(p),
                    self.sentiment_label.configure(text=f"{c} / {t}")
                ])

            count = analyzer.analyze_pending(callback=cb)
            self.after(0, lambda: [
                self.sentiment_progress.set(1.0),
                self.sentiment_label.configure(text=f"✓ {count} zpracováno"),
                self.refresh_results()
            ])
        except Exception as e:
            self.after(0, lambda: self.sentiment_label.configure(text=f"Chyba: {e}"))
        finally:
            self.after(0, lambda: self.btn_sentiment.configure(
                state="normal", text="▶  Spustit analýzu"
            ))

    # ------------------------------------------------------------------
    # Akce — OCR
    # ------------------------------------------------------------------
    def run_ocr(self, mode: str):
        for btn in [self.btn_ocr_posts, self.btn_ocr_comments, self.btn_ocr_both]:
            btn.configure(state="disabled")
        self.ocr_progress.set(0)
        self.ocr_label.configure(text="Probíhá...")
        threading.Thread(target=self._ocr_thread, args=(mode,), daemon=True).start()

    def _ocr_thread(self, mode: str):
        try:
            from src.analysis.image_ocr import ImageOCRAnalyzer
            analyzer = ImageOCRAnalyzer()
            total_processed = 0

            def cb(current, total):
                pct = current / total if total > 0 else 0
                self.after(0, lambda c=current, t=total, p=pct: [
                    self.ocr_progress.set(p),
                    self.ocr_label.configure(text=f"{c} / {t}")
                ])

            if mode in ("posts", "both"):
                total_processed += analyzer.analyze_pending_posts(callback=cb)
            if mode in ("comments", "both"):
                self.after(0, lambda: self.ocr_progress.set(0))
                total_processed += analyzer.analyze_pending_comments(callback=cb)

            self.after(0, lambda n=total_processed: [
                self.ocr_progress.set(1.0),
                self.ocr_label.configure(text=f"✓ {n} zpracováno"),
                self._refresh_ocr_stats(),
                self.refresh_results()
            ])
        except Exception as e:
            self.after(0, lambda err=e: self.ocr_label.configure(text=f"Chyba: {err}"))
            print(f"[OCR ERROR] {e}")
        finally:
            self.after(0, lambda: [
                btn.configure(state="normal")
                for btn in [self.btn_ocr_posts, self.btn_ocr_comments, self.btn_ocr_both]
            ])

    # ------------------------------------------------------------------
    # Statistiky OCR (kolik obrázků zbývá)
    # ------------------------------------------------------------------
    def _refresh_ocr_stats(self):
        if not self.controller.db_path.exists():
            return
        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            cur = conn.cursor()

            stats = {}
            for table in ("posts", "comments"):
                try:
                    cur.execute(f"""
                        SELECT
                            COUNT(*) AS total_with_media,
                            SUM(CASE WHEN media_text IS NOT NULL AND media_text != '' THEN 1 ELSE 0 END) AS with_text,
                            SUM(CASE WHEN media_text IS NULL THEN 1 ELSE 0 END) AS pending
                        FROM {table}
                        WHERE media_url IS NOT NULL AND media_url != ''
                          AND (
                            media_url LIKE '%.jpg%' OR media_url LIKE '%.jpeg%'
                            OR media_url LIKE '%.png%' OR media_url LIKE '%.webp%'
                            OR media_url LIKE '%pbs.twimg%' OR media_url LIKE '%cdninstagram%'
                          )
                    """)
                    row = cur.fetchone()
                    stats[table] = row if row else (0, 0, 0)
                except Exception:
                    stats[table] = (0, 0, 0)

            conn.close()

            p_total, p_text, p_pend = stats["posts"]
            c_total, c_text, c_pend = stats["comments"]

            msg = (
                f"Příspěvky: {p_text or 0}/{p_total or 0} s textem  |  "
                f"Komentáře: {c_text or 0}/{c_total or 0} s textem  |  "
                f"Čeká na zpracování: {(p_pend or 0) + (c_pend or 0)}"
            )
            self.after(0, lambda: self.ocr_stats_label.configure(text=msg))

        except Exception as e:
            print(f"[OCR STATS ERROR] {e}")

    # ------------------------------------------------------------------
    # Obnovení výsledkové tabulky
    # ------------------------------------------------------------------
    def refresh_results(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not self.controller.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.controller.db_path))
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    u.platform,
                    u.username,
                    COUNT(c.id)                      AS total,
                    ROUND(AVG(c.sentiment_score), 3) AS avg_score,
                    SUM(CASE WHEN c.sentiment_label = 'positive' THEN 1 ELSE 0 END) AS pos,
                    SUM(CASE WHEN c.sentiment_label = 'neutral'  THEN 1 ELSE 0 END) AS neu,
                    SUM(CASE WHEN c.sentiment_label = 'negative' THEN 1 ELSE 0 END) AS neg,
                    SUM(CASE WHEN c.media_text IS NOT NULL AND c.media_text != '' THEN 1 ELSE 0 END) AS ocr_count
                FROM comments c
                JOIN posts p ON c.post_id = p.id
                JOIN users u ON p.user_id = u.id
                WHERE c.sentiment_score IS NOT NULL
                GROUP BY u.platform, u.username
                ORDER BY avg_score DESC
            """)
            rows = cur.fetchall()
            conn.close()

            for r in rows:
                platform, username, total, avg, pos, neu, neg, ocr = r
                avg_str = f"{avg:+.3f}" if avg is not None else "N/A"

                if avg is not None and avg >= 0.05:
                    tag = "positive"
                elif avg is not None and avg <= -0.05:
                    tag = "negative"
                else:
                    tag = "neutral"

                self.tree.insert(
                    "", "end",
                    values=(platform, username, total, avg_str, pos, neu, neg, ocr or 0),
                    tags=(tag,)
                )

        except Exception as e:
            print(f"[ANALYSIS GUI ERROR] {e}")