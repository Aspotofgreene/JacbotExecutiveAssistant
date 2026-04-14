"""
Offline smoke test for Jacbot.

Verifies that:
  - all modules import cleanly
  - DB schema creates in a temp sqlite file
  - core DB helpers round-trip (users, tasks, journal, settings, reports)
  - carry_over_unfinished + count_days_carried behave correctly
  - handler modules load

Does NOT hit Telegram or the Anthropic API.

Usage:
    python scripts/smoke_test.py

Exits 0 on success, 1 on any failure.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

# Set dummy env vars BEFORE importing jacbot.config so _require() passes
os.environ.setdefault("TELEGRAM_TOKEN", "smoke-test-token")
os.environ.setdefault("OLLAMA_MAC_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MAC_MODEL", "qwen3:14b")
os.environ.setdefault("OLLAMA_DESKTOP_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_DESKTOP_MODEL", "qwen3:14b")

# Point DB at a throwaway file
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
TMP_DB = Path(_tmp.name)

# Make sure we import from the repo, not a pip-installed copy
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Patch db path before init
from jacbot import db  # noqa: E402
db.DB_PATH = TMP_DB


PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


def check(label: str, fn):
    try:
        fn()
        print(f"  {PASS} {label}")
        return True
    except Exception as e:
        print(f"  {FAIL} {label}")
        traceback.print_exc()
        return False


def test_imports():
    import jacbot.config  # noqa: F401
    import jacbot.db      # noqa: F401
    import jacbot.scheduler  # noqa: F401
    import jacbot.ai      # noqa: F401
    import jacbot.handlers.core      # noqa: F401
    import jacbot.handlers.checkin   # noqa: F401
    import jacbot.handlers.reports   # noqa: F401
    import jacbot.main    # noqa: F401


def test_db_init():
    db.init_db()
    with db.get_conn() as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    expected = {"users", "tasks", "checkins", "journal_entries",
                "reflections", "reports", "settings"}
    missing = expected - tables
    assert not missing, f"missing tables: {missing}"


def test_user_seeded():
    user = db.get_user()
    assert user is not None, "default user row not seeded"
    assert user["id"] == 1


def test_task_roundtrip():
    today = date.today()
    tid1 = db.add_task(today, 1, "Draft proposal", "Client needs it Friday")
    db.add_task(today, 2, "Fix login bug")
    db.add_task(today, 3, "Call accountant")
    assert db.count_tasks_for_date(today) == 3
    db.mark_task_done(tid1)
    t = db.get_task_by_id(tid1)
    assert t["status"] == "done"
    assert t["completed_at"] is not None


def test_categorize_and_checkin():
    today = date.today()
    tasks = db.get_tasks_for_date(today)
    pending = [t for t in tasks if t["status"] == "pending"][0]
    db.set_task_category(pending["id"], "Deep Work")
    count = db.log_checkin(pending["id"], "in_progress")
    assert count == 1
    count = db.log_checkin(pending["id"], "in_progress")
    assert count == 2
    db.suppress_checkins(pending["id"])
    refreshed = db.get_task_by_id(pending["id"])
    assert refreshed["ai_category"] == "Deep Work"
    assert refreshed["next_checkin_at"] == "suppressed"


def test_carry_over_and_chain():
    day0 = date.today() - timedelta(days=5)
    day1 = day0 + timedelta(days=1)
    day2 = day1 + timedelta(days=1)
    day3 = day2 + timedelta(days=1)

    orig = db.add_task(day0, 1, "Nagging task")
    # simulate it staying pending and being carried forward each day
    n = db.carry_over_unfinished(day0, day1)
    assert n == 1
    n = db.carry_over_unfinished(day1, day2)
    assert n == 1
    n = db.carry_over_unfinished(day2, day3)
    assert n == 1

    # find the latest carried copy
    latest = [t for t in db.get_tasks_for_date(day3)
              if t["text"] == "Nagging task"][0]
    days = db.count_days_carried(latest["id"])
    assert days >= 3, f"expected 3+ days carried, got {days}"


def test_journal_and_reports():
    eid = db.add_journal_entry("Felt stuck on the proposal today.")
    assert eid > 0
    entries = db.get_journal_entries_in_range(
        date.today() - timedelta(days=1), date.today() + timedelta(days=1))
    assert any(e["id"] == eid for e in entries)

    rid = db.save_report(
        "week",
        date.today() - timedelta(days=6),
        date.today(),
        "Sample report content.")
    assert rid > 0
    latest = db.get_latest_report("week")
    assert latest is not None
    assert latest["content"] == "Sample report content."


def test_silent_mode():
    db.set_silent_until(datetime.now() + timedelta(hours=1))
    assert db.is_silent() is True
    db.set_silent_until(None)
    assert db.is_silent() is False


def test_scheduler_parse():
    from jacbot.scheduler import _parse_time
    assert _parse_time("07:30", 0, 0) == (7, 30)
    assert _parse_time("garbage", 9, 15) == (9, 15)
    assert _parse_time("", 6, 0) == (6, 0)


def main() -> int:
    print("Running Jacbot smoke test...\n")
    tests = [
        ("imports load",               test_imports),
        ("db.init_db creates schema",  test_db_init),
        ("default user row seeded",    test_user_seeded),
        ("tasks insert/complete",      test_task_roundtrip),
        ("categorize + check-in log",  test_categorize_and_checkin),
        ("carry-over + chain count",   test_carry_over_and_chain),
        ("journal + report save",      test_journal_and_reports),
        ("silent mode toggle",         test_silent_mode),
        ("scheduler _parse_time",      test_scheduler_parse),
    ]
    results = [check(label, fn) for label, fn in tests]
    failed = results.count(False)
    print()
    if failed:
        print(f"{FAIL} {failed}/{len(results)} tests failed")
        return 1
    print(f"{PASS} all {len(results)} tests passed")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        try:
            TMP_DB.unlink()
        except OSError:
            pass
    sys.exit(rc)
