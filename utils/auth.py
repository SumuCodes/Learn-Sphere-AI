# utils/auth.py
"""
User Authentication – Sign up, Login, Logout, Password management.
Uses SQLite with bcrypt for password hashing.
"""

import sqlite3
import time
import logging
import bcrypt
import streamlit as st
from pathlib import Path
from datetime import datetime

# Set up logger
logger = logging.getLogger(__name__)

# Ensure data directory exists
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "users.db"

# Brute-force protection
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_SECONDS = 300  # 5 minutes
_failed_attempts = {}  # {username: (count, first_attempt_time)}


def get_connection():
    """Return a database connection with WAL mode enabled."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except sqlite3.OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        raise RuntimeError(f"Database connection failed: {e}")


def init_db():
    """Initialize user database tables."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                theme TEXT DEFAULT 'dark',
                is_active INTEGER DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_id TEXT UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        conn.commit()
        logger.info("User database initialized successfully.")
    finally:
        conn.close()


# ==========================================================
# Password Functions
# ==========================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ==========================================================
# Brute-Force Protection
# ==========================================================

def _is_locked_out(username: str) -> bool:
    """Check if username is temporarily locked out."""
    if username not in _failed_attempts:
        return False
    count, first_attempt = _failed_attempts[username]
    if count >= _MAX_FAILED_ATTEMPTS:
        elapsed = time.time() - first_attempt
        if elapsed < _LOCKOUT_SECONDS:
            return True
        # Lockout expired, reset
        del _failed_attempts[username]
        return False
    return False


def _record_failed_attempt(username: str):
    """Record a failed login attempt."""
    now = time.time()
    if username in _failed_attempts:
        count, first_attempt = _failed_attempts[username]
        # Reset window if older than lockout period
        if now - first_attempt > _LOCKOUT_SECONDS:
            _failed_attempts[username] = (1, now)
        else:
            _failed_attempts[username] = (count + 1, first_attempt)
    else:
        _failed_attempts[username] = (1, now)


def _clear_failed_attempts(username: str):
    """Clear failed attempts on successful login."""
    _failed_attempts.pop(username, None)


# ==========================================================
# User Management
# ==========================================================

def create_user(username: str, email: str, password: str) -> bool:
    """Create a new user. Returns True if successful."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        conn.commit()
        logger.info(f"User created: {username}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"User creation failed (duplicate): {username}")
        return False  # Username or email already exists
    finally:
        conn.close()


def authenticate_user(username: str, password: str):
    """
    Authenticate a user. Returns user dict if successful, None otherwise.
    Includes brute-force protection.
    """
    # Check lockout
    if _is_locked_out(username):
        logger.warning(f"Locked out user attempted login: {username}")
        return None

    conn = get_connection()
    try:
        cursor = conn.cursor()
        user = cursor.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,)
        ).fetchone()

        if user and verify_password(password, user['password_hash']):
            # Success — clear failed attempts and update last login
            _clear_failed_attempts(username)
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user['id'],)
            )
            conn.commit()
            logger.info(f"User logged in: {username}")
            return dict(user)
        else:
            # Failed
            _record_failed_attempt(username)
            logger.warning(f"Failed login attempt for username: {username}")
            return None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    """Get user by ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        user = cursor.execute(
            "SELECT id, username, email, created_at, last_login, theme FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return dict(user) if user else None
    finally:
        conn.close()


def update_user_theme(user_id: int, theme: str):
    """Update user's theme preference."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET theme = ? WHERE id = ?",
            (theme, user_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_user_theme(user_id: int) -> str:
    """Get user's theme preference."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        result = cursor.execute(
            "SELECT theme FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return result['theme'] if result else 'dark'
    finally:
        conn.close()


def delete_user_account(user_id: int):
    """Soft delete a user account."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        logger.info(f"User account soft-deleted: {user_id}")
    finally:
        conn.close()


# ==========================================================
# Session Management
# ==========================================================

def get_current_user():
    """Get the currently logged-in user from session state."""
    if 'user_id' in st.session_state and st.session_state.user_id:
        return get_user_by_id(st.session_state.user_id)
    return None


def is_logged_in() -> bool:
    """Check if a user is logged in."""
    return 'user_id' in st.session_state and st.session_state.user_id is not None


def login_user(user_id: int):
    """Log in a user by setting session state."""
    st.session_state.user_id = user_id
    st.session_state.logged_in = True
    user = get_user_by_id(user_id)
    if user:
        st.session_state.username = user['username']
        st.session_state.theme = user.get('theme', 'dark')
        logger.info(f"Session started for user: {user['username']}")
    else:
        logger.error(f"login_user called with invalid user_id: {user_id}")
        st.session_state.logged_in = False


def logout_user():
    """Log out the current user."""
    username = st.session_state.get('username', 'Unknown')
    for key in ['user_id', 'username', 'logged_in']:
        if key in st.session_state:
            del st.session_state[key]
    logger.info(f"User logged out: {username}")