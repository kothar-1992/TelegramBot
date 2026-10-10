"""Navigation router.

Handles swapping the currently visible bot messages for a new screen, and
implements the ⬅️ Back / 🏠 Main Menu trail stored in the database so that
history survives bot restarts.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import db
import views
from keyboards import MAIN
from views import Part

log = logging.getLogger(__name__)


async def _delete_msgs(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Remove the messages of the previous screen so the chat stays clean."""
    for message_id in db.get_msgs(user_id):
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=message_id)
        except (BadRequest, Exception):  # noqa: B014 - deleting must never break navigation
            pass
    db.set_msgs(user_id, [])


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
    """
    user_id = update.effective_user.id
    db.upsert_user(user_id, update.effective_user.username, update.effective_user.full_name)

    if trail is None:
        trail = [] if target == MAIN else db.trail(user_id) + [target]
    db.set_trail(user_id, trail)

    parts = views.build(target, user_id)
    old_msgs = db.get_msgs(user_id)

    # Fast path: exactly one visible message and the new screen is one message.
    # (A part carrying a reply keyboard must be sent fresh, never edited.)
    if len(parts) == 1 and parts[0].reply_keyboard is None and len(old_msgs) == 1 and update.callback_query is not None:
        if await _try_edit(update, context, parts[0]):
            db.set_msgs(user_id, old_msgs)
            return

    await _delete_msgs(context, user_id)
    new_ids: list[int] = []
    for part in parts:
        new_ids.append(await _send_part(context, user_id, part))
    db.set_msgs(user_id, new_ids)


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
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Send a one-off message to the user and track it for clean-up."""
    message = await context.bot.send_message(
        user_id, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )
    db.add_msgs(user_id, [message.message_id])