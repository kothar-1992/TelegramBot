"""Offline tests for the deployment helpers: health endpoint, keep-alive, snapshots.

    python selftest_infra.py
"""

from __future__ import annotations

import asyncio
import dataclasses
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
import bot as bot_module
import db
import handlers_admin as admin
import health
from config import settings

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
        #: file_id -> bytes, standing in for Telegram's own storage.
        self.cloud: dict[str, bytes] = {}

    async def set_my_description(self, description: str = "", **kw) -> None:
        self.description = description

    async def get_me(self):
        return SimpleNamespace(id=8725359712, username="shop_bot")

    async def get_chat(self, chat_id: int):
        return SimpleNamespace(id=chat_id, description=self.description)

    async def send_document(self, chat_id, document, caption=None, **kw):
        name, handle = document
        self.cloud[f"file-{len(self.cloud)}"] = handle.read()
        handle.close()
        self.sent.append((chat_id, name, caption))
        newest = next(reversed(self.cloud))
        return SimpleNamespace(document=SimpleNamespace(file_id=newest))

    async def get_file(self, file_id):
        try:
            payload = self.cloud[file_id]
        except KeyError:
            raise RuntimeError("file is gone") from None
        return SimpleNamespace(download_to_drive=self._downloader(payload))

    @staticmethod
    def _downloader(payload: bytes):
        def download_to_drive(custom_path):
            with open(custom_path, "wb") as fh:
                fh.write(payload)

        return download_to_drive


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
    check(await backup._recall(bot) == [], "no pointer before the first backup")
    check("shopdb:" not in (bot.description or ""), "a random bio is not mistaken for a pointer")

    await backup._remember(bot, "AgACAGUAAxkBAAIB1234")
    check("shopdb:AgACAGUAAxkBAAIB1234" in bot.description, "file_id is parked in the description")
    check(await backup._recall(bot) == ["AgACAGUAAxkBAAIB1234"], "pointer round-trips through getChat()")

    await backup._remember(bot, "SecondSnapshot")
    pointers = await backup._recall(bot)
    check(pointers[0] == "SecondSnapshot", "the newest snapshot is tried first")
    check("AgACAGUAAxkBAAIB1234" in pointers, "the previous snapshot is kept as a spare")

    # Regression guard: getMe() carries no description; only getChat() does.
    me = await bot.get_me()
    check(not hasattr(me, "description"), "getMe() returns a bare User (no description field)")
    check(hasattr(await bot.get_chat(me.id), "description"), "getChat(bot_id) carries the bio")

    class BrokenBot(FakeBot):
        async def get_chat(self, chat_id):
            raise RuntimeError("boom")

    check(await backup._recall(BrokenBot()) == [], "a broken getChat never raises out of restore")

    print("5) dirty flag drives the backup job")
    db.clear_dirty()
    check(db.is_dirty() is False, "clean after clear")
    db.add_category("Accounts", "🎟")
    check(db.is_dirty() is True, "writes mark the database dirty")
    db.clear_dirty()
    check(db.is_dirty() is False, "flag clears again")

    print("6) flush saves the shop the moment an admin edits it")
    # `config` is frozen at import time, so swap the module's own binding.
    real_settings, backup.settings = backup.settings, dataclasses.replace(
        settings,
        backup_enabled=True,
        backup_admin_id=0,
        admin_ids=(999,),
        # Never point the backup helpers at the repository's own shop.db —
        # `restore()` overwrites whatever db_path names.
        db_path=source,
    )
    check(backup.enabled() is True, "snapshots are on once BACKUP_ENABLED is set")
    check(backup.chat_id() == 999, "snapshots go to the first admin when BACKUP_ADMIN_ID is unset")

    save_bot = FakeBot()
    db.clear_dirty()
    check(await backup.flush(save_bot, 999) is False, "a clean database is never uploaded")
    check(not save_bot.sent, "nothing was sent for a clean database")

    db.add_product("CapCut Pro", 10_000, category_id=cat)
    check(await backup.flush(save_bot, 999) is True, "an edit is saved immediately")
    check(len(save_bot.sent) == 1, "one snapshot reached the admin's chat")
    check(db.is_dirty() is False, "a successful save clears the dirty flag")

    class UselessBot(FakeBot):
        async def send_document(self, chat_id, document, caption=None, **kw):
            document[1].close()
            self.sent.append((chat_id, document[0], caption))
            raise RuntimeError("network down")

    db.add_product("Another Product", 20_000, category_id=cat)
    check(await backup.flush(UselessBot(), 999) is False, "a failed upload is reported")
    check(db.is_dirty() is True, "a failed save stays dirty so the next run retries")

    print("7) every admin handler is wrapped in a save")
    check(
        "status" in set(bot_module.ADMIN_COMMANDS),
        "/status is routed like every other admin command",
    )
    check(
        set(bot_module.ADMIN_COMMANDS) == {
            "addcat", "cats", "delcat", "addproduct", "products", "delproduct", "toggle",
            "give", "balance", "broadcast", "setbanner", "setname", "pending", "demo",
            "paymethods", "addpay", "delpay", "setlang", "status",
        },
        "every admin command is still routed",
    )
    wrapped = set(bot_module.ADMIN_COMMANDS.values()) | {bot_module.ADMIN_CALLBACK}
    check(len(wrapped) == len(set(wrapped)), "no handler was wrapped twice")
    check(
        all(getattr(h, "__wrapped__", None) is not None for h in wrapped),
        "admin commands and callbacks all trigger a save",
    )
    check(
        bot_module.saving(admin.cmd_products).__wrapped__ is admin.cmd_products,
        "the wrapper keeps the original handler",
    )
    print("8) the admin's catalogue survives a deploy")
    # This is the reported failure: an admin adds products, the free host is
    # rebuilt and wipes the disk.  Nothing may be lost.
    survive_bot = FakeBot()
    db.clear_dirty()
    for name in ("USDT TRC20", "USDT BEP20", "CapCut Pro", "Canva Pro", "Zoom Pro"):
        db.add_product(name, 10_000, category_id=cat)
    expected = {row["name"] for row in db.list_products(None, limit=50, active_only=False)}
    check(len(expected) == 6, f"the catalogue holds {len(expected)} products")
    check(await backup.flush(survive_bot, 999) is True, "the catalogue was saved on the spot")

    # Wipe the disk exactly like a redeploy does, then boot again.
    live = backup.settings.db_path
    check(live == source, "the test only ever touches its own temp database")
    live.write_bytes(b"")
    check(await backup.restore(survive_bot) is True, "the catalogue came back after the wipe")

    db.init(live)
    names = {row["name"] for row in db.list_products(None, limit=50, active_only=False)}
    check(names == expected, f"every product survived (missing {sorted(expected - names)})")
    check("CapCut Pro" in names, "the last product added is still there")
    check(db.get_user(1234)["balance"] == 500, "balances survived too")

    print("9) a dead snapshot falls back to the previous one")
    db.add_product("After The Snapshot", 1_000, category_id=cat)
    check(await backup.flush(survive_bot, 999) is True, "saved again before the fallback test")
    check(bool(db.get_setting(backup.LAST_SAVE)), "a successful save records when it happened")
    survive_bot.cloud.clear()  # Telegram expired everything we stored
    check(await backup.restore(survive_bot) is False, "restore fails cleanly when nothing is left")
    check(live.exists(), "a failed restore leaves the existing database alone")

    backup.settings = real_settings

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