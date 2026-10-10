"""Telegram shop bot — entry point.

Run with:  python bot.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import backup
import db
import handlers_admin as admin
import handlers_user as user
import health
import lang
import router
import uploads
import views
from config import is_admin, settings
from handlers_user import notify_admins
from lang import t
from views import esc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
)
# httpx logs every request including the bot token in the URL — keep it quiet.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("bot")

ADMIN_COMMANDS = {
    "addcat": admin.cmd_addcat,
    "cats": admin.cmd_cats,
    "delcat": admin.cmd_delcat,
    "addproduct": admin.cmd_addproduct,
    "products": admin.cmd_products,
    "delproduct": admin.cmd_delproduct,
    "toggle": admin.cmd_toggle,
    "give": admin.cmd_give,
    "balance": admin.cmd_balance,
    "broadcast": admin.cmd_broadcast,
    "setbanner": admin.cmd_setbanner,
    "setname": admin.cmd_setname,
    "pending": admin.cmd_pending,
    "demo": admin.cmd_demo,
    "paymethods": admin.cmd_paymethods,
    "addpay": admin.cmd_addpay,
    "delpay": admin.cmd_delpay,
    "setlang": admin.cmd_setlang,
}


# --------------------------------------------------------------------------- #
# generic callbacks
# --------------------------------------------------------------------------- #
# Anything that is not a compressed Telegram photo. A user can smuggle any
# byte stream through as a "document", so refuse the whole family outright.
#: Every media type that is *not* a compressed Telegram photo.
UNTRUSTED_UPLOADS = (
    filters.Document.ALL
    | filters.VIDEO
    | filters.AUDIO
    | filters.VOICE
    | filters.ANIMATION
    | filters.VIDEO_NOTE
    | filters.Sticker.ALL
)


async def on_rejected_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Refuse documents/archives/videos without ever touching the disk."""
    user.resolve_language(update)
    await update.message.reply_text(uploads.reject_text(), parse_mode=ParseMode.HTML)
    raise ApplicationHandlerStop


async def _user_topup_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """`tstatus:<id>` / `tcancel:<id>` — the customer's side of the review."""
    lang_code = user.resolve_language(update)
    query = update.callback_query
    kind, _, raw_id = data.partition(":")
    request = db.get_topup(int(raw_id))
    if request is None or request["user_id"] != update.effective_user.id:
        await query.answer(t("not_found"), show_alert=True)
        return

    request_id = int(request["id"])
    if kind == "tcancel" and request["status"] == "pending":
        db.resolve_topup(request_id, "rejected")
        await query.answer(t("review_cancelled"), show_alert=True)
    elif request["status"] == "pending":
        await query.answer(t("review_still_pending", minutes=settings.review_minutes), show_alert=True)
        return
    else:
        await query.answer(t("review_already"), show_alert=True)
        return

    await _replace_review_notice(context, request_id, int(request["user_id"]), lang_code)


async def _replace_review_notice(
    context: ContextTypes.DEFAULT_TYPE, request_id: int, user_id: int, language: str | None = None
) -> None:
    request = db.get_topup(request_id)
    if not request:
        return
    def body() -> str:
        return "\n".join(p.text for p in views.topup_review(request_id, db.get_balance(user_id)))

    if request["notice_message_id"]:
        await router.replace_notice(context, user_id, request["notice_message_id"], body, language=language)
    else:
        await router.notice(context, user_id, body, language=language)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id
    user.resolve_language(update)

    if data.startswith("lang:set:"):
        await user.on_language_pick(update, context)
        return

    if data == "nav:back":
        await query.answer()
        await router.go_back(update, context)
        return

    if data.startswith(("tstatus:", "tcancel:")):
        await _user_topup_action(update, context, data)
        return

    if data.startswith("copy:"):
        await _copy_payload(update)
        return

    if data.startswith("tut:"):
        await _show_tutorial(update, context, int(data.split(":")[1]))
        return

    if data.startswith("order:"):
        await query.answer()
        await user.on_order_confirm(update, context)
        return

    if data.startswith("usr:"):
        await _user_action(update, context, data)
        return

    if data.startswith("adm:"):
        if not is_admin(user_id):
            await query.answer(t("admin_only_cmd"), show_alert=True)
            return
        await query.answer()
        await admin.on_admin_callback(update, context)
        return

    await query.answer()
    await router.go(update, context, data)


async def _copy_payload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`copy:<what>:<text>` — echo the value in an alert so it can be copied."""
    query = update.callback_query
    _, what, value = query.data.split(":", 2)
    labels = {"no": "🔢", "name": "👤", "ref": "🔖"}
    await query.answer(f"{labels.get(what, '📋')} {value}", show_alert=True)


async def _show_tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    """`tut:<id>` — send the tutorial link as a shareable message."""
    query = update.callback_query
    product = db.get_product(product_id)
    url = product["tutorial_url"] if product else None
    if not url:
        await query.answer(t("err_no_tutorial"), show_alert=True)
        return
    await query.answer(t("tutorial_open"), show_alert=True)
    await context.bot.send_message(
        update.effective_user.id, t("tutorial_msg", name=esc(product["name"]), url=esc(url)), parse_mode=ParseMode.HTML
    )


async def _user_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """`usr:deliver:<order_id>` — customer confirms they received the goods."""
    query = update.callback_query
    await query.answer(t("deliver_thanks"), show_alert=True)
    _, _, order_id = data.split(":")
    order = db.get_order(int(order_id))
    if order is None or order["user_id"] != update.effective_user.id:
        return
    db.set_order_status(int(order_id), "delivered")
    try:
        await query.edit_message_text(t("order_received"), parse_mode=ParseMode.HTML)
    except TelegramError:
        log.debug("Could not edit the delivery confirmation", exc_info=True)

    await notify_admins(
        context,
        text=lambda: t("deliver_notify", user_id=update.effective_user.id, order_id=order_id),
    )


# --------------------------------------------------------------------------- #
# command wrapper (routes admin-only commands)
# --------------------------------------------------------------------------- #
async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user.resolve_language(update)
    name = update.message.text.split()[0].split("@")[0].lstrip("/").lower()

    if name in {"start", "menu", "home", "id", "language", "lang"}:
        # Handled by the dedicated handlers registered in group 0.
        return

    handler = ADMIN_COMMANDS.get(name)
    if handler is not None:
        if not is_admin(user_id):
            await update.message.reply_text(t("err_admin_only"))
            return
        await handler(update, context)
        return

    await update.message.reply_text(t("err_unknown_cmd"))


async def cmd_id_stopping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user.resolve_language(update)
    await admin.cmd_id(update, context)
    raise ApplicationHandlerStop


async def cmd_home_stopping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await user.cmd_start(update, context)
    raise ApplicationHandlerStop


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/language` — open the picker without losing the current screen."""
    user.resolve_language(update)
    await router.go(update, context, "menu:lang")
    try:
        await update.effective_message.delete()
    except TelegramError:
        pass


# --------------------------------------------------------------------------- #
# errors & scheduled jobs
# --------------------------------------------------------------------------- #
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Unhandled error", exc_info=context.error)


async def keep_alive_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ping our own URL so the free instance never idles to sleep."""
    ok = await asyncio.to_thread(health.ping, settings.self_url)
    log.info("Keep-alive ping: %s", "ok" if ok else "failed")


async def backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ship shop.db to Telegram storage whenever it has changed."""
    if not db.is_dirty():
        return
    admin_id = settings.backup_admin_id or (settings.admin_ids[0] if settings.admin_ids else 0)
    if await backup.upload(context.bot, admin_id):
        db.clear_dirty()
    else:
        db.clear_dirty()  # do not retry in a tight loop


async def expire_topups_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Every minute: reject receipts nobody reviewed within the window."""
    await admin._expire_topups(context)


def _seed_default_language() -> None:
    """Adopt the env default only while `/setlang` has never chosen one."""
    if not lang.is_supported(settings.default_lang):
        log.warning("DEFAULT_LANG=%r is not a known language; using %s", settings.default_lang, lang.DEFAULT_LANG)
        return
    if db.get_setting("default_lang") is None:
        db.set_setting("default_lang", settings.default_lang)


async def post_init(app: Application) -> None:
    me = await app.bot.get_me()
    log.info("Bot started as @%s (%s)", me.username, me.id)
    log.info("Admins: %s", settings.admin_ids or "— none configured —")
    if not settings.admin_ids:
        log.warning("ADMIN_IDS is empty — run /id in Telegram and add it to .env.")
    lang.reset()
    log.info("Default language: %s", lang.native_name(db.get_setting("default_lang") or lang.DEFAULT_LANG))
    health.start_health_server()
    _schedule_jobs(app)


def _schedule_jobs(app: Application) -> None:
    """Wire the periodic keep-alive and backup jobs, if the extra is installed."""
    if app.job_queue is None:
        log.warning(
            "PTB has no JobQueue — keep-alive and DB snapshots are OFF. "
            'Install with: pip install "python-telegram-bot[job-queue]"'
        )
        return

    if settings.self_url:
        app.job_queue.run_repeating(
            keep_alive_job, interval=timedelta(minutes=settings.keepalive_minutes), first=timedelta(seconds=45)
        )
    if backup.enabled():
        app.job_queue.run_repeating(
            backup_job, interval=timedelta(minutes=settings.backup_minutes), first=timedelta(seconds=60)
        )
        log.info("Database snapshots -> Telegram every %d min", settings.backup_minutes)

    app.job_queue.run_repeating(expire_topups_job, interval=timedelta(minutes=1), first=timedelta(seconds=30))
    log.info("Top-up review window: %d min", settings.review_minutes)


# --------------------------------------------------------------------------- #
def build_app() -> Application:
    """Create the Application and register every handler."""
    builder = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(post_init)
        .connect_timeout(20)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(20)
        .get_updates_connect_timeout(20)
        .get_updates_read_timeout(30)
        .get_updates_write_timeout(30)
        .get_updates_pool_timeout(20)
    )
    if settings.proxy:
        builder = builder.proxy(settings.proxy)
        log.info("Using proxy: %s", settings.proxy)

    app = builder.build()

    # Commands (group 0 — these must short-circuit the generic router).
    app.add_handler(CommandHandler(["start", "menu", "home"], cmd_home_stopping))
    app.add_handler(CommandHandler(["language", "lang"], cmd_language))
    app.add_handler(CommandHandler("id", cmd_id_stopping))

    # Inline buttons.
    app.add_handler(CallbackQueryHandler(on_callback))

    # Never store a customer-supplied file: refuse every non-photo upload first.
    app.add_handler(MessageHandler(UNTRUSTED_UPLOADS, on_rejected_file), group=0)

    # Admin wizard runs before the generic user handlers and stops the chain
    # only when it actually acted on a pending session.
    app.add_handler(MessageHandler(filters.PHOTO, admin.on_admin_photo), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin.on_admin_text), group=0)

    # Users / remaining commands.
    app.add_handler(MessageHandler(filters.COMMAND, on_command), group=1)
    app.add_handler(MessageHandler(filters.PHOTO, user.on_photo), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user.on_text), group=1)

    app.add_error_handler(on_error)
    return app


async def _restore_database() -> None:
    """Pull shop.db back from Telegram storage before the schema is opened."""
    if not backup.enabled():
        return
    from telegram import Bot

    log.info("Looking for the latest shop.db snapshot…")
    if await backup.restore(Bot(settings.bot_token)):
        log.info("Snapshot restored ✅")


def main() -> int:
    if not settings.configured:
        print("❌ BOT_TOKEN မရှိပါ။ .env ဖိုင်ကို စစ်ပါ။ (.env.example ကို ကြည့်ပါ)")
        return 1

    if backup.enabled():
        try:
            asyncio.run(_restore_database())
        except Exception as err:
            print(f"⚠️ Snapshot restore skipped ({type(err).__name__}: {err}) — starting with an empty database")

    db.init(settings.db_path)
    _seed_default_language()
    log.info("Database: %s", settings.db_path)

    try:
        build_app().run_polling(
            drop_pending_updates=True,
            bootstrap_retries=3,
            allowed_updates=Update.ALL_TYPES,
        )
    except (TimedOut, NetworkError) as err:
        print(f"\n❌ Telegram API နဲ့ မချိတ်နိုင်ပါ — {type(err).__name__}")
        if settings.proxy:
            print(f"   Proxy: {settings.proxy}  ← ဒါက မှန်လား စစ်ပါ (VPN/proxy ဖွင့်ထားပါသလား?)")
        else:
            print("   PROXY မသတ်မှတ်ထားပါ — .env ထဲမှာ သတ်မှတ်ပါ။")
            print("   ဥပမာ — v2rayN/Nekoray သုံးနေရင်  socks5://127.0.0.1:10809")
        print("   Telegram block ထားတဲ့ နိုင်ငံမှာ proxy မလိုက်ရင် ဘယ်လိုမှ ချိတ်နိုင်မှာမဟုတ်ပါ။")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())