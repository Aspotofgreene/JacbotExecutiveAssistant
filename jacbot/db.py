import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "jacbot.db"

def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY,
                name            TEXT    NOT NULL DEFAULT 'User',
                timezone        TEXT    NOT NULL DEFAULT 'America/New_York',
                morning_time    TEXT    NOT NULL DEFAULT '07:00',
                evening_time    TEXT    NOT NULL DEFAULT '20:00',
                report_day      INTEGER NOT NULL DEFAULT 6,
                report_time     TEXT    NOT NULL DEFAULT '18:00',
                telegram_id     INTEGER UNIQUE,
                created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                date                TEXT    NOT NULL,
                position            INTEGER NOT NULL,
                text                TEXT    NOT NULL,
                why                 TEXT,
                status              TEXT    NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending','done','missed','carried','killed')),
                carried_from_id     INTEGER REFERENCES tasks(id),
                ai_category         TEXT,
                ai_effort_min       INTEGER,
                next_checkin_at     TEXT,
                checkin_count       INTEGER NOT NULL DEFAULT 0,
                created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
                completed_at        TEXT,
                killed_reason       TEXT
            );

            CREATE TABLE IF NOT EXISTS checkins (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         INTEGER NOT NULL REFERENCES tasks(id),
                sent_at         TEXT    NOT NULL DEFAULT (datetime('now')),
                response        TEXT CHECK (response IN ('done','in_progress','blocked','snooze','reschedule', NULL)),
                note            TEXT,
                responded_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS journal_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                text        TEXT    NOT NULL,
                ai_tags     TEXT,
                mood        INTEGER CHECK (mood BETWEEN 1 AND 5)
            );

            CREATE TABLE IF NOT EXISTS reflections (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL UNIQUE,
                prompt      TEXT    NOT NULL,
                response    TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                period      TEXT    NOT NULL CHECK (period IN ('week','month','year')),
                start_date  TEXT    NOT NULL,
                end_date    TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                generated_at TEXT   NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                silent_until    TEXT,
                theme_this_week TEXT,
                last_updated    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            INSERT OR IGNORE INTO users (id) VALUES (1);
            INSERT OR IGNORE INTO settings (id) VALUES (1);
        """)
        _migrate_remove_position_check(conn)

def _migrate_remove_position_check(conn) -> None:
    """Drop the CHECK (position BETWEEN 1 AND 3) constraint if it still exists."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'").fetchone()
    if not row or "BETWEEN 1 AND 3" not in row["sql"]:
        return
    conn.executescript("""
        PRAGMA foreign_keys = OFF;

        CREATE TABLE tasks_new (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            date                TEXT    NOT NULL,
            position            INTEGER NOT NULL,
            text                TEXT    NOT NULL,
            why                 TEXT,
            status              TEXT    NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','done','missed','carried','killed')),
            carried_from_id     INTEGER REFERENCES tasks_new(id),
            ai_category         TEXT,
            ai_effort_min       INTEGER,
            next_checkin_at     TEXT,
            checkin_count       INTEGER NOT NULL DEFAULT 0,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
            completed_at        TEXT,
            killed_reason       TEXT
        );

        INSERT INTO tasks_new SELECT * FROM tasks;
        DROP TABLE tasks;
        ALTER TABLE tasks_new RENAME TO tasks;

        PRAGMA foreign_keys = ON;
    """)

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_tasks_for_date(day: date) -> list:
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM tasks WHERE date = ? ORDER BY (carried_from_id IS NOT NULL) DESC, position ASC
        """, (day.isoformat(),)).fetchall()

def count_tasks_for_date(day: date) -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM tasks WHERE date = ?", (day.isoformat(),)).fetchone()[0]

def add_task(day: date, position: int, text: str, why: str | None = None, carried_from_id: int | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute("""INSERT INTO tasks (date, position, text, why, carried_from_id) VALUES (?, ?, ?, ?, ?)""", 
                          (day.isoformat(), position, text, why, carried_from_id))
        return cur.lastrowid

def mark_task_done(task_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET status = 'done', completed_at = datetime('now') WHERE id = ?", (task_id,))

def kill_task(task_id: int, reason: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET status = 'killed', killed_reason = ? WHERE id = ?", (reason, task_id))

def delete_tasks_for_date(day: date) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE date = ? AND carried_from_id IS NULL", (day.isoformat(),))

def carry_over_unfinished(from_date: date, to_date: date) -> int:
    with get_conn() as conn:
        pending = conn.execute("SELECT * FROM tasks WHERE date = ? AND status = 'pending'", 
                              (from_date.isoformat(),)).fetchall()
        existing = conn.execute("SELECT COUNT(*) FROM tasks WHERE date = ?", (to_date.isoformat(),)).fetchone()[0]
        for i, task in enumerate(pending):
            conn.execute("""INSERT INTO tasks (date, position, text, why, status, carried_from_id, ai_category, ai_effort_min) 
                           VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
                        (to_date.isoformat(), existing + i + 1, task["text"], task["why"], task["id"], 
                         task["ai_category"], task["ai_effort_min"]))
            conn.execute("UPDATE tasks SET status = 'carried' WHERE id = ?", (task["id"],))
        return len(pending)

def get_task_by_id(task_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def get_user():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id = 1").fetchone()


def log_checkin(task_id: int, response: str) -> int:
    """Log a check-in response. Returns updated checkin_count."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO checkins (task_id, response, responded_at) VALUES (?, ?, datetime('now'))",
            (task_id, response))
        conn.execute(
            "UPDATE tasks SET checkin_count = checkin_count + 1 WHERE id = ?", (task_id,))
        row = conn.execute(
            "SELECT checkin_count FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return row["checkin_count"] if row else 0


def suppress_checkins(task_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET next_checkin_at = 'suppressed' WHERE id = ?", (task_id,))


def set_task_category(task_id: int, category: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET ai_category = ? WHERE id = ?", (category, task_id))


def count_days_carried(task_id: int) -> int:
    """Count how many days a task has been carried (follow the chain)."""
    with get_conn() as conn:
        count = 0
        current_id = task_id
        seen = set()
        while current_id and current_id not in seen:
            seen.add(current_id)
            row = conn.execute(
                "SELECT carried_from_id FROM tasks WHERE id = ?", (current_id,)
            ).fetchone()
            if not row or not row["carried_from_id"]:
                break
            current_id = row["carried_from_id"]
            count += 1
        return count


def get_tasks_in_range(start: date, end: date) -> list:
    """Return all tasks between start and end dates inclusive."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM tasks
            WHERE date BETWEEN ? AND ?
            ORDER BY date ASC, position ASC
        """, (start.isoformat(), end.isoformat())).fetchall()


def get_journal_entries_in_range(start: date, end: date) -> list:
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM journal_entries
            WHERE date(created_at) BETWEEN ? AND ?
            ORDER BY created_at ASC
        """, (start.isoformat(), end.isoformat())).fetchall()


def save_report(period: str, start: date, end: date, content: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO reports (period, start_date, end_date, content)
            VALUES (?, ?, ?, ?)
        """, (period, start.isoformat(), end.isoformat(), content))
        return cur.lastrowid


def get_latest_report(period: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM reports WHERE period = ?
            ORDER BY generated_at DESC LIMIT 1
        """, (period,)).fetchone()


def add_journal_entry(text: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO journal_entries (text) VALUES (?)", (text,))
        return cur.lastrowid

def get_settings():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()

def set_silent_until(until: datetime | None) -> None:
    val = until.isoformat() if until else None
    with get_conn() as conn:
        conn.execute("UPDATE settings SET silent_until = ?, last_updated = datetime('now') WHERE id = 1", (val,))

def is_silent() -> bool:
    s = get_settings()
    return s["silent_until"] is not None and datetime.fromisoformat(s["silent_until"]) > datetime.now()

def set_telegram_id(telegram_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET telegram_id = ? WHERE id = 1", (telegram_id,))
