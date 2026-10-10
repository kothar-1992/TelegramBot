"""Inline-keyboard builders.

Every screen keeps a ⬅️ Back and 🏠 Main Menu row.  All labels come from
`lang.t()` so the keyboards follow the customer's chosen language.
"""

from __future__ import annotations

import sqlite3
import urllib.parse

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import settings
from lang import LANGUAGES, t

MAIN = "menu:main"
BACK = "nav:back"
MENU_LABEL = "🏠 Menu"


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def grid(buttons: list[InlineKeyboardButton], per_row: int = 2) -> list[list[InlineKeyboardButton]]:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


def menu_reply_keyboard() -> ReplyKeyboardMarkup:
    """The persistent 🏠 Menu button under the message input (as in the mockup)."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(MENU_LABEL)]],
        resize_keyboard=True,
        input_field_placeholder="Write a message...",
    )


def language_picker() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_btn(f"{meta['flag']} {meta['native']}", f"lang:set:{code}")]
            for code, meta in LANGUAGES.items()
        ]
    )


def nav_row(extra: list[InlineKeyboardButton] | None = None, back: bool = True) -> list[list[InlineKeyboardButton]]:
    """Build the standard ⬅️ Back / 🏠 Main Menu block (plus optional extras)."""
    rows: list[list[InlineKeyboardButton]] = []
    if extra:
        rows.append(list(extra))
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(_btn(t("back"), BACK))
    row.append(_btn(t("main_menu"), MAIN))
    rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# screens
# --------------------------------------------------------------------------- #
def main_menu(username: str = "", is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [_btn(t("menu_products"), "menu:catalog"), _btn(t("menu_balance"), "menu:balance")],
        [_btn(t("menu_orders"), "menu:orders"), _btn(t("menu_support"), "menu:support")],
        [_btn(t("menu_help"), "menu:help"), _btn(t("menu_language"), "menu:lang")],
    ]
    if is_admin:
        rows.append([_btn(t("menu_admin"), "menu:admin")])
    return InlineKeyboardMarkup(rows)


def categories(cats: list[sqlite3.Row], page: int = 0, pages: int = 1) -> InlineKeyboardMarkup:
    """Two-line category buttons — the emoji carries the colour, the count the size."""
    rows = grid(
        [_btn(f"{c['emoji']} {c['name']}\n" + _items(int(c["item_count"])), f"cat:{c['id']}:0") for c in cats],
        per_row=2,
    )

    clamped = max(0, min(page, pages - 1))
    rows.append(
        [
            _btn(t("prev"), f"menu:catalog:{max(clamped - 1, 0)}"),
            _btn(t("page", page=clamped + 1, pages=max(pages, 1)), f"menu:catalog:{clamped}"),
            _btn(t("next"), f"menu:catalog:{min(clamped + 1, pages - 1)}"),
        ]
    )
    rows += nav_row()
    return InlineKeyboardMarkup(rows)


def _items(count: int) -> str:
    return t("n_items_one") if count == 1 else t("n_items", count=count)


#: Telegram truncates very long button labels, so keep the whole row this wide.
BUTTON_BUDGET = 46


def _clip(name: str, suffix: str) -> str:
    """Trim the product name so `name + suffix` still fits on one button."""
    room = max(12, BUTTON_BUDGET - len(suffix) - 2)
    return name if len(name) <= room else name[: room - 1].rstrip() + "…"


def product_row(product: sqlite3.Row, emoji: str) -> InlineKeyboardButton:
    """`🎬 CapCut Pro 1 Month · 10,000 MMK` — one button per product.

    Telegram buttons are plain text: no HTML, no colours.  The only colour
    available is the emoji glyph itself, so a sold-out item swaps the category
    emoji for a red marker and drops the price, since it cannot be bought.
    """
    name = product["name"].strip()
    if product["stock"] == 0:
        return _btn(f"🔴 {_clip(name, t('sold_out_short'))} · {t('sold_out_short')}", f"prod:{product['id']}")
    price = _price(product["price"]) if int(product["price"]) > 0 else t("price_tbd_short")
    return _btn(f"{emoji or '🛍'} {_clip(name, price)} · {price}", f"prod:{product['id']}")


def product_list(
    products: list[sqlite3.Row], cat_id: int, page: int, pages: int, emoji: str = "🛍"
) -> InlineKeyboardMarkup:
    """The whole category on one message: a button per product, then the pager."""
    rows: list[list[InlineKeyboardButton]] = [[product_row(p, emoji)] for p in products]
    rows += product_list_controls(cat_id, page, pages)
    rows += nav_row()
    return InlineKeyboardMarkup(rows)


def product_list_controls(cat_id: int, page: int, pages: int) -> list[list[InlineKeyboardButton]]:
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(_btn(t("prev"), f"plist:{cat_id}:{page - 1}"))
    row.append(_btn(t("page", page=page + 1, pages=max(pages, 1)), f"plist:{cat_id}:{page}"))
    if page + 1 < pages:
        row.append(_btn(t("next"), f"plist:{cat_id}:{page + 1}"))
    return grid(row, per_row=3)


def product_detail(
    product: sqlite3.Row, back: list[InlineKeyboardButton] | None = None
) -> InlineKeyboardMarkup:
    action = (
        _btn(t("buy_or"), f"qty:{product['id']}:1")
        if int(product["price"]) > 0
        else _btn(t("ask_price"), f"ask:{product['id']}")
    )
    return InlineKeyboardMarkup(nav_row(extra=[action] + back if back else [action]))


def _price(amount: int) -> str:
    """`0` means price-on-request — never advertise a free product."""
    return f"{int(amount):,} {settings.currency}" if int(amount) > 0 else t("price_tbd")


def qty_selector(product, qty: int, total: int, user_id: int) -> InlineKeyboardMarkup:
    """The −/N/+ stepper plus Buy Now, Tutorial, Top-up and Share rows."""
    pid = product["id"]
    rows = [
        [
            _btn("➖", f"qadj:{pid}:{qty}:-1"),
            _btn(t("qty_step", qty=qty), f"qty:{pid}:{qty}"),
            _btn("➕", f"qadj:{pid}:{qty}:1"),
        ],
        [_btn(t("buy_total", total=_price(total)), f"confirm:{pid}:{qty}")],
    ]

    extras: list[InlineKeyboardButton] = []
    if product["tutorial_url"]:
        extras.append(_btn("📂 Tutorial", f"tut:{pid}"))
    extras.append(_btn(t("menu_topup"), "menu:topup"))
    rows.append(extras)
    rows.append([InlineKeyboardButton("🔗 Share", url=share_link(pid, product["name"]))])
    rows.append([_btn(t("back"), f"prod:{pid}"), _btn(t("main_menu"), MAIN)])
    return InlineKeyboardMarkup(rows)


def share_link(product_id: int, name: str) -> str:
    """Opens Telegram's share sheet so customers can forward the product."""
    text = urllib.parse.quote(t("share_msg", name=name))
    inner = urllib.parse.quote(f"https://t.me/share?text={text}")
    return f"https://t.me/share/url?url={inner}&text={text}"


def confirm_order(product, qty: int, total: int, short: int) -> InlineKeyboardMarkup:
    pid = product["id"]
    rows: list[list[InlineKeyboardButton]] = []
    if short > 0:
        rows.append([_btn(t("topup_short", amount=_price(short)), f"topup:{short}")])
    rows.append([_btn(t("confirm_yes"), f"order:yes:{pid}:{qty}")])
    rows.append([_btn(t("back"), f"qty:{pid}:{qty}")])
    return InlineKeyboardMarkup(rows)


def pay_methods(methods, amount: int) -> InlineKeyboardMarkup:
    rows = grid([_btn(f"{m['emoji']} {m['name']}", f"pay:{m['id']}:{amount}") for m in methods], per_row=2)
    rows.append([_btn(t("main_menu"), "menu:main"), _btn(t("cancel"), MAIN)])
    return InlineKeyboardMarkup(rows)


def pay_details(method, amount: int, user_id: int, code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _btn(t("copy_number"), f"copy:no:{method['account_number']}"),
                _btn(t("copy_name"), f"copy:name:{method['account_name']}"),
            ],
            [_btn(t("copy_ref"), f"copy:ref:{code}")],
            [_btn(t("cancel"), f"pay:{method['id']}:{amount}")],
            [_btn(t("main_menu"), MAIN)],
        ]
    )


def topup_review(request_id: int) -> InlineKeyboardMarkup:
    """Buttons on the pending-review notice that survives navigation."""
    return InlineKeyboardMarkup(
        [
            [_btn(t("review_status_btn"), f"tstatus:{request_id}")],
            [_btn(t("review_cancel_btn"), f"tcancel:{request_id}")],
            [_btn(t("main_menu"), MAIN)],
        ]
    )


def admin_topup(request_id: int, user_id: int, amount: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[_btn(t("admin_yes"), f"adm:topup:yes:{request_id}"), _btn(t("admin_no"), f"adm:topup:no:{request_id}")]]
    )


def simple(buttons: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(buttons)


def admin_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_btn(t("admin_cat_new"), "adm:cat:new"), _btn(t("admin_cat_list"), "adm:cat:list")],
            [_btn(t("admin_prod_list"), "adm:prod:list"), _btn(t("admin_orders"), "adm:orders")],
            [_btn(t("admin_users"), "adm:users"), _btn(t("admin_stats"), "adm:stats")],
            [_btn(t("admin_banner"), "adm:banner"), _btn(t("admin_lang"), "adm:lang")],
            [_btn(t("main_menu"), MAIN)],
        ]
    )


def admin_product_list(products: list[sqlite3.Row], page: int, pages: int) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{'🟢' if p['is_active'] else '🔴'} {p['name'][:28]} — {_price(p['price'])}", f"adm:prod:{p['id']}")]
        for p in products
    ]
    clamped = max(0, min(page, pages - 1))
    pager = [_btn(t("prev"), f"adm:prod:page:{max(clamped - 1, 0)}")]
    pager.append(_btn(t("page", page=clamped + 1, pages=max(pages, 1)), "adm:prod:list"))
    pager.append(_btn(t("next"), f"adm:prod:page:{min(clamped + 1, pages - 1)}"))
    rows.append(pager)
    rows.append([_btn(t("back"), "menu:admin"), _btn(t("main_menu"), MAIN)])
    return InlineKeyboardMarkup(rows)


def admin_category_list(cats: list[sqlite3.Row]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{c['emoji']} {c['name']} (id: {c['id']}) — {c['item_count']}", f"adm:cat:{c['id']}")]
        for c in cats
    ]
    rows.append([_btn(t("back"), "menu:admin"), _btn(t("main_menu"), MAIN)])
    return InlineKeyboardMarkup(rows)


def language_options() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[_btn(f"{meta['flag']} {meta['name']}", f"adm:lang:{code}")] for code, meta in LANGUAGES.items()]
    )