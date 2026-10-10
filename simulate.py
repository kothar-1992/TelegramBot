"""End-to-end simulation of a shopping session with a fake Telegram bot.

No network access — messages are recorded in memory so the whole navigation
flow (start → catalogue → product → order → back) can be asserted.

    python simulate.py
"""

from __future__ import annotations

import asyncio
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from telegram.error import BadRequest

import bot as bot_module
import db
import handlers_user
import lang
import views
from config import settings

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        FAILURES.append(label)


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #
class FakeUser:
    def __init__(self, uid: int, username: str = "tester", full_name: str = "Sim User") -> None:
        self.id = uid
        self.username = username
        self.full_name = full_name


class SentMessage:
    def __init__(self, chat_id: int, message_id: int, text=None, photo=None) -> None:
        self.chat_id = chat_id
        self.message_id = message_id
        self.text = text
        self.caption = None
        self.photo = photo
        self.reply_markup = None
        self.deleted = False


class FakeBot:
    def __init__(self, owner: int = 0) -> None:
        self.messages: dict[int, SentMessage] = {}
        self._next = 1000
        self.deleted: list[int] = []
        self.ignored: set[int] = set()  # persistent chrome (reply-keyboard helper)
        self.owner = owner

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None, **kw) -> SentMessage:
        self._next += 1
        msg = SentMessage(chat_id, self._next, text=text)
        msg.reply_markup = reply_markup
        self.messages[msg.message_id] = msg
        return msg

    async def send_photo(self, chat_id, photo, caption=None, reply_markup=None, parse_mode=None, **kw) -> SentMessage:
        self._next += 1
        msg = SentMessage(chat_id, self._next, photo=photo)
        msg.caption = caption
        msg.reply_markup = reply_markup
        self.messages[msg.message_id] = msg
        return msg

    async def delete_message(self, chat_id=None, message_id=None, **kw) -> bool:
        self.deleted.append(message_id)
        if message_id in self.messages:
            self.messages[message_id].deleted = True
        return True

    def visible(self) -> list[SentMessage]:
        """Messages currently shown to the simulated customer."""
        return [
            m
            for m in self.messages.values()
            if not m.deleted
            and m.message_id not in self.ignored
            and m.chat_id == self.owner
        ]

    def everything(self) -> list[SentMessage]:
        return [m for m in self.messages.values() if not m.deleted]


class FakeMessage:
    def __init__(self, fake: FakeBot, user: FakeUser, text: str = "") -> None:
        self._fake = fake
        self.chat_id = user.id
        self.text = text
        self.message_id = 1
        self.photo = None

    async def reply_text(self, text, reply_markup=None, parse_mode=None, **kw) -> SentMessage:
        return await self._fake.send_message(self.chat_id, text, reply_markup, parse_mode)

    async def delete(self) -> bool:
        return await self._fake.delete_message(self.chat_id, self.message_id)


class FakeCallbackQuery:
    def __init__(self, fake: FakeBot, user: FakeUser, data: str, target: SentMessage) -> None:
        self._fake = fake
        self.message = target
        self.from_user = user
        self.data = data
        self.answered = 0
        self.answer_text = None

    async def answer(self, text=None, show_alert=False, **kw) -> None:
        self.answered += 1
        self.answer_text = text

    def _target(self):
        return self._fake.messages.get(self.message.message_id)

    async def edit_message_text(self, text=None, reply_markup=None, parse_mode=None, **kw) -> SentMessage:
        target = self._target()
        if target is None or target.deleted:
            raise BadRequest("Message to edit not found")
        if target.caption is not None:
            raise BadRequest("There is no text in the message")
        target.text = text
        target.reply_markup = reply_markup
        return target

    async def edit_message_caption(self, caption=None, reply_markup=None, parse_mode=None, **kw) -> SentMessage:
        target = self._target()
        if target is None or target.deleted:
            raise BadRequest("Message to edit not found")
        if target.caption is None:
            raise BadRequest("There is no caption in the message")
        target.caption = caption
        target.reply_markup = reply_markup
        return target


class FakeContext:
    def __init__(self, fake: FakeBot) -> None:
        self.bot = fake
        self.bot_data: dict = {}


class FakeUpdate:
    def __init__(self, user: FakeUser, message=None, callback_query=None) -> None:
        self.effective_user = user
        self.effective_message = message
        self.callback_query = callback_query

    @property
    def message(self):
        return self.effective_message


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def labels(messages: list[SentMessage]) -> list[str]:
    out = []
    for m in messages:
        body = m.caption if m.caption is not None else m.text
        out.append((body or "").strip().splitlines()[0][:36])
    return out


def body(message) -> str:
    """Photo messages carry their text as a caption."""
    return (message.caption if message.caption is not None else message.text) or ""


def buttons(messages: list[SentMessage]) -> list[str]:
    out: list[str] = []
    for m in messages:
        markup = m.reply_markup
        if markup is None or not hasattr(markup, "inline_keyboard"):
            continue
        for row in markup.inline_keyboard:
            out.extend(b.callback_data for b in row)
    return out


def captions(messages: list[SentMessage]) -> list[str]:
    """The visible text on every button — Telegram renders these verbatim."""
    return [
        b.text
        for m in messages
        for row in (m.reply_markup.inline_keyboard if getattr(m.reply_markup, "inline_keyboard", None) else [])
        for b in row
    ]


def trail_len(user_id: int) -> int:
    row = db._one("SELECT trail FROM sessions WHERE user_id = ?", (user_id,))
    return len(__import__("json").loads(row["trail"]))


# --------------------------------------------------------------------------- #
# scenario
# --------------------------------------------------------------------------- #
async def main() -> int:
    tmp = Path(__file__).resolve().parent / "_sim.db"
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(tmp) + suffix)
        if p.exists():
            p.unlink()
    db.init(tmp)

    fake = FakeBot()
    context = FakeContext(fake)
    user = FakeUser(424_242, "sim_user", "Sim User")
    fake.owner = user.id
    handlers_user.settings = dataclasses.replace(settings, admin_ids=(999,))
    bot_module.is_admin = lambda uid: uid == 999

    cat = db.add_category("USDT", "💰")
    product_id = db.add_product("USDT TRC20", 65_000, category_id=cat, description="Fast", photo_id="PHOTO_ID_1")
    second_id = db.add_product("USDT BEP20", 64_000, category_id=cat, photo_id="PHOTO_ID_2")
    db.change_balance(user.id, 200_000)
    db.set_language(user.id, "en")
    db.set_language(999, "en")

    async def tap(data: str, actor: FakeUser | None = None) -> FakeCallbackQuery:
        who = actor or user
        query = FakeCallbackQuery(fake, who, data, fake.visible()[-1])
        await bot_module.on_callback(FakeUpdate(who, callback_query=query), context)
        check(query.answered >= 1, f"tap '{data}': query answered")
        return query

    print("1) /start")
    db.set_setting("banner_photo", "WELCOME_CARD_FILE_ID")
    start_msg = FakeMessage(fake, user, "/start")
    await handlers_user.cmd_start(FakeUpdate(user, message=start_msg), context)
    vis = fake.visible()
    check(len(vis) == 2, f"only welcome card + balance, no helper message (got {labels(vis)})")
    check(vis[0].photo == "WELCOME_CARD_FILE_ID", "welcome card rendered as a photo")
    check(hasattr(vis[0].reply_markup, "keyboard") and not hasattr(vis[0].reply_markup, "inline_keyboard"),
          "🏠 Menu reply keyboard attached to the welcome card")
    check("menu:catalog" in buttons(vis) and "menu:balance" in buttons(vis), "main menu buttons present")
    check(db.trail(user.id) == [], "trail starts empty")

    print("2) catalogue")
    await tap("menu:catalog")
    vis = fake.visible()
    check(len(vis) == 1, "single message on the catalogue screen")
    check(f"cat:{cat}:0" in buttons(vis), "category button present")
    check("nav:back" in buttons(vis) and "menu:main" in buttons(vis), "Back + Main Menu present")

    print("3) category listing")
    await tap(f"cat:{cat}:0")
    vis = fake.visible()
    check(len(vis) == 1, f"one compact list message (got {len(vis)})")
    check(f"prod:{product_id}" in buttons(vis), "the list links to each product")
    check(f"prod:{second_id}" in buttons(vis), "every product on the page is listed")
    check(
        any(c.startswith("\U0001f4b0") and c.endswith("65,000 MMK") for c in captions(vis)),
        "each button carries the category emoji and the price",
    )
    check("nav:back" in buttons(vis), "Back button on the list")

    print("4) product detail")
    await tap(f"prod:{product_id}")
    vis = fake.visible()
    check(f"qty:{product_id}:1" in buttons(vis), "detail offers a Buy button")
    check("nav:back" in buttons(vis) and "menu:main" in buttons(vis), "Back + Main Menu on detail")

    print("5) quantity + order")
    await tap(f"qty:{product_id}:2")
    vis = fake.visible()
    check("130,000 MMK" in body(vis[-1]), "qty screen shows price x qty")

    before = db.get_balance(user.id)
    check(before == 200_000, f"balance before order = {before}")
    q = await tap(f"order:yes:{product_id}:2")
    order = db._one("SELECT * FROM orders ORDER BY id DESC LIMIT 1")
    check(order is not None, f"order row created (answer={q.answer_text!r})")
    check(order["total"] == 130_000, "order total = price x qty")
    check(order["status"] == "pending", "order starts pending")
    check(db.get_balance(user.id) == before - 130_000, "balance debited")
    admin_msgs = [m for m in fake.everything() if m.chat_id == 999 and not m.deleted]
    check(bool(admin_msgs), "admin received the order notification")
    check(any(b.startswith("adm:order:yes") for b in buttons(admin_msgs)), "admin notification has Approve")
    check(any(b.startswith("adm:order:no") for b in buttons(admin_msgs)), "admin notification has Reject")

    print("6) admin approves")
    admin_msg = admin_msgs[-1]
    query = FakeCallbackQuery(fake, FakeUser(999, "boss", "Boss"),
                              f"adm:order:yes:{order['id']}", admin_msg)
    await bot_module.on_callback(FakeUpdate(FakeUser(999, "boss", "Boss"), callback_query=query), context)
    check(db.get_order(order["id"])["status"] == "approved", "order marked approved")
    buyer_msgs = [m for m in fake.visible() if "Order approved" in (m.text or "")]
    check(bool(buyer_msgs), "buyer notified of approval")
    check(any(b == f"usr:deliver:{order['id']}" for b in buttons(buyer_msgs)), "buyer can confirm delivery")

    print("6b) customer confirms delivery")
    dq = FakeCallbackQuery(fake, user, f"usr:deliver:{order['id']}", buyer_msgs[-1])
    await bot_module.on_callback(FakeUpdate(user, callback_query=dq), context)
    check(db.get_order(order["id"])["status"] == "delivered", "order marked delivered")
    check(any(m.chat_id == 999 and "#1" in (m.text or "") for m in fake.everything()), "admin told the customer confirmed")

    print("7) back navigation")
    await tap("menu:catalog")
    await tap(f"cat:{cat}:0")
    vis = fake.visible()
    check(len(vis) == 1, f"category screen is one message (got {len(vis)})")
    await tap("nav:back")
    vis = fake.visible()
    check(len(vis) == 1 and "Categories" in (vis[0].text or ""),
          f"back returns to the catalogue list (got {labels(vis)})")
    await tap("nav:back")
    vis = fake.visible()
    check(len(vis) == 2 and "balance" in (vis[-1].text or "").lower(),
          f"back at the root returns to the main menu (got {labels(vis)})")
    check(db.trail(user.id) == [], "trail reset at the main menu")

    print("8) repeated back presses stay safe")
    for _ in range(6):
        await tap("nav:back")
    check(len(fake.visible()) >= 1, "still renders after repeated back presses")

    print("9) non-admin is locked out")
    stranger = FakeUser(1_000_001, "nobody", "Nobody")
    q = await tap("adm:orders", actor=stranger)
    check(q.answer_text is not None and "Admin" in str(q.answer_text), "refused with an alert")
    check(not any(m.chat_id == stranger.id and "Orders" in (m.text or "") for m in fake.visible()),
          "no admin screen leaked to the stranger")

    print("10) insufficient balance is refused")
    db.change_balance(user.id, -db.get_balance(user.id))
    q = await tap(f"order:yes:{product_id}:1")
    check(db._one("SELECT COUNT(*) AS c FROM orders")["c"] == 1, "no extra order created")
    check("MMK" in str(q.answer_text), "user is told why")

    print("11) empty catalogue still navigable")
    db.init(":memory:")
    parts = views.build("menu:catalog", user.id)
    flat = [b.callback_data for r in parts[0].keyboard.inline_keyboard for b in r]
    check("nav:back" in flat and "menu:main" in flat, "Back + Main Menu on the empty state")

    print("12) the customer's own message is cleaned up")
    fake2 = FakeBot()
    fake2.owner = user.id
    ctx2 = FakeContext(fake2)
    real_is_admin = handlers_user.is_admin

    def as_message(who: FakeUser, message_id: int, text: str) -> FakeMessage:
        msg = FakeMessage(fake2, who, text)
        msg.message_id = message_id
        fake2.messages[message_id] = SentMessage(who.id, message_id, text=text)
        return msg

    typed = as_message(user, 9001, "50000")
    db.set_pending(user.id, {"action": "topup_amount"})
    await handlers_user.on_text(FakeUpdate(user, message=typed), ctx2)
    check(fake2.messages[9001].deleted, "the typed top-up amount is deleted from the chat")
    check(db.get_pending(user.id) == {"action": "topup_receipt", "amount": 50000}, "the amount was still processed")

    stray = as_message(user, 9002, "hello?")
    await handlers_user.on_text(FakeUpdate(user, message=stray), ctx2)
    check(fake2.messages[9002].deleted, "ordinary chat messages are deleted too")

    boss = FakeUser(999, "boss", "Boss")
    handlers_user.is_admin = lambda uid: uid == 999  # this module reads its own copy
    boss_msg = as_message(boss, 9003, "/products")
    db.set_pending(boss.id, {"action": "topup_amount"})
    await handlers_user.on_text(FakeUpdate(boss, message=boss_msg), ctx2)
    check(not fake2.messages[9003].deleted, "admin messages stay put as a working console")
    handlers_user.is_admin = real_is_admin

    print("13) switching language re-renders the whole bot")
    db.init(tmp)
    lang.set_lang("en")
    english = "\n".join(p.text for p in views.main(user.id))
    pick = await tap("menu:lang")
    check(any(b.startswith("lang:set:") for b in buttons(fake.visible())), "language picker is offered")
    await tap("lang:set:my")
    check(db.get_language(user.id) == "my", "the choice is remembered in the database")
    burmese = "\n".join(p.text for p in views.main(user.id))
    check(burmese != english, "the main menu is no longer the English copy")
    check("လက်ကောင်း" in burmese, "the Burmese balance line is shown")
    lang.set_lang("en")
    check(views.main(user.id)[0].text.startswith("👋 Welcome"), "the bot flips back to English too")
    check(pick.answered >= 1, "the picker query was answered")

    print("14) a new customer is asked to choose first")
    newcomer = FakeUser(1_000_002, "newbie", "Newbie")
    start2 = FakeMessage(fake, newcomer, "/start")
    await handlers_user.cmd_start(FakeUpdate(newcomer, message=start2), context)
    check(db.get_language(newcomer.id) is None, "no language is forced on a first-time customer")
    greeted = [m for m in fake.everything() if m.chat_id == newcomer.id and not m.deleted]
    check(any(b.startswith("lang:set:") for b in buttons(greeted)), "the picker greets them")
    await tap("lang:set:en", actor=newcomer)
    check(db.get_language(newcomer.id) == "en", "their pick is stored")

    print()
    if FAILURES:
        print(f"❌ {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ full shopping flow works end to end")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))