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
import router
from config import is_admin, settings
from handlers_user import notify_admins

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
}


# --------------------------------------------------------------------------- #
# generic callbacks
# --------------------------------------------------------------------------- #
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id
    db.upsert_user(user_id, query.from_user.username, query.from_user.full_name)

    if data == "nav:back":
        await query.answer()
        await router.go_back(update, context)
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
            await query.answer("🔒 Admin သာ လုပ်လို့ရပါတယ်။", show_alert=True)
            return
        await query.answer()
        await admin.on_admin_callback(update, context)
        return

    await query.answer()
    await router.go(update, context, data)


async def _user_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """`usr:deliver:<order_id>` — customer confirms they received the goods."""
    query = update.callback_query
    await query.answer("ကျေးဇူးတင်ပါသည်! 🙏")
    _, _, order_id = data.split(":")
    order = db.get_order(int(order_id))
    if order is None or order["user_id"] != update.effective_user.id:
        return
    db.set_order_status(int(order_id), "delivered")
    try:
        await query.edit_message_text(
            "✅ <b>လက်ခံရရှိပြီး</b>\n\nကျေးဇူးတင်ပါသည်! 🙏 နောက်ထပ်လည်မဝယ်နိုင်ပါပေမယ့် Admin ကို အကြောင်းကြားပါပါတယ်။",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        log.debug("Could not edit the delivery confirmation", exc_info=True)

    await notify_admins(
        context,
        text=f"✅ ID <code>{update.effective_user.id}</code> က အော်ဒါ #{order_id} ကို လက်ခံရရှိပြီးပါပြီ။",
    )


# --------------------------------------------------------------------------- #
# command wrapper (routes admin-only commands)
# --------------------------------------------------------------------------- #
async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    db.upsert_user(user_id, update.effective_user.username, update.effective_user.full_name)
    name = update.message.text.split()[0].split("@")[0].lstrip("/").lower()

    if name in {"start", "menu", "home", "id"}:
        # Handled by the dedicated handlers registered in group 0.
        return

    handler = ADMIN_COMMANDS.get(name)
    if handler is not None:
        if not is_admin(user_id):
            await update.message.reply_text("🔒 ဤ command ကို admin သာ သုံးနိုင်ပါတယ်။")
            return
        await handler(update, context)
        return

    await update.message.reply_text("⚠️ မသိမှန်တဲ့ command ဖြစ်ပါတယ်။ `/menu` နှိပါပါ။")


async def cmd_id_stopping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin.cmd_id(update, context)
    raise ApplicationHandlerStop


async def cmd_home_stopping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await user.cmd_start(update, context)
    raise ApplicationHandlerStop


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


async def post_init(app: Application) -> None:
    me = await app.bot.get_me()
    log.info("Bot started as @%s (%s)", me.username, me.id)
    log.info("Admins: %s", settings.admin_ids or "— none configured —")
    if not settings.admin_ids:
        log.warning("ADMIN_IDS မရှိကြောင်း သတိပြုပါ။ @BotFather မှာ /id နှိပါပြီး .env တွင် ထည့်သွင်းပါ။")

    health.start_health_server()
    if settings.self_url:
        app.job_queue.run_repeating(
            keep_alive_job, interval=timedelta(minutes=settings.keepalive_minutes), first=timedelta(seconds=45)
        )
    if backup.enabled():
        app.job_queue.run_repeating(
            backup_job, interval=timedelta(minutes=settings.backup_minutes), first=timedelta(seconds=60)
        )
        log.info("Database snapshots -> Telegram every %d min", settings.backup_minutes)


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
    app.add_handler(CommandHandler("id", cmd_id_stopping))

    # Inline buttons.
    app.add_handler(CallbackQueryHandler(on_callback))

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
        except (NetworkError, TelegramError) as err:
            print(f"⚠️ Snapshot restore skipped ({type(err).__name__}) — starting with an empty database")

    db.init(settings.db_path)
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