from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection, *, currency: str, timezone_name: str) -> None:
    schema = Path(__file__).with_name("schema.sql").read_text()
    conn.executescript(schema)
    conn.executemany(
        "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
        [("currency", currency.upper()), ("timezone", timezone_name)],
    )
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def rows_dict(rows) -> list[dict]:
    return [dict(row) for row in rows]


def settings(conn: sqlite3.Connection) -> dict[str, str]:
    return {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM settings")}


def seed_demo(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM tasks LIMIT 1").fetchone():
        return
    now = utc_now()
    today = date.today()
    today_iso = today.isoformat()
    week_start = today.fromordinal(today.toordinal() - today.weekday()).isoformat()
    month = today_iso[:7]
    currency = settings(conn)["currency"]

    with transaction(conn):
        conn.execute(
            "INSERT INTO daily_focus VALUES (?, ?, ?, ?, ?)",
            (
                today_iso,
                "Ship a clear product walkthrough",
                "Finish the demo, verify the ledgers, and make the story easy to repeat.",
                "demo-agent",
                now,
            ),
        )
        tasks = [
            ("Review the launch outline", "Make the first 20 seconds concrete.", "high", 30),
            ("Verify the demo numbers", "Reconcile the example time and money totals.", "high", 25),
            ("Record the product walkthrough", "Use the 6–7 minute launch script.", "medium", 45),
            ("Publish the repository", "Check the anonymous GitHub view first.", "medium", 20),
        ]
        for order, (title, notes, priority, minutes) in enumerate(tasks):
            conn.execute(
                """INSERT INTO tasks
                   (id,title,notes,status,priority,estimated_minutes,source,sort_order,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    new_id("task"),
                    title,
                    notes,
                    "open",
                    priority,
                    minutes,
                    "demo-agent",
                    order,
                    now,
                    now,
                ),
            )

        accounts = [
            ("account_checking", "Everyday account", "asset", 620_000, 0),
            ("account_savings", "Savings", "asset", 1_850_000, 1),
            ("account_card", "Credit card", "liability", 84_000, 2),
        ]
        for account_id, name, account_type, balance, order in accounts:
            conn.execute(
                """INSERT INTO money_accounts
                   (id,name,account_type,currency,balance_minor,sort_order,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (account_id, name, account_type, currency, balance, order, now, now),
            )

        budgets = [
            ("budget_income", "Project income", "income", "income", 500_000),
            ("budget_housing", "Housing", "housing", "expense", 160_000),
            ("budget_food", "Food", "food", "expense", 60_000),
            ("budget_transport", "Transport", "transport", "expense", 18_000),
            ("budget_tools", "Tools", "tools", "expense", 22_000),
            ("budget_flexible", "Flexible", "flexible", "expense", 35_000),
        ]
        for order, (item_id, title, category, direction, amount) in enumerate(budgets):
            conn.execute(
                """INSERT INTO money_budget_items
                   (id,month,title,category,direction,amount_minor,currency,sort_order,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (item_id, month, title, category, direction, amount, currency, order, now, now),
            )

        time_budgets = [
            ("time_sleep", "Sleep", "foundation", 56 * 60, "committed"),
            ("time_work", "Work", "work", 40 * 60, "committed"),
            ("time_health", "Health", "health", 7 * 60, "protected"),
            ("time_learning", "Learning", "learning", 5 * 60, "protected"),
            ("time_people", "Relationships", "relationships", 7 * 60, "protected"),
            ("time_admin", "Life admin", "admin", 4 * 60, "flexible"),
        ]
        for order, (item_id, label, category, minutes, protection) in enumerate(time_budgets):
            conn.execute(
                """INSERT INTO time_budget_items
                   (id,week_start,label,category,weekly_minutes,protection,sort_order,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (item_id, week_start, label, category, minutes, protection, order, now, now),
            )


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
