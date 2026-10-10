"""Admin handlers: catalogue management, order review, balances, broadcasts."""

from __future__ import annotations

import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

import db
import router
from config import settings
from views import esc, money

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
#: Demo catalogue — `(category emoji, category name, [(product, price, stock, note)])`
DEMO_DATA: tuple[tuple[str, str, tuple[tuple[str, int, int, str], ...]], ...] = (
    ("💰", "USDT / Crypto", (
        ("USDT TRC20", 65_000, 10, "မိနစ်ပိုင်းအတွင်း ပေးပို့ပါမည်။"),
        ("USDT BEP20", 64_000, 5, "Binance Smart Chain။"),
        ("USDT TON", 63_000, 0, "ယခုအချိန်တွင် ကုန်မရှိပါ။"),
    )),
    ("🤖", "ChatGPT", (
        ("ChatGPT GO 1 Month (Full Warranty)", 45_000, 3, "30 ရက်အာမခံ။"),
        ("ChatGPT Plus 1 Month (10 Day Warranty)", 53_000, 2, "အကောင့်ပေးပို့။"),
        ("ChatGPT Plus K12 Edu 2 Year", 0, 0, "ပမာနှင့်ထည့်ရန် ဆက်သွယ်ရန်။"),
    )),
    ("💼", "Microsoft", (
        ("Microsoft 365 Personal 1 Month", 12_000, 20, "စုပစ္စည်း အားလုံးပါ။"),
        ("Windows 11 Pro Lifetime", 35_000, 8, "တစ်ခါရှည်တည်း။"),
    )),
    ("🎨", "Adobe", (
        ("Adobe CC All Apps 1 Month", 40_000, 4, "Photoshop, Illustrator အားလုံး။"),
        ("Photoshop 1 Month", 15_000, 10, "အသုံးပြုသူအများကြိုက်ပါတယ်။"),
    )),
    ("📹", "Zoom", (
        ("Zoom Pro 1 Month", 18_000, 15, "Meeting 500 ကနေ့အထက်။"),
    )),
    ("🎬", "Design Tools", (
        ("Canva Pro 1 Year", 25_000, 6, "၁ နှစ်စာများအသုံးပြု။"),
        ("Canva Team 1 Month", 12_000, 0, "လက်ရှိမရှိပါ။"),
    )),
)

DEMO_SETTING = "demo_ids"


def _seed_demo() -> tuple[list[int], list[int]]:
    cat_ids: list[int] = []
    product_ids: list[int] = []
    for emoji, name, products in DEMO_DATA:
        cat_id = db.add_category(name, emoji)
        cat_ids.append(cat_id)
        for title, price, stock, note in products:
            product_ids.append(db.add_product(title, price, category_id=cat_id, description=note, stock=stock))
    return cat_ids, product_ids


def _clear_demo() -> int:
    stored = _read_demo_ids()
    removed = 0
    for pid in stored.get("products", []):
        db.delete_product(int(pid))
        removed += 1
    for cid in stored.get("categories", []):
        db.delete_category(int(cid))
    db.set_setting(DEMO_SETTING, None)
    return removed


def _read_demo_ids() -> dict:
    import json

    try:
        return json.loads(db.get_setting(DEMO_SETTING) or "{}")
    except (ValueError, TypeError):
        return {}


async def cmd_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/demo` seeds a sample catalogue; `/demo clear` removes it again."""
    argument = " ".join(update.message.text.split()[1:]).strip().lower()

    if argument.startswith(("clear", "clean", "remove", "ဖျက်")):
        removed = _clear_demo()
        await update.message.reply_text(
            f"🗑 Demo ထုတ်ကုန် <b>{removed}</b> ခု ဖျက်ပြီးပါပြီ။"
            if removed
            else "ℹ️ Demo data မရှိပါ။ အရင်က <code>/demo</code> ရိုက်ဖို့ မလိုပါ။",
            parse_mode=ParseMode.HTML,
        )
        return

    if db.get_setting(DEMO_SETTING):
        await update.message.reply_text(
            "ℹ️ Demo data ရှိနေပါပြီ။ အရင် <code>/demo clear</code> နဲ့ ဖျက်ပါ။",
            parse_mode=ParseMode.HTML,
        )
        return

    import json

    cat_ids, product_ids = _seed_demo()
    db.set_setting(DEMO_SETTING, json.dumps({"categories": cat_ids, "products": product_ids}))

    admin_id = update.effective_user.id
    if db.get_balance(admin_id) == 0:
        db.change_balance(admin_id, 500_000)  # so the order flow can be tested

    await update.message.reply_text(
        "✅ <b>Demo catalogue ထည့်ပြီးပါပြီ</b>\n\n"
        f"🗂 Category: <b>{len(cat_ids)}</b> ခု\n"
        f"🛍 ထုတ်ကုန်: <b>{len(product_ids)}</b> ခု\n"
        f"💰 သင့်လက်ကောင်း: <b>{money(db.get_balance(admin_id))}</b>\n\n"
        "🛍 <b>ထုတ်ကုန်များ</b> ကို နှိပါပြီး စမ်းကြည့်ပါ။\n"
        "🧹 ဖျက်ချင်ရင် <code>/demo clear</code>",
        parse_mode=ParseMode.HTML,
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 သင့် Telegram ID: <code>{user.id}</code>\n"
        f"👤 အမည်: {esc(user.full_name)}\n"
        f"🔑 Admin: {'ဟုတ်ကဲ့' if user.id in settings.admin_ids else 'မဟုတ်'}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_addcat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/addcat 💰 Wallet` — emoji is optional."""
    raw = " ".join(update.message.text.split()[1:]).strip()
    if not raw:
        db.set_pending(update.effective_user.id, {"action": "category_name"})
        await update.message.reply_text("🗂 Category အမည် ရိုက်ထည့်ပါ။")
        return

    parts = raw.split(maxsplit=1)
    if len(parts) == 2 and len(parts[0]) <= 3 and not parts[0].isalnum():
        emoji, name = parts[0], parts[1].strip()
    else:
        emoji, name = "📦", raw

    cat_id = db.add_category(name, emoji)
    await update.message.reply_text(f"✅ Category ထည့်ပြီးပါပြီ — <code>{cat_id}</code> · {emoji} {esc(name)}", parse_mode=ParseMode.HTML)


async def cmd_cats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cats = db.list_categories()
    if not cats:
        await update.message.reply_text("🗂 Category မရှိသေးပါ။ `/addcat <အမည်>` သုံးပါ။")
        return
    lines = ["🗂 <b>Category စာရင်း</b>\n"]
    lines += [f"<code>{c['id']}</code> · {c['emoji']} {esc(c['name'])} — {c['item_count']} ခု" for c in cats]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_delcat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text("⚠️ `/delcat <id>` သုံးပါ။")
        return
    db.delete_category(int(parts[1]))
    await update.message.reply_text(f"🗑 Category <code>{parts[1]}</code> ဖျက်ပြီးပါပြီ။")


async def cmd_addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db.set_pending(update.effective_user.id, {"action": "product_photo"})
    await update.message.reply_text(
        "🛍 <b>ထုတ်ကုန်ထည့်ရန်</b>\n\n"
        "အဆင့် (၁) — ထုတ်ကုန်ရုပ်ပုံကို ပို့ပါ။\n\n"
        "အဆင့် (၂) — ပို့လိုက်တဲ့ ရုပ်ပုံနဲ့အတူ Caption ရိုက်ထည့်ပါ —\n\n"
        "<code>အမည် | စျေးကြေး | Category | ကုန်ပမာနှင့်</code>\n"
        "<code>USDT TRC20 | 65000 | Crypto | 10</code>\n\n"
        "• Category နဲ့ ကုန်ပမာနှင့် ကို ချန်လို့ရပါတယ်။\n"
        "• ကုန်ပမာနှင့် မထည့်ရင် အကန့်မဲ့အဖြစ် သတ်မှတ်ပါမည်။\n"
        "• Caption ရဲ့ ပထမဆုံးလိုင်းအောက်မှာ ကျန်ကို description အဖြစ် သိမ်းပါမည်။",
        parse_mode=ParseMode.HTML,
    )


def parse_caption(caption: str) -> tuple[str, int, int | None, str, int] | None:
    """`name | price | category | stock` -> (name, price, category_id, description, stock).

    `category` and `stock` are optional; stock defaults to -1 (unlimited).
    """
    head, _, description = caption.partition("\n")
    fields = [f.strip() for f in head.split("|")]
    if len(fields) < 2:
        return None

    name = fields[0].strip()
    price_raw = fields[1].replace(",", "").replace("_", "").strip()
    if not name or not price_raw.lstrip("-").isdigit():
        return None
    price = int(price_raw)
    if price < 0:
        return None

    category_id: int | None = None
    if len(fields) >= 3 and fields[2]:
        token = fields[2].strip()
        if token.isdigit():
            category_id = int(token)
            if db.get_category(category_id) is None:
                category_id = None
        else:
            row = db.find_category(token)
            category_id = int(row["id"]) if row else None

    stock = -1
    if len(fields) >= 4 and fields[3]:
        stock_raw = fields[3].replace(",", "").strip()
        if not stock_raw.isdigit():
            return None
        stock = int(stock_raw)

    return name, price, category_id, description.strip(), stock


async def cmd_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = db.list_products(None, limit=15, active_only=False)
    if not rows:
        await update.message.reply_text("🛍 ထုတ်ကုန် မရှိသေးပါ။ `/addproduct` သုံးပါ။")
        return
    lines = ["🛍 <b>ထုတ်ကုန်စာရင်း</b>\n"]
    lines += [
        f"<code>{p['id']}</code> · {'🟢' if p['is_active'] else '🔴'} {esc(p['name'])} — {money(p['price'])}"
        for p in rows
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_delproduct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text("⚠️ `/delproduct <id>` သုံးပါ။")
        return
    db.delete_product(int(parts[1]))
    await update.message.reply_text(f"🗑 ထုတ်ကုန် <code>{parts[1]}</code> ဖျက်ပြီးပါပြီ။")


async def cmd_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text("⚠️ `/toggle <id>` သုံးပါ။")
        return
    pid = int(parts[1])
    product = db.get_product(pid)
    if product is None:
        await update.message.reply_text("⚠️ ထုတ်ကုန် မတွေ့ပါ။")
        return
    db.set_product_active(pid, not product["is_active"])
    await update.message.reply_text(
        f"{'🟢 ပြန်ဖွင့်ပြီး' if not product['is_active'] else '🔴 ပိတ်ပြီး'} — {esc(product['name'])}"
    )


async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/give <user_id> <amount>` — add (or subtract with a minus) balance."""
    parts = update.message.text.split()
    if len(parts) != 3 or not parts[1].lstrip("-").isdigit() or not parts[2].lstrip("-").isdigit():
        await update.message.reply_text("⚠️ `/give <user_id> <amount>` သုံးပါ။")
        return
    user_id, amount = int(parts[1]), int(parts[2])
    if db.get_user(user_id) is None:
        await update.message.reply_text("⚠️ အဲဒီ user ကို မတွေ့ပါ။")
        return
    new_balance = db.change_balance(user_id, amount)
    await update.message.reply_text(f"✅ ID <code>{user_id}</code> လက်ကောင်း: {money(new_balance)}", parse_mode=ParseMode.HTML)
    await _safe_notify(context, user_id, f"💰 လက်ကောင်းအသစ်: {money(new_balance)}")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await update.message.reply_text("⚠️ `/balance <user_id>` သုံးပါ။")
        return
    row = db.get_user(int(parts[1]))
    if row is None:
        await update.message.reply_text("⚠️ အဲဒီ user ကို မတွေ့ပါ။")
        return
    await update.message.reply_text(
        f"👤 {esc(row['full_name'] or '—')}\n🆔 <code>{row['user_id']}</code>\n💰 {money(row['balance'])}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(update.message.text.split()[1:]).strip()
    if not text:
        db.set_pending(update.effective_user.id, {"action": "broadcast"})
        await update.message.reply_text("📢 ပို့ရန် မက်ဆော်စာကို ရိုက်ထည့်ပါ။")
        return
    db.set_pending(update.effective_user.id, {"action": "broadcast", "text": text})
    await _send_broadcast(update, context)


async def _send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = db.get_pending(update.effective_user.id) or {}
    text = pending.get("text", "")
    if not text:
        return
    ok = failed = 0
    status = await update.effective_message.reply_text("📢 ပို့နေပါသည်...")
    for row in db._rows("SELECT user_id FROM users"):
        try:
            await context.bot.send_message(row["user_id"], text, parse_mode=ParseMode.HTML)
            ok += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)
    db.set_pending(update.effective_user.id, None)
    await status.edit_text(f"📢 ပို့ပြီးပါပြီ — အောင်မြင် {ok} · မအောင်မြင် {failed}")


async def cmd_setbanner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if db.get_setting("banner_photo"):
        db.set_setting("banner_photo", None)
        await update.message.reply_text("🖼 Welcome banner ဖယ်ရှားပြီးပါပြီ။")
        return
    db.set_pending(update.effective_user.id, {"action": "banner"})
    await update.message.reply_text("🖼 ကြောင်းပြနှင့်ပြသမည့် welcome banner ပုံကို ပို့ပါ။")


async def cmd_setname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = " ".join(update.message.text.split()[1:]).strip()
    if not name:
        await update.message.reply_text("⚠️ `/setname <ဆိုင်အမည်>` သုံးပါ။")
        return
    db.set_setting("shop_name", name)
    await update.message.reply_text(f"✅ ဆိုင်အမည်: {esc(name)}", parse_mode=ParseMode.HTML)


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await router.go(update, context, "adm:orders")


# --------------------------------------------------------------------------- #
# photo / text wizard (admin-only, runs before the user handlers)
# --------------------------------------------------------------------------- #
async def on_admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = db.get_pending(update.effective_user.id) or {}
    action = pending.get("action")
    if action not in {"product_photo", "banner", "topup_receipt"}:
        return

    photo = update.message.photo[-1]
    file_id = photo.file_id

    if action == "banner":
        db.set_setting("banner_photo", file_id)
        db.set_pending(update.effective_user.id, None)
        await update.message.reply_text("🖼 Welcome banner သိမ်းပြီးပါပြီ။ /setbanner နဲ့ ဖျက်နိုင်ပါတယ်။")
        raise ApplicationHandlerStop

    if action == "product_photo":
        db.set_pending(update.effective_user.id, {"action": "product_caption", "photo_id": file_id})
        await update.message.reply_text(
            "📝 အဆင့် (၂) — ရုပ်ပုံနဲ့အတူ Caption ရိုက်ထည့်ပါ။\n\n"
            "<code>အမည် | စျေးကြေး | Category | ကုန်ပမာနှင့်</code>\n<code>USDT TRC20 | 65000 | Crypto | 10</code>",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    if action == "topup_receipt":
        # A receipt meant for the customer support flow — store and notify admins.
        from handlers_user import on_photo as user_on_photo  # local import avoids a cycle

        await user_on_photo(update, context)
        raise ApplicationHandlerStop


async def on_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = db.get_pending(update.effective_user.id) or {}
    action = pending.get("action")
    if action is None:
        return

    text = (update.message.text or "").strip()

    if action == "product_caption":
        parsed = parse_caption(text)
        if parsed is None:
            await update.message.reply_text("⚠️ Caption ပုံစံ မမှန်ပါ — `<အမည်> | <စျေးကြေး> | <Category>` အတိုင်း ထည့်ပါ။")
            return
        name, price, category_id, description, stock = parsed
        product_id = db.add_product(
            name=name,
            price=price,
            category_id=category_id,
            description=description,
            photo_id=pending["photo_id"],
            stock=stock,
        )
        db.set_pending(update.effective_user.id, None)
        cat = db.get_category(category_id) if category_id else None
        cat_label = f"{cat['emoji']} {esc(cat['name'])}" if cat else "Category မသတ်မှတ်"
        await update.message.reply_text(
            "✅ <b>ထုတ်ကုန် ထည့်ပြီးပါပြီ</b>\n\n"
            f"<code>#{product_id}</code> — {esc(name)}\n"
            f"💵 {money(price)}\n"
            f"📦 ကုန်ပမာနှင့်: {'အကန့်မဲ့' if stock < 0 else stock}\n"
            f"🗂 {cat_label}",
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    if action == "category_name":
        db.set_pending(update.effective_user.id, None)
        if not text:
            await update.message.reply_text("⚠️ အမည် လိုပါတယ်။")
            return
        cat_id = db.add_category(text, "📦")
        await update.message.reply_text(f"✅ Category ထည့်ပြီးပါပြီ — <code>{cat_id}</code> · 📦 {esc(text)}", parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop

    if action == "broadcast":
        pending["text"] = text
        db.set_pending(update.effective_user.id, pending)
        await _send_broadcast(update, context)
        raise ApplicationHandlerStop


# --------------------------------------------------------------------------- #
# admin callbacks
# --------------------------------------------------------------------------- #
async def on_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    parts = data.split(":")
    head = parts[1] if len(parts) > 1 else ""

    if head == "cat" and len(parts) >= 3 and parts[2] == "new":
        db.set_pending(query.from_user.id, {"action": "category_name"})
        await query.message.reply_text("🗂 Category အမည် ရိုက်ထည့်ပါ။")
        return

    if head == "banner":
        await cmd_setbanner_from_query(update, context)
        return

    if head == "user" and len(parts) >= 3 and parts[2] == "zero" and parts[3].isdigit():
        await _zero_balance(update, context, int(parts[3]))
        return

    if head == "user" and len(parts) >= 3 and parts[2].isdigit():
        await _user_card(update, context, int(parts[2]))
        return

    if head == "user" and len(parts) >= 5 and parts[2] == "add" and parts[3].isdigit() and parts[4].lstrip("-").isdigit():
        await _quick_add(update, context, int(parts[3]), int(parts[4]))
        return

    if head == "prod" and len(parts) >= 3 and parts[2].isdigit():
        await _product_card(update, context, int(parts[2]))
        return

    if head == "prod" and len(parts) >= 4 and parts[2] == "toggle":
        await _toggle_product(update, context, int(parts[3]))
        return

    if head == "prod" and len(parts) >= 4 and parts[2] == "del":
        await _delete_product(update, context, int(parts[3]))
        return

    if head == "cat" and len(parts) >= 4 and parts[2] == "del":
        await _delete_category(update, context, int(parts[3]))
        return

    if head == "order" and len(parts) >= 4:
        await _order_action(update, context, parts[2], int(parts[3]))
        return

    if head == "topup" and len(parts) >= 5:
        await _topup_action(update, context, int(parts[3]), int(parts[4]), parts[2] == "yes")
        return

    # Fall through: navigation callbacks.
    await router.go(update, context, data)


async def cmd_setbanner_from_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if db.get_setting("banner_photo"):
        db.set_setting("banner_photo", None)
        await query.answer("🖼 Banner ဖျက်ပြီးပါပြီ", show_alert=True)
        return
    db.set_pending(query.from_user.id, {"action": "banner"})
    await query.answer("ပုံပို့ပါ 📷", show_alert=True)


async def _user_card(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    query = update.callback_query
    row = db.get_user(user_id)
    if row is None:
        await query.answer("⚠️ user မတွေ့ပါ။", show_alert=True)
        return
    orders = db.user_orders(user_id, limit=5)
    text = (
        f"👤 <b>{esc(row['full_name'] or '—')}</b>\n"
        f"🆔 <code>{row['user_id']}</code>\n"
        f"🕐 @{esc(row['username'] or '—')}\n"
        f"💰 လက်ကောင်း: <b>{money(row['balance'])}</b>\n"
        f"🧾 အော်ဒါ {len(orders)} ခု"
    )
    keyboard = [
        [
            InlineKeyboardButton("+10,000", callback_data=f"adm:user:add:{user_id}:10000"),
            InlineKeyboardButton("+50,000", callback_data=f"adm:user:add:{user_id}:50000"),
            InlineKeyboardButton("+100,000", callback_data=f"adm:user:add:{user_id}:100000"),
        ],
        [
            InlineKeyboardButton("-10,000", callback_data=f"adm:user:add:{user_id}:-10000"),
            InlineKeyboardButton("💵 Balance သတ်မှတ်", callback_data=f"adm:user:zero:{user_id}"),
        ],
    ]
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)


async def _quick_add(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: int) -> None:
    query = update.callback_query
    new_balance = db.change_balance(user_id, amount)
    await query.answer(f"✅ {money(amount)} → {money(new_balance)}", show_alert=True)
    verb = "💰 လက်ကောင်းဖြည့်ပြီး" if amount > 0 else "💸 လက်ကောင်းနှုတ်ပြီး"
    await _safe_notify(context, user_id, f"{verb}\n\nကျန်လက်ကောင်း: <b>{money(new_balance)}</b>")


async def _zero_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    query = update.callback_query
    current = db.get_balance(user_id)
    db.change_balance(user_id, -current)
    await query.answer("💵 လက်ကောင်း 0 သို့ ပြောင်းပြီးပါပြီ", show_alert=True)
    await _safe_notify(context, user_id, f"💵 လက်ကောင်းသတ်မှတ်ဖြစ်ပြီး — ကျန်လက်ကောင်း: <b>{money(0)}</b>")


async def _safe_notify(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Notify a user without letting a blocked bot break the admin's action."""
    try:
        await router.notify(context, user_id, text, reply_markup)
    except TelegramError:
        log.warning("Could not notify user %s", user_id, exc_info=True)


async def _product_card(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    query = update.callback_query
    p = db.get_product(product_id)
    if p is None:
        await query.answer("⚠️ ထုတ်ကုန် မတွေ့ပါ။", show_alert=True)
        return
    cat_label = f"{p['cat_emoji']} {esc(p['cat_name'])}" if p["cat_name"] else "—"
    text = (
        f"{'🟢' if p['is_active'] else '🔴'} <b>{esc(p['name'])}</b>\n\n"
        f"<code>#{p['id']}</code>\n"
        f"💵 စျေးကြေး: <b>{money(p['price'])}</b>\n"
        f"📦 ကုန်ပမာနှင့်: {'အကန့်မဲ့' if p['stock'] < 0 else p['stock']}\n"
        f"🗂 {cat_label}"
    )
    keyboard = [
        [
            InlineKeyboardButton(
                "🔴 ဖွင့်ပါ" if p["is_active"] else "🟢 ပြန်ဖွင့်ပါ",
                callback_data=f"adm:prod:toggle:{product_id}",
            )
        ],
        [InlineKeyboardButton("🗑 ဖျက်ပါ", callback_data=f"adm:prod:del:{product_id}")],
    ]
    if p["photo_id"]:
        await query.message.reply_photo(
            p["photo_id"], caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML
        )
    else:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)


async def _toggle_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    p = db.get_product(product_id)
    if p is None:
        return
    db.set_product_active(product_id, not p["is_active"])
    await update.callback_query.answer(
        f"{'🔴 ပိတ်ပြီး' if p['is_active'] else '🟢 ပြန်ဖွင့်ပြီး'} — {esc(p['name'][:30])}", show_alert=True
    )


async def _delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    db.delete_product(product_id)
    await update.callback_query.answer("🗑 ဖျက်ပြီးပါပြီ", show_alert=True)


async def _delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: int) -> None:
    db.delete_category(cat_id)
    await update.callback_query.answer("🗑 Category ဖျက်ပြီးပါပြီ", show_alert=True)
    await router.go(update, context, "adm:cat:list")


async def _order_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, order_id: int) -> None:
    query = update.callback_query
    order = db.get_order(order_id)
    if order is None:
        await query.answer("⚠️ အော်ဒါ မတွေ့ပါ။", show_alert=True)
        return
    product = db.get_product(order["product_id"])
    buyer = db.get_user(order["user_id"])
    buyer_handle = f"@{esc(buyer['username'])}" if buyer and buyer["username"] else "—"

    if action == "yes":
        db.set_order_status(order_id, "approved")
        text = (
            "✅ <b>အော်ဒါ အတည်ပြုပြီး</b>\n\n"
            f"<code>#{order_id}</code> — {esc(product['name'] if product else '—')}\n"
            f"🧮 x{order['qty']} · {money(order['total'])}\n"
            f"👤 သင့်အတွက် ({buyer_handle})\n\n"
            "Admin က ပစ္စည်းပေးပို့ပေးပါမည်။ ရရှိပြီးရင် အောက်က ခလုပ်ပေးပါ။"
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✅ လက်ခံရရှိပြီး", callback_data=f"usr:deliver:{order_id}")]]
        )
    elif action == "no":
        db.set_order_status(order_id, "rejected")
        new_balance = db.change_balance(order["user_id"], order["total"])
        text = (
            "❌ <b>အော်ဒါ ပယ်ဖျက်ပြီး</b>\n\n"
            f"<code>#{order_id}</code>\n\n"
            f"💰 ငွေပြန်အမည်: {money(order['total'])}\n"
            f"💵 ကျန်လက်ကောင်း: {money(new_balance)}"
        )
        kb = None
    elif action == "done":
        db.set_order_status(order_id, "delivered")
        text = f"🔵 <b>အော်ဒါ #{order_id}</b> — ပေးပြီးသွင်းပါပြီ။"
        kb = None
    else:
        return

    await _safe_notify(context, order["user_id"], text, kb)

    await _paint_admin_notice(query, f"🔁 <code>#{order_id}</code> → <b>{action}</b>", "order")


async def _topup_action(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: int, approve: bool) -> None:
    query = update.callback_query
    if approve:
        new_balance = db.change_balance(user_id, amount)
        user_text = f"✅ <b>သိန်းငွေ ဖြည့်ပြီးပါပြီ</b>\n\n💵 ထည့်သွင်းသော: {money(amount)}\n💰 ကျန်လက်ကောင်း: <b>{money(new_balance)}</b>"
    else:
        user_text = (
            "❌ <b>သိန်းငွေဖြည့်မှု မအတည်ပြုပါ</b>\n\n"
            "Receipt ကို ပြန်စစ်ဆေးပေးပါ။ အချက်ချင်း ထပ်ပို့နိုင်ပါတယ်။"
        )
    await _safe_notify(context, user_id, user_text)
    await _paint_admin_notice(
        query, f"💸 ID <code>{user_id}</code> → <b>{money(amount)}</b> ({'အတည်ပြု' if approve else 'မဖြည့်'})", "topup"
    )


async def _paint_admin_notice(query, text: str, tag: str) -> None:
    """Replace the admin's action buttons with a one-line result."""
    try:
        await query.edit_message_text(
            text=f"{text}\n<i>({esc(tag)})</i>", reply_markup=InlineKeyboardMarkup([]), parse_mode=ParseMode.HTML
        )
    except TelegramError:
        pass