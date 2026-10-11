"""Screen builders.

Every callback payload understood by the bot is turned into a list of
`Part` objects here.  A `Part` is one Telegram message: optional photo,
caption text and an inline keyboard.  The router knows how to swap the
currently visible parts for a new set.

All copy comes from `lang.t()` so every screen follows the language chosen by
the customer.
"""

from __future__ import annotations

import html
import time
from dataclasses import dataclass

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup

import db
import keyboards as kb
from config import is_admin, settings
from lang import t


@dataclass
class Part:
    text: str
    photo: str | None = None
    keyboard: InlineKeyboardMarkup | None = None
    #: Telegram allows an inline keyboard *or* a reply keyboard on a message,
    #: never both — `_send_part` sends this one and drops `keyboard` if set.
    reply_keyboard: ReplyKeyboardMarkup | None = None


def money(amount: int) -> str:
    """`0` means "price on request" — never show a free product by accident."""
    return f"{int(amount):,} {settings.currency}" if int(amount) > 0 else t("price_tbd")


def money_balance(amount: int) -> str:
    """Balances and revenue: zero is a real value, never "price on request"."""
    return f"{int(amount):,} {settings.currency}"


def esc(text: str | None) -> str:
    return html.escape(str(text or ""), quote=False)


def _profile(user_id: int) -> tuple[str, str]:
    row = db.get_user(user_id)
    name = (row["full_name"] if row else "") or "—"
    user = (row["username"] if row else "") or "—"
    return esc(name), f"@{esc(user)}"


def _stock(row) -> str:
    return t("product_stock_inf") if row["stock"] < 0 else t("product_stock", stock=row["stock"])


# --------------------------------------------------------------------------- #
# public screens
# --------------------------------------------------------------------------- #
def main(user_id: int) -> list[Part]:
    banner = db.get_setting("banner_photo")
    shop = esc(settings.shop_name)
    welcome = settings.welcome_text.format(shop=shop) if settings.welcome_text else t("welcome", shop=shop)
    balance_line = t("balance_line", balance=money_balance(db.get_balance(user_id)))
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


def language_picker() -> list[Part]:
    """Shown on first `/start`.

    A message can carry an inline keyboard *or* a reply keyboard, never both,
    so the picker stays inline-only; the 🏠 Menu button arrives with the main
    menu the instant a language is chosen.
    """
    return [Part(text=t("lang_pick"), keyboard=kb.language_picker())]


CATEGORIES_PER_PAGE = 8


def catalog(user_id: int, page: int = 0) -> list[Part]:
    all_cats = db.list_categories()
    if not all_cats:
        return [Part(text=t("catalog_empty"), keyboard=kb.simple(kb.nav_row()))]

    pages = max(1, -(-len(all_cats) // CATEGORIES_PER_PAGE))
    page = max(0, min(page, pages - 1))
    cats = all_cats[page * CATEGORIES_PER_PAGE : (page + 1) * CATEGORIES_PER_PAGE]
    return [Part(text=t("catalog_header"), keyboard=kb.categories(cats, page, pages))]


def category_products(cat_id: int, page: int) -> list[Part]:
    """One message for the whole category: a colourful button per product."""
    cat = db.get_category(cat_id)
    if cat is None:
        return [Part(text=t("not_found"), keyboard=kb.simple(kb.nav_row()))]

    per_page = settings.page_size
    total = db.count_products(cat_id)
    pages = max(1, -(-total // per_page))
    page = max(0, min(page, pages - 1))
    rows = db.list_products(cat_id, offset=page * per_page, limit=per_page, buyable_first=True)

    if not rows:
        return [
            Part(
                text=t("cat_empty", emoji=cat["emoji"], name=esc(cat["name"])),
                keyboard=kb.simple(kb.nav_row()),
            )
        ]

    text = t(
        "cat_header",
        emoji=cat["emoji"],
        name=esc(cat["name"]),
        count=total,
        page=page + 1,
        pages=pages,
    )
    return [Part(text=text, keyboard=kb.product_list(rows, cat_id, page, pages, cat["emoji"]))]


def product_detail(product_id: int) -> list[Part]:
    p = db.get_product(product_id)
    if p is None:
        return [Part(text=t("not_found"), keyboard=kb.simple(kb.nav_row()))]

    text = [f"📦 <b>{esc(p['name'])}</b>"]
    if p["cat_name"]:
        text.append(f"{p['cat_emoji']} {esc(p['cat_name'])}")
    text.append(f"💵 {money(p['price'])}")
    if p["warranty"]:
        text.append(t("product_warranty", warranty=esc(p["warranty"])))
    text.append(_stock(p))
    if p["description"]:
        text.append(f"\n{esc(p['description'])}")
    if p["tutorial_url"]:
        text.append(f"\n{t('product_tutorial', url=esc(p['tutorial_url']))}")

    # Name the category on the Back button so leaving a list never feels blind.
    back = (
        [kb._btn(t("back_to_cat", name=esc(p["cat_name"])), f"cat:{p['category_id']}:0")]
        if p["category_id"] is not None and p["cat_name"]
        else None
    )
    part = Part(text="\n".join(text), photo=p["photo_id"])
    part.keyboard = kb.simple(kb.nav_row(extra=back)) if p["stock"] == 0 else kb.product_detail(p, back)
    return [part]


def quantity_screen(product_id: int, qty: int, user_id: int) -> list[Part]:
    p = db.get_product(product_id)
    if p is None:
        return [Part(text=t("not_found"), keyboard=kb.simple(kb.nav_row()))]

    qty = max(1, min(qty, 99))
    total = int(p["price"]) * qty
    text = [
        t("qty_header", name=esc(p["name"])),
        t("qty_unit", price=money(p["price"])),
    ]
    if p["warranty"]:
        text.append(t("product_warranty", warranty=esc(p["warranty"])))
    if p["stock"] >= 0:
        text.append(t("product_stock", stock=p["stock"]))
    text.append(t("qty_selected", qty=qty))
    text.append(t("qty_total", total=money(total)))

    return [Part(text="\n".join(text), photo=p["photo_id"], keyboard=kb.qty_selector(p, qty, total, user_id))]


def confirm_screen(product_id: int, qty: int, user_id: int) -> list[Part]:
    p = db.get_product(product_id)
    if p is None:
        return [Part(text=t("not_found"), keyboard=kb.simple(kb.nav_row()))]

    total = int(p["price"]) * qty
    balance = db.get_balance(user_id)
    short = max(0, total - balance)

    text = [
        t("confirm_title"),
        t("confirm_product", name=esc(p["name"])),
        t("confirm_qty", qty=qty),
        t("confirm_total", total=money(total)),
        "",
        t("confirm_wallet", balance=money_balance(balance)),
    ]
    if short:
        text.append(t("confirm_short", short=money(short)))

    return [Part(text="\n".join(text), keyboard=kb.confirm_order(p, qty, total, short))]


def topup_methods(amount: int) -> list[Part]:
    methods = db.list_payment_methods()
    text = t("methods_title", amount=money(amount)) + "\n" + t("methods_pick")
    if not methods:
        return [Part(text=text + "\n\n" + t("methods_empty"), keyboard=kb.simple(kb.nav_row()))]
    return [Part(text=text, keyboard=kb.pay_methods(methods, amount))]


def pay_details(method_id: int, amount: int, user_id: int) -> list[Part]:
    m = db.get_payment_method(method_id)
    if m is None:
        return [Part(text=t("not_found"), keyboard=kb.simple(kb.nav_row()))]

    code = reference_code(user_id, amount)
    text = [
        t("details_title"),
        t("confirm_total", total=money(amount)),
        "",
        t("details_pay", emoji=m["emoji"], name=esc(m["name"])),
    ]
    if m["account_number"]:
        text.append(t("details_number", number=esc(m["account_number"])))
    if m["account_name"]:
        text.append(t("details_name", name=esc(m["account_name"])))
    if m["note"]:
        text.append("")
        text.append(t("details_note", note=esc(m["note"])))
    text.append("")
    text.append(t("details_receipt"))
    text.append(t("details_ref", code=code))

    return [Part(text="\n".join(text), keyboard=kb.pay_details(m, amount, user_id, code))]


def topup_review(request_id: int, balance: int) -> list[Part]:
    """The message a customer keeps while the admin reviews their receipt."""
    r = db.get_topup(request_id)
    if r is None:
        return [Part(text=t("not_found"), keyboard=kb.simple(kb.nav_row()))]

    extra = f" · <code>{esc(r['reference'])}</code>" if r["reference"] else ""
    text = [
        t("review_title"),
        t("review_ref", id=r["id"], extra=extra),
        t("review_amount", amount=money(r["amount"])),
        t("review_balance", balance=money_balance(balance)),
        t("status", status=t(f"review_{r['status']}", default=r["status"])),
    ]
    if r["status"] == "pending":
        text.append("")
        text.append(t("review_waiting", minutes=settings.review_minutes))
        keyboard = kb.topup_review(r["id"])
    else:
        keyboard = kb.simple(kb.nav_row())

    return [Part(text="\n".join(text), keyboard=keyboard)]


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
        return [Part(text=t("not_found"), keyboard=kb.simple(kb.nav_row()))]

    handle = settings.support_username
    contact = f"@{esc(handle)}" if handle else "Admin"
    text = (
        f"📞 <b>{t('ask_price_title')}</b>\n\n"
        f"🛍 {esc(p['name'])}\n"
        f"💵 {t('price_tbd')}\n\n"
        f"{contact}"
    )
    return [Part(text=text, photo=p["photo_id"], keyboard=kb.simple(kb.nav_row()))]


def balance_screen(user_id: int) -> list[Part]:
    name, handle = _profile(user_id)
    text = "\n".join(
        [
            t("balance_title").rstrip(),
            t("balance_name", name=name),
            t("balance_id", user_id=user_id),
            t("balance_handle", handle=handle),
            t("balance_amount", balance=money_balance(db.get_balance(user_id))),
        ]
    )
    keyboard = [[kb._btn(t("menu_topup"), "menu:topup")]]
    return [Part(text=text, keyboard=kb.simple(keyboard + kb.nav_row()))]


def topup_screen(user_id: int) -> list[Part]:
    _, handle = _profile(user_id)
    text = "\n".join(
        [
            t("topup_title"),
            t("topup_step1"),
            "",
            t("topup_step2"),
            "",
            t("topup_your_id", user_id=user_id, handle=handle),
        ]
    )
    return [Part(text=text, keyboard=kb.simple(kb.nav_row()))]


def orders_screen(user_id: int) -> list[Part]:
    rows = db.user_orders(user_id, limit=10)
    if not rows:
        return [
            Part(
                text=t("orders_empty"),
                keyboard=kb.simple([[kb._btn(t("orders_buy"), "menu:catalog")]] + kb.nav_row()),
            )
        ]

    lines = [t("orders_title")]
    for o in rows:
        lines.append(
            t(
                "orders_item",
                id=o["id"],
                product=esc(o["product_name"] or t("archived")),
                qty=o["qty"],
                total=money(o["total"]),
                status=t(f"status_{o['status']}", default=o["status"]),
            )
        )
    return [Part(text="\n".join(lines), keyboard=kb.simple(kb.nav_row()))]


def support_screen() -> list[Part]:
    handle = settings.support_username
    body = t("support_body", handle=esc(handle)) if handle else t("support_no_body")
    return [Part(text=t("support_title").rstrip("\n") + "\n\n" + body, keyboard=kb.simple(kb.nav_row()))]


def help_screen(user_id: int) -> list[Part]:
    text = "\n".join(
        [t("help_title").rstrip(), t("help_1"), t("help_2"), t("help_3"), t("help_4"), t("help_5"), "", t("lang_hint")]
    )
    return [Part(text=text, keyboard=kb.simple(kb.nav_row()))]


# --------------------------------------------------------------------------- #
# admin screens
# --------------------------------------------------------------------------- #
def admin_panel_screen() -> list[Part]:
    return [Part(text=t("admin_title"), keyboard=kb.admin_panel())]


def admin_stats_screen() -> list[Part]:
    total = db._one("SELECT COUNT(*) AS c FROM products")["c"]
    active = db._one("SELECT COUNT(*) AS c FROM products WHERE is_active = 1")["c"]
    revenue = db._one("SELECT COALESCE(SUM(total), 0) AS s FROM orders WHERE status IN ('approved','delivered')")["s"]
    text = "\n".join(
        [
            t("stats_title").rstrip(),
            t("stats_users", users=db.user_count()),
            t("stats_cats", cats=len(db.list_categories())),
            t("stats_products", active=active, hidden=total - active),
            t("stats_orders", orders=db.order_count()),
            t("stats_revenue", revenue=money_balance(revenue)),
        ]
    )
    return [Part(text=text, keyboard=kb.simple([[kb._btn(t("back"), "menu:admin")]]))]


def admin_orders_screen() -> list[Part]:
    rows = db.pending_orders()
    if not rows:
        return [Part(text=t("admin_pending"), keyboard=kb.simple([[kb._btn(t("back"), "menu:admin")]]))]

    parts: list[Part] = []
    for o in rows:
        handle = f"@{esc(o['username'])}" if o["username"] else "—"
        text = t(
            "admin_pending_item",
            id=o["id"],
            product=esc(o["product_name"] or "—"),
            qty=o["qty"],
            total=money(o["total"]),
            name=esc(o["full_name"] or "—"),
            handle=handle,
            user_id=o["user_id"],
        )
        keyboard = kb.simple(
            [
                [kb._btn(t("admin_yes"), f"adm:order:yes:{o['id']}"), kb._btn(t("admin_no"), f"adm:order:no:{o['id']}")],
                [kb._btn(t("admin_delivered"), f"adm:order:done:{o['id']}")],
            ]
        )
        parts.append(Part(text=text, keyboard=keyboard))
    parts.append(
        Part(
            text=t("admin_pending"),
            keyboard=kb.simple(
                [[kb._btn("🔄", "adm:orders")], [kb._btn(t("back"), "menu:admin")]]
            ),
        )
    )
    return parts


def admin_users_screen() -> list[Part]:
    rows = db.top_users(15)
    if not rows:
        return [Part(text=t("admin_users_title") + "—", keyboard=kb.simple([[kb._btn(t("back"), "menu:admin")]]))]

    lines = [t("admin_users_title")]
    buttons = []
    for u in rows:
        lines.append(f"<code>{u['user_id']}</code> · {esc(u['full_name'] or '—')} · {money_balance(u['balance'])}")
        buttons.append([kb._btn(f"{u['full_name'] or u['user_id']}", f"adm:user:{u['user_id']}")])
    buttons.append([kb._btn(t("back"), "menu:admin")])
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
            "lang": language_picker,
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
            return [Part(text=t("cat_none"), keyboard=kb.simple([[kb._btn(t("back"), "menu:admin")]]))]
        return [Part(text=t("cat_list_title"), keyboard=kb.admin_category_list(cats))]
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
        return [
            Part(
                text=t("prod_none"),
                keyboard=kb.simple([[kb._btn(t("admin_prod_new"), "adm:cat:new")], [kb._btn(t("back"), "menu:admin")]]),
            )
        ]
    return [Part(text=t("prod_list_title"), keyboard=kb.admin_product_list(rows, page, pages))]


def admin_category_screen(cat_id: int) -> list[Part]:
    """The admin's view of one category: its products, plus add and delete."""
    cat = db.get_category(cat_id)
    if cat is None:
        return [Part(text=t("not_found"), keyboard=kb.simple([[kb._btn(t("back"), "menu:admin")]]))]

    rows = db.list_products(cat_id, limit=20, active_only=False)
    active = sum(1 for r in rows if r["is_active"])

    if not rows:
        return [
            Part(
                text=t("adm_cat_empty", emoji=cat["emoji"], name=esc(cat["name"]), id=cat["id"]),
                keyboard=kb.simple(
                    [
                        [kb._btn(t("admin_prod_new"), f"adm:cat:new:{cat_id}")],
                        [kb._btn(t("cat_del_btn"), f"adm:cat:del:{cat_id}")],
                        [kb._btn(t("back"), "adm:cat:list")],
                    ]
                ),
            )
        ]

    keyboard = [[kb._btn(kb.admin_product_label(p), f"adm:prod:{p['id']}")] for p in rows]
    keyboard.append([kb._btn(t("admin_prod_new"), f"adm:cat:new:{cat_id}")])
    keyboard.append([kb._btn(t("cat_del_btn"), f"adm:cat:del:{cat_id}"), kb._btn(t("back"), "adm:cat:list")])
    text = t(
        "adm_cat_header",
        emoji=cat["emoji"],
        name=esc(cat["name"]),
        id=cat["id"],
        total=len(rows),
        active=active,
    )
    return [Part(text=text, keyboard=kb.simple(keyboard))]