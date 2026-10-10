"""SQLite storage layer.

Everything the bot needs to remember lives here: users, balances, catalogue
categories, products, orders, admin settings and a small per-user session
state (navigation trail + pending action).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()
_dirty = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    full_name  TEXT,
    balance    INTEGER NOT NULL DEFAULT 0,
    language   TEXT,
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

CREATE TABLE IF NOT EXISTS payment_methods (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    emoji           TEXT NOT NULL DEFAULT '💳',
    account_name    TEXT NOT NULL DEFAULT '',
    account_number  TEXT NOT NULL DEFAULT '',
    note            TEXT NOT NULL DEFAULT '',
    sort_order      INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS topup_requests (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    amount             INTEGER NOT NULL,
    reference          TEXT NOT NULL DEFAULT '',
    photo_path         TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'pending',
    notice_message_id  INTEGER,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at        TEXT
);
"""

#: Shipped with every install so a fresh shop can take payments right away.
DEFAULT_PAYMENT_METHODS: tuple[tuple[str, str], ...] = (
    ("💳", "KBZPay"),
    ("📱", "AYAPAY"),
    ("💳", "CBPAY ACCOUNT SPECIAL"),
    ("💎", "BINANCE PAY"),
    ("🪙", "USDT (BEP20)"),
)


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
    _migrate()
    _seed_payment_methods()


def _migrate() -> None:
    """Add columns introduced after a database was first created."""
    columns = {row["name"] for row in _rows("PRAGMA table_info(products)")}
    for name, ddl in (("warranty", "TEXT"), ("tutorial_url", "TEXT"), ("delivery", "TEXT")):
        if name not in columns:
            _exec(f"ALTER TABLE products ADD COLUMN {name} {ddl}")

    user_columns = {row["name"] for row in _rows("PRAGMA table_info(users)")}
    if "language" not in user_columns:
        _exec("ALTER TABLE users ADD COLUMN language TEXT")


def _seed_payment_methods() -> None:
    if _one("SELECT COUNT(*) AS c FROM payment_methods")["c"]:
        return
    for order, (emoji, name) in enumerate(DEFAULT_PAYMENT_METHODS, start=1):
        _exec(
            "INSERT INTO payment_methods (name, emoji, sort_order) VALUES (?, ?, ?)",
            (name, emoji, order),
        )
    log.info("Seeded %d default payment methods", len(DEFAULT_PAYMENT_METHODS))


def list_payment_methods(active_only: bool = True) -> list[sqlite3.Row]:
    where = "WHERE is_active = 1" if active_only else ""
    return _rows(f"SELECT * FROM payment_methods {where} ORDER BY sort_order, id")


def get_payment_method(method_id: int) -> sqlite3.Row | None:
    return _one("SELECT * FROM payment_methods WHERE id = ?", (method_id,))


def add_payment_method(name: str, emoji: str, account_name: str = "", account_number: str = "", note: str = "") -> int:
    order = _one("SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM payment_methods")["n"]
    return _exec(
        "INSERT INTO payment_methods (name, emoji, account_name, account_number, note, sort_order) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, emoji, account_name, account_number, note, order),
    )


def delete_payment_method(method_id: int) -> None:
    _exec("DELETE FROM payment_methods WHERE id = ?", (method_id,))


# --------------------------------------------------------------------------- #
# top-up requests (receipt review queue)
# --------------------------------------------------------------------------- #
def create_topup(user_id: int, amount: int, reference: str = "", photo_path: str = "") -> int:
    return _exec(
        "INSERT INTO topup_requests (user_id, amount, reference, photo_path) VALUES (?, ?, ?, ?)",
        (user_id, amount, reference, photo_path),
    )


def get_topup(request_id: int) -> sqlite3.Row | None:
    return _one("SELECT * FROM topup_requests WHERE id = ?", (request_id,))


def set_topup_notice(request_id: int, message_id: int) -> None:
    _exec("UPDATE topup_requests SET notice_message_id = ? WHERE id = ?", (message_id, request_id))


def resolve_topup(request_id: int, status: str) -> None:
    _exec(
        "UPDATE topup_requests SET status = ?, resolved_at = datetime('now') WHERE id = ?",
        (status, request_id),
    )


def pending_topups() -> list[sqlite3.Row]:
    return _rows("SELECT * FROM topup_requests WHERE status = 'pending' ORDER BY id")


def stale_topups(max_age_minutes: int) -> list[sqlite3.Row]:
    """Pending requests the admin never touched within the review window."""
    return _rows(
        "SELECT * FROM topup_requests WHERE status = 'pending' AND created_at < datetime('now', ?)",
        (f"-{int(max_age_minutes)} minutes",),
    )


def user_topups(user_id: int, limit: int = 5) -> list[sqlite3.Row]:
    return _rows("SELECT * FROM topup_requests WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))


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


def get_language(user_id: int) -> str | None:
    """The language the customer picked, or None if they have not chosen yet."""
    row = _one("SELECT language FROM users WHERE user_id = ?", (user_id,))
    return row["language"] if row else None


def set_language(user_id: int, code: str) -> None:
    _ensure_user(user_id)
    _exec("UPDATE users SET language = ? WHERE user_id = ?", (code, user_id))


def _ensure_user(user_id: int) -> None:
    _exec("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))


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
    warranty: str = "",
    tutorial_url: str = "",
) -> int:
    return _exec(
        "INSERT INTO products (category_id, name, description, price, stock, photo_id, warranty, tutorial_url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (category_id, name, description, price, stock, photo_id, warranty, tutorial_url),
    )


def list_products(
    category_id: int | None,
    offset: int = 0,
    limit: int = 6,
    active_only: bool = True,
    buyable_first: bool = False,
) -> list[sqlite3.Row]:
    """Products newest-first; `buyable_first` sinks sold-out items to the end."""
    where = "WHERE is_active = 1" if active_only else ""
    params: list[Any] = []
    if category_id is not None:
        where = f"{where} AND category_id = ?".strip()
        params.append(category_id)
    order = "ORDER BY (p.stock = 0), p.id DESC" if buyable_first else "ORDER BY p.id DESC"
    params.extend([limit, offset])
    return _rows(
        f"SELECT p.*, c.name AS cat_name, c.emoji AS cat_emoji FROM products p "
        f"LEFT JOIN categories c ON c.id = p.category_id {where} "
        f"{order} LIMIT ? OFFSET ?",
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


def _ensure_session(user_id: int) -> None:
    """Make sure the session row exists before an UPDATE writes to it.

    Without this every setter silently no-ops for a user who has never opened
    a screen — which broke the top-up flow on a first message.
    """
    _exec("INSERT OR IGNORE INTO sessions (user_id) VALUES (?)", (user_id,))


def trail(user_id: int) -> list[str]:
    """Navigation stack of visited screens; the last entry is the current one."""
    try:
        return json.loads(_session(user_id)["trail"])
    except (json.JSONDecodeError, TypeError):
        return []


def set_trail(user_id: int, entries: list[str]) -> None:
    _ensure_session(user_id)
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
    _ensure_session(user_id)
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
    _ensure_session(user_id)
    _exec("UPDATE sessions SET pending = ? WHERE user_id = ?", (json.dumps(data) if data else None, user_id))


def get_pending(user_id: int) -> dict | None:
    try:
        return json.loads(_session(user_id)["pending"])
    except (json.JSONDecodeError, TypeError):
        return None


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")