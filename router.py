"""Navigation router.

Handles swapping the currently visible bot messages for a new screen, and
implements the ⬅️ Back / 🏠 Main Menu trail stored in the database so that
history survives bot restarts.

Ordering matters: a new screen is **sent before** the old one is deleted.  If
Telegram is slow, the customer keeps looking at a usable screen instead of an
empty chat, and a send that fails outright leaves the previous screen intact.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, RetryAfter, TelegramError, TimedOut
from telegram.ext import ContextTypes

import db
import lang
import views
from keyboards import MAIN
from views import Part

log = logging.getLogger(__name__)

#: Telegram tolerates a few concurrent sends to one chat; more risks FloodWait.
SEND_FANOUT = 3

#: A screen body is either ready-made text or a thunk rendered in the recipient's
#: language at send time (an admin replying to a customer in *their* language).
def _render(text: str | Callable[[], str], language: str | None) -> str:
    """Build a message body, activating `language` for the duration."""
    if callable(text):
        previous = lang.get()
        lang.set_lang(language or previous)
        try:
            return text()
        finally:
            lang.set_lang(previous)
    return text


async def _delete_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_ids: Iterable[int]) -> None:
    """Best-effort clean-up; a message that refuses to go is not worth failing over."""
    ids = [message_id for message_id in message_ids if message_id]
    if not ids:
        return
    gate = asyncio.Semaphore(SEND_FANOUT)

    async def one(message_id: int) -> None:
        async with gate:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except BadRequest:
                pass  # already gone — Telegram's own clean-up, or a rollback
            except TelegramError:
                log.debug("Could not delete message %s in %s", message_id, chat_id, exc_info=True)

    await asyncio.gather(*(one(message_id) for message_id in ids))


async def _send_part(context: ContextTypes.DEFAULT_TYPE, user_id: int, part: Part) -> int:
    reply_markup = part.reply_keyboard or part.keyboard
    if part.photo:
        msg = await context.bot.send_photo(
            chat_id=user_id,
            photo=part.photo,
            caption=part.text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    else:
        msg = await context.bot.send_message(
            chat_id=user_id,
            text=part.text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    return msg.message_id


async def _send_part_safely(context: ContextTypes.DEFAULT_TYPE, user_id: int, part: Part) -> int | None:
    """Send one part, riding out a rate limit or a single timeout.

    PTB raises `RetryAfter` for HTTP 429, so a flood-limited send waits the
    server's own cooldown instead of being thrown away.
    """
    for attempt in range(3):
        try:
            return await _send_part(context, user_id, part)
        except RetryAfter as err:
            cooldown = err.retry_after.total_seconds() if hasattr(err.retry_after, "total_seconds") else err.retry_after
            log.info("Rate limited; waiting %.1fs before retrying", cooldown)
            await asyncio.sleep(min(cooldown + 0.5, 60))
        except TimedOut:
            # Back off rather than hammering a connection that is already struggling.
            log.debug("Send timed out (attempt %d), retrying", attempt + 1)
            await asyncio.sleep(0.4 * (attempt + 1))
        except TelegramError:
            log.warning("Could not send a message part", exc_info=True)
            return None
    return None


async def _send_parts(context: ContextTypes.DEFAULT_TYPE, user_id: int, parts: list[Part]) -> list[int] | None:
    """Send every part of a screen; return their ids, or None if any failed.

    A few at a time keeps a multi-card screen snappy without tripping the
    per-chat flood limit.  A partial screen is never returned — the caller
    rolls it back rather than leaving a half-drawn screen behind.
    """
    gate = asyncio.Semaphore(SEND_FANOUT)

    async def one(part: Part) -> int | None:
        async with gate:
            return await _send_part_safely(context, user_id, part)

    sent = list(await asyncio.gather(*(one(part) for part in parts)))
    if any(message_id is None for message_id in sent):
        return None
    return [message_id for message_id in sent if message_id is not None]


async def _try_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, part: Part) -> bool:
    """Seamlessly edit the single visible message when possible."""
    query = update.callback_query
    if query is None or query.message is None or part.keyboard is None:
        return False
    try:
        if part.photo:
            await query.edit_message_caption(caption=part.text, reply_markup=part.keyboard, parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(text=part.text, reply_markup=part.keyboard, parse_mode=ParseMode.HTML)
        return True
    except BadRequest:
        # Text <-> caption mismatch, or "message is not modified": fall through to resend.
        return False


async def go(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target: str,
    *,
    trail: list[str] | None = None,
) -> None:
    """Render the screen identified by the `target` callback payload.

    `trail` is the full navigation stack *including* `target`.  When omitted a
    new visit to `target` is appended to the current stack — except for the
    main menu, which always resets navigation to the root.

    The new screen is sent *before* the old one is cleared.  Telegram is often
    slow on a bad connection, and deleting first leaves the chat blank while
    the replacement is still in flight; sending first means the customer always
    has something readable on screen.  If the send fails outright, the previous
    screen is left alone and they are asked to try again.
    """
    user_id = update.effective_user.id
    db.upsert_user(user_id, update.effective_user.username, update.effective_user.full_name)

    previous_trail = db.trail(user_id)
    if trail is None:
        trail = [] if target == MAIN else previous_trail + [target]

    parts = views.build(target, user_id)
    old_msgs = db.get_msgs(user_id)

    # Fast path: exactly one visible message and the new screen is one message.
    # (A part carrying a reply keyboard must be sent fresh, never edited.)
    # This one is atomic — the message is swapped, never absent.
    if len(parts) == 1 and parts[0].reply_keyboard is None and len(old_msgs) == 1 and update.callback_query is not None:
        if await _try_edit(update, context, parts[0]):
            db.set_trail(user_id, trail)
            db.set_msgs(user_id, old_msgs)
            return

    new_ids = await _send_parts(context, user_id, parts)
    if new_ids is None:
        # Nothing was drawn, so nothing is cleared: keep the screen we have.
        log.warning("Screen %r not sent for %s — keeping the previous one", target, user_id)
        await _alert(update)
        return

    db.set_trail(user_id, trail)
    db.set_msgs(user_id, new_ids)
    await _delete_messages(context, user_id, [m for m in old_msgs if m not in new_ids])


async def _alert(update: Update) -> None:
    """Tell a customer whose screen failed to load, without losing their place."""
    query = getattr(update, "callback_query", None)
    try:
        if query is not None:
            await query.answer(lang.t("try_again"), show_alert=True)
        elif update.effective_message is not None:
            await update.effective_message.reply_text(lang.t("try_again"))
    except TelegramError:
        log.debug("Could not show the retry notice", exc_info=True)


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Leave the current screen and re-render the one before it."""
    user_id = update.effective_user.id
    stack = db.trail(user_id)
    if not stack:
        await go(update, context, MAIN, trail=[])
        return

    stack.pop()  # drop the screen we are leaving
    if stack:
        await go(update, context, stack[-1], trail=stack)
    else:
        await go(update, context, MAIN, trail=[])


async def notify(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text: str | Callable[[], str],
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    language: str | None = None,
) -> None:
    """Send a one-off message to the user and track it for clean-up."""
    message = await context.bot.send_message(
        user_id, _render(text, language), reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    db.add_msgs(user_id, [message.message_id])


async def notice(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text: str | Callable[[], str],
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    language: str | None = None,
) -> int:
    """Send a message that must survive navigation (e.g. a pending review).

    Returns the message id so it can be edited later when the request is
    approved, rejected or times out.
    """
    message = await context.bot.send_message(
        user_id, _render(text, language), reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    return message.message_id


async def replace_notice(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    message_id: int | None,
    text: str | Callable[[], str],
    *,
    language: str | None = None,
) -> None:
    """Rewrite a notice in place; falls back to a fresh message when needed."""
    if not message_id:
        return
    try:
        await context.bot.edit_message_text(
            chat_id=user_id, message_id=message_id, text=_render(text, language), parse_mode=ParseMode.HTML
        )
    except TelegramError:
        log.debug("Could not edit notice %s for %s", message_id, user_id, exc_info=True)