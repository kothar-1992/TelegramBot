"""Tests for the top-up review flow and per-screen chat clean-up.

    python selftest_topup.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db
import handlers_admin as admin
import keyboards as kb
import lang
import router
import views
from config import settings

FAILURES: list[str] = []
USER, ADMIN = 4242, 999


def check(condition: bool, label: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        FAILURES.append(label)


class Sent:
    def __init__(self, chat_id, message_id, text, markup=None):
        self.chat_id = chat_id
        self.message_id = message_id
        self.text = text
        self.reply_markup = markup
        self.deleted = False
        self.edits: list[str] = []


class FakeBot:
    def __init__(self) -> None:
        self.messages: dict[int, Sent] = {}
        self._next = 500

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None, **kw):
        self._next += 1
        msg = Sent(chat_id, self._next, text, reply_markup)
        self.messages[msg.message_id] = msg
        return msg

    async def send_photo(self, chat_id, photo, caption=None, reply_markup=None, parse_mode=None, **kw):
        return await self.send_message(chat_id, caption or "", reply_markup)

    async def delete_message(self, chat_id=None, message_id=None, **kw):
        if message_id in self.messages:
            self.messages[message_id].deleted = True
        return True

    async def edit_message_text(self, chat_id=None, message_id=None, text=None, **kw):
        self.messages[message_id].text = text
        self.messages[message_id].edits.append(text)
        return self.messages[message_id]

    def visible(self, chat_id):
        return [m for m in self.messages.values() if not m.deleted and m.chat_id == chat_id]


class FakeQuery:
    def __init__(self, data: str = "") -> None:
        self.data = data
        self.answer_text = None
        self.message = None
        self.edited_text = None

    async def answer(self, text=None, show_alert=False, **kw):
        self.answer_text = text

    async def edit_message_text(self, text=None, reply_markup=None, parse_mode=None, **kw):
        self.edited_text = text
        return None


class FakeContext:
    def __init__(self, fake: FakeBot) -> None:
        self.bot = fake
        self.bot_data: dict = {}


def buttons(markup) -> list[str]:
    return [] if markup is None else [b.callback_data for row in markup.inline_keyboard for b in row]


def update_for(user_id: int, query=None):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="u", full_name="U"),
        effective_message=None,
        message=None,
        callback_query=query,
    )


async def main() -> int:
    db.init(Path(tempfile.mkdtemp()) / "topup.db")
    fake = FakeBot()
    context = FakeContext(fake)
    db.upsert_user(USER, "buyer", "Buyer")
    db.upsert_user(ADMIN, "boss", "Boss")
    # The shop owner works in English; the customer reads Burmese.  Every message
    # below must land in the *right* language for the person receiving it.
    db.set_language(ADMIN, "en")
    db.set_language(USER, "my")

    print("0) the two languages are actually different")
    check(lang.missing_keys() == set(), "every English key has a Burmese counterpart")
    lang.set_lang("my")
    burmese = lang.t("review_waiting", minutes=15)
    lang.set_lang("en")
    check(burmese != lang.t("review_waiting", minutes=15), "the same key renders in both languages")

    print("1) a receipt creates a pending review with buttons")
    request_id = db.create_topup(USER, 50_000, "DEP-261010-ABCDE", "receipts/x.jpg")
    request = db.get_topup(request_id)
    check(request["status"] == "pending", "new request starts pending")
    check(request["reference"] == "DEP-261010-ABCDE", "the payment reference is stored")

    lang.set_lang("my")
    notice_id = await router.notice(
        context, USER, lambda: "\n".join(p.text for p in views.topup_review(request_id, 0)), kb.topup_review(request_id)
    )
    db.set_topup_notice(request_id, notice_id)
    screen = fake.messages[notice_id]
    flat = buttons(screen.reply_markup)
    check(f"tstatus:{request_id}" in flat, "review notice has a status button")
    check(f"tcancel:{request_id}" in flat, "review notice has a cancel button")
    check(f"{settings.review_minutes} မိနစ်ခန့်" in screen.text, "the waiting time is stated")
    check("စောင့်ဆိုင်းငံ့" in screen.text, "the status line says pending")

    print("2) browsing never deletes the review notice")
    cat = db.add_category("ChatGPT", "🤖")
    db.add_product("ChatGPT Plus", 53_000, category_id=cat)
    gemini = db.add_category("Gemini", "✨")
    db.add_product("Gemini Pro", 60_000, category_id=gemini)

    me = update_for(USER)
    for target in ("menu:main", f"cat:{cat}:0", f"cat:{gemini}:0", "menu:catalog"):
        await router.go(me, context, target)
        check(not fake.messages[notice_id].deleted, f"review notice survives '{target}'")
    check(db.get_topup(request_id)["status"] == "pending", "navigating never resolves the request")

    print("3) only the *current screen* is cleared when moving on")
    db.add_product("ChatGPT GO", 45_000, category_id=cat)
    await router.go(me, context, f"cat:{cat}:0")
    chatgpt_ids = [m.message_id for m in fake.visible(USER) if m.message_id != notice_id]
    check(len(chatgpt_ids) == 1, "the ChatGPT list rendered as one message")
    check(
        f"prod:{db.list_products(cat, limit=1)[0]['id']}" in buttons(fake.messages[chatgpt_ids[0]].reply_markup),
        "the list carries a button per product",
    )
    await router.go(me, context, f"cat:{gemini}:0")
    check(
        all(fake.messages[i].deleted for i in chatgpt_ids),
        "every message of the previous ChatGPT screen was cleared",
    )
    check(not fake.messages[notice_id].deleted, "the older review notice was left alone")

    print("4) approval credits the balance and reports the remainder")
    lang.set_lang("en")  # the admin presses the button in their own language
    verdict_query = FakeQuery()
    await admin._topup_action(update_for(ADMIN, verdict_query), context, request_id, True)
    check(db.get_topup(request_id)["status"] == "approved", "request marked approved")
    check(db.get_balance(USER) == 50_000, "balance credited")
    check(
        any("ကျန်ရှိ: 50,000 MMK" in m.text for m in fake.visible(USER)),
        "the customer is told the remaining balance",
    )
    check(
        any(m.edits and "အတည်ပြုပြီး" in m.edits[-1] for m in fake.messages.values()),
        "the pending notice was rewritten in place, not duplicated",
    )

    print("4b) the admin is answered in the admin's own language")
    check(
        "Approved" in str(verdict_query.edited_text),
        "the review verdict reaches the admin in English",
    )
    check(
        "အတည်ပြုပြီး" not in str(verdict_query.edited_text),
        "the admin never sees the customer's Burmese copy",
    )

    print("5) approving twice is refused")
    again = FakeQuery()
    await admin._topup_action(update_for(ADMIN, again), context, request_id, True)
    check("already" in str(again.answer_text).lower(), "a second approval is rejected with an explanation")
    check(db.get_balance(USER) == 50_000, "balance is not credited twice")

    print("6) unattended requests expire automatically")
    expired_id = db.create_topup(USER, 20_000, "DEP-261010-ZZZZZ", "")
    db._exec("UPDATE topup_requests SET created_at = datetime('now', '-99 minutes') WHERE id = ?", (expired_id,))
    check(len(db.stale_topups(15)) == 1, "a 99-minute-old request is stale at a 15-minute window")
    check(len(db.stale_topups(600)) == 0, "the same request is still fresh at a 10-hour window")
    count = await admin._expire_topups(context)
    check(count == 1, "exactly the stale request expired")
    check(db.get_topup(expired_id)["status"] == "expired", "status set to expired")
    check(db.get_balance(USER) == 50_000, "an expired request credits nothing")
    check(
        any("အချိန်ကုန်သွားပါပြီ" in m.text for m in fake.visible(USER)),
        "the customer is told it timed out",
    )
    check(await admin._expire_topups(context) == 0, "running the job again is a no-op")
    lang.reset()

    print()
    if FAILURES:
        print(f"❌ {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ top-up review flow works")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))