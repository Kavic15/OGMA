"""
src/analysis/text_stats.py

Textová statistická analýza příspěvků a komentářů profilu.
  - Nejpoužívanější hashtagy (#tag)
  - Nejčastější zmínky (@handle)
  - Top slova (tokenizace + stop-slova)
  - Word cloud jako PIL Image (pro zobrazení v GUI)

Data jsou rozdělena na dva zdroje:
  - owner:      texty vlastních příspěvků sledovaného profilu
  - commenters: texty komentářů pod jeho příspěvky (bez limitu)
"""

import re
from collections import Counter
from io import BytesIO
from src.core.database import DatabaseManager

# Stop-slova — vícejazyčná sada pro EN/CS/SK/ES
STOP_WORDS = {
    # Angličtina
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "not", "no", "so",
    "if", "as", "it", "its", "this", "that", "these", "those", "i", "you",
    "he", "she", "we", "they", "my", "your", "his", "her", "our", "their",
    "what", "which", "who", "when", "where", "why", "how", "all", "just",
    "more", "also", "about", "than", "then", "there", "here", "up", "out",
    "very", "too", "now", "new", "get", "got", "like", "go", "one", "time",
    "people", "into", "see", "him", "her", "them", "us", "me", "s", "t",
    "re", "ve", "ll", "d", "rt",
    # Čeština / Slovenština
    "je", "se", "to", "na", "ve", "že", "ale", "do", "za", "po", "při",
    "pro", "byl", "byla", "bylo", "jsou", "jsem", "jsi", "jsme", "jste",
    "ten", "ta", "ti", "ty", "co", "jak", "kdy", "kde", "kdo", "nebo",
    "také", "tak", "jako", "jeho", "její", "jejich", "tohoto", "této",
    "tento", "tato", "toto", "mezi", "které", "který", "která", "více",
    "si", "mi", "ho", "mu", "ji", "ze", "aby", "jen", "už", "ještě",
    "bude", "být", "tam", "zde", "tady", "mám", "má", "mít", "vše",
    "svou", "své", "svůj", "není", "ani", "když", "pak", "proto", "tedy",
    "přes", "před", "nad", "pod", "bez", "celý", "celá", "celé",
    # Španělština
    "el", "la", "los", "las", "un", "una", "y", "en", "de", "que", "es",
    "con", "por", "su", "sus", "del", "al", "se", "lo", "le", "les",
    "me", "mi", "nos", "te", "tu", "yo", "él", "ella", "pero", "no",
    "si", "más", "ya", "todo", "como", "muy", "fue", "son", "tiene",
    # Obecné
    "rt", "via", "amp", "gt", "lt", "http", "https", "www",
}


class TextStatsAnalyzer:
    def __init__(self):
        self.db = DatabaseManager()

    # ------------------------------------------------------------------
    # Hlavní metoda — vrátí statistiky rozdělené na vlastníka a komentující
    # ------------------------------------------------------------------
    def get_profile_stats(
        self,
        user_id: str,
        posts_limit: int = 100,
        top_n: int = 10,
    ) -> dict:
        """
        Vrátí slovník se statistikami rozdělenými na dvě sekce:
        {
            "owner": {
                "top_hashtags": [...], "top_mentions": [...], "top_words": [...],
                "total_posts": int,
            },
            "commenters": {
                "top_hashtags": [...], "top_mentions": [...], "top_words": [...],
                "total_comments": int,
            },
        }
        """
        texts_posts    = self._fetch_post_texts(user_id, posts_limit)
        texts_comments = self._fetch_comment_texts(user_id)   # bez limitu

        return {
            "owner": {
                "top_hashtags": self._extract_hashtags(texts_posts, top_n),
                "top_mentions": self._extract_mentions(texts_posts, top_n),
                "top_words":    self._extract_top_words(texts_posts, top_n),
                "total_posts":  len(texts_posts),
            },
            "commenters": {
                "top_hashtags": self._extract_hashtags(texts_comments, top_n),
                "top_mentions": self._extract_mentions(texts_comments, top_n),
                "top_words":    self._extract_top_words(texts_comments, top_n),
                "total_comments": len(texts_comments),
            },
        }

    # ------------------------------------------------------------------
    # Načtení textů z DB
    # ------------------------------------------------------------------
    def _fetch_post_texts(self, user_id: str, limit: int) -> list[str]:
        try:
            self.db.cursor.execute(
                """SELECT text_content FROM posts
                   WHERE user_id = ? AND text_content IS NOT NULL
                     AND text_content NOT IN (
                         '[OBSAHUJE VIDEO]','[OBSAHUJE FOTKU]','[OBSAHUJE MÉDIA/GIF]'
                     )
                   ORDER BY timestamp_posted DESC
                   LIMIT ?""",
                (user_id, limit),
            )
            return [row[0] for row in self.db.cursor.fetchall()]
        except Exception as e:
            print(f"[TEXT-STATS ERROR] Načtení příspěvků selhalo: {e}")
            return []

    def _fetch_comment_texts(self, user_id: str) -> list[str]:
        """Načte všechny komentáře pod příspěvky daného profilu — bez limitu."""
        try:
            self.db.cursor.execute(
                """SELECT c.text_content FROM comments c
                   JOIN posts p ON c.post_id = p.id
                   WHERE p.user_id = ? AND c.text_content IS NOT NULL
                     AND c.text_content NOT IN (
                         '[OBSAHUJE VIDEO]','[OBSAHUJE FOTKU]','[OBSAHUJE MÉDIA/GIF]'
                     )
                   ORDER BY c.timestamp_posted DESC""",
                (user_id,),
            )
            return [row[0] for row in self.db.cursor.fetchall()]
        except Exception as e:
            print(f"[TEXT-STATS ERROR] Načtení komentářů selhalo: {e}")
            return []

    # ------------------------------------------------------------------
    # Extrakce hashtagů
    # ------------------------------------------------------------------
    def _extract_hashtags(self, texts: list[str], top_n: int) -> list[tuple]:
        counter = Counter()
        for text in texts:
            tags = re.findall(r'#(\w+)', text, re.UNICODE)
            counter.update(t.lower() for t in tags if len(t) > 1)
        return [(f"#{tag}", count) for tag, count in counter.most_common(top_n)]

    # ------------------------------------------------------------------
    # Extrakce zmínek
    # ------------------------------------------------------------------
    def _extract_mentions(self, texts: list[str], top_n: int) -> list[tuple]:
        counter = Counter()
        for text in texts:
            mentions = re.findall(r'@(\w+)', text, re.UNICODE)
            counter.update(m.lower() for m in mentions if len(m) > 1)
        return [(f"@{mention}", count) for mention, count in counter.most_common(top_n)]

    # ------------------------------------------------------------------
    # Extrakce top slov
    # ------------------------------------------------------------------
    def _extract_top_words(self, texts: list[str], top_n: int) -> list[tuple]:
        counter = Counter()
        for text in texts:
            clean = re.sub(r'https?://\S+', '', text)
            clean = re.sub(r'[@#]\w+', '', clean)
            words = re.findall(r'\b\w{3,}\b', clean, re.UNICODE)
            filtered = [
                w.lower() for w in words
                if w.lower() not in STOP_WORDS
                and not w.isdigit()
                and len(w) >= 3
            ]
            counter.update(filtered)
        return counter.most_common(top_n)

    # ------------------------------------------------------------------
    # Generování Word Cloud jako PNG bytes
    # ------------------------------------------------------------------
    def generate_word_cloud(
        self,
        user_id: str,
        source: str = "commenters",   # "owner" | "commenters" | "both"
        posts_limit: int = 100,
        width: int = 600,
        height: int = 260,
    ) -> bytes | None:
        """
        Vygeneruje word cloud.
        source:
          "owner"      — pouze příspěvky vlastníka
          "commenters" — pouze komentáře (bez limitu)
          "both"       — obojí dohromady
        """
        try:
            from wordcloud import WordCloud
        except ImportError:
            print("[TEXT-STATS] Knihovna 'wordcloud' není nainstalována. "
                  "Spusť: pip install wordcloud matplotlib")
            return None

        texts = []
        if source in ("owner", "both"):
            texts += self._fetch_post_texts(user_id, posts_limit)
        if source in ("commenters", "both"):
            texts += self._fetch_comment_texts(user_id)

        if not texts:
            return None

        combined = " ".join(texts)
        combined = re.sub(r'https?://\S+', '', combined)
        combined = re.sub(r'[@#]\w+', '', combined)
        combined = re.sub(r'\b\w{1,2}\b', '', combined)

        if len(combined.strip()) < 20:
            return None

        try:
            wc = WordCloud(
                width=width,
                height=height,
                background_color="#2c3035",
                color_func=_dark_theme_color,
                stopwords=STOP_WORDS,
                max_words=80,
                prefer_horizontal=0.85,
                min_font_size=10,
                max_font_size=60,
                collocations=False,
            ).generate(combined)

            img = wc.to_image()
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        except Exception as e:
            print(f"[TEXT-STATS ERROR] Generování word cloud selhalo: {e}")
            return None


# ------------------------------------------------------------------
# Barevná funkce pro dark theme word cloud
# ------------------------------------------------------------------
def _dark_theme_color(word, font_size, position, orientation, random_state=None, **kwargs):
    import random
    palettes = [
        "hsl(210, 80%, 70%)",
        "hsl(210, 60%, 85%)",
        "hsl(0, 0%, 90%)",
        "hsl(210, 40%, 60%)",
        "hsl(0, 0%, 70%)",
        "hsl(195, 70%, 65%)",
    ]
    return random.choice(palettes)