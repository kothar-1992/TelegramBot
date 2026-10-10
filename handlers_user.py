"""User-facing handlers: /start, catalogue browsing, orders and top-ups.

The active language is resolved once per update in `_register`, then every
screen and message below is rendered through `lang.t()`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import db
import keyboards as kb
import lang
import router
import uploads
import views
from config import is_admin, settings
from keyboards import MAIN
from lang import t
from views import esc, money

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
RECEIPTS_DIR = BASE_DIR / "receipts"

MENU_TEXTS = {"menu", "/start", "start", "home", "main menu", "မီနူ", "ပင်မ", "home menu"}


# --------------------------------------------------------------------------- #
# language
# --------------------------------------------------------------------------- #
def resolve_language(update: Update) -> str:
    """Pick the language for this update and return the code that was chosen.

    Precedence: the customer's own saved choice, then the shop default set by
    `/setlang`, then the language their Telegram client reports.
    """
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.full_name)

    saved = db.get_language(user.id)
    if lang.is_supported(saved):
        return lang.set_lang(saved)

    shop_default = db.get_setting("default_lang")
    if lang.is_supported(shop_default):
        return lang.set_lang(shop_default)

    return lang.set_lang(lang.detect(None, getattr(user, "language_code", None)))


def needs_picker(user_id: int) -> bool:
    """True until the customer has explicitly chosen a language."""
    return not lang.is_supported(db.get_language(user_id))


def saved_language(user_id: int) -> str:
    """The language to render a *push* message in for this customer."""
    saved = db.get_language(user_id)
    if lang.is_supported(saved):
        return saved
    default = db.get_setting("default_lang")
    return default if lang.is_supported(default) else lang.DEFAULT_LANG


async def wipe(update: Update) -> bool:
    """Delete the customer's own message so the chat never fills with clutter."""
    if not settings.clean_messages or is_admin(update.effective_user.id):
        return False
    try:
        await update.effective_message.delete()
        return True
    except (TelegramError, AttributeError):
        log.debug("Could not delete message", exc_info=True)
        return False


# --------------------------------------------------------------------------- #
# entry points
# --------------------------------------------------------------------------- #
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    resolve_language(update)
    user_id = update.effective_user.id
    if needs_picker(user_id):
        await router.go(update, context, "menu:lang")
    else:
        await router.go(update, context, MAIN)
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    resolve_language(update)
    await router.go(update, context, MAIN)
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Plain-text messages: menu button, top-up amount entry, or a nudge home."""
    resolve_language(update)
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    await wipe(update)

    if text.lower().lstrip("🏠").strip() in MENU_TEXTS:
        await router.go(update, context, MAIN)
        return

    pending = db.get_pending(user_id)
    if pending and pending.get("action") == "topup_amount":
        db.set_pending(user_id, None)
        amount = text.replace(",", "").replace("_", "").replace(" ", "")
        if not amount.isdigit() or int(amount) <= 0:
            await update.message.reply_text(t("topup_amount_bad"))
            return
        db.set_pending(user_id, {"action": "topup_receipt", "amount": int(amount)})
        await update.message.reply_text(t("topup_amount_ok", amount=money(int(amount))))
        return

    await router.go(update, context, MAIN)


async def on_language_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`lang:set:<code>` — remember the choice, then show the menu in it."""
    resolve_language(update)
    user_id = update.effective_user.id
    code = update.callback_query.data.split(":")[-1]
    db.set_language(user_id, lang.set_lang(code))

    await update.callback_query.answer()
    await router.go(update, context, MAIN, trail=db.trail(user_id))


# --------------------------------------------------------------------------- #
# top-up receipts
# --------------------------------------------------------------------------- #
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Photos from users are only meaningful as top-up receipts."""
    resolve_language(update)
    user_id = update.effective_user.id
    pending = db.get_pending(user_id)
    if not pending or pending.get("action") != "topup_receipt":
        await update.message.reply_text(t("topup_need_start"))
        return

    photo = update.message.photo[-1]
    if not uploads.check_size(getattr(photo, "file_size", None), settings.max_upload_mb):
        await update.message.reply_text(t("upload_too_big", limit=settings.max_upload_mb))
        return

    amount = int(pending["amount"])
    await wipe(update)
    RECEIPTS_DIR.mkdir(exist_ok=True)
    path = RECEIPTS_DIR / f"topup-{user_id}-{db.stamp()}.jpg"
    saved: str | None = None
    try:
        telegram_file = await photo.get_file()
        await telegram_file.download_to_drive(custom_path=str(path))
    except TelegramError:
        log.warning("receipt download failed for user %s", user_id, exc_info=True)
        path.unlink(missing_ok=True)

    if path.exists():
        # Telegram says "photo", but verify the bytes before anything is stored.
        if not uploads.looks_like_image(path):
            path.unlink(missing_ok=True)
            await update.message.reply_text(t("upload_fake"))
            return
        correct = path.with_suffix(uploads.extension_for(path))
        correct.replace(path)
        path = correct
        saved = str(path.relative_to(BASE_DIR))

    db.set_pending(user_id, None)

    request_id = db.create_topup(user_id, amount, views.reference_code(user_id, amount), saved or "")
    notice_id = await router.notice(
        context,
        user_id,
        "\n".join(part.text for part in views.topup_review(request_id, db.get_balance(user_id))),
        reply_markup=kb.topup_review(request_id),
    )
    db.set_topup_notice(request_id, notice_id)

    note = f"\n📎 {esc(saved)}" if saved else ""
    await notify_admins(
        context,
        text=lambda: t(
            "admin_topup_item",
            id=request_id,
            name=esc(update.effective_user.full_name),
            user_id=user_id,
            amount=money(amount),
            note=note,
            minutes=settings.review_minutes,
        ),
        reply_markup=kb.admin_topup(request_id, user_id, amount),
    )


async def notify_admins(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str | Callable[[], str],
    reply_markup: InlineKeyboardMarkup | None = None,
    photo: str | None = None,
    language: str | None = None,
) -> None:
    """Fan a message out to every configured admin id.

    Pass a thunk for `text` so each admin receives it in *their own* language.
    """
    previous = lang.get()
    try:
        for admin_id in settings.admin_ids:
            lang.set_lang(language or saved_language(admin_id))
            body = text() if callable(text) else text
            try:
                if photo:
                    await context.bot.send_photo(
                        admin_id, photo, caption=body, reply_markup=reply_markup, parse_mode=ParseMode.HTML
                    )
                else:
                    await context.bot.send_message(
                        admin_id, body, reply_markup=reply_markup, parse_mode=ParseMode.HTML
                    )
            except TelegramError:
                log.warning("Could not notify admin %s", admin_id, exc_info=True)
    finally:
        lang.set_lang(previous)


# --------------------------------------------------------------------------- #
# ordering
# --------------------------------------------------------------------------- #
async def on_order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`order:yes:<product_id>:<qty>` — charge the balance and file the order."""
    resolve_language(update)
    user_id = update.effective_user.id
    query = update.callback_query
    _, _, pid, qty = query.data.split(":")
    product_id, qty = int(pid), int(qty)

    product = db.get_product(product_id)
    if product is None or product["is_active"] != 1:
        await query.answer(t("not_found"), show_alert=True)
        return

    if product["stock"] == 0:
        await query.answer(t("err_sold_out"), show_alert=True)
        return

    if int(product["price"]) <= 0:
        await query.answer(t("err_price_tbd"), show_alert=True)
        return

    total = int(product["price"]) * qty
    if db.get_balance(user_id) < total:
        await query.answer(t("err_low_balance", amount=money(total)), show_alert=True)
        return

    order_id = db.create_order(user_id, product_id, qty, total)
    new_balance = db.change_balance(user_id, -total)
    db.decrease_stock(product_id, qty)

    await router.go(update, context, MAIN)
    await router.notify(
        context,
        user_id,
        lambda: t(
            "order_done",
            id=order_id,
            name=esc(product["name"]),
            qty=qty,
            total=money(total),
            balance=money(new_balance),
        ),
        language=saved_language(user_id),
    )

    buyer = db.get_user(user_id)
    await notify_admins(
        context,
        text=lambda: t(
            "admin_pending_item",
            id=order_id,
            product=esc(product["name"]),
            qty=qty,
            total=money(total),
            name=esc(buyer["full_name"] if buyer else "—"),
            handle=f"@{esc(buyer['username'])}" if buyer and buyer["username"] else "—",
            user_id=user_id,
        ),
        reply_markup=kb.simple(
            [
                [
                    kb._btn(t("admin_yes"), f"adm:order:yes:{order_id}"),
                    kb._btn(t("admin_no"), f"adm:order:no:{order_id}"),
                ],
                [kb._btn(t("admin_delivered"), f"adm:order:done:{order_id}")],
            ]
        ),
    )