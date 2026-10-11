"""Renders the populated catalogue exactly as Telegram would show it.

    python mockup.py

Prints every screen the shop produces once the demo catalogue is seeded, so
the layout can be reviewed without touching the running bot.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db
import handlers_admin as admin
import lang
import views

CUSTOMER_ID = 424_242


def _show(label: str, parts) -> None:
    print(f"\n{'─' * 60}\n▶ {label}\n{'─' * 60}")
    for part in parts:
        print("\n" + "_" * 54)
        print(f"| {part.text}")
        print("|" + " " * 53 + "|")
        if part.photo:
            print(f"| 📷 photo: {part.photo}")
            print("|" + " " * 53 + "|")
        if part.keyboard:
            for row in part.keyboard.inline_keyboard:
                print("| " + "   ".join(f"[{b.text}]" for b in row))
                print("|" + " " * 53 + "|")
        if part.reply_keyboard:
            labels = [b.text for r in part.reply_keyboard.keyboard for b in r]
            print(f"| ⌨️  {labels}")
            print("|" + " " * 53 + "|")
    print()


def render(label: str, target: str, user_id: int) -> None:
    _show(f"{label}   ({target})", views.build(target, user_id))


def _seed_orders_and_topup(customer_id: int, product_ids: list[int]) -> int:
    """Seed one pending order, one delivered order and a pending top-up so
    those screens show data instead of their empty states. Returns the id of
    the pending top-up request (0 when nothing could be seeded)."""
    if not product_ids:
        return 0
    priced = db.get_product(product_ids[0])
    if priced is None or not priced["price"]:
        return 0

    total = int(priced["price"])
    db.create_order(customer_id, priced["id"], 1, total, "mockup pending order")
    delivered = db.create_order(customer_id, priced["id"], 2, total * 2, "mockup delivered order")
    db.set_order_status(delivered, "delivered")

    amount = 53_000
    code = views.reference_code(customer_id, amount)
    return db.create_topup(customer_id, amount, reference=code, photo_path="mockup_receipt.png")


def main() -> int:
    db.init(Path(tempfile.mkdtemp()) / "mockup.db")
    user_id = 528_013_8602
    db.upsert_user(user_id, "kothar1992", "Shop Owner")
    db.upsert_user(CUSTOMER_ID, "sim_user", "Sim User")
    db.change_balance(user_id, 500_000)

    cats, products, note = admin._seed_demo()
    print(f"seeded {len(cats)} categories and {len(products)} products ({note})")

    topup_request_id = _seed_orders_and_topup(CUSTOMER_ID, products)

    for code in lang.available():
        lang.set_lang(code)
        print(f"\n\n{'=' * 62}\n  LANGUAGE: {code}  ({lang.native_name(code)})\n{'=' * 62}")
        _render_all(user_id, cats, topup_request_id)
    lang.reset()
    print()
    return 0


def _render_all(user_id: int, cats, topup_request_id: int) -> None:
    render("Main menu", "menu:main", user_id)
    render("Balance", "menu:balance", user_id)
    render("Category list", "menu:catalog", user_id)
    render("Top-up guide", "menu:topup", user_id)
    render("My orders", "menu:orders", CUSTOMER_ID)
    render("Support", "menu:support", user_id)

    if cats:
        first = cats[1] if len(cats) > 1 else cats[0]
        render("Product list", f"cat:{first}:0", user_id)
        priced = db._one(
            "SELECT id FROM products WHERE price > 0 AND stock > 0 AND warranty IS NOT NULL LIMIT 1"
        )
        pid = int(priced["id"]) if priced else db.list_products(first, limit=1)[0]["id"]
        render("Product detail", f"prod:{pid}", user_id)
        render("Quantity stepper", f"qty:{pid}:2", user_id)

        balance = db.get_balance(user_id)
        affordable = db._one(
            "SELECT id FROM products WHERE price > 0 AND price <= ? AND stock <> 0 ORDER BY price LIMIT 1",
            (balance,),
        )
        if affordable:
            render("Confirm order (wallet ok)", f"confirm:{affordable['id']}:1", user_id)
        render("Confirm order (wallet short)", f"confirm:{pid}:2", user_id)

        render("Payment methods", "topup:53000", user_id)
        render("Payment details", "pay:1:53000", user_id)
        render("Admin category detail", f"adm:cat:{first}", user_id)

    if topup_request_id:
        _show(
            "Top-up under review",
            views.topup_review(topup_request_id, db.get_balance(CUSTOMER_ID)),
        )

    sold_out = db._one("SELECT id FROM products WHERE stock = 0 LIMIT 1")
    if sold_out:
        render("Sold-out product", f"prod:{sold_out['id']}", user_id)

    tbd = db._one("SELECT id FROM products WHERE price = 0 LIMIT 1")
    if tbd:
        render("Price on request", f"ask:{tbd['id']}", user_id)

    render("Admin panel", "menu:admin", user_id)
    render("Admin stats", "adm:stats", user_id)
    render("Admin orders (pending)", "adm:orders", user_id)
    render("Admin users", "adm:users", user_id)
    render("Admin product list", "adm:prod:list", user_id)
    render("Admin category list", "adm:cat:list", user_id)
    render("Help", "menu:help", user_id)
    render("Language picker", "menu:lang", user_id)


if __name__ == "__main__":
    raise SystemExit(main())
