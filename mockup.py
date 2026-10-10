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


def render(label: str, target: str, user_id: int) -> None:
    print(f"\n{'─' * 60}\n▶ {label}   ({target})\n{'─' * 60}")
    for part in views.build(target, user_id):
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


def main() -> int:
    db.init(Path(tempfile.mkdtemp()) / "mockup.db")
    user_id = 528_013_8602
    db.upsert_user(user_id, "kothar1992", "Shop Owner")
    db.change_balance(user_id, 500_000)

    cats, products = admin._seed_demo()
    print(f"seeded {len(cats)} categories and {len(products)} products")

    for code in lang.available():
        lang.set_lang(code)
        print(f"\n\n{'=' * 62}\n  LANGUAGE: {code}  ({lang.native_name(code)})\n{'=' * 62}")
        _render_all(user_id, cats)
    lang.reset()
    print()
    return 0


def _render_all(user_id: int, cats) -> None:
    render("Main menu", "menu:main", user_id)
    render("Balance", "menu:balance", user_id)
    render("Category list", "menu:catalog", user_id)

    first = cats[1]  # ChatGPT — three items, shows the card layout
    render("Product list", f"cat:{first}:0", user_id)
    priced = db._one("SELECT id FROM products WHERE price > 0 AND stock > 0 AND warranty IS NOT NULL LIMIT 1")
    pid = int(priced["id"]) if priced else db.list_products(first, limit=1)[0]["id"]
    render("Product detail", f"prod:{pid}", user_id)
    render("Quantity stepper", f"qty:{pid}:2", user_id)
    render("Confirm order (wallet short)", f"confirm:{pid}:2", user_id)
    render("Payment methods", "topup:53000", user_id)
    render("Payment details", "pay:1:53000", user_id)

    sold_out = db._one("SELECT id FROM products WHERE stock = 0 LIMIT 1")
    if sold_out:
        render("Sold-out product", f"prod:{sold_out['id']}", user_id)

    tbd = db._one("SELECT id FROM products WHERE price = 0 LIMIT 1")
    if tbd:
        render("Price on request", f"ask:{tbd['id']}", user_id)

    render("Admin panel", "menu:admin", user_id)
    render("Help", "menu:help", user_id)
    render("Language picker", "menu:lang", user_id)


if __name__ == "__main__":
    raise SystemExit(main())