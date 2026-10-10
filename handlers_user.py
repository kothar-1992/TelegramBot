"""User-facing handlers: /start, catalogue browsing, ordering and top-ups."""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import db
import router
from config import is_admin, settings
from keyboards import MAIN
from views import esc, money

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
RECEIPTS_DIR = BASE_DIR / "receipts"

MENU_TEXTS = {"menu", "/start", "start", "home", "main menu", "မီနူ", "ပင်မ", "home menu"}


def _register(update: Update) -> int:
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.full_name)
    return user.id


async def wipe(update: Update) -> bool:
    """Delete the customer's own message so the chat never fills with clutter.

    Admins are skipped on purpose — they type commands and upload product
    photos, and they need to see them while driving the console.
    """
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
    _register(update)
    await router.go(update, context, MAIN)
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _register(update)
    await router.go(update, context, MAIN)
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Plain-text messages: menu button, top-up amount entry, or a nudge home."""
    user_id = _register(update)
    text = (update.message.text or "").strip()
    await wipe(update)  # keep the chat tidy before anything is rendered

    if text.lower().lstrip("🏠").strip() in MENU_TEXTS:
        await router.go(update, context, MAIN)
        return

    pending = db.get_pending(user_id)
    if pending and pending.get("action") == "topup_amount":
        db.set_pending(user_id, None)
        amount = text.replace(",", "").replace("_", "").replace(" ", "")
        if not amount.isdigit() or int(amount) <= 0:
            await update.message.reply_text("⚠️ ပမာနှင့်ကိန်းကို နံပါတ်ပြထဲ ရိုက်ထည့်ပါ။ (ဥပမာ — 50000)")
            return
        db.set_pending(user_id, {"action": "topup_receipt", "amount": int(amount)})
        await update.message.reply_text(
            f"✅ <b>{money(int(amount))}</b> သိန်းငွေဖြည့်မည်။\n\n"
            "အဆင့် (၂) — လက်ဆိုင်/ပို့က်နှင့် receipt ပုံကို ပို့ပါ။",
            parse_mode=ParseMode.HTML,
        )
        return

    await router.go(update, context, MAIN)


# --------------------------------------------------------------------------- #
# top-up receipts
# --------------------------------------------------------------------------- #
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Photos from users are only meaningful as top-up receipts."""
    user_id = _register(update)
    pending = db.get_pending(user_id)
    if not pending or pending.get("action") != "topup_receipt":
        await update.message.reply_text("📸 ရုပ်ပုံပို့ရန် အရင် “💸 သိန်းငွေဖြည့်မည်” ကို နှိပါပါ။")
        return

    amount = int(pending["amount"])
    await wipe(update)  # the receipt is saved to disk + backed up already
    RECEIPTS_DIR.mkdir(exist_ok=True)
    path = RECEIPTS_DIR / f"topup-{user_id}-{db.stamp()}.jpg"
    saved: str | None = None
    try:
        telegram_file = await update.message.photo[-1].get_file()
        await telegram_file.download_to_drive(custom_path=str(path))
        saved = str(path.relative_to(BASE_DIR))
    except TelegramError:
        log.warning("receipt download failed for user %s", user_id, exc_info=True)

    db.set_pending(user_id, None)
    await update.message.reply_text(
        "📨 <b>သိန်းငွေဖြည့်တင်မှု ပို့ပြီးပါပြီ</b>\n\n"
        f"💵 ပမာနှင့်: <b>{money(amount)}</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        "Admin က စစ်ဆေးပြီး လက်ကောင်း ဖြည့်ပေးပါမည်။",
        parse_mode=ParseMode.HTML,
    )

    admin_kb = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ လက်ကောင်းဖြည့်မည်", callback_data=f"adm:topup:yes:{user_id}:{amount}"),
            InlineKeyboardButton("❌ မဖြည့်", callback_data=f"adm:topup:no:{user_id}:{amount}"),
        ]]
    )
    note = f"\n\n📎 ငွေပို့ပုံ: <code>{esc(saved)}</code>" if saved else ""
    await notify_admins(
        context,
        text=(
            "💸 <b>သိန်းငွေဖြည့်တင်မှု (receipt)</b>\n\n"
            f"👤 အမည်: {esc(update.effective_user.full_name)}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💵 ပမာနှင့်: <b>{money(amount)}</b>{note}"
        ),
        reply_markup=admin_kb,
    )


async def notify_admins(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    photo: str | None = None,
) -> None:
    """Fan a message out to every configured admin id."""
    for admin_id in settings.admin_ids:
        try:
            if photo:
                await context.bot.send_photo(
                    admin_id, photo, caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
                )
            else:
                await context.bot.send_message(
                    admin_id, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
                )
        except TelegramError:
            log.warning("Could not notify admin %s", admin_id, exc_info=True)


# --------------------------------------------------------------------------- #
# ordering
# --------------------------------------------------------------------------- #
async def on_order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`order:yes:<product_id>:<qty>` — charge the balance and file the order."""
    user_id = _register(update)
    query = update.callback_query
    _, _, pid, qty = query.data.split(":")
    product_id, qty = int(pid), int(qty)

    product = db.get_product(product_id)
    if product is None or product["is_active"] != 1:
        await query.answer("⚠️ ထုတ်ကုန် မရှိသေးဘူး။", show_alert=True)
        return

    if product["stock"] == 0:
        await query.answer("⚠️ ဤထုတ်ကုန် ကုန်ပမာနှင့်မရှိတော့ပါ။", show_alert=True)
        return

    if int(product["price"]) <= 0:
        await query.answer("📞 ဤထုတ်ကုန်က စျေးနှင့်မသတ်မှတ်ဖြစ်လို့ အော်ဒါလုပ်လို့ မရပါ။", show_alert=True)
        return

    total = int(product["price"]) * qty
    if db.get_balance(user_id) < total:
        await query.answer(
            f"💰 လက်ကောင်း မလုံလောက်ပါ။ လိုအပ်သော: {money(total)}", show_alert=True
        )
        return

    order_id = db.create_order(user_id, product_id, qty, total)
    new_balance = db.change_balance(user_id, -total)
    db.decrease_stock(product_id, qty)

    await router.go(update, context, MAIN)
    await router.notify(
        context,
        user_id,
        "✅ <b>အော်ဒါ အတည်ပြုပြီး</b>\n\n"
        f"<code>#{order_id}</code> — {esc(product['name'])}\n"
        f"🧮 အရေအတွက်: <b>{money(total)}</b>\n"
        f"💰 ကျန်လက်ကောင်း: {money(new_balance)}\n\n"
        "Admin က စစ်ဆေးပြီး ပေးပို့ပေးပါမည်။",
    )

    buyer = db.get_user(user_id)
    buyer_handle = f"@{esc(buyer['username'])}" if buyer and buyer["username"] else "—"
    admin_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ အတည်ပြု", callback_data=f"adm:order:yes:{order_id}"),
                InlineKeyboardButton("❌ ပယ်ဖျက်+ငွေပြန်", callback_data=f"adm:order:no:{order_id}"),
            ],
            [InlineKeyboardButton("🔵 ပေးပြီးသွင်းမည်", callback_data=f"adm:order:done:{order_id}")],
        ]
    )
    await notify_admins(
        context,
        text=(
            "🔔 <b>အော်ဒါအသစ်</b>\n\n"
            f"<code>#{order_id}</code> — {esc(product['name'])}\n"
            f"🧮 x{qty} · <b>{money(total)}</b>\n"
            f"👤 ဝယ်သူ: {esc(buyer['full_name'] if buyer else '')} ({buyer_handle})\n"
            f"🆔 <code>{user_id}</code>"
        ),
        reply_markup=admin_kb,
    )