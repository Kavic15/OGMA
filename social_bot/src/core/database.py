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

    def _connect(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()

    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_user_id TEXT,
                username TEXT NOT NULL,
                display_name TEXT,
                bio TEXT,
                followers_count INTEGER,
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
        
        self.conn.commit()

    def upsert_user(self, platform, username, platform_user_id=None, display_name=None, bio=None, followers_count=None):
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
                    last_scraped = ?
                WHERE id = ?
            ''', (platform_user_id, display_name, bio, followers_count, now, user_id))
        else:
            user_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO users (id, platform, platform_user_id, username, display_name, bio, followers_count, last_scraped)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, platform, platform_user_id, username, display_name, bio, followers_count, now))
        
        self.conn.commit()
        return user_id

    def upsert_post(self, user_id, platform, platform_post_id, text_content, timestamp_posted, likes_count=0, shares_count=0, comments_count=0, url=None, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('SELECT id FROM posts WHERE platform_post_id = ?', (platform_post_id,))
        row = self.cursor.fetchone()
        
        if row:
            post_id = row[0]
            self.cursor.execute('''
                UPDATE posts SET
                    media_url = COALESCE(?, media_url),
                    likes_count = ?,
                    shares_count = ?,
                    comments_count = ?,
                    scraped_at = ?
                WHERE id = ?
            ''', (media_url, likes_count, shares_count, comments_count, now, post_id))
        else:
            post_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO posts (id, user_id, platform, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (post_id, user_id, platform, platform_post_id, text_content, media_url, timestamp_posted, likes_count, shares_count, comments_count, url, now))
        
        self.conn.commit()
        return post_id

    def upsert_comment(self, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, timestamp_posted, likes_count=0, shares_count=0, replies_count=0, media_url=None):
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('SELECT id FROM comments WHERE platform_comment_id = ?', (platform_comment_id,))
        row = self.cursor.fetchone()
        
        if row:
            comment_id = row[0]
            self.cursor.execute('''
                UPDATE comments SET
                    media_url = COALESCE(?, media_url),
                    likes_count = ?,
                    shares_count = ?,
                    replies_count = ?,
                    scraped_at = ?
                WHERE id = ?
            ''', (media_url, likes_count, shares_count, replies_count, now, comment_id))
        else:
            comment_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO comments (id, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (comment_id, post_id, platform, platform_comment_id, author_username, author_display_name, text_content, media_url, timestamp_posted, likes_count, shares_count, replies_count, now))
        
        self.conn.commit()
        return comment_id

    def upsert_trend(self, platform, rank, category, topic_name, post_count):
        now = datetime.now(timezone.utc).isoformat()
        
        self.cursor.execute('SELECT id FROM trending WHERE platform = ? AND topic_name = ?', (platform, topic_name))
        row = self.cursor.fetchone()
        
        if row:
            trend_id = row[0]
            self.cursor.execute('''
                UPDATE trending SET
                    rank = ?,
                    category = ?,
                    post_count = ?,
                    scraped_at = ?
                WHERE id = ?
            ''', (rank, category, post_count, now, trend_id))
        else:
            trend_id = str(uuid.uuid4())
            self.cursor.execute('''
                INSERT INTO trending (id, platform, rank, category, topic_name, post_count, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (trend_id, platform, rank, category, topic_name, post_count, now))
        
        self.conn.commit()
        return trend_id

    def close(self):
        if self.conn:
            self.conn.close()