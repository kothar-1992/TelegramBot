"""Durable database snapshots stored in Telegram itself.

Free PaaS instances have an ephemeral filesystem — a redeploy or a crash
wipes ``shop.db`` and with it every product, balance and order.  Rather than
pull in an external database, the admin's own Telegram chat doubles as cloud
storage: the bot uploads a snapshot document and restores it on boot.

To find the snapshot again after a restart, the newest document's ``file_id``
is parked in the bot's own profile description (``GET /getMe`` returns it),
which survives every redeploy and costs no extra account.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import db
from config import settings
from lang import t

log = logging.getLogger(__name__)

#: Where the file_id of the newest snapshot lives. Render wipes the disk, not the profile.
MARKER = re.compile(r"shopdb:([A-Za-z0-9_\-]+)")


def _snapshot_path() -> Path:
    return Path(tempfile.gettempdir()) / f"{settings.db_path.stem}-snapshot.db"


def create_snapshot(source: Path) -> Path | None:
    """Copy the live database into a temp file using SQLite's online backup API."""
    target = _snapshot_path()
    try:
        # `with sqlite3.connect(...)` only ends the transaction — it does not
        # close the handle, so close() explicitly or Windows keeps the file locked.
        with closing(sqlite3.connect(str(source))) as src, closing(sqlite3.connect(str(target))) as dst:
            src.backup(dst)
    except (sqlite3.Error, OSError):
        log.warning("Could not create database snapshot", exc_info=True)
        return None
    return target


async def _remember(bot, file_id: str) -> None:
    """Park the snapshot's file_id in the bot profile so a restart can find it."""
    try:
        await bot.set_my_description(description=f"🛍 {settings.shop_name}\nshopdb:{file_id}")
    except Exception:
        log.warning("Could not store snapshot pointer in the bot profile", exc_info=True)


async def _recall(bot) -> str | None:
    """Read the pointer back out of the bot profile.

    NB: `getMe` returns a bare `User` object — it carries no description field.
    The bot's bio lives on `getChat(bot_id).description`.
    """
    try:
        chat = await bot.get_chat((await bot.get_me()).id)
        match = MARKER.search(getattr(chat, "description", None) or "")
    except Exception:
        log.warning("Could not read the snapshot pointer from the bot profile", exc_info=True)
        return None
    return match.group(1) if match else None


async def upload(bot, admin_id: int) -> str | None:
    """Upload a fresh snapshot. Returns its file_id (also saved to the profile)."""
    source = settings.db_path
    if not source.exists():
        return None

    snapshot = await asyncio.to_thread(create_snapshot, source)
    if snapshot is None:
        return None

    size = snapshot.stat().st_size
    try:
        with snapshot.open("rb") as fh:
            message = await bot.send_document(
                chat_id=admin_id,
                document=(snapshot.name, fh),
                caption=t(
                    "backup_caption",
                    when=db.stamp(),
                    users=db.user_count(),
                    orders=db.order_count(),
                ),
                parse_mode="HTML",
            )
    except Exception:
        log.warning("Snapshot upload failed", exc_info=True)
        return None
    finally:
        snapshot.unlink(missing_ok=True)

    file_id = getattr(message.document, "file_id", None)
    if file_id:
        await _remember(bot, file_id)
    log.info("Database snapshot uploaded (%s bytes)", f"{size:,}")
    return file_id


async def restore(bot) -> bool:
    """Download the newest snapshot over the local database. True if one was applied."""
    file_id = await _recall(bot)
    if not file_id:
        return False

    target = settings.db_path
    try:
        handle = await bot.get_file(file_id)
        await asyncio.to_thread(handle.download_to_drive, custom_path=str(target))
    except Exception:
        log.warning("Snapshot restore failed", exc_info=True)
        return False

    log.info("Restored %s from the Telegram snapshot", target.name)
    return True


def enabled() -> bool:
    return settings.backup_enabled and settings.backup_admin_id > 0