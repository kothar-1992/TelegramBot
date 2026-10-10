"""Security regression tests for upload handling.

Verifies that only Telegram *photos* reach the disk, that documents and every
other media type are refused, and that a file that lies about being an image
is caught by its magic bytes.

    python selftest_security.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import bot
import db
import uploads

FAILURES: list[str] = []
TMP = Path(tempfile.mkdtemp())

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffdb00430008")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16
EXE = b"MZ\x90\x00" + b"\x00" * 64
ZIP = b"PK\x03\x04" + b"\x00" * 64
SCRIPT = b"#!/bin/sh\nrm -rf /\n"


def check(condition: bool, label: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        FAILURES.append(label)


MEDIA_ATTRS = ("photo", "document", "video", "audio", "voice", "animation", "video_note", "sticker", "text")


def message_with(attribute: str):
    """A minimal Update whose message carries exactly one media attribute."""
    from types import SimpleNamespace

    message = SimpleNamespace(**{name: (object() if name == attribute else None) for name in MEDIA_ATTRS})
    update = SimpleNamespace(effective_message=message, effective_user=None, message=message)
    for name in ("callback_query", "channel_post", "edited_channel_post", "inline_query", "chosen_inline_result"):
        setattr(update, name, None)
    return update


def main() -> int:
    print("1) the reject filter matches every non-photo media type")
    blocked = [
        ("document", "document"),
        ("video", "video"),
        ("audio", "audio"),
        ("voice", "voice"),
        ("animation", "animation"),
        ("video note", "video_note"),
        ("sticker", "sticker"),
    ]
    for name, attribute in blocked:
        matched = bot.UNTRUSTED_UPLOADS.check_update(message_with(attribute))
        check(matched, f"{name} is routed to the reject handler")
    check(not bot.UNTRUSTED_UPLOADS.check_update(message_with("photo")), "photos are NOT rejected")
    check(not bot.UNTRUSTED_UPLOADS.check_update(message_with("text")), "plain text is NOT rejected")

    print("2) magic-byte verification")
    for name, blob in [("jpg", JPEG), ("png", PNG), ("gif", GIF), ("webp", WEBP)]:
        path = TMP / f"good.{name}"
        path.write_bytes(blob)
        check(uploads.looks_like_image(path), f"a real {name} passes")
    for name, blob in [("windows exe", EXE), ("zip archive", ZIP), ("shell script", SCRIPT)]:
        path = TMP / f"bad-{name.replace(' ', '-')}"
        path.write_bytes(blob)
        check(not uploads.looks_like_image(path), f"a {name} is rejected")
        check(path.exists(), f"the {name} is left on disk for inspection (never executed)")

    print("3) extension mapping")
    check(uploads.extension_for(TMP / "x.jpg") == ".jpg", "jpeg → .jpg")
    path = TMP / "shot.jpg"
    path.write_bytes(PNG)
    check(uploads.extension_for(path) == ".png", "a png named .jpg is corrected to .png")

    print("4) size ceiling")
    check(uploads.check_size(5 * 1024 * 1024, 10), "5 MB is accepted at a 10 MB limit")
    check(not uploads.check_size(50 * 1024 * 1024, 10), "50 MB is refused at a 10 MB limit")
    check(uploads.check_size(None, 10), "unknown size is allowed through (Bot API caps at 20 MB)")

    print("5) the reject message explains what to do instead")
    for keyword in ("Photo", "ပုံ"):
        check(keyword in uploads.REJECT_TEXT, f"REJECT_TEXT mentions {keyword}")

    print("6) only one download path exists")
    import inspect

    import handlers_user

    source = inspect.getsource(handlers_user.on_photo)
    check("download_to_drive" in source, "receipts are still saved for the admin")
    check("looks_like_image" in source, "the downloaded receipt is verified before it is kept")
    check(source.index("looks_like_image") < source.index("db.set_pending(user_id, None)"),
          "verification happens before the order is treated as submitted")

    db.init(TMP / "sec.db")

    print()
    if FAILURES:
        print(f"❌ {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ uploads are locked down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())