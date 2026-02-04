import sqlite3
from contextlib import contextmanager
from datetime import datetime

DATABASE_PATH = "publiclinks.db"


def init_db():
    """Initialize the database with required tables."""
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                picture TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT REFERENCES users(id),
                filename TEXT NOT NULL,
                r2_key TEXT UNIQUE NOT NULL,
                dub_url TEXT,
                dub_link_id TEXT,
                dub_key TEXT,
                content_type TEXT,
                size_bytes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add dub_link_id and dub_key columns if they don't exist (migration for existing DBs)
        try:
            db.execute("ALTER TABLE files ADD COLUMN dub_link_id TEXT")
        except:
            pass  # Column already exists
        try:
            db.execute("ALTER TABLE files ADD COLUMN dub_key TEXT")
        except:
            pass  # Column already exists
        db.commit()


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# User operations
def get_or_create_user(user_id: str, email: str, name: str, picture: str = None) -> dict:
    """Get existing user or create new one."""
    with get_db() as db:
        cursor = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if user:
            # Update user info in case it changed
            db.execute(
                "UPDATE users SET email = ?, name = ?, picture = ? WHERE id = ?",
                (email, name, picture, user_id)
            )
            db.commit()
        else:
            db.execute(
                "INSERT INTO users (id, email, name, picture) VALUES (?, ?, ?, ?)",
                (user_id, email, name, picture)
            )
            db.commit()
        
        cursor = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return dict(cursor.fetchone())


def get_user_by_id(user_id: str) -> dict | None:
    """Get user by ID."""
    with get_db() as db:
        cursor = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# File operations
def create_file(user_id: str, filename: str, r2_key: str, content_type: str, size_bytes: int, dub_url: str = None) -> dict:
    """Create a new file record."""
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO files (user_id, filename, r2_key, content_type, size_bytes, dub_url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, filename, r2_key, content_type, size_bytes, dub_url)
        )
        db.commit()
        file_id = cursor.lastrowid
        
        cursor = db.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        return dict(cursor.fetchone())


def get_all_files() -> list[dict]:
    """Get all files with uploader info."""
    with get_db() as db:
        cursor = db.execute("""
            SELECT f.*, u.email as uploader_email, u.name as uploader_name
            FROM files f
            JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_file_by_id(file_id: int) -> dict | None:
    """Get file by ID."""
    with get_db() as db:
        cursor = db.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_file_by_r2_key(r2_key: str) -> dict | None:
    """Get file by R2 key."""
    with get_db() as db:
        cursor = db.execute("SELECT * FROM files WHERE r2_key = ?", (r2_key,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_file(file_id: int) -> bool:
    """Delete a file record."""
    with get_db() as db:
        cursor = db.execute("DELETE FROM files WHERE id = ?", (file_id,))
        db.commit()
        return cursor.rowcount > 0


def update_file_dub_url(file_id: int, dub_url: str, dub_link_id: str = None, dub_key: str = None):
    """Update the dub.co URL for a file."""
    with get_db() as db:
        db.execute(
            "UPDATE files SET dub_url = ?, dub_link_id = ?, dub_key = ? WHERE id = ?",
            (dub_url, dub_link_id, dub_key, file_id)
        )
        db.commit()


def update_file_dub_link(file_id: int, dub_url: str, dub_key: str):
    """Update the dub.co URL and key for a file (when editing the short link)."""
    with get_db() as db:
        db.execute(
            "UPDATE files SET dub_url = ?, dub_key = ? WHERE id = ?",
            (dub_url, dub_key, file_id)
        )
        db.commit()
