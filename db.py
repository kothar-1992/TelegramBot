"""SQLite storage layer.

Everything the bot needs to remember lives here: users, balances, catalogue
categories, products, orders, admin settings and a small per-user session
state (navigation trail + pending action).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()
_dirty = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    full_name  TEXT,
    balance    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    emoji      TEXT NOT NULL DEFAULT '📦',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price       INTEGER NOT NULL DEFAULT 0,
    stock       INTEGER NOT NULL DEFAULT -1,
    photo_id    TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty        INTEGER NOT NULL DEFAULT 1,
    total      INTEGER NOT NULL DEFAULT 0,
    status     TEXT NOT NULL DEFAULT 'pending',
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    user_id  INTEGER PRIMARY KEY,
    trail    TEXT NOT NULL DEFAULT '[]',
    msgs     TEXT NOT NULL DEFAULT '[]',
    pending  TEXT
);
"""


# --------------------------------------------------------------------------- #
# connection helpers
# --------------------------------------------------------------------------- #
def init(path: Path | str) -> None:
    """Open (and if needed create) the database file."""
    global _conn
    with _lock:
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.executescript(SCHEMA)
        _conn.commit()


def _rows(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return _conn.execute(sql, params).fetchall()


def _one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    rows = _rows(sql, params)
    return rows[0] if rows else None


def _exec(sql: str, params: tuple = ()) -> int:
    global _dirty
    with _lock:
        cur = _conn.execute(sql, params)
        _conn.commit()
        if cur.rowcount >= 0 and not sql.lstrip().upper().startswith(("SELECT", "PRAGMA")):
            _dirty = True
        return cur.lastrowid or 0


def is_dirty() -> bool:
    """True when a write happened since the last :func:`clear_dirty` (backup trigger)."""
    return _dirty


def clear_dirty() -> None:
    global _dirty
    _dirty = False


def backend_ready() -> bool:
    """True once :func:`init` has run — lets helpers query settings before boot."""
    return _conn is not None


# --------------------------------------------------------------------------- #
# users & balance
# --------------------------------------------------------------------------- #
def upsert_user(user_id: int, username: str | None, full_name: str | None) -> sqlite3.Row:
    _exec(
        "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, "
        "full_name=excluded.full_name",
        (user_id, username, full_name),
    )
    return get_user(user_id)


def get_user(user_id: int) -> sqlite3.Row | None:
    return _one("SELECT * FROM users WHERE user_id = ?", (user_id,))


def get_balance(user_id: int) -> int:
    row = _one("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    return int(row["balance"]) if row else 0


def change_balance(user_id: int, delta: int) -> int:
    """Add (or subtract) `delta` from a balance and return the new value."""
    with _lock:
        _conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        _conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        _conn.commit()
    return get_balance(user_id)


def user_count() -> int:
    return _one("SELECT COUNT(*) AS c FROM users")["c"]


def top_users(limit: int = 10) -> list[sqlite3.Row]:
    return _rows("SELECT * FROM users ORDER BY balance DESC LIMIT ?", (limit,))


# --------------------------------------------------------------------------- #
# categories & products
# --------------------------------------------------------------------------- #
def add_category(name: str, emoji: str = "📦") -> int:
    order = _one("SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM categories")["n"]
    return _exec("INSERT INTO categories (name, emoji, sort_order) VALUES (?, ?, ?)", (name, emoji, order))


def list_categories() -> list[sqlite3.Row]:
    return _rows(
        "SELECT c.*, (SELECT COUNT(*) FROM products p "
        " WHERE p.category_id = c.id AND p.is_active = 1) AS item_count "
        "FROM categories c ORDER BY c.sort_order, c.id"
    )


def get_category(cat_id: int) -> sqlite3.Row | None:
    return _one("SELECT * FROM categories WHERE id = ?", (cat_id,))


def find_category(name: str) -> sqlite3.Row | None:
    return _one("SELECT * FROM categories WHERE lower(name) = lower(?)", (name.strip(),))


def delete_category(cat_id: int) -> None:
    _exec("DELETE FROM categories WHERE id = ?", (cat_id,))


def add_product(
    name: str,
    price: int,
    category_id: int | None = None,
    description: str = "",
    photo_id: str | None = None,
    stock: int = -1,
) -> int:
    return _exec(
        "INSERT INTO products (category_id, name, description, price, stock, photo_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (category_id, name, description, price, stock, photo_id),
    )


def list_products(category_id: int | None, offset: int = 0, limit: int = 6, active_only: bool = True) -> list[sqlite3.Row]:
    where = "WHERE is_active = 1" if active_only else ""
    params: list[Any] = []
    if category_id is not None:
        where = f"{where} AND category_id = ?".strip()
        params.append(category_id)
    params.extend([limit, offset])
    return _rows(
        f"SELECT p.*, c.name AS cat_name, c.emoji AS cat_emoji FROM products p "
        f"LEFT JOIN categories c ON c.id = p.category_id {where} "
        f"ORDER BY p.id DESC LIMIT ? OFFSET ?",
        tuple(params),
    )


def count_products(category_id: int | None = None, active_only: bool = True) -> int:
    where = "WHERE is_active = 1" if active_only else ""
    params: tuple = ()
    if category_id is not None:
        where = f"{where} AND category_id = ?".strip()
        params = (category_id,)
    return _one(f"SELECT COUNT(*) AS c FROM products {where}", params)["c"]


def get_product(product_id: int) -> sqlite3.Row | None:
    return _one(
        "SELECT p.*, c.name AS cat_name, c.emoji AS cat_emoji FROM products p "
        "LEFT JOIN categories c ON c.id = p.category_id WHERE p.id = ?",
        (product_id,),
    )


def set_product_photo(product_id: int, photo_id: str) -> None:
    _exec("UPDATE products SET photo_id = ? WHERE id = ?", (photo_id, product_id))


def set_product_active(product_id: int, active: bool) -> None:
    _exec("UPDATE products SET is_active = ? WHERE id = ?", (1 if active else 0, product_id))


def delete_product(product_id: int) -> None:
    _exec("DELETE FROM products WHERE id = ?", (product_id,))


def decrease_stock(product_id: int, qty: int) -> None:
    _exec("UPDATE products SET stock = CASE WHEN stock < 0 THEN -1 ELSE stock - ? END WHERE id = ?", (qty, product_id))


# --------------------------------------------------------------------------- #
# orders
# --------------------------------------------------------------------------- #
def create_order(user_id: int, product_id: int, qty: int, total: int, note: str = "") -> int:
    return _exec(
        "INSERT INTO orders (user_id, product_id, qty, total, note) VALUES (?, ?, ?, ?, ?)",
        (user_id, product_id, qty, total, note),
    )


def get_order(order_id: int) -> sqlite3.Row | None:
    return _one("SELECT * FROM orders WHERE id = ?", (order_id,))


def set_order_status(order_id: int, status: str) -> None:
    _exec("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


def user_orders(user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    return _rows(
        "SELECT o.*, p.name AS product_name FROM orders o "
        "LEFT JOIN products p ON p.id = o.product_id "
        "WHERE o.user_id = ? ORDER BY o.id DESC LIMIT ?",
        (user_id, limit),
    )


def pending_orders(limit: int = 50) -> list[sqlite3.Row]:
    return _rows(
        "SELECT o.*, p.name AS product_name, u.username, u.full_name FROM orders o "
        "LEFT JOIN products p ON p.id = o.product_id "
        "LEFT JOIN users u ON u.user_id = o.user_id "
        "WHERE o.status = 'pending' ORDER BY o.id LIMIT ?",
        (limit,),
    )


def order_count() -> int:
    return _one("SELECT COUNT(*) AS c FROM orders")["c"]


# --------------------------------------------------------------------------- #
# key/value settings
# --------------------------------------------------------------------------- #
def get_setting(key: str, default: str | None = None) -> str | None:
    row = _one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str | None) -> None:
    _exec(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


# --------------------------------------------------------------------------- #
# per-user session state
# --------------------------------------------------------------------------- #
def _session(user_id: int) -> sqlite3.Row:
    row = _one("SELECT * FROM sessions WHERE user_id = ?", (user_id,))
    if row is None:
        _exec("INSERT OR IGNORE INTO sessions (user_id) VALUES (?)", (user_id,))
        row = _one("SELECT * FROM sessions WHERE user_id = ?", (user_id,))
    return row


def trail(user_id: int) -> list[str]:
    """Navigation stack of visited screens; the last entry is the current one."""
    try:
        return json.loads(_session(user_id)["trail"])
    except (json.JSONDecodeError, TypeError):
        return []


def set_trail(user_id: int, entries: list[str]) -> None:
    _exec("UPDATE sessions SET trail = ? WHERE user_id = ?", (json.dumps(entries), user_id))


def push_trail(user_id: int, entry: str) -> None:
    set_trail(user_id, trail(user_id) + [entry])


def pop_trail(user_id: int) -> str | None:
    entries = trail(user_id)
    if not entries:
        return None
    entry = entries.pop()
    set_trail(user_id, entries)
    return entry


def clear_trail(user_id: int) -> None:
    set_trail(user_id, [])


def set_msgs(user_id: int, msgs: list[int]) -> None:
    _exec("UPDATE sessions SET msgs = ? WHERE user_id = ?", (json.dumps(msgs), user_id))


def add_msgs(user_id: int, new_ids: list[int]) -> None:
    """Track extra bot messages (confirmations, notices) so they get cleaned up."""
    set_msgs(user_id, get_msgs(user_id) + new_ids)


def get_msgs(user_id: int) -> list[int]:
    try:
        return json.loads(_session(user_id)["msgs"])
    except (json.JSONDecodeError, TypeError):
        return []


def set_pending(user_id: int, data: dict | None) -> None:
    _exec("UPDATE sessions SET pending = ? WHERE user_id = ?", (json.dumps(data) if data else None, user_id))


def get_pending(user_id: int) -> dict | None:
    try:
        return json.loads(_session(user_id)["pending"])
    except (json.JSONDecodeError, TypeError):
        return None


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")