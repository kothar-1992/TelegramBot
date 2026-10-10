"""Inline-keyboard builders.  Every screen keeps a ⬅️ Back and 🏠 Main Menu row."""

from __future__ import annotations

import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

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


def categories(cats: list[sqlite3.Row]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{c['emoji']} {c['name']}  ({c['item_count']})", f"cat:{c['id']}:0")]
        for c in cats
    ]
    rows += nav_row()
    return InlineKeyboardMarkup(rows)


def product_card(product: sqlite3.Row) -> InlineKeyboardMarkup:
    """Keyboard attached to a single product photo card."""
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
    return InlineKeyboardMarkup(
        nav_row(extra=[_btn("🛒 သို့မဟုတ် ဝယ်မည်", f"qty:{product['id']}:1")])
    )


def qty_selector(product: sqlite3.Row, options: tuple[int, ...] = (1, 2, 3, 5, 10)) -> InlineKeyboardMarkup:
    rows = [_btn(f"x{n}", f"qty:{product['id']}:{n}") for n in options]
    return InlineKeyboardMarkup(
        grid(rows, per_row=len(options)) + nav_row(extra=[_btn("🔙 ပြန်သွားမယ်", f"prod:{product['id']}")])
    )


def confirm_order(product: sqlite3.Row, qty: int, total: int) -> InlineKeyboardMarkup:
    data = f"{product['id']}:{qty}"
    return InlineKeyboardMarkup(
        [
            [_btn("✅ အတည်ပြုဝယ်မည်", f"order:yes:{data}")],
            [_btn("💸 သိန်းငွေဖြည့်မယ်", "menu:topup")],
            [_btn("⬅️ Back", f"prod:{product['id']}"), _btn("🏠 Main Menu", MAIN)],
        ]
    )


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