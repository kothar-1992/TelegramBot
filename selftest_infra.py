"""Offline tests for the deployment helpers: health endpoint, keep-alive, snapshots.

    python selftest_infra.py
"""

from __future__ import annotations

import asyncio
import os
import socket
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx

import backup
import db
import health

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        FAILURES.append(label)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeBot:
    """Mimics the real `telegram.Bot` API surface the backup code touches.

    Note the deliberate detail: `get_me()` returns a bare `User` with **no**
    description attribute — the bio only comes back from `get_chat()`.
    """

    def __init__(self) -> None:
        self.description: str | None = "🛍 my shop"
        self.sent: list[tuple] = []

    async def set_my_description(self, description: str = "", **kw) -> None:
        self.description = description

    async def get_me(self):
        return SimpleNamespace(id=8725359712, username="shop_bot")

    async def get_chat(self, chat_id: int):
        return SimpleNamespace(id=chat_id, description=self.description)

    async def send_document(self, chat_id, document, caption=None, **kw):
        self.sent.append((chat_id, document, caption))
        return SimpleNamespace(document=SimpleNamespace(file_id="AgACAGUAAxkBAAIB1234"))


def main() -> int:
    return asyncio.run(_run())


async def _run() -> int:
    port = free_port()
    os.environ["PORT"] = str(port)

    print("1) health endpoint")
    server = health.start_health_server()
    check(server is not None, f"health server bound to :{port}")
    base = f"http://127.0.0.1:{port}"
    response = httpx.get(f"{base}/health", timeout=10)
    check(response.status_code == 200, "/health returns 200")
    check(response.json() == {"status": "ok"}, "/health returns a JSON status")
    check(httpx.get(f"{base}/", timeout=10).status_code == 200, "/ is an alias for /health")
    check(httpx.get(f"{base}/nope", timeout=10).status_code == 404, "unknown paths 404")
    check(httpx.get(f"{base}/health?x=1", timeout=10).status_code == 200, "query strings are ignored")

    print("2) keep-alive ping")
    check(health.ping(f"127.0.0.1:{port}") is True, "a bare host:port uses http:// for localhost")
    check(health.ping(f"http://127.0.0.1:{port}/health") is True, "an explicit URL works")
    check(health.ping(f"http://127.0.0.1:{port}/health?x=1") is True, "query strings survive normalisation")
    check(health._normalise("shop.onrender.com") == "https://shop.onrender.com/health", "public hosts get https")
    check(health._normalise("http://shop.onrender.com/") == "http://shop.onrender.com/health", "trailing slash trimmed")
    check(health.ping("http://127.0.0.1:1/health") is False, "ping failures are reported, not raised")

    print("3) database snapshot")
    source = Path(tempfile.mkdtemp()) / "shop.db"
    db.init(source)
    cat = db.add_category("USDT", "💰")
    db.add_product("USDT TRC20", 65_000, category_id=cat)
    db.change_balance(1234, 500)

    snapshot = backup.create_snapshot(source)
    check(snapshot is not None and snapshot.exists(), "snapshot file created")
    if snapshot:
        with closing(sqlite3.connect(snapshot)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM products").fetchall()
            balance = conn.execute("SELECT balance FROM users WHERE user_id = 1234").fetchone()
        check(len(rows) == 1 and rows[0]["name"] == "USDT TRC20", "snapshot carries the products")
        check(balance["balance"] == 500, "snapshot carries balances")
        check(snapshot.name.endswith("-snapshot.db"), "snapshot has a recognisable filename")
        snapshot.unlink(missing_ok=True)
        check(not snapshot.exists(), "create_snapshot releases the file handle")

    print("4) snapshot pointer lives in the bot profile")
    bot = FakeBot()
    check(await backup._recall(bot) is None, "no pointer before the first backup")
    check("shopdb:" not in (bot.description or ""), "a random bio is not mistaken for a pointer")

    await backup._remember(bot, "AgACAGUAAxkBAAIB1234")
    check("shopdb:AgACAGUAAxkBAAIB1234" in bot.description, "file_id is parked in the description")
    check(await backup._recall(bot) == "AgACAGUAAxkBAAIB1234", "pointer round-trips through getChat()")

    # Regression guard: getMe() carries no description; only getChat() does.
    me = await bot.get_me()
    check(not hasattr(me, "description"), "getMe() returns a bare User (no description field)")
    check(hasattr(await bot.get_chat(me.id), "description"), "getChat(bot_id) carries the bio")

    class BrokenBot(FakeBot):
        async def get_chat(self, chat_id):
            raise RuntimeError("boom")

    check(await backup._recall(BrokenBot()) is None, "a broken getChat never raises out of restore")

    print("5) dirty flag drives the backup job")
    db.clear_dirty()
    check(db.is_dirty() is False, "clean after clear")
    db.add_category("Accounts", "🎟")
    check(db.is_dirty() is True, "writes mark the database dirty")
    db.clear_dirty()
    check(db.is_dirty() is False, "flag clears again")

    if server is not None:
        server.shutdown()

    print()
    if FAILURES:
        print(f"❌ {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ deployment helpers work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())