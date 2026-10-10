"""Configuration loading for the Telegram shop bot.

Values are read from a local `.env` file (see `.env.example`).  A tiny
dotenv reader is bundled so the project has no extra runtime dependency.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Populate `os.environ` from a `.env` file without overriding real env vars."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


def _int_list(raw: str | None) -> tuple[int, ...]:
    """Parse `ADMIN_IDS=123, 456` into a tuple of ints."""
    if not raw:
        return ()
    ids: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return tuple(ids)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: tuple[int, ...]
    db_path: Path
    currency: str
    shop_name: str
    support_username: str
    welcome_text: str
    page_size: int
    proxy: str
    menu_button: bool
    self_url: str
    keepalive_minutes: int
    backup_enabled: bool
    backup_admin_id: int
    backup_minutes: int
    clean_messages: bool
    max_upload_mb: int

    @property
    def configured(self) -> bool:
        return bool(self.bot_token) and ":" in self.bot_token


settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", "").strip(),
    admin_ids=_int_list(os.getenv("ADMIN_IDS")),
    db_path=BASE_DIR / os.getenv("DB_PATH", "shop.db").strip(),
    currency=os.getenv("CURRENCY", "MMK").strip() or "MMK",
    shop_name=os.getenv("SHOP_NAME", "W3K Digital Pay & Services").strip(),
    support_username=os.getenv("SUPPORT_USERNAME", "").lstrip("@").strip(),
    welcome_text=os.getenv("WELCOME_TEXT", "👋 Welcome to {shop}").strip(),
    page_size=max(1, min(int(os.getenv("PAGE_SIZE", "6") or 6), 10)),
    proxy=os.getenv("PROXY", "").strip(),
    menu_button=os.getenv("MENU_BUTTON", "true").strip().lower() not in {"0", "false", "no", "off"},
    self_url=os.getenv("SELF_URL", "").strip().rstrip("/"),
    keepalive_minutes=max(1, int(os.getenv("KEEPALIVE_MINUTES", "9") or 9)),
    backup_enabled=os.getenv("BACKUP_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
    backup_admin_id=int(_int_list(os.getenv("BACKUP_ADMIN_ID"))[0]) if _int_list(os.getenv("BACKUP_ADMIN_ID")) else 0,
    backup_minutes=max(1, int(os.getenv("BACKUP_MINUTES", "10") or 10)),
    clean_messages=os.getenv("CLEAN_MESSAGES", "true").strip().lower() not in {"0", "false", "no", "off"},
    max_upload_mb=max(1, int(os.getenv("MAX_UPLOAD_MB", "10") or 10)),
)


def is_admin(user_id: int | None) -> bool:
    """True when the given Telegram user id is a shop administrator."""
    return user_id is not None and user_id in settings.admin_ids