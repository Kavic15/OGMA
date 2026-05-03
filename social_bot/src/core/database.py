import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone

class DatabaseManager:
    def __init__(self, db_name="osint.db"):
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        self.data_dir = project_root / 'data'
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.db_path = self.data_dir / db_name
        self.conn = None
        self.cursor = None
        
        self._connect()
        self._create_tables()
        self._migrate_db() # Důležité: Přidá nové sloupce do existující DB

    def _connect(self):
        self.conn = sqlite3.connect(str(self.db_path), timeout=10, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def _create_tables(self):
        # TABULKA USERS - Rozšířená o metadata
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_user_id TEXT,
                username TEXT NOT NULL,
                display_name TEXT,
                bio TEXT,
                followers_count INTEGER,
                following_count INTEGER,
                joined_date TEXT,
                location TEXT,
                website TEXT, 
                is_verified INTEGER DEFAULT 0,
                profile_pic_url TEXT, 
                banner_url TEXT,
                last_scraped TIMESTAMP,
                UNIQUE(platform, username)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                platform_post_id TEXT NOT NULL,
                text_content TEXT,
                media_url TEXT,
                timestamp_posted TIMESTAMP,
                likes_count INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                url TEXT,
                scraped_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                UNIQUE(platform_post_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                platform_comment_id TEXT NOT NULL,
                author_username TEXT,
                author_display_name TEXT,
                text_content TEXT,
                media_url TEXT,
                timestamp_posted TIMESTAMP,
                likes_count INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0,
                replies_count INTEGER DEFAULT 0,
                scraped_at TIMESTAMP,
                FOREIGN KEY(post_id) REFERENCES posts(id),
                UNIQUE(platform_comment_id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trending (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                rank INTEGER,
                category TEXT,
                topic_name TEXT NOT NULL,
                post_count TEXT,
                scraped_at TIMESTAMP,
                UNIQUE(platform, topic_name)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                source_username TEXT NOT NULL,
                target_username TEXT NOT NULL,
                connection_type TEXT NOT NULL,
                scraped_at TIMESTAMP,
                UNIQUE(platform, source_username, target_username, connection_type)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                platform        TEXT    NOT NULL DEFAULT 'IG',
                username        TEXT    NOT NULL,
                interval_min    INTEGER NOT NULL DEFAULT 20,
                limit_posts     INTEGER NOT NULL DEFAULT 10,
                limit_comments  INTEGER NOT NULL DEFAULT 50,
                limit_followers INTEGER NOT NULL DEFAULT 0,
                limit_following INTEGER NOT NULL DEFAULT 0,
                enabled         INTEGER NOT NULL DEFAULT 1,
                last_scraped_at TEXT,
                next_scrape_at  TEXT,
                added_at        TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(platform, username)
            )
        ''')
        self.conn.commit()

    def _migrate_db(self):
        """Zkontroluje a přidá chybějící sloupce."""
        required_columns = {
            "following_count": "INTEGER",
            "joined_date": "TEXT",
            "location": "TEXT",
            "website": "TEXT",
            "is_verified": "INTEGER DEFAULT 0",
            "banner_url": "TEXT",
            "profile_pic_url": "TEXT"
        }

        try:
            self.cursor.execute("PRAGMA table_info(users)")
            existing = [row[1] for row in self.cursor.fetchall()]

            for col, type_ in required_columns.items():
                if col not in existing:
                    print(f"[DB] Migrace: Přidávám sloupec '{col}'...")
                    try: self.cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {type_}")
                    except: pass
            self.conn.commit()
        except Exception as e:
            print(f"[DB ERROR] Migrace selhala: {e}")

    def upsert_user(self, platform, username, platform_user_id=None, display_name=None, 
                    bio=None, followers_count=None, following_count=None, 
                    joined_date=None, location=None, website=None, is_verified=0,
                    profile_pic_url=None, banner_url=None):
        
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('SELECT id FROM users WHERE platform = ? AND username = ?', (platform, username))
        row = self.cursor.fetchone()
        
        if row:
            user_id = row[0]
            self.cursor.execute('''
                UPDATE users SET
                    platform_user_id = COALESCE(?, platform_user_id),
                    display_name = COALESCE(?, display_name),
                    bio = COALESCE(?, bio),
                    followers_count = COALESCE(?, followers_count),
                    following_count = COALESCE(?, following_count),
                    joined_date = COALESCE(?, joined_date),
                    location = COALESCE(?, location),
                    website = COALESCE(?, website),
                    is_verified = ?,
                    profile_pic_url = COALESCE(?, profile_pic_url),
                    banner_url = COALESCE(?, banner_url),
                    last_scraped = ?
                WHERE id = ?
            ''', (platform_user_id, display_name, bio, followers_count, following_count, 
                  joined_date, location, website, is_verified, profile_pic_url, banner_url, now, user_id))
        else:
            user_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO users (
                    id, platform, platform_user_id, username, display_name, bio, 
                    followers_count, following_count, joined_date, location, website, is_verified,
                    profile_pic_url, banner_url, last_scraped
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, platform, platform_user_id, username, display_name, bio, 
                  followers_count, following_count, joined_date, location, website, is_verified,
                  profile_pic_url, banner_url, now))
        
        self.conn.commit()
        return user_id
    
    def post_exists(self, platform_post_id: str) -> bool:
        self.cursor.execute(
            "SELECT 1 FROM posts WHERE platform_post_id = ?",
            (platform_post_id,)
        )
        return self.cursor.fetchone() is not None

    def upsert_post(self, user_id, platform, platform_post_id, text_content, timestamp_posted, likes_count=0, shares_count=0, comments_count=0, url=None, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM posts WHERE platform_post_id = ?', (platform_post_id,))
        row = self.cursor.fetchone()
        if row:
            post_id = row[0]
            self.cursor.execute('''UPDATE posts SET media_url=?, likes_count=?, shares_count=?, comments_count=?, scraped_at=? WHERE id=?''', (media_url, likes_count, shares_count, comments_count, now, post_id))
        else:
            post_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO posts (id, user_id, platform, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (post_id, user_id, platform, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, now))
        self.conn.commit()
        return post_id

    def upsert_comment(self, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, timestamp_posted, likes_count=0, shares_count=0, replies_count=0, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM comments WHERE platform_comment_id = ?', (platform_comment_id,))
        row = self.cursor.fetchone()
        if row:
            comment_id = row[0]
            self.cursor.execute('''UPDATE comments SET media_url=?, likes_count=?, shares_count=?, replies_count=?, scraped_at=? WHERE id=?''', (media_url, likes_count, shares_count, replies_count, now, comment_id))
        else:
            comment_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO comments (id, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (comment_id, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, now))
        self.conn.commit()
        return comment_id

    def upsert_trend(self, platform, rank, category, topic_name, post_count):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('SELECT id FROM trending WHERE platform = ? AND topic_name = ?', (platform, topic_name))
        row = self.cursor.fetchone()
        if row:
            trend_id = row[0]
            self.cursor.execute('''UPDATE trending SET rank=?, category=?, post_count=?, scraped_at=? WHERE id=?''', (rank, category, post_count, now, trend_id))
        else:
            trend_id = str(uuid.uuid4())
            self.cursor.execute('''INSERT INTO trending (id, platform, rank, category, topic_name, post_count, scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?)''', (trend_id, platform, rank, category, topic_name, post_count, now))
        self.conn.commit()
        return trend_id
    
    def get_known_handle(self, query):
        """
        Pokusí se najít username v DB na základě query (shoda s username nebo display_name).
        Vrací username (str) nebo None.
        """
        clean_q = query.replace('@', '').strip()
        
        try:
            self.cursor.execute('''
                SELECT username FROM users 
                WHERE platform = 'X' AND (LOWER(username) = LOWER(?) OR LOWER(display_name) = LOWER(?))
                LIMIT 1
            ''', (clean_q, clean_q))
            row = self.cursor.fetchone()
            
            if row:
                return row[0]
            return None
            
        except Exception as e:
            print(f"[DB ERROR] Chyba při hledání handle: {e}")
            return None
        
    def upsert_connection(self, platform, source_username, target_username, connection_type="follower"):
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute('''
            SELECT id FROM connections 
            WHERE platform = ? AND source_username = ? AND target_username = ? AND connection_type = ?
        ''', (platform, source_username, target_username, connection_type))
        row = self.cursor.fetchone()
        
        if row:
            conn_id = row[0]
            self.cursor.execute('UPDATE connections SET scraped_at = ? WHERE id = ?', (now, conn_id))
        else:
            conn_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO connections (id, platform, source_username, target_username, connection_type, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (conn_id, platform, source_username, target_username, connection_type, now))
        self.conn.commit()
        return conn_id

    def close(self):
        if self.conn:
            self.cursor.close()
            self.conn.close()