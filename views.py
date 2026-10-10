"""Screen builders.

Every callback payload understood by the bot is turned into a list of
`Part` objects here.  A `Part` is one Telegram message: optional photo,
caption text and an inline keyboard.  The router knows how to swap the
currently visible parts for a new set.
"""

from __future__ import annotations

import html
import time
from dataclasses import dataclass

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup

import db
import keyboards as kb
from config import is_admin, settings


@dataclass
class Part:
    text: str
    photo: str | None = None
    keyboard: InlineKeyboardMarkup | None = None
    reply_keyboard: ReplyKeyboardMarkup | None = None


PRICE_TBD = "💬 စျေးနှင့်မသတ်မှတ်"


def money(amount: int) -> str:
    """`0` means "price on request" — never show a free product by accident."""
    return f"{int(amount):,} {settings.currency}" if int(amount) > 0 else PRICE_TBD


def esc(text: str | None) -> str:
    return html.escape(str(text or ""), quote=False)


def _profile(user_id: int) -> tuple[str, str]:
    row = db.get_user(user_id)
    name = (row["full_name"] if row else "") or "အသုံးပြုသူ"
    user = (row["username"] if row else "") or "—"
    return esc(name), f"@{esc(user)}"


# --------------------------------------------------------------------------- #
# public screens
# --------------------------------------------------------------------------- #
def main(user_id: int) -> list[Part]:
    banner = db.get_setting("banner_photo")
    welcome = settings.welcome_text.format(shop=esc(settings.shop_name))
    balance_line = f"💰 <b>သင့်လက်ကောင်း:</b> {money(db.get_balance(user_id))}"
    menu_kb = kb.main_menu(is_admin=is_admin(user_id))
    menu_btn = kb.menu_reply_keyboard() if settings.menu_button else None

    if banner:
        # The welcome card also carries the persistent 🏠 Menu reply keyboard,
        # so no extra helper message is needed in the chat.
        return [
            Part(text=welcome, photo=banner, reply_keyboard=menu_btn),
            Part(text=balance_line, keyboard=menu_kb),
        ]
    return [Part(text=f"{welcome}\n\n{balance_line}", keyboard=menu_kb)]


CATEGORIES_PER_PAGE = 8


def catalog(user_id: int, page: int = 0) -> list[Part]:
    all_cats = db.list_categories()
    if not all_cats:
        return [
            Part(
                text="🛍 <b>ထုတ်ကုန်စာရင်း</b>\n\nယခုအချိန်တွင် ထုတ်ကုန်များ မရှိသေးပါ။",
                keyboard=kb.simple(kb.nav_row()),
            )
        ]

    pages = max(1, -(-len(all_cats) // CATEGORIES_PER_PAGE))
    page = max(0, min(page, pages - 1))
    cats = all_cats[page * CATEGORIES_PER_PAGE : (page + 1) * CATEGORIES_PER_PAGE]

    total_products = db.count_products()
    header = [
        f"🗂 <b>Category စာရင်း</b> — အမျိုးအစား {len(all_cats)} ခု · ထုတ်ကုန် {total_products} ခု\n",
        "အောက်က အမျိုးအစားကို နှိပါပြီး ထုတ်ကုန်များကြည့်ပါ။",
    ]
    return [Part(text="\n".join(header), keyboard=kb.categories(cats, page, pages))]


def category_products(cat_id: int, page: int) -> list[Part]:
    cat = db.get_category(cat_id)
    if cat is None:
        return [Part(text="⚠️ Category မတူတော့ဘူး။", keyboard=kb.simple(kb.nav_row()))]

    per_page = settings.page_size
    total = db.count_products(cat_id)
    pages = max(1, -(-total // per_page))
    page = max(0, min(page, pages - 1))
    rows = db.list_products(cat_id, offset=page * per_page, limit=per_page)

    parts: list[Part] = []
    for p in rows:
        cat_tag = f"{p['cat_emoji']} {esc(p['cat_name'])}" if p["cat_name"] else ""
        caption = (
            f"<b>{esc(p['name'])}</b>\n"
            f"{cat_tag}\n"
            f"💵 စျေးကြေး: <b>{money(p['price'])}</b>\n"
            f"📦 ကုန်ပမာနှင့်: {'∞' if p['stock'] < 0 else p['stock']}"
        )
        if p["description"]:
            caption += f"\n\n{esc(p['description'])}"
        parts.append(Part(text=caption, photo=p["photo_id"], keyboard=kb.product_card(p)))

    controls = kb.product_list_controls(cat_id, page, pages)
    footer = f"{cat['emoji']} <b>{esc(cat['name'])}</b> — စာရင်း {total} ခု · စာမျက်နှာ {page + 1}/{pages}"
    parts.append(Part(text=footer, keyboard=InlineKeyboardMarkup(controls + kb.nav_row())))
    return parts


def product_detail(product_id: int) -> list[Part]:
    p = db.get_product(product_id)
    if p is None:
        return [Part(text="⚠️ ထုတ်ကုန် မတွေ့ရဘူး။", keyboard=kb.simple(kb.nav_row()))]

    text = [f"📦 <b>{esc(p['name'])}</b>"]
    if p["cat_name"]:
        text.append(f"{p['cat_emoji']} {esc(p['cat_name'])}")
    text.append(f"💵 စျေးကြေး: <b>{money(p['price'])}</b>")
    if p["warranty"]:
        text.append(f"🛡 အာမခံ: {esc(p['warranty'])}")
    text.append(f"📦 ကုန်ပမာနှင့်: {'အကန့်မဲ့' if p['stock'] < 0 else p['stock']}")
    if p["description"]:
        text.append(f"\n{esc(p['description'])}")
    if p["tutorial_url"]:
        text.append(f"\n🔗 {esc(p['tutorial_url'])}")

    part = Part(text="\n".join(text), photo=p["photo_id"])
    if p["stock"] == 0:
        part.keyboard = kb.simple(kb.nav_row())
    else:
        part.keyboard = kb.product_detail(p)
    return [part]


def quantity_screen(product_id: int, qty: int, user_id: int) -> list[Part]:
    p = db.get_product(product_id)
    if p is None:
        return [Part(text="⚠️ ထုတ်ကုန် မတွေ့ရဘူး။", keyboard=kb.simple(kb.nav_row()))]

    qty = max(1, min(qty, 99))
    total = int(p["price"]) * qty
    text = [
        f"🔽 <b>{esc(p['name'])}</b>\n",
        f"💵 စျေးကြေးတစ်ခုလျှင်: <b>{money(p['price'])}</b>",
    ]
    if p["warranty"]:
        text.append(f"🛡 အာမခံ: {esc(p['warranty'])}")
    if p["stock"] >= 0:
        text.append(f"📦 ကုန်ပမာနှင့်: {p['stock']}")
    text.append(f"\n🔢 ရွေးပြီးသော ပမာနှင့်: <b>{qty}</b>")
    text.append(f"💵 စုစုပေါင်း: <b>{money(total)}</b>")

    return [Part(text="\n".join(text), photo=p["photo_id"], keyboard=kb.qty_selector(p, qty, total, user_id))]


def confirm_screen(product_id: int, qty: int, user_id: int) -> list[Part]:
    p = db.get_product(product_id)
    if p is None:
        return [Part(text="⚠️ ထုတ်ကုန် မတွေ့ရဘူး။", keyboard=kb.simple(kb.nav_row()))]

    total = int(p["price"]) * qty
    balance = db.get_balance(user_id)
    short = max(0, total - balance)

    text = [
        "📋 <b>အတည်ပြုရန် — အော်ဒါ</b>\n",
        f"📦 {esc(p['name'])}",
        f"🔢 ပမာနှင့် — <b>{qty}</b>",
        f"💵 စုစုပေါင်း — <b>{money(total)}</b>",
        f"\n💳 လက်ကောင်း — <b>{money(balance)}</b>",
    ]
    if short:
        text.append(f"⚠️ လိုအပ်သော — <b>{money(short)}</b>")

    return [Part(text="\n".join(text), keyboard=kb.confirm_order(p, qty, total, short))]


def topup_methods(amount: int) -> list[Part]:
    methods = db.list_payment_methods()
    text = (
        "🎯 <b>အတိအကျ သိန်းငွေဖြည့်မည်</b>\n\n"
        f"🧾 Order အတိုင်း <b>{money(amount)}</b> ကို ပေးချေးမယ်\n"
        "👇 ပေးချေးမည့် နည်းလမ်းကို ရွေးပါ"
    )
    if not methods:
        return [Part(text=text + "\n\nℹ️ ပေးချေးမည့်နည်းလမ်း မရှိသေးပါ — admin က `/addpay` ထည့်ပါ။", keyboard=kb.simple(kb.nav_row()))]
    return [Part(text=text, keyboard=kb.pay_methods(methods, amount))]


def pay_details(method_id: int, amount: int, user_id: int) -> list[Part]:
    m = db.get_payment_method(method_id)
    if m is None:
        return [Part(text="⚠️ ပေးချေးမည့်နည်းလမ်း မတွေ့ရဘူး။", keyboard=kb.simple(kb.nav_row()))]

    code = reference_code(user_id, amount)
    text = [
        "🎯 <b>အတိအကျ သိန်းငွေဖြည့်မည်</b>",
        f"🧾 Order အတိုင်း <b>{money(amount)}</b> ကို ပေးချေးမယ်\n",
        f"{m['emoji']} <b>{esc(m['name'])} အလှန်လှဲ့နေရန်</b>\n",
    ]
    if m["account_number"]:
        text.append(f"🏦 ဘဏ်/အကောင့် — <code>{esc(m['account_number'])}</code>")
    if m["account_name"]:
        text.append(f"👤 အမည် — <b>{esc(m['account_name'])}</b>")
    if m["note"]:
        text.append(f"\n📝 {esc(m['note'])}")
    text.append("\n\n💬 ပေးချေးပြီးလျှင် receipt ပုံ ပို့ပါ")
    text.append(f"🔢 အမှတ်အသား — <code>{code}</code>")

    return [Part(text="\n".join(text), keyboard=kb.pay_details(m, amount, user_id, code))]


def reference_code(user_id: int, amount: int) -> str:
    """A stable per-day reference the admin can match against a payment."""
    import hashlib

    seed = f"{user_id}:{amount}:{time.strftime('%Y%m%d')}".encode()
    digest = hashlib.sha1(seed).hexdigest().upper()
    return f"DEP-{time.strftime('%y%m%d')}-{digest[:5]}"


def enquire(product_id: int) -> list[Part]:
    """`ask:<id>` — shown when a product has no fixed price."""
    p = db.get_product(product_id)
    if p is None:
        return [Part(text="⚠️ ထုတ်ကုန် မတွေ့ရဘူး။", keyboard=kb.simple(kb.nav_row()))]

    handle = settings.support_username
    contact = f"@{esc(handle)} ကို ဆက်သွယ်ပေးပါ။" if handle else "Admin ကို ဆက်သွယ်ပေးပါ။"
    text = (
        "📞 <b>စျေးနှင့်မေးမြန်းရန်</b>\n\n"
        f"🛍 ထုတ်ကုန်: <b>{esc(p['name'])}</b>\n"
        f"💵 စျေးကြေး: {PRICE_TBD}\n\n"
        f"{contact}"
    )
    return [Part(text=text, photo=p["photo_id"], keyboard=kb.simple(kb.nav_row()))]


def qty_picker(product_id: int, qty: int, user_id: int) -> list[Part]:
    p = db.get_product(product_id)
    if p is None:
        return [Part(text="⚠️ ထုတ်ကုန် မတွေ့ရဘူး။", keyboard=kb.simple(kb.nav_row()))]

    total = int(p["price"]) * qty
    balance = db.get_balance(user_id)
    hint = "" if balance >= total else "\n\n⚠️ လက်ကောင်း မလုံလောက်သေးပါ။ အရေအတွက် ဖြည့်ရန် လိုပါသေးသလို့ ပမာနှင့် လျှော့ပါ။"
    text = (
        f"🛒 <b>{esc(p['name'])}</b>\n\n"
        f"ယူမည့်အများအစား: <b>{qty}</b>\n"
        f"💵 စျေးကြေး: {money(p['price'])}\n"
        f"🧮 စုစုပေါင်း: <b>{money(total)}</b>\n"
        f"💰 လက်ကောင်း: {money(balance)}\n\n"
        f"အောက်က အများအစား ရွေးပါ။{hint}"
    )
    return [Part(text=text, keyboard=kb.qty_selector(p))]


def balance_screen(user_id: int) -> list[Part]:
    bal = db.get_balance(user_id)
    name, handle = _profile(user_id)
    text = (
        f"💰 <b>လက်ကောင်းအင်ဒုတ်</b>\n\n"
        f"👤 အမည်: {name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"🕐 အကောင့်: {handle}\n"
        f"💵 ကျန်လက်ကောင်း: <b>{money(bal)}</b>"
    )
    return [Part(text=text, keyboard=kb.simple([[kb._btn("💸 သိန်းငွေဖြည့်မယ်", "menu:topup")]] + kb.nav_row()))]


def topup_screen(user_id: int) -> list[Part]:
    name, handle = _profile(user_id)
    text = (
        "💸 <b>သိန်းငွေဖြည့်မည်</b>\n\n"
        "<b>အဆင့် (၁)</b> — ဖြည့်ချင်သော ပမာနှင့်ကိန်းကို အောက်က input box တွင် ရိုက်ထည့်ပါ။ (ဥပမာ — 50000)\n\n"
        "<b>အဆင့် (၂)</b> — ငွေလွှဲပြေးပြီးလျှင် လက်ဆိုင်/ပို့က်နှင့် receipt ပုံ ပို့ပါ။\n\n"
        f"👤 သင့် ID: <code>{user_id}</code> ({handle})"
    )
    return [Part(text=text, keyboard=kb.simple(kb.nav_row()))]


def orders_screen(user_id: int) -> list[Part]:
    rows = db.user_orders(user_id, limit=10)
    if not rows:
        text = "🧾 <b>အော်ဒါမှုမှတ်တမ်း</b>\n\nအော်ဒါ မရှိသေးပါ။"
        return [Part(text=text, keyboard=kb.simple([[kb._btn("🛍 ထုတ်ကုန်များ", "menu:catalog")]] + kb.nav_row()))]

    status_map = {
        "pending": "🟡 ဆိုင်းငံ့",
        "approved": "🟢 အတည်ပြုပြီး",
        "delivered": "🔵 ပေးပြီး",
        "rejected": "🔴 ပယ်ဖျက်ပြီး",
    }
    lines = ["🧾 <b>အော်ဒါမှုမှတ်တမ်း</b>\n"]
    for o in rows:
        lines.append(
            f"<code>#{o['id']}</code> — {esc(o['product_name'] or 'ဖျက်ပြီး')}\n"
            f"   x{o['qty']} · {money(o['total'])} · {status_map.get(o['status'], o['status'])}"
        )
    return [Part(text="\n".join(lines), keyboard=kb.simple(kb.nav_row()))]


def support_screen() -> list[Part]:
    handle = settings.support_username
    text = (
        "💬 <b>Live Chat</b>\n\n"
        f"အကောင်းပြုမှုအတွက် @{esc(handle)} ကို ရိုက်ဆက်ပေးပါ။"
        if handle
        else "💬 <b>Live Chat</b>\n\nအကောင်းပြုမှုအတွက် admin ကို ဆက်သွယ်ပါ။"
    )
    return [Part(text=text, keyboard=kb.simple(kb.nav_row()))]


def help_screen(user_id: int) -> list[Part]:
    text = (
        "📖 <b>အသုံးပြုနည်း</b>\n\n"
        "1️⃣ <b>🛍 ထုတ်ကုန်များ</b> — အမျိုးအစားရွေးပြီး ထုတ်ကုန်များ ကြည့်ပါ။\n"
        "2️⃣ <b>🛒 ဝယ်မည်</b> — ထုတ်ကုန်ကို ရွေးပြီး အရေအတွက် လက်ကောင်းထဲမှ နှုက်လူးပါ။\n"
        "3️⃣ <b>💰 သိန်းငွေဖြည့်မယ်</b> — receipt ပို့ပြီး admin အတည်ပြုပေးပါ။\n"
        "4️⃣ <b>⬅️ Back / 🏠 Main Menu</b> — နောက်သို့ ပြန်သွားရန်။\n\n"
        "⌨️ အောက်ခေါင်းရှိ <b>🏠 Menu</b> ခလုပ်ကို နှိပါပြီး Main Menu ပြန်သွားနိုင်ပါတယ်။"
    )
    return [Part(text=text, keyboard=kb.simple(kb.nav_row()))]


def empty_screen(message: str) -> list[Part]:
    return [Part(text=message, keyboard=kb.simple(kb.nav_row()))]


# --------------------------------------------------------------------------- #
# admin screens
# --------------------------------------------------------------------------- #
def admin_panel_screen() -> list[Part]:
    text = (
        "🛠 <b>Admin Panel</b>\n\n"
        "ထုတ်ကုန်များကို ဒီနေရာကနေ စီမံခန့်ပါ။"
    )
    return [Part(text=text, keyboard=kb.admin_panel())]


def admin_stats_screen() -> list[Part]:
    products = db._one("SELECT COUNT(*) AS c FROM products")["c"]
    active = db._one("SELECT COUNT(*) AS c FROM products WHERE is_active = 1")["c"]
    revenue = db._one("SELECT COALESCE(SUM(total), 0) AS s FROM orders WHERE status IN ('approved','delivered')")["s"]
    text = (
        "📊 <b>အချက်အလက်များ</b>\n\n"
        f"👥 အသုံးပြုသူ: <b>{db.user_count()}</b>\n"
        f"🗂 Category: <b>{len(db.list_categories())}</b>\n"
        f"🛍 ထုတ်ကုန်: <b>{active}</b> (ဖျက်ထား {products - active})\n"
        f"🧾 အော်ဒါစုစုပေါင်း: <b>{db.order_count()}</b>\n"
        f"💵 ရောင်းရလိုက်သော: <b>{money(revenue)}</b>"
    )
    return [Part(text=text, keyboard=kb.simple([[kb._btn("⬅️ Back", "menu:admin")]]))]


def admin_orders_screen() -> list[Part]:
    rows = db.pending_orders()
    if not rows:
        return [Part(text="📥 <b>အော်ဒါများ</b>\n\nဆိုင်းငံ့ အော်ဒါ မရှိပါ။", keyboard=kb.simple([[kb._btn("⬅️ Back", "menu:admin")]]))]

    parts = []
    for o in rows:
        text = (
            "🔔 <b>အော်ဒါအသစ်</b>\n\n"
            f"<code>#{o['id']}</code> · {esc(o['product_name'] or '—')}\n"
            f"🧮 အရေအတွက်: <b>{money(o['total'])}</b> (x{o['qty']})\n"
            f"👤 ဝယ်သူ: {esc(o['full_name'] or '—')} {('@' + esc(o['username'])) if o['username'] else ''}\n"
            f"🆔 <code>{o['user_id']}</code>"
        )
        kbs = kb.simple(
            [
                [kb._btn("✅ အတည်ပြု", f"adm:order:yes:{o['id']}"), kb._btn("❌ ပယ်ဖျက်", f"adm:order:no:{o['id']}")],
                [kb._btn("🔵 ပေးပြီးသွင်း", f"adm:order:done:{o['id']}")],
            ]
        )
        parts.append(Part(text=text, keyboard=kbs))
    parts.append(Part(text="⬆️ နောက်ထပ် အော်ဒါများ", keyboard=kb.simple([[kb._btn("🔄 ပြန်ဖတ်မည်", "adm:orders")], [kb._btn("⬅️ Back", "menu:admin")]])))
    return parts


def admin_users_screen() -> list[Part]:
    rows = db.top_users(15)
    if not rows:
        return [Part(text="👥 အသုံးပြုသူ မရှိသေးပါ။", keyboard=kb.simple([[kb._btn("⬅️ Back", "menu:admin")]]))]

    lines = ["👥 <b>အသုံးပြုသူများ</b>\n"]
    buttons = []
    for u in rows:
        lines.append(f"<code>{u['user_id']}</code> · {esc(u['full_name'] or '—')} · {money(u['balance'])}")
        buttons.append([kb._btn(f"{u['full_name'] or u['user_id']} — ငွေထည့်", f"adm:user:{u['user_id']}")])
    buttons.append([kb._btn("⬅️ Back", "menu:admin")])
    return [Part(text="\n".join(lines), keyboard=kb.simple(buttons))]


# --------------------------------------------------------------------------- #
# router
# --------------------------------------------------------------------------- #
def build(data: str, user_id: int) -> list[Part]:
    parts = data.split(":")
    head = parts[0]

    if head == "menu":
        page = parts[1] if len(parts) > 1 else "main"
        arg = parts[2] if len(parts) > 2 else "0"
        return {
            "main": lambda: main(user_id),
            "catalog": lambda: catalog(user_id, int(arg) if arg.isdigit() else 0),
            "balance": lambda: balance_screen(user_id),
            "orders": lambda: orders_screen(user_id),
            "support": support_screen,
            "help": lambda: help_screen(user_id),
            "topup": lambda: topup_screen(user_id),
            "admin": admin_panel_screen,
        }.get(page, lambda: main(user_id))()

    if head == "cat" and len(parts) == 3:
        return category_products(int(parts[1]), int(parts[2]))
    if head == "plist" and len(parts) == 3:
        return category_products(int(parts[1]), int(parts[2]))
    if head == "prod" and len(parts) == 2:
        return product_detail(int(parts[1]))
    if head == "ask" and len(parts) == 2:
        return enquire(int(parts[1]))
    if head == "qty" and len(parts) == 3:
        return quantity_screen(int(parts[1]), int(parts[2]), user_id)
    if head == "qadj" and len(parts) == 4:
        return quantity_screen(int(parts[1]), max(1, int(parts[2]) + int(parts[3])), user_id)
    if head == "confirm" and len(parts) == 3:
        return confirm_screen(int(parts[1]), int(parts[2]), user_id)
    if head == "topup" and len(parts) == 2:
        return topup_methods(int(parts[1]))
    if head == "pay" and len(parts) == 3:
        return pay_details(int(parts[1]), int(parts[2]), user_id)
    if head == "adm":
        return _build_admin(parts, user_id)

    return main(user_id)


def _build_admin(parts: list[str], user_id: int) -> list[Part]:
    if len(parts) >= 2 and parts[1] == "stats":
        return admin_stats_screen()
    if len(parts) >= 2 and parts[1] == "orders":
        return admin_orders_screen()
    if len(parts) >= 2 and parts[1] == "users":
        return admin_users_screen()
    if len(parts) >= 3 and parts[1] == "prod" and parts[2] == "list":
        return admin_product_screen(0)
    if len(parts) >= 4 and parts[1] == "prod" and parts[2] == "page":
        return admin_product_screen(int(parts[3]))
    if len(parts) >= 3 and parts[1] == "cat" and parts[2] == "list":
        cats = db.list_categories()
        if not cats:
            return [Part(text="🗂 Category မရှိသေးပါ။", keyboard=kb.simple([[kb._btn("⬅️ Back", "menu:admin")]]))]
        return [Part(text="🗂 <b>Category စာရင်း</b>\n\nဖျက်ချင်တဲ့ category ကို နှိပါပါ။", keyboard=kb.admin_category_list(cats))]
    if len(parts) >= 3 and parts[1] == "cat" and parts[2].isdigit():
        return admin_category_screen(int(parts[2]))
    return admin_panel_screen()


def admin_product_screen(page: int) -> list[Part]:
    per_page = 8
    total = db.count_products(active_only=False)
    pages = max(1, -(-total // per_page))
    page = max(0, min(page, pages - 1))
    rows = db.list_products(None, offset=page * per_page, limit=per_page, active_only=False)
    if not rows:
        return [Part(text="🛍 ထုတ်ကုန် မရှိသေးပါ။\n\nPhoto + caption ဖြင့် ထုတ်ကုန်ထည့်ရန် /addproduct ကို သုံးပါ။", keyboard=kb.simple([[kb._btn("⬅️ Back", "menu:admin")]]))]
    text = "🛍 <b>ထုတ်ကုန်စာရင်း</b>\n\nဖျက်ရန်/ဖွင့်ရန် ထုတ်ကုန်ကို နှိပါပါ။"
    return [Part(text=text, keyboard=kb.admin_product_list(rows, page, pages))]


def admin_category_screen(cat_id: int) -> list[Part]:
    cat = db.get_category(cat_id)
    if cat is None:
        return [Part(text="⚠️ Category မတူတော့ဘူး။", keyboard=kb.simple([[kb._btn("⬅️ Back", "menu:admin")]]))]
    text = (
        f"🗂 <b>{cat['emoji']} {esc(cat['name'])}</b>  (id: {cat['id']})\n\n"
        "🗑 ဖျက်ချင်ရင် အောက်က ခလုပ်ပါ။"
    )
    return [Part(text=text, keyboard=kb.simple([[kb._btn("🗑 Category ဖျက်မယ်", f"adm:cat:del:{cat_id}")], [kb._btn("⬅️ Back", "adm:cat:list")]]))]