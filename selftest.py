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


#: Every coroutine-returning Telegram/httpx method the bot calls.  Calling one
#: of these without `await` produces no error and sends nothing at all.
ASYNC_METHODS = {
    "answer", "delete_message", "download_to_drive", "edit_message_caption", "edit_message_text",
    "edit_text", "get_chat", "get_file", "get_me", "reply_caption", "reply_photo", "reply_text",
    "send_document", "send_message", "send_photo", "set_my_description",
}

#: Only the runtime modules — the test files define these methods themselves.
SCANNED = (
    "backup.py", "bot.py", "config.py", "db.py", "handlers_admin.py", "handlers_user.py",
    "health.py", "keyboards.py", "lang.py", "router.py", "uploads.py", "views.py",
)


def un_awaited_telegram_calls(root: Path | None = None) -> dict[str, list[str]]:
    """Find calls to a Telegram API method whose result is never awaited."""
    import ast

    root = root or Path(__file__).resolve().parent
    problems: dict[str, list[str]] = {}
    for filename in SCANNED:
        path = root / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        awaited = {id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Await)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or id(node) in awaited:
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ASYNC_METHODS:
                problems.setdefault(filename, []).append(f"line {node.lineno}: {func.attr}()")
    return problems


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

    print("2b) every admin screen is titled for what it actually shows")
    # Regression: the categories list was headed "Users" and the product list
    # "Categories", so nobody could tell where they were.
    heads = {
        "adm:users": lang.t("admin_users_title"),
        "adm:cat:list": lang.t("cat_list_title"),
        "adm:prod:list": lang.t("prod_list_title"),
        "adm:stats": lang.t("stats_title"),
    }
    for target, expected in heads.items():
        text = views.build(target, user_id)[0].text
        check(text.startswith(expected.strip()), f"{target} is headed {expected.strip()!r}")
    for target in ("adm:cat:list", "adm:prod:list"):
        text = views.build(target, user_id)[0].text
        wrong = [h for t, h in heads.items() if t != target and h.strip() == text.strip()]
        check(not wrong, f"{target} does not reuse another screen's heading")

    print("2c) a category screen offers a way forward")
    empty_cat = db.add_category("Nothing Here", "🈳")
    flat = [b for row in views.build(f"adm:cat:{empty_cat}", user_id)[0].keyboard.inline_keyboard for b in row]
    datas = [b.callback_data for b in flat]
    check(f"adm:cat:new:{empty_cat}" in datas, "an empty category offers to add its first product")
    check(f"adm:cat:del:{empty_cat}" in datas, "an empty category can still be deleted")
    check("adm:cat:list" in datas, "there is a way back to the category list")
    check(all(r["category_id"] == cat for r in db.list_products(cat, limit=50, active_only=False)),
          "the filled category lists only its own products")
    db.delete_category(empty_cat)

    print("2d) no coroutine is ever created and thrown away")
    # Regression: `_prompt_category` called `message.reply_text(...)` without
    # awaiting, so the "New category" button did nothing at all.  A silent
    # no-op is exactly what a mistyped await looks like from the outside.
    leaked = un_awaited_telegram_calls()
    for name, spots in leaked.items():
        for spot in spots:
            check(False, f"{name}: {spot} is never awaited")
    check(not leaked, f"every Telegram API call is awaited ({len(leaked)} file(s) with problems)")

    print("3) caption parser")
    from handlers_admin import parse_caption, split_emoji

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

    print("3a) /addcat accepts what people actually type")
    for raw, expected in [
        ("\U0001f3ac CapCut", ("\U0001f3ac", "CapCut")),
        ("CapCut", ("\U0001f4e6", "CapCut")),
        ("Top Up", ("\U0001f4e6", "Top Up")),
        ("3D Models", ("\U0001f4e6", "3D Models")),
        ("  \U0001f4b0   USDT  ", ("\U0001f4b0", "USDT")),
    ]:
        check(split_emoji(raw) == expected, f"/addcat {raw.strip()!r} -> {expected[1]!r}")
    check(split_emoji("\U0001f4b0") == ("\U0001f4b0", ""), "a bare emoji asks for the name instead of becoming one")
    check(split_emoji("") == ("\U0001f4e6", ""), "empty input asks for a name")

    print("3b) a category filter is never silently dropped")
    # Regression: `" AND category_id = ?"` appended to an empty base landed on
    # the LEFT JOIN, so `active_only=False` returned the whole catalogue.
    other = db.add_category("Gemini", "✨")
    baseline_live = db.count_products(cat)
    baseline_all = db.count_products(cat, active_only=False)
    db.add_product("Gemini Pro", 60_000, category_id=other)
    hidden_id = db.add_product("Hidden ChatGPT", 1_000, category_id=cat)
    db.set_product_active(hidden_id, False)

    for label, kwargs in (("live", {}), ("all", {"active_only": False})):
        listed = db.list_products(cat, limit=50, **kwargs)
        check(
            all(r["category_id"] == cat for r in listed),
            f"list_products({label}) only returns that category",
        )
        check(
            all(r["name"] != "Gemini Pro" for r in listed),
            f"list_products({label}) excludes the other category",
        )
    check(
        len(db.list_products(cat, limit=50, active_only=False)) == baseline_all + 1,
        "hidden products are included",
    )
    check(len(db.list_products(cat, limit=50)) == baseline_live, "hidden products are excluded by default")
    check(db.count_products(cat, active_only=False) == baseline_all + 1, "count_products matches list_products")
    check(db.count_products(cat) == baseline_live, "count_products honours active_only")
    check(
        db.count_products(active_only=False) == len(db.list_products(None, limit=999, active_only=False)),
        "counting everything matches listing everything",
    )
    db.delete_product(hidden_id)
    db.delete_category(other)

    print("3c) /demo fills the categories the admin already has")
    import json

    from handlers_admin import DEMO_SETTING, _clear_demo, _seed_demo

    demo_cats = [db.add_category(name, "\U0001f4e6") for name in ("ChatGPT", "Gemini", "Claude")]
    for cid in demo_cats:
        check(db.count_products(cid, active_only=False) == 0, f"category {cid} starts empty")

    baseline_products = db.count_products(active_only=False)
    baseline_cats = [c["id"] for c in db.list_categories()]

    new_cats, new_products, note = _seed_demo()
    check(len(new_products) == 13, f"/demo seeds 13 products (got {len(new_products)})")
    check(new_cats == [], f"no duplicate categories are created (got {new_cats})")
    check(all(db.count_products(cid, active_only=False) > 0 for cid in demo_cats), "every category got samples")
    check(
        db.count_products(active_only=False) == baseline_products + 13,
        "nothing beyond the 13 samples was created",
    )
    check("already had" in note, "the reply explains where they went")

    chatgpt_id = demo_cats[0]
    matching = [pid for pid in new_products if db.get_product(pid)["category_id"] == chatgpt_id]
    check(bool(matching), "the category named ChatGPT received samples")
    check(
        all(db.get_product(pid)["name"].startswith("ChatGPT") for pid in matching),
        "products whose group name matches land in that category",
    )

    # The bookkeeping /demo clear relies on.
    db.set_setting(DEMO_SETTING, json.dumps({"categories": new_cats, "products": new_products}))
    check(_clear_demo() == 13, "/demo clear removes every seeded product")
    check(db.count_products(active_only=False) == baseline_products, "the catalogue is back to how it was")
    check([c["id"] for c in db.list_categories()] == baseline_cats, "the admin's own categories survive")
    db.delete_category(demo_cats[1])

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