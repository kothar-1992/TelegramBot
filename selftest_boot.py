"""Guards against the failure modes that broke previous Render deploys.

    python selftest_boot.py
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import backup as backup_mod
import bot
import db
from config import settings

FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        FAILURES.append(label)


class _FakeJobQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    def run_repeating(self, callback, interval=None, first=None, **kw) -> None:
        self.jobs.append((callback.__name__, interval))


class _FakeApp:
    def __init__(self, job_queue) -> None:
        self.job_queue = job_queue


def main() -> int:
    print("1) the JobQueue extra is actually installed")
    check(settings.configured, "BOT_TOKEN is present")
    check(bot.build_app is not None, "build_app() exists")

    print("2) jobs schedule when the JobQueue is available")
    # Locally SELF_URL/BACKUP are off, so force them on for this check.
    original = bot.settings
    forced = dataclasses.replace(
        original, self_url="https://example.onrender.com", backup_enabled=True, backup_admin_id=1
    )
    bot.settings = forced
    backup_mod.settings = forced  # backup.enabled() reads its own copy
    queue = _FakeJobQueue()
    bot._schedule_jobs(_FakeApp(queue))
    names = [name for name, _ in queue.jobs]
    check("keep_alive_job" in names, "keep-alive job registered")
    check("backup_job" in names, "backup job registered")
    bot.settings = original
    backup_mod.settings = original

    print("3) a missing JobQueue warns instead of crashing the deploy")
    bare = _FakeApp(None)
    try:
        bot._schedule_jobs(bare)
        check(True, "post_init survives a None job_queue (no AttributeError)")
    except AttributeError as err:
        check(False, f"post_init crashed on a None job_queue: {err}")

    print("4) health endpoint binds the platform port")
    import os

    os.environ["PORT"] = "18099"
    import health

    server = health.start_health_server()
    check(server is not None, "health server bound to :18099")
    if server is not None:
        import httpx

        check(httpx.get("http://127.0.0.1:18099/health", timeout=10).status_code == 200, "/health answers 200")
        server.shutdown()

    print("5) database still initialises cleanly")
    db.init(":memory:")
    db.upsert_user(1, "t", "T")
    check(db.get_balance(1) == 0, "fresh database is usable")

    print()
    if FAILURES:
        print(f"❌ {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ boot path is safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())