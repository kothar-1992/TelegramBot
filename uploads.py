"""Upload hardening.

Only compressed Telegram *photos* are ever accepted — never documents, videos
or archives.  A user can hand the bot any byte stream they like by sending it
as a `document`, so the rule is: nothing lands on the server unless Telegram
itself classified it as a photo **and** the downloaded bytes really are an
image.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

#: Magic-byte signatures for the formats Telegram actually compresses to.
IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", ".jpg"),  # JPEG
    (b"\x89PNG\r\n\x1a\n", ".png"),  # PNG
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
)

REJECT_TEXT = (
    "🚫 <b>ဖိုင်ပို့ခြင်း မခွင့်ပါ။</b>\n\n"
    "ငွေလွှဲလက်ခံရန် စာမျက်နှာပုံကို screenshot လုပ်ပြီး "
    "<b>Photo (ပုံ)</b> အဖြစ်သာ ပို့ပါ။\n"
    "📎 ဖိုင်/Document အဖြစ်ပို့လျှင် လုံးဝ လက်ခံမည်မဟုတ်ပါ။\n\n"
    "📸 ပုံဖွင့်ရန် — စာမျက်နှာရုပ်ပေါ်မှာ အလင်းရောင် 🎨 ကို နှိပ်ပြီး ပုံရိုက်ပါ။"
)

REJECT_SIZE = "⚠️ ပုံအရွယ်အစား ကြီးလွန်းပါသည်။ {limit} MB အောက် ဖြစ်သော ပုံဖြင့် ထပ်ပို့ပါ။"

REJECT_FAKE = "⚠️ ဖိုင်သည် ပုံမဟုတ်ပါ။ ကျွန်တော်က ပုံမှန်များကိုသာ လက်ခံပါမယ်။"


def looks_like_image(path: Path) -> bool:
    """Verify the first bytes really are an image, not an .exe or .zip in disguise."""
    try:
        with path.open("rb") as fh:
            head = fh.read(16)
    except OSError:
        return False

    if any(head.startswith(signature) for signature, _ in IMAGE_SIGNATURES):
        return True
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return True
    return False


def check_size(size_bytes: int | None, limit_mb: int) -> bool:
    """True when the upload is inside the configured size ceiling."""
    if not size_bytes:
        return True
    return size_bytes <= limit_mb * 1024 * 1024


def extension_for(path: Path) -> str:
    for signature, extension in IMAGE_SIGNATURES:
        try:
            with path.open("rb") as fh:
                if fh.read(len(signature)) == signature:
                    return extension
        except OSError:
            break
    return path.suffix or ".jpg"


def human_size(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f} MB"