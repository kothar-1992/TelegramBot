"""Admin handlers: catalogue management, order review, balances, broadcasts.

Every string comes from `lang.t()`.  Admin screens follow the admin's own
language setting; messages pushed to customers are rendered in *their*
language (see `router.notify`, which resolves it per recipient).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

import backup
import db
import handlers_user as user
import lang
import router
import views
from config import settings
from lang import t
from views import esc, money

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# durability
# --------------------------------------------------------------------------- #
async def save_now(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Mirror shop.db to Telegram immediately after an admin edit.

    The free host's disk is wiped on every deploy, so waiting for the periodic
    snapshot is a gamble: an admin who adds a product and then triggers a
    rebuild would lose it.  This makes the save part of the action itself.
    """
    try:
        return await backup.flush(context.bot, backup.chat_id())
    except TelegramError:
        log.warning("Could not save the catalogue after an admin edit", exc_info=True)
        return False


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
#: Demo catalogue — `(category emoji, category name, [(product, price, stock, note, warranty, tutorial)])`
DEMO_DATA: tuple[tuple[str, str, tuple[tuple[str, int, int, str, str, str], ...]], ...] = (
    ("💰", "USDT / Crypto", (
        ("USDT TRC20", 65_000, 10, "Delivered within minutes.", "30 days", "https://t.me/w3ktutorial/1"),
        ("USDT BEP20", 64_000, 5, "Binance Smart Chain.", "30 days", ""),
        ("USDT TON", 63_000, 0, "Out of stock right now.", "", ""),
    )),
    ("🤖", "ChatGPT", (
        ("ChatGPT GO 1 Month (Full Warranty)", 45_000, 3, "Full 30-day warranty.", "30 days", "https://t.me/w3ktutorial/2"),
        ("ChatGPT Plus 1 Month (10 Day Warranty)", 53_000, 2, "Account is handed over instantly.", "10 days", "https://t.me/w3ktutorial/3"),
        ("ChatGPT Plus K12 Edu 2 Year", 0, 0, "Ask the admin for stock.", "", ""),
    )),
    ("💼", "Microsoft", (
        ("Microsoft 365 Personal 1 Month", 12_000, 20, "All Office apps included.", "30 days", ""),
        ("Windows 11 Pro Lifetime", 35_000, 8, "One-off purchase, yours forever.", "Lifetime", ""),
    )),
    ("🎨", "Adobe", (
        ("Adobe CC All Apps 1 Month", 40_000, 4, "Photoshop, Illustrator and more.", "30 days", ""),
        ("Photoshop 1 Month", 15_000, 10, "Popular with designers.", "30 days", ""),
    )),
    ("📹", "Zoom", (
        ("Zoom Pro 1 Month", 18_000, 15, "Meetings up to 500.", "30 days", ""),
    )),
    ("🎬", "Design Tools", (
        ("Canva Pro 1 Year", 25_000, 6, "A full year of everything.", "1 year", ""),
        ("Canva Team 1 Month", 12_000, 0, "Sold out at the moment.", "", ""),
    )),
)

DEMO_SETTING = "demo_ids"


def _demo_targets(existing: list) -> dict[int, tuple[str, str, int | None]]:
    """Assign each demo group to one of the categories the admin already has.

    Names are matched first so ChatGPT samples land in ChatGPT, then whatever
    is left is filled round-robin.  With no categories at all the demo set
    brings its own — that is the only time it creates any.
    """
    if not existing:
        return {i: (emoji, name, None) for i, (emoji, name, _p) in enumerate(DEMO_DATA)}

    by_name: dict[str, object] = {}
    for row in existing:
        by_name.setdefault(row["name"].strip().lower(), row)

    targets: dict[int, tuple[str, str, int | None]] = {}
    for index, (_emoji, name, _products) in enumerate(DEMO_DATA):
        match = by_name.get(name.strip().lower())
        if match is not None and match["id"] not in {t[2] for t in targets.values()}:
            targets[index] = (match["emoji"], match["name"], match["id"])

    spare = [row for row in existing if row["id"] not in {t[2] for t in targets.values()}]
    for offset, index in enumerate(i for i in range(len(DEMO_DATA)) if i not in targets):
        row = spare[offset % len(spare)]
        targets[index] = (row["emoji"], row["name"], row["id"])
    return targets


def _seed_demo() -> tuple[list[int], list[int], str]:
    """Fill the shop with sample products. Returns (new category ids, product ids, note)."""
    existing = db.list_categories()
    targets = _demo_targets(existing)

    cat_ids: list[int] = []
    product_ids: list[int] = []

    for index, (_emoji, _name, products) in enumerate(DEMO_DATA):
        emoji, name, existing_id = targets[index]
        cat_id = existing_id if existing_id is not None else db.add_category(name, emoji)
        if existing_id is None:
            cat_ids.append(cat_id)

        for entry in products:
            title, price, stock, note = entry[:4]
            warranty = entry[4] if len(entry) > 4 else ""
            tutorial = entry[5] if len(entry) > 5 else ""
            product_ids.append(
                db.add_product(
                    title, price, category_id=cat_id, description=note, stock=stock,
                    warranty=warranty, tutorial_url=tutorial,
                )
            )

    if cat_ids and existing:
        note = f"created {len(cat_ids)} new categor{'y' if len(cat_ids) == 1 else 'ies'} for the remainder"
    elif cat_ids:
        note = "built a fresh demo catalogue"
    else:
        note = f"filled the {len(existing)} categories you already had"
    return cat_ids, product_ids, note


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
            t("demo_cleared", count=removed) if removed else t("demo_nothing"), parse_mode=ParseMode.HTML
        )
        return

    if db.get_setting(DEMO_SETTING):
        await update.message.reply_text(t("demo_exists"), parse_mode=ParseMode.HTML)
        return

    cat_ids, product_ids, note = _seed_demo()
    db.set_setting(DEMO_SETTING, json.dumps({"categories": cat_ids, "products": product_ids}))

    admin_id = update.effective_user.id
    if db.get_balance(admin_id) == 0:
        db.change_balance(admin_id, 500_000)  # so the order flow can be tested

    summary = "\n".join(
        f"{row['emoji']} {esc(row['name'])} — {row['n']}"
        for row in db.demo_summary(product_ids)
    )
    await update.message.reply_text(
        t(
            "demo_done",
            cats=len(cat_ids),
            products=len(product_ids),
            balance=money(db.get_balance(admin_id)),
            note=note,
            summary=summary,
        ),
        parse_mode=ParseMode.HTML,
    )


async def cmd_paymethods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    methods = db.list_payment_methods(active_only=False)
    if not methods:
        await update.message.reply_text(t("paymethods_none"))
        return

    lines = [t("paymethods_title")]
    for m in methods:
        flag = "🟢" if m["is_active"] else "🔴"
        number = f" · <code>{esc(m['account_number'])}</code>" if m["account_number"] else ""
        holder = f" · {esc(m['account_name'])}" if m["account_name"] else ""
        lines.append(
            t("paymethods_item", flag=flag, id=m["id"], emoji=m["emoji"], name=esc(m["name"]), number=number, holder=holder)
        )
    lines.append("")
    lines.append(t("paymethods_edit"))
    lines.append(t("paymethods_del"))
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_addpay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/addpay 💳 KBZPay | 09xxxxxxxx | YeHtutNaung`"""
    raw = " ".join(update.message.text.split()[1:]).strip()
    if not raw:
        await update.message.reply_text(t("addpay_usage"))
        return

    fields = [f.strip() for f in raw.split("|")]
    head = fields[0].split(maxsplit=1)
    if len(head) == 2 and len(head[0]) <= 3:
        emoji, name = head[0], head[1].strip()
    else:
        emoji, name = "💳", fields[0]

    number = fields[1] if len(fields) > 1 else ""
    holder = fields[2] if len(fields) > 2 else ""
    method_id = db.add_payment_method(name, emoji, holder, number)
    await update.message.reply_text(t("addpay_done", id=method_id, emoji=emoji, name=esc(name)), parse_mode=ParseMode.HTML)


async def cmd_delpay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text(t("delpay_usage"))
        return
    db.delete_payment_method(int(parts[1]))
    await update.message.reply_text(t("cat_deleted", id=parts[1]))


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        t("id_reply", user_id=user.id, name=esc(user.full_name),
          admin=t("id_yes") if user.id in settings.admin_ids else t("id_no")),
        parse_mode=ParseMode.HTML,
    )


def _category_saved(message, cat_id: int, emoji: str, name: str) -> None:
    """Confirm a new category and offer to fill it straight away."""
    message.reply_text(
        t("addcat_saved", id=cat_id, emoji=emoji, name=esc(name)),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(t("admin_prod_new"), callback_data=f"adm:cat:new:{cat_id}")],
                [InlineKeyboardButton(t("back"), callback_data="adm:cat:list")],
            ]
        ),
    )


async def cmd_addcat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/addcat 💰 Wallet` — emoji is optional."""
    raw = " ".join(update.message.text.split()[1:]).strip()
    if not raw:
        db.set_pending(update.effective_user.id, {"action": "category_name"})
        await update.message.reply_text(t("addcat_prompt"))
        return

    parts = raw.split(maxsplit=1)
    if len(parts) == 2 and len(parts[0]) <= 3 and not parts[0].isalnum():
        emoji, name = parts[0], parts[1].strip()
    else:
        emoji, name = "📦", raw

    cat_id = db.add_category(name, emoji)
    _category_saved(update.message, cat_id, emoji, name)


async def cmd_cats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cats = db.list_categories()
    if not cats:
        await update.message.reply_text(t("cat_none"))
        return
    lines = [t("cat_list_title")]
    lines += [t("cat_list_item", id=c["id"], emoji=c["emoji"], name=esc(c["name"]), count=c["item_count"]) for c in cats]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_delcat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text(t("delcat_usage"))
        return
    db.delete_category(int(parts[1]))
    await update.message.reply_text(t("cat_deleted", id=parts[1]))


async def cmd_addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _start_product(update, context, None)


async def _start_product(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int | None) -> None:
    """Begin the photo → caption wizard, optionally locked to one category."""
    pending: dict = {"action": "product_photo"}
    if category_id is not None:
        pending["category_id"] = category_id

    db.set_pending(update.effective_user.id, pending)
    cat = db.get_category(category_id) if category_id else None
    await update.message.reply_text(
        t("addproduct_prompt_into", category=f"{cat['emoji']} {esc(cat['name'])}") if cat else t("addproduct_prompt"),
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
        await update.message.reply_text(t("prod_none"))
        return
    lines = [t("prod_list_title")]
    lines += [
        t(
            "paymethods_item",
            flag="🟢" if p["is_active"] else "🔴",
            id=p["id"],
            emoji="",
            name=esc(p["name"]),
            number=f" — {money(p['price'])}",
            holder="",
        )
        for p in rows
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_delproduct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text(t("delproduct_usage"))
        return
    db.delete_product(int(parts[1]))
    await update.message.reply_text(t("prod_deleted"))


async def cmd_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await update.message.reply_text(t("toggle_usage"))
        return
    pid = int(parts[1])
    product = db.get_product(pid)
    if product is None:
        await update.message.reply_text(t("not_found"))
        return
    db.set_product_active(pid, not product["is_active"])
    await update.message.reply_text(
        t("prod_toggled", state=t("prod_on") if not product["is_active"] else t("prod_off"), name=esc(product["name"])),
        parse_mode=ParseMode.HTML,
    )


async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/give <user_id> <amount>` — add (or subtract with a minus) balance."""
    parts = update.message.text.split()
    if len(parts) != 3 or not parts[1].lstrip("-").isdigit() or not parts[2].lstrip("-").isdigit():
        await update.message.reply_text(t("give_usage"))
        return
    user_id, amount = int(parts[1]), int(parts[2])
    if db.get_user(user_id) is None:
        await update.message.reply_text(t("err_user_not_found"))
        return
    new_balance = db.change_balance(user_id, amount)
    await update.message.reply_text(t("give_done", user_id=user_id, balance=money(new_balance)), parse_mode=ParseMode.HTML)
    await _safe_notify(context, user_id, t("give_notify", balance=money(new_balance)))


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split()
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await update.message.reply_text(t("balance_usage"))
        return
    row = db.get_user(int(parts[1]))
    if row is None:
        await update.message.reply_text(t("err_user_not_found"))
        return
    await update.message.reply_text(
        t(
            "admin_user_card",
            name=esc(row["full_name"] or "—"),
            user_id=row["user_id"],
            handle=esc(row["username"] or "—"),
            balance=money(row["balance"]),
            orders=len(db.user_orders(row["user_id"], limit=5)),
        ),
        parse_mode=ParseMode.HTML,
    )


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(update.message.text.split()[1:]).strip()
    if not text:
        db.set_pending(update.effective_user.id, {"action": "broadcast"})
        await update.message.reply_text(t("broadcast_prompt"))
        return
    db.set_pending(update.effective_user.id, {"action": "broadcast", "text": text})
    await _send_broadcast(update, context)


async def _send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = db.get_pending(update.effective_user.id) or {}
    text = pending.get("text", "")
    if not text:
        return
    ok = failed = 0
    status = await update.effective_message.reply_text(t("broadcast_sending"))
    for row in db._rows("SELECT user_id FROM users"):
        try:
            await context.bot.send_message(row["user_id"], text, parse_mode=ParseMode.HTML)
            ok += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)
    db.set_pending(update.effective_user.id, None)
    await status.edit_text(t("broadcast_done", ok=ok, failed=failed))


async def cmd_setbanner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if db.get_setting("banner_photo"):
        db.set_setting("banner_photo", None)
        await update.message.reply_text(t("setbanner_cleared"))
        return
    db.set_pending(update.effective_user.id, {"action": "banner"})
    await update.message.reply_text(t("setbanner_prompt"))


async def cmd_setname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = " ".join(update.message.text.split()[1:]).strip()
    if not name:
        await update.message.reply_text(t("setname_usage"))
        return
    db.set_setting("shop_name", name)
    await update.message.reply_text(t("setname_done", name=esc(name)), parse_mode=ParseMode.HTML)


async def cmd_setlang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/setlang my` — the language new customers get by default."""
    raw = " ".join(update.message.text.split()[1:]).strip().lower()
    if not lang.is_supported(raw):
        await update.message.reply_text(
            "\n".join([f"🌐 {meta['flag']} <code>{code}</code> — {meta['name']}" for code, meta in lang.LANGUAGES.items()]),
            parse_mode=ParseMode.HTML,
        )
        return
    db.set_setting("default_lang", raw)
    await update.message.reply_text(t("lang_admin_set", name=lang.native_name(raw)), parse_mode=ParseMode.HTML)


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await router.go(update, context, "adm:orders")


# --------------------------------------------------------------------------- #
# photo / text wizard (admin-only, runs before the user handlers)
# --------------------------------------------------------------------------- #
async def on_admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user.resolve_language(update)
    pending = db.get_pending(update.effective_user.id) or {}
    action = pending.get("action")
    if action not in {"product_photo", "banner", "topup_receipt"}:
        return

    photo = update.message.photo[-1]
    file_id = photo.file_id

    if action == "banner":
        db.set_setting("banner_photo", file_id)
        db.set_pending(update.effective_user.id, None)
        await update.message.reply_text(t("banner_set_hint"))
        raise ApplicationHandlerStop

    if action == "product_photo":
        pending = dict(pending)
        pending.update({"action": "product_caption", "photo_id": file_id})
        db.set_pending(update.effective_user.id, pending)
        await update.message.reply_text(t("addproduct_caption_prompt"), parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop

    if action == "topup_receipt":
        # A receipt meant for the customer support flow — store and notify admins.
        from handlers_user import (
            on_photo as user_on_photo,  # local import avoids a cycle
        )

        await user_on_photo(update, context)
        raise ApplicationHandlerStop


async def on_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user.resolve_language(update)
    pending = db.get_pending(update.effective_user.id) or {}
    action = pending.get("action")
    if action is None:
        return

    text = (update.message.text or "").strip()

    if action == "product_caption":
        parsed = parse_caption(text)
        if parsed is None:
            await update.message.reply_text(t("addproduct_bad_caption"))
            return
        name, price, category_id, description, stock = parsed
        # A product started from a category keeps it, unless the caption names another.
        if category_id is None:
            category_id = pending.get("category_id")
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
        cat_label = f"{cat['emoji']} {esc(cat['name'])}" if cat else t("prod_no_category")
        await update.message.reply_text(
            t(
                "prod_saved",
                id=product_id,
                name=esc(name),
                price=money(price),
                stock=t("product_stock_inf") if stock < 0 else stock,
                category=cat_label,
            ),
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop

    if action == "category_name":
        db.set_pending(update.effective_user.id, None)
        if not text:
            await update.message.reply_text(t("not_found"))
            return
        cat_id = db.add_category(text, "📦")
        _category_saved(update.message, cat_id, "📦", text)
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
    user.resolve_language(update)
    query = update.callback_query
    data = query.data
    parts = data.split(":")
    head = parts[1] if len(parts) > 1 else ""

    if head == "cat" and len(parts) >= 3 and parts[2] == "new":
        # `adm:cat:new` asks for a category, `adm:cat:new:<id>` fills one in.
        if len(parts) >= 4 and parts[3].isdigit():
            await _start_product(update, context, int(parts[3]))
            return
        db.set_pending(query.from_user.id, {"action": "category_name"})
        await query.message.reply_text(t("addcat_prompt"))
        return

    if head == "banner":
        await cmd_setbanner_from_query(update, context)
        return

    if head == "lang" and len(parts) >= 3 and parts[2] in lang.LANGUAGES:
        db.set_setting("default_lang", parts[2])
        await query.answer(t("lang_admin_set", name=lang.native_name(parts[2])), show_alert=True)
        return

    if head == "user" and len(parts) >= 4 and parts[2] == "zero" and parts[3].isdigit():
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

    if head == "topup" and len(parts) >= 3:
        await _topup_action(update, context, int(parts[2]), parts[1] == "yes")
        return

    # Fall through: navigation callbacks.
    await router.go(update, context, data)


async def cmd_setbanner_from_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if db.get_setting("banner_photo"):
        db.set_setting("banner_photo", None)
        await query.answer(t("banner_cleared_alert"), show_alert=True)
        return
    db.set_pending(query.from_user.id, {"action": "banner"})
    await query.answer(t("banner_sent"), show_alert=True)


async def _user_card(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    query = update.callback_query
    row = db.get_user(user_id)
    if row is None:
        await query.answer(t("err_user_not_found"), show_alert=True)
        return
    orders = db.user_orders(user_id, limit=5)
    text = t(
        "admin_user_card",
        name=esc(row["full_name"] or "—"),
        user_id=row["user_id"],
        handle=esc(row["username"] or "—"),
        balance=money(row["balance"]),
        orders=len(orders),
    )
    keyboard = [
        [
            InlineKeyboardButton("+10,000", callback_data=f"adm:user:add:{user_id}:10000"),
            InlineKeyboardButton("+50,000", callback_data=f"adm:user:add:{user_id}:50000"),
            InlineKeyboardButton("+100,000", callback_data=f"adm:user:add:{user_id}:100000"),
        ],
        [
            InlineKeyboardButton("-10,000", callback_data=f"adm:user:add:{user_id}:-10000"),
            InlineKeyboardButton(t("admin_zero"), callback_data=f"adm:user:zero:{user_id}"),
        ],
    ]
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)


async def _quick_add(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: int) -> None:
    query = update.callback_query
    new_balance = db.change_balance(user_id, amount)
    await query.answer(f"✅ {money(amount)} → {money(new_balance)}", show_alert=True)
    verb = f"💰 {t('add_note')}" if amount > 0 else f"💸 {t('add_note_sub')}"
    await _safe_notify(context, user_id, t("quick_add_notify", verb=verb, balance=money(new_balance)))


async def _zero_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    query = update.callback_query
    current = db.get_balance(user_id)
    db.change_balance(user_id, -current)
    await query.answer(t("admin_zero"), show_alert=True)
    await _safe_notify(context, user_id, t("zero_notify", balance=money(db.get_balance(user_id))))


async def _safe_notify(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text: str | Callable[[], str],
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    language: str | None = None,
) -> None:
    """Notify a user without letting a blocked bot break the admin's action.

    Pass a thunk for `text` so the body is built in the *recipient's* language
    rather than the admin's.
    """
    try:
        await router.notify(context, user_id, text, reply_markup, language=language)
    except TelegramError:
        log.warning("Could not notify user %s", user_id, exc_info=True)


async def _product_card(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    query = update.callback_query
    p = db.get_product(product_id)
    if p is None:
        await query.answer(t("not_found"), show_alert=True)
        return
    cat_label = f"{p['cat_emoji']} {esc(p['cat_name'])}" if p["cat_name"] else "—"
    text = "\n".join(
        [
            f"{'🟢' if p['is_active'] else '🔴'} <b>{esc(p['name'])}</b>",
            "",
            f"<code>#{p['id']}</code>",
            t("prod_admin_price", price=money(p["price"])),
            t("prod_admin_stock", stock=t("product_stock_inf") if p["stock"] < 0 else p["stock"]),
            t("prod_admin_cat", category=cat_label),
        ]
    )
    keyboard = [
        [InlineKeyboardButton(t("prod_hide_btn") if p["is_active"] else t("prod_show_btn"),
                              callback_data=f"adm:prod:toggle:{product_id}")],
        [InlineKeyboardButton(t("prod_del_btn"), callback_data=f"adm:prod:del:{product_id}")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    if p["photo_id"]:
        await query.message.reply_photo(p["photo_id"], caption=text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await query.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def _toggle_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    p = db.get_product(product_id)
    if p is None:
        return
    db.set_product_active(product_id, not p["is_active"])
    await update.callback_query.answer(
        t("prod_toggled", state=t("prod_off") if p["is_active"] else t("prod_on"), name=esc(p["name"][:30])),
        show_alert=True,
    )


async def _delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int) -> None:
    db.delete_product(product_id)
    await update.callback_query.answer(t("prod_deleted"), show_alert=True)


async def _delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: int) -> None:
    db.delete_category(cat_id)
    await update.callback_query.answer(t("cat_deleted", id=cat_id), show_alert=True)
    await router.go(update, context, "adm:cat:list")


async def _order_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, order_id: int) -> None:
    query = update.callback_query
    order = db.get_order(order_id)
    if order is None:
        await query.answer(t("err_no_order"), show_alert=True)
        return
    product = db.get_product(order["product_id"])
    buyer = db.get_user(order["user_id"])
    buyer_handle = f"@{esc(buyer['username'])}" if buyer and buyer["username"] else "—"
    buyer_lang = (buyer["language"] if buyer else None) or lang.DEFAULT_LANG

    if action == "yes":
        db.set_order_status(order_id, "approved")

        def body() -> str:
            return t(
                "order_approved",
                id=order_id,
                product=esc(product["name"] if product else "—"),
                qty=order["qty"],
                total=money(order["total"]),
                handle=buyer_handle,
            )

        markup = InlineKeyboardMarkup([[InlineKeyboardButton(t("deliver_btn"), callback_data=f"usr:deliver:{order_id}")]])
    elif action == "no":
        db.set_order_status(order_id, "rejected")
        new_balance = db.change_balance(order["user_id"], order["total"])

        def body() -> str:
            return t("order_refund", id=order_id, total=money(order["total"]), balance=money(new_balance))

        markup = None
    elif action == "done":
        db.set_order_status(order_id, "delivered")

        def body() -> str:
            return t("admin_done", id=order_id)

        markup = None
    else:
        return

    await _safe_notify(context, order["user_id"], body, markup, language=buyer_lang)
    await _paint_admin_notice(query, f"🔁 <code>#{order_id}</code> → <b>{action}</b>", "order")


async def _topup_action(update: Update, context: ContextTypes.DEFAULT_TYPE, request_id: int, approve: bool) -> None:
    query = update.callback_query
    request = db.get_topup(request_id)
    if request is None:
        await query.answer(t("not_found"), show_alert=True)
        return
    if request["status"] != "pending":
        await query.answer(t("err_already_done"), show_alert=True)
        return

    user_id, amount = int(request["user_id"]), int(request["amount"])
    buyer = db.get_user(user_id)
    buyer_lang = (buyer["language"] if buyer else None) or lang.DEFAULT_LANG

    if approve:
        new_balance = db.change_balance(user_id, amount)
        db.resolve_topup(request_id, "approved")

        def body() -> str:
            return "\n".join(
                [
                    t("approve_title", id=request_id),
                    t("approve_amount", amount=money(amount)),
                    t("approve_balance", balance=money(new_balance)),
                ]
            )

    else:
        db.resolve_topup(request_id, "rejected")

        def body() -> str:
            return t("reject_title", id=request_id)

    await _safe_notify(context, user_id, body, language=buyer_lang)
    if approve:
        await router.replace_notice(
            context,
            user_id,
            request["notice_message_id"],
            lambda: "\n".join(
                p.text for p in views.topup_review(request_id, db.get_balance(user_id))
            ),
            language=buyer_lang,
        )
    verdict = t("review_approved") if approve else t("review_rejected")
    await _paint_admin_notice(query, f"💸 <code>#{request_id}</code> → <b>{verdict}</b>", "topup")


async def _expire_topups(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Reject review requests the admin never answered in time."""
    expired = 0
    for request in db.stale_topups(settings.review_minutes):
        request_id = int(request["id"])
        db.resolve_topup(request_id, "expired")
        user_id = int(request["user_id"])
        buyer = db.get_user(user_id)
        buyer_lang = (buyer["language"] if buyer else None) or lang.DEFAULT_LANG
        await router.replace_notice(
            context,
            user_id,
            request["notice_message_id"],
            lambda rid=request_id, uid=user_id: "\n".join(
                p.text for p in views.topup_review(rid, db.get_balance(uid))
            ),
            language=buyer_lang,
        )
        await _safe_notify(
            context,
            user_id,
            lambda minutes=settings.review_minutes: t("expire_title", minutes=minutes),
            language=buyer_lang,
        )
        expired += 1
    if expired:
        log.info("Auto-rejected %d stale top-up request(s)", expired)
    return expired


async def _paint_admin_notice(query, text: str, tag: str) -> None:
    """Replace the admin's action buttons with a one-line result."""
    try:
        await query.edit_message_text(
            text=f"{text}\n<i>({esc(tag)})</i>", reply_markup=InlineKeyboardMarkup([]), parse_mode=ParseMode.HTML
        )
    except TelegramError:
        pass