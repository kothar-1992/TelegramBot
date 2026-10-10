"""Inline-keyboard builders.  Every screen keeps a ⬅️ Back and 🏠 Main Menu row."""

from __future__ import annotations

import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config import settings

MAIN = "menu:main"
BACK = "nav:back"


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def grid(buttons: list[InlineKeyboardButton], per_row: int = 2) -> list[list[InlineKeyboardButton]]:
    rows = [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]
    return rows


def menu_reply_keyboard() -> ReplyKeyboardMarkup:
    """The persistent 🏠 Menu button under the message input (as in the mockup)."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 Menu")]],
        resize_keyboard=True,
        input_field_placeholder="Write a message...",
    )


def home_row() -> list[InlineKeyboardButton]:
    return [_btn("🏠 Main Menu", MAIN)]


def nav_row(extra: list[InlineKeyboardButton] | None = None, back: bool = True) -> list[list[InlineKeyboardButton]]:
    """Build the standard ⬅️ Back / 🏠 Main Menu block (plus optional extras)."""
    rows: list[list[InlineKeyboardButton]] = []
    if extra:
        rows.append(list(extra))
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(_btn("⬅️ Back", BACK))
    row.append(_btn("🏠 Main Menu", MAIN))
    rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# screens
# --------------------------------------------------------------------------- #
def main_menu(username: str = "", is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn("🛍 ထုတ်ကုန်များ", "menu:catalog"),
            _btn("💰 သိန်းငွေ", "menu:balance"),
        ],
        [
            _btn("🧾 အော်ဒါမှုမှတ်တမ်း", "menu:orders"),
            _btn("💬 Live Chat", "menu:support"),
        ],
        [_btn("📖 အကြံပြုချက်", "menu:help")],
    ]
    if is_admin:
        rows.append([_btn("🛠 Admin Panel", "menu:admin")])
    return InlineKeyboardMarkup(rows)


def categories(cats: list[sqlite3.Row], page: int = 0, pages: int = 1) -> InlineKeyboardMarkup:
    rows = [_btn(f"{c['emoji']} {c['name']}  ({c['item_count']})", f"cat:{c['id']}:0") for c in cats]
    rows = grid(rows, per_row=2)

    pager: list[InlineKeyboardButton] = []
    pager.append(_btn("◀️", f"menu:catalog:{page - 1}" if page > 0 else f"menu:catalog:{max(page - 1, 0)}"))
    pager.append(_btn(f"📄 {page + 1}/{max(pages, 1)}", f"menu:catalog:{page}"))
    pager.append(
        _btn("နောက်သို့ ▶️", f"menu:catalog:{page + 1}" if page + 1 < pages else f"menu:catalog:{page}")
    )
    rows.append(pager)
    rows += nav_row()
    return InlineKeyboardMarkup(rows)


def product_card(product: sqlite3.Row) -> InlineKeyboardMarkup:
    """Keyboard attached to a single product photo card."""
    if int(product["price"]) <= 0:
        return InlineKeyboardMarkup(
            [[_btn("📞 စျေးနှင့်မေးမြန်းမည်", f"ask:{product['id']}")]]
        )
    return InlineKeyboardMarkup([[_btn("🛒 ဝယ်မည်", f"prod:{product['id']}")]])


def product_list_controls(cat_id: int, page: int, pages: int) -> list[list[InlineKeyboardButton]]:
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(_btn("◀️ ရှေ့သို့", f"plist:{cat_id}:{page - 1}"))
    row.append(_btn(f"📄 {page + 1}/{max(pages, 1)}", f"plist:{cat_id}:{page}"))
    if page + 1 < pages:
        row.append(_btn("နောက်သို့ ▶️", f"plist:{cat_id}:{page + 1}"))
    return grid(row, per_row=3)


def product_detail(product: sqlite3.Row) -> InlineKeyboardMarkup:
    action = (
        _btn("🛒 သို့မဟုတ် ဝယ်မည်", f"qty:{product['id']}:1")
        if int(product["price"]) > 0
        else _btn("📞 စျေးနှင့်မေးမြန်းမည်", f"ask:{product['id']}")
    )
    return InlineKeyboardMarkup(nav_row(extra=[action]))


def _price(amount: int) -> str:
    """`0` means price-on-request — never advertise a free product."""
    return f"{int(amount):,} {settings.currency}" if int(amount) > 0 else "စျေးနှင့်မသတ်မှတ်"


def qty_selector(product, qty: int, total: int, user_id: int) -> InlineKeyboardMarkup:
    """The −/N/+ stepper plus Buy Now, Tutorial, Top-up and Share rows."""
    pid = product["id"]
    rows = [
        [
            _btn("➖", f"qadj:{pid}:{qty}:-1"),
            _btn(f"🔢 {qty}", f"qty:{pid}:{qty}"),
            _btn("➕", f"qadj:{pid}:{qty}:1"),
        ],
        [_btn(f"🚚 ဝယ်မည် · {_price(total)}", f"confirm:{pid}:{qty}")],
    ]

    extras: list[InlineKeyboardButton] = []
    if product["tutorial_url"]:
        extras.append(_btn("📂 Tutorial", f"tut:{pid}"))
    extras.append(_btn("💰 သိန်းငွေဖြည့်မည်", "menu:topup"))
    rows.append(extras)
    rows.append([InlineKeyboardButton("🔗 Share", url=share_link(pid, product["name"]))])
    rows.append([_btn("⬅️ Back", f"prod:{pid}"), _btn("🏠 Main Menu", MAIN)])
    return InlineKeyboardMarkup(rows)


def share_link(product_id: int, name: str) -> str:
    """Opens Telegram's share sheet so customers can forward the product."""
    import urllib.parse

    text = urllib.parse.quote(f"🛍 {name}")
    return f"https://t.me/share/url?url={urllib.parse.quote(f'https://t.me/share?text={text}')}&text={text}"


def confirm_order(product, qty: int, total: int, short: int) -> InlineKeyboardMarkup:
    pid = product["id"]
    rows: list[list[InlineKeyboardButton]] = []
    if short > 0:
        rows.append([_btn(f"💳 သိန်းငွေဖြည့်မည် · {_price(short)}", f"topup:{short}")])
    rows.append([_btn("✅ အတည်ပြုဝယ်မည်", f"order:yes:{pid}:{qty}")])
    rows.append([_btn("⬅️ Back", f"qty:{pid}:{qty}")])
    return InlineKeyboardMarkup(rows)


def pay_methods(methods, amount: int) -> InlineKeyboardMarkup:
    rows = grid(
        [_btn(f"{m['emoji']} {m['name']}", f"pay:{m['id']}:{amount}") for m in methods],
        per_row=2,
    )
    rows.append([_btn("🏠 Back", "menu:main"), _btn("🚫 ပယ်ဖျက်", MAIN)])
    return InlineKeyboardMarkup(rows)


def pay_details(method, amount: int, user_id: int, code: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("📋 နံပါတ်ကိုကူးယူ", callback_data=f"copy:no:{method['account_number']}"),
            InlineKeyboardButton("📋 အမည်ကိုကူးယူ", callback_data=f"copy:name:{method['account_name']}"),
        ],
        [_btn("🔢 အမှတ်အသားကိုကူးယူ", f"copy:ref:{code}")],
        [_btn("🚫 ပယ်ဖျက်", f"pay:{method['id']}:{amount}")],
        [_btn("🏠 Main Menu", MAIN)],
    ]
    return InlineKeyboardMarkup(rows)



def simple(buttons: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(buttons)


def admin_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_btn("➕ Category ထည့်မယ်", "adm:cat:new")],
            [_btn("🗂 Category စာရင်း", "adm:cat:list")],
            [_btn("🛍 ထုတ်ကုန်စာရင်း", "adm:prod:list")],
            [_btn("📥 အော်ဒါမှုများ", "adm:orders")],
            [_btn("👥 အသုံးပြုသူများ", "adm:users")],
            [_btn("🖼 Welcome Banner", "adm:banner")],
            [_btn("📊 အချက်အလက်များ", "adm:stats")],
            [_btn("🏠 Main Menu", MAIN)],
        ]
    )


def admin_product_list(products: list[sqlite3.Row], page: int, pages: int) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{'🟢' if p['is_active'] else '🔴'} {p['name'][:28]} — {p['price']:,}", f"adm:prod:{p['id']}")]
        for p in products
    ]
    pager = []
    if page > 0:
        pager.append(_btn("◀️", f"adm:prod:page:{page - 1}"))
    pager.append(_btn(f"{page + 1}/{max(pages, 1)}", "adm:prod:list"))
    if page + 1 < pages:
        pager.append(_btn("▶️", f"adm:prod:page:{page + 1}"))
    rows.append(pager)
    rows.append([_btn("⬅️ Back", "menu:admin"), _btn("🏠 Main Menu", MAIN)])
    return InlineKeyboardMarkup(rows)


def admin_category_list(cats: list[sqlite3.Row]) -> InlineKeyboardMarkup:
    rows = [[_btn(f"{c['emoji']} {c['name']} (id: {c['id']}) — {c['item_count']} items", f"adm:cat:{c['id']}")] for c in cats]
    rows.append([_btn("⬅️ Back", "menu:admin"), _btn("🏠 Main Menu", MAIN)])
    return InlineKeyboardMarkup(rows)