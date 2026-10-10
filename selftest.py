"""Offline smoke test — renders every screen without touching the network.

    python selftest.py
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
import lang
import views

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        FAILURES.append(label)


def walk(keyboard, label: str) -> None:
    """Buttons must either carry callback data or point at a valid URL."""
    if keyboard is None:
        return
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.url:
                check(button.url.startswith("http"), f"{label}: url button '{button.text}' has a valid URL")
                continue
            data = button.callback_data or ""
            check(bool(data), f"{label}: button '{button.text}' has callback data")
            check(len(data.encode()) <= 64, f"{label}: '{data}' is <=64 bytes ({len(data.encode())})")


def render(label: str, target: str, user_id: int) -> list[views.Part]:
    parts = views.build(target, user_id)
    check(len(parts) > 0, f"{label}: produced at least one part")
    for part in parts:
        check(isinstance(part.text, str) and part.text.strip() != "", f"{label}: part has text")
        walk(part.keyboard, label)
    return parts


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "selftest.db"
    db.init(tmp)

    user_id = 999_000_111
    db.upsert_user(user_id, "selftest", "Self Test")
    cat = db.add_category("USDT", "💰")
    db.add_category("Accounts", "🎟")
    for i in range(1, 8):
        db.add_product(f"Test Product {i}", 1000 * i, category_id=cat, description=f"desc {i}")
    db.change_balance(user_id, 500_000)

    print("1) rendering every screen")
    for target in [
        "menu:main", "menu:catalog", "menu:balance", "menu:orders",
        "menu:support", "menu:help", "menu:topup",
        f"cat:{cat}:0", f"plist:{cat}:1",
        "prod:1", "qty:1:3",
    ]:
        render(target, target, user_id)

    print("2) admin screens")
    for target in ["menu:admin", "adm:stats", "adm:orders", "adm:users", "adm:prod:list", "adm:cat:list", f"adm:cat:{cat}"]:
        render(target, target, user_id)

    print("3) caption parser")
    from handlers_admin import parse_caption

    parsed = parse_caption("USDT TRC20 | 65,000 | USDT\nFast delivery.\n24/7 support")
    check(parsed is not None, "parser: valid caption accepted")
    if parsed:
        name, price, category_id, description, stock = parsed
        check(name == "USDT TRC20", "parser: name")
        check(price == 65000, "parser: price strips commas")
        check(category_id == cat, "parser: category resolved by name")
        check(description.startswith("Fast delivery."), "parser: description captured")
        check(stock == -1, "parser: stock defaults to unlimited")
    limited = parse_caption("Limited Item | 500 | 1 | 7")
    check(limited is not None and limited[4] == 7, "parser: optional stock field")
    check(parse_caption("name | abc") is None, "parser: rejects non-numeric price")
    check(parse_caption("name | 100 | 1 | many") is None, "parser: rejects non-numeric stock")

    print("4) navigation trail")
    db.push_trail(user_id, "menu:catalog")
    db.push_trail(user_id, f"cat:{cat}:0")
    check(db.pop_trail(user_id) == f"cat:{cat}:0", "trail: pops last entry")
    check(db.pop_trail(user_id) == "menu:catalog", "trail: pops previous entry")
    check(db.pop_trail(user_id) is None, "trail: empty when exhausted")

    print("4b) session setters work on a brand-new user")
    fresh = 555_000_111  # never seen by this process
    db.set_pending(fresh, {"action": "topup_amount"})
    check(db.get_pending(fresh) == {"action": "topup_amount"}, "set_pending creates the session row")
    db.set_trail(fresh, ["menu:main"])
    check(db.trail(fresh) == ["menu:main"], "set_trail creates the session row")
    db.set_msgs(fresh, [1, 2, 3])
    check(db.get_msgs(fresh) == [1, 2, 3], "set_msgs creates the session row")
    db.set_pending(fresh, None)
    check(db.get_pending(fresh) is None, "set_pending(None) clears the state")
    db.change_balance(fresh, 500)
    check(db.get_balance(fresh) == 500, "change_balance creates the user row")
    db.change_balance(fresh, -500)
    check(db.get_balance(fresh) == 0, "balance returns to zero")

    print("5) balance + stock maths")
    before = db.get_balance(user_id)
    total = 1000 * 3
    db.change_balance(user_id, -total)
    check(db.get_balance(user_id) == before - total, "balance: debit applied")
    db.decrease_stock(1, 3)
    check(db.get_product(1)["stock"] == -1, "stock: unlimited (-1) stays unlimited")
    limited = db.add_product("Limited", 500, category_id=cat, stock=10)
    db.decrease_stock(limited, 4)
    check(db.get_product(limited)["stock"] == 6, "stock: limited stock decrements")

    print("6) order lifecycle")
    order_id = db.create_order(user_id, 1, 2, 2000)
    check(db.get_order(order_id)["status"] == "pending", "order: starts pending")
    db.set_order_status(order_id, "approved")
    check(db.get_order(order_id)["status"] == "approved", "order: status updates")

    print("7) settings")
    db.set_setting("banner_photo", "FAKE_FILE_ID")
    parts = views.build("menu:main", user_id)
    check(len(parts) == 2 and parts[0].photo == "FAKE_FILE_ID", "banner: main menu shows welcome photo")
    check(parts[0].reply_keyboard is not None, "banner: 🏠 Menu reply keyboard rides on the welcome card")
    check(parts[1].keyboard is not None, "banner: inline main menu stays on the balance message")
    check(parts[0].keyboard is None, "banner: no inline buttons mixed with the reply keyboard")
    db.set_setting("banner_photo", None)
    parts = views.build("menu:main", user_id)
    check(len(parts) == 1, "banner: falls back to a single message")
    check(parts[0].reply_keyboard is None, "banner: no reply keyboard without a banner card")

    print("8) unknown payload is safe")
    parts = views.build("garbage:data", user_id)
    check(len(parts) >= 1, "router: unknown payload falls back to main menu")

    print("9) empty catalogue")
    empty = Path(tempfile.mkdtemp()) / "empty.db"
    db.init(empty)
    for code in lang.available():
        lang.set_lang(code)
        parts = views.build("menu:catalog", user_id)
        check(
            "no products yet" in parts[0].text.lower() or "မရှိသေး" in parts[0].text,
            f"catalogue: empty state message ({code})",
        )
    lang.reset()

    print()
    if FAILURES:
        print(f"❌ {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())