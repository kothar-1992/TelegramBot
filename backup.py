"""Durable database snapshots stored in Telegram itself.

Free PaaS instances have an ephemeral filesystem — a redeploy or a crash
wipes ``shop.db`` and with it every product, balance and order.  Rather than
pull in an external database, the admin's own Telegram chat doubles as cloud
storage: the bot uploads a snapshot document and restores it on boot.

To find the snapshots again after a restart, their ``file_id`` values are
parked in the bot's own profile description (``GET /getChat`` returns it),
which survives every redeploy and costs no extra account.  A short ring of
recent ids is kept, so one failed profile update cannot strand the database.
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

#: Where the file_ids of the newest snapshots live. Render wipes the disk, not the profile.
MARKER = re.compile(r"shopdb:(.*)")
#: How many recent snapshots to remember. Fits comfortably in the 512-char bio.
KEEP_POINTERS = 3
#: Setting holding the timestamp of the last successful snapshot.
LAST_SAVE = "last_backup"


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
    """Park the newest snapshot's file_id in the bot profile, keeping a few spares."""
    recent = [file_id, *(old for old in await _recall(bot) if old != file_id)][:KEEP_POINTERS]
    try:
        await bot.set_my_description(description=f"🛍 {settings.shop_name}\nshopdb:{' '.join(recent)}")
    except Exception:
        log.warning("Could not store snapshot pointer in the bot profile", exc_info=True)


async def _recall(bot) -> list[str]:
    """Read the stored snapshot pointers back, newest first.

    NB: `getMe` returns a bare `User` object — it carries no description field.
    The bot's bio lives on `getChat(bot_id).description`.
    """
    try:
        chat = await bot.get_chat((await bot.get_me()).id)
        description = getattr(chat, "description", None) or ""
    except Exception:
        log.warning("Could not read the snapshot pointer from the bot profile", exc_info=True)
        return []
    match = MARKER.search(description)
    return [chunk for chunk in (match.group(1).split() if match else []) if chunk]


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


async def flush(bot, admin_id: int) -> bool:
    """Mirror the database to Telegram right now.

    Called after every admin edit so a deploy can never take the catalogue with
    it, and by the periodic job as a safety net.  A failure leaves the dirty
    flag set so the next run tries again.
    """
    if not enabled():
        return False
    if not db.is_dirty():
        return False

    file_id = await upload(bot, admin_id or settings.backup_admin_id)
    if file_id:
        # Record the time *before* clearing: writing the setting is itself a
        # write, so clearing first would leave the database dirty for ever and
        # the periodic job would snapshot again on every tick.
        db.set_setting(LAST_SAVE, db.stamp())
        db.clear_dirty()
        return True

    log.warning("Snapshot not saved — the catalogue stays dirty until the next attempt")
    return False


async def restore(bot) -> bool:
    """Download the newest usable snapshot over the local database.

    Each remembered id is tried in turn, so a snapshot that has expired or been
    deleted only costs a little time.
    """
    pointers = await _recall(bot)
    if not pointers:
        return False

    target = settings.db_path
    for index, file_id in enumerate(pointers):
        try:
            handle = await bot.get_file(file_id)
            await asyncio.to_thread(handle.download_to_drive, custom_path=str(target))
        except Exception:
            log.warning("Snapshot %d/%d is unusable, trying the next one", index + 1, len(pointers), exc_info=True)
            continue
        log.info("Restored %s from the Telegram snapshot (%d/%d)", target.name, index + 1, len(pointers))
        db.clear_dirty()  # what is on disk is now the source of truth
        return True
    return False


def enabled() -> bool:
    return settings.backup_enabled and chat_id() > 0


def chat_id() -> int:
    """Where snapshots go: the configured admin, else the first admin on file."""
    return settings.backup_admin_id or (settings.admin_ids[0] if settings.admin_ids else 0)