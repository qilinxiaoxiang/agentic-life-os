from __future__ import annotations

import os
import re
import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

from . import db
from .service import (
    ValidationError,
    amount_to_minor,
    budget_adjustment_dict,
    commit_proposal,
    context_today,
    decide_budget_adjustment,
    minor_to_amount,
    money_overview,
    parse_date,
    preview_proposal,
    proposal_dict,
    propose_budget_adjustment,
    task_to_dict,
    time_overview,
    week_start_for,
)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DB_PATH=os.environ.get("LIFEOS_DB_PATH", "./data/lifeos.sqlite"),
        DEFAULT_CURRENCY=os.environ.get("LIFEOS_CURRENCY", "USD").upper(),
        DEFAULT_TIMEZONE=os.environ.get("LIFEOS_TIMEZONE", "UTC"),
        DEMO=os.environ.get("LIFEOS_DEMO", "0") == "1",
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    _validate_currency(app.config["DEFAULT_CURRENCY"])
    path = Path(app.config["DB_PATH"])
    conn = db.connect(path)
    db.initialize(
        conn,
        currency=app.config["DEFAULT_CURRENCY"],
        timezone_name=app.config["DEFAULT_TIMEZONE"],
    )
    if app.config["DEMO"]:
        db.seed_demo(conn)
    conn.close()

    @app.before_request
    def open_db():
        g.db = db.connect(app.config["DB_PATH"])

    @app.teardown_request
    def close_db(_error=None):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.errorhandler(ValidationError)
    def validation_error(error):
        return jsonify({"ok": False, "error": str(error)}), 400

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity_error(error):
        return jsonify({"ok": False, "error": f"data conflict: {error}"}), 409

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/")
    def index():
        date_iso = request.args.get("date", date.today().isoformat())
        settings = db.settings(g.db)
        context = context_today(g.db, date_iso, settings["currency"])
        proposals = [
            proposal_dict(row)
            for row in g.db.execute(
                "SELECT * FROM ledger_proposals WHERE status='pending' ORDER BY created_at DESC"
            )
        ]
        adjustment_proposals = [
            budget_adjustment_dict(row)
            for row in g.db.execute(
                """SELECT * FROM budget_adjustment_proposals
                   WHERE status='pending' ORDER BY created_at DESC"""
            )
        ]
        return render_template(
            "index.html",
            context=context,
            settings=settings,
            proposals=proposals,
            adjustment_proposals=adjustment_proposals,
            money_symbol=_currency_symbol(settings["currency"]),
            money=minor_to_amount,
            compact_money=_compact_money,
            duration=_duration,
        )

    @app.get("/api/v1/settings")
    def get_settings():
        return jsonify({"ok": True, "settings": db.settings(g.db)})

    @app.patch("/api/v1/settings")
    def patch_settings():
        payload = _json()
        current = db.settings(g.db)
        if "currency" in payload:
            currency = str(payload["currency"]).upper()
            _validate_currency(currency)
            financial_rows = sum(
                g.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("money_accounts", "money_budget_items", "money_transactions")
            )
            if financial_rows and currency != current["currency"]:
                raise ValidationError(
                    "primary currency can change only before financial data exists"
                )
            g.db.execute("UPDATE settings SET value=? WHERE key='currency'", (currency,))
        if "timezone" in payload:
            timezone_name = str(payload["timezone"]).strip()
            if not timezone_name:
                raise ValidationError("timezone cannot be empty")
            g.db.execute("UPDATE settings SET value=? WHERE key='timezone'", (timezone_name,))
        g.db.commit()
        return jsonify({"ok": True, "settings": db.settings(g.db)})

    @app.get("/api/v1/context/today")
    def get_context():
        date_iso = request.args.get("date", date.today().isoformat())
        settings = db.settings(g.db)
        return jsonify({"ok": True, "context": context_today(g.db, date_iso, settings["currency"])})

    @app.put("/api/v1/today/<date_iso>")
    def put_focus(date_iso: str):
        parse_date(date_iso)
        payload = _json()
        headline = str(payload.get("headline", "")).strip()
        if not headline:
            raise ValidationError("headline is required")
        now = db.utc_now()
        g.db.execute(
            """INSERT INTO daily_focus(focus_date,headline,brief,source,updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(focus_date) DO UPDATE SET headline=excluded.headline,
               brief=excluded.brief,source=excluded.source,updated_at=excluded.updated_at""",
            (
                date_iso,
                headline,
                str(payload.get("brief", "")).strip(),
                str(payload.get("source", "agent")),
                now,
            ),
        )
        g.db.commit()
        row = g.db.execute("SELECT * FROM daily_focus WHERE focus_date=?", (date_iso,)).fetchone()
        return jsonify({"ok": True, "focus": dict(row)})

    @app.get("/api/v1/tasks")
    def list_tasks():
        status = request.args.get("status")
        if status and status not in {"open", "done"}:
            raise ValidationError("status must be open or done")
        query = "SELECT * FROM tasks"
        args = ()
        if status:
            query += " WHERE status=?"
            args = (status,)
        query += " ORDER BY status='done', sort_order, created_at"
        return jsonify({"ok": True, "tasks": db.rows_dict(g.db.execute(query, args))})

    @app.post("/api/v1/tasks")
    def create_task():
        payload = _json()
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValidationError("title is required")
        priority = str(payload.get("priority", "medium"))
        if priority not in {"low", "medium", "high"}:
            raise ValidationError("priority must be low, medium, or high")
        due_date = payload.get("due_date") or None
        if due_date:
            parse_date(due_date, "due_date")
        estimated = payload.get("estimated_minutes")
        if estimated is not None:
            try:
                estimated = int(estimated)
            except (TypeError, ValueError) as exc:
                raise ValidationError("estimated_minutes must be an integer") from exc
            if estimated <= 0:
                raise ValidationError("estimated_minutes must be positive")
        now = db.utc_now()
        task_id = db.new_id("task")
        sort_order = g.db.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM tasks").fetchone()[0]
        g.db.execute(
            """INSERT INTO tasks
               (id,title,notes,status,priority,due_date,estimated_minutes,source,sort_order,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task_id,
                title,
                str(payload.get("notes", "")).strip(),
                "open",
                priority,
                due_date,
                estimated,
                str(payload.get("source", "agent")),
                sort_order,
                now,
                now,
            ),
        )
        g.db.commit()
        return jsonify({"ok": True, "task": _task(g.db, task_id)}), 201

    @app.get("/api/v1/tasks/<task_id>")
    def get_task(task_id: str):
        return jsonify({"ok": True, "task": _task(g.db, task_id)})

    @app.patch("/api/v1/tasks/<task_id>")
    def patch_task(task_id: str):
        _task(g.db, task_id)
        payload = _json()
        allowed = {
            "title",
            "notes",
            "priority",
            "due_date",
            "estimated_minutes",
            "status",
            "sort_order",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValidationError(f"unknown task fields: {', '.join(sorted(unknown))}")
        if not payload:
            raise ValidationError("at least one task field is required")
        if "title" in payload and not str(payload["title"]).strip():
            raise ValidationError("title cannot be empty")
        if "priority" in payload and payload["priority"] not in {"low", "medium", "high"}:
            raise ValidationError("priority must be low, medium, or high")
        if "status" in payload and payload["status"] not in {"open", "done"}:
            raise ValidationError("status must be open or done")
        if payload.get("due_date"):
            parse_date(payload["due_date"], "due_date")
        if "estimated_minutes" in payload and payload["estimated_minutes"] is not None:
            payload["estimated_minutes"] = int(payload["estimated_minutes"])
            if payload["estimated_minutes"] <= 0:
                raise ValidationError("estimated_minutes must be positive")
        clean = {
            key: (str(value).strip() if key in {"title", "notes"} else value)
            for key, value in payload.items()
        }
        if clean.get("status") == "done":
            clean["completed_at"] = db.utc_now()
        elif clean.get("status") == "open":
            clean["completed_at"] = None
        clean["updated_at"] = db.utc_now()
        assignments = ",".join(f"{key}=?" for key in clean)
        g.db.execute(f"UPDATE tasks SET {assignments} WHERE id=?", (*clean.values(), task_id))
        g.db.commit()
        return jsonify({"ok": True, "task": _task(g.db, task_id)})

    @app.delete("/api/v1/tasks/<task_id>")
    def delete_task(task_id: str):
        _task(g.db, task_id)
        g.db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        g.db.commit()
        return jsonify({"ok": True, "deleted": task_id})

    @app.post("/api/v1/tasks/reorder")
    def reorder_tasks():
        ids = _json().get("ids")
        if not isinstance(ids, list):
            raise ValidationError("ids must be an array")
        with db.transaction(g.db):
            for order, task_id in enumerate(ids):
                g.db.execute(
                    "UPDATE tasks SET sort_order=?,updated_at=? WHERE id=?",
                    (order, db.utc_now(), task_id),
                )
        return jsonify({"ok": True})

    @app.get("/api/v1/money/overview")
    def get_money_overview():
        settings = db.settings(g.db)
        month = request.args.get("month", date.today().isoformat()[:7])
        currency = request.args.get("currency", settings["currency"]).upper()
        _validate_currency(currency)
        return jsonify({"ok": True, "money": money_overview(g.db, month, currency)})

    @app.get("/api/v1/money/accounts")
    def list_accounts():
        return jsonify(
            {
                "ok": True,
                "accounts": db.rows_dict(
                    g.db.execute("SELECT * FROM money_accounts ORDER BY currency,sort_order,name")
                ),
            }
        )

    @app.post("/api/v1/money/accounts")
    def create_account():
        payload = _json()
        name = str(payload.get("name", "")).strip()
        account_type = str(payload.get("account_type", "asset"))
        currency = str(payload.get("currency", db.settings(g.db)["currency"])).upper()
        if not name:
            raise ValidationError("name is required")
        if account_type not in {"asset", "liability"}:
            raise ValidationError("account_type must be asset or liability")
        _validate_currency(currency)
        balance_minor = 0
        if payload.get("opening_balance") not in {None, "", 0, "0"}:
            balance_minor = amount_to_minor(payload["opening_balance"])
        account_id = str(payload.get("id", "")).strip() or db.new_id("account")
        now = db.utc_now()
        order = g.db.execute(
            "SELECT COALESCE(MAX(sort_order),-1)+1 FROM money_accounts"
        ).fetchone()[0]
        g.db.execute(
            """INSERT INTO money_accounts
               (id,name,account_type,currency,balance_minor,sort_order,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (account_id, name, account_type, currency, balance_minor, order, now, now),
        )
        g.db.commit()
        return jsonify(
            {
                "ok": True,
                "account": dict(
                    g.db.execute(
                        "SELECT * FROM money_accounts WHERE id=?", (account_id,)
                    ).fetchone()
                ),
            }
        ), 201

    @app.patch("/api/v1/money/accounts/<account_id>")
    def patch_account(account_id: str):
        _require_row(g.db, "money_accounts", account_id, "account")
        payload = _json()
        allowed = {"name", "account_type", "sort_order"}
        if not payload or set(payload) - allowed:
            raise ValidationError("account patch accepts name, account_type, and sort_order")
        if "name" in payload:
            payload["name"] = str(payload["name"]).strip()
            if not payload["name"]:
                raise ValidationError("name cannot be empty")
        if "account_type" in payload:
            if payload["account_type"] not in {"asset", "liability"}:
                raise ValidationError("account_type must be asset or liability")
            used = g.db.execute(
                """SELECT COUNT(*) FROM money_transactions
                   WHERE account_id=? OR to_account_id=?""",
                (account_id, account_id),
            ).fetchone()[0]
            if used:
                raise ValidationError("account_type cannot change after transactions exist")
        payload["updated_at"] = db.utc_now()
        _update_fields(g.db, "money_accounts", account_id, payload)
        return jsonify(
            {
                "ok": True,
                "account": dict(_require_row(g.db, "money_accounts", account_id, "account")),
            }
        )

    @app.delete("/api/v1/money/accounts/<account_id>")
    def delete_account(account_id: str):
        _require_row(g.db, "money_accounts", account_id, "account")
        used = g.db.execute(
            "SELECT COUNT(*) FROM money_transactions WHERE account_id=? OR to_account_id=?",
            (account_id, account_id),
        ).fetchone()[0]
        if used:
            raise ValidationError("account with transactions cannot be deleted")
        g.db.execute("DELETE FROM money_accounts WHERE id=?", (account_id,))
        g.db.commit()
        return jsonify({"ok": True, "deleted": account_id})

    @app.get("/api/v1/money/budgets")
    def list_money_budgets():
        month = request.args.get("month", date.today().isoformat()[:7])
        rows = g.db.execute(
            "SELECT * FROM money_budget_items WHERE month=? ORDER BY currency,sort_order,title",
            (month,),
        )
        return jsonify({"ok": True, "budget_items": db.rows_dict(rows)})

    @app.post("/api/v1/money/budgets")
    def create_money_budget():
        payload = _json()
        month = str(payload.get("month", ""))
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ValidationError("month must be YYYY-MM")
        title = str(payload.get("title", "")).strip()
        category = str(payload.get("category", "")).strip()
        direction = str(payload.get("direction", "expense"))
        currency = str(payload.get("currency", db.settings(g.db)["currency"])).upper()
        if not title or not category:
            raise ValidationError("title and category are required")
        if direction not in {"expense", "income"}:
            raise ValidationError("direction must be expense or income")
        _validate_currency(currency)
        item_id = str(payload.get("id", "")).strip() or db.new_id("money_budget")
        now = db.utc_now()
        order = g.db.execute(
            "SELECT COALESCE(MAX(sort_order),-1)+1 FROM money_budget_items"
        ).fetchone()[0]
        g.db.execute(
            """INSERT INTO money_budget_items
               (id,month,title,category,direction,amount_minor,currency,sort_order,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                item_id,
                month,
                title,
                category,
                direction,
                amount_to_minor(payload.get("amount")),
                currency,
                order,
                now,
                now,
            ),
        )
        g.db.commit()
        return jsonify({"ok": True, "budget_item_id": item_id}), 201

    @app.patch("/api/v1/money/budgets/<item_id>")
    def patch_money_budget(item_id: str):
        _require_row(g.db, "money_budget_items", item_id, "money budget item")
        payload = _json()
        allowed = {"title", "category", "direction", "amount", "sort_order"}
        if not payload or set(payload) - allowed:
            raise ValidationError("invalid money budget patch fields")
        for field in ("title", "category"):
            if field in payload:
                payload[field] = str(payload[field]).strip()
                if not payload[field]:
                    raise ValidationError(f"{field} cannot be empty")
        if "direction" in payload and payload["direction"] not in {"expense", "income"}:
            raise ValidationError("direction must be expense or income")
        if "amount" in payload:
            payload["amount_minor"] = amount_to_minor(payload.pop("amount"))
        payload["updated_at"] = db.utc_now()
        _update_fields(g.db, "money_budget_items", item_id, payload)
        return jsonify(
            {
                "ok": True,
                "budget_item": dict(
                    _require_row(g.db, "money_budget_items", item_id, "money budget item")
                ),
            }
        )

    @app.delete("/api/v1/money/budgets/<item_id>")
    def delete_money_budget(item_id: str):
        _require_row(g.db, "money_budget_items", item_id, "money budget item")
        used = g.db.execute(
            "SELECT COUNT(*) FROM money_transactions WHERE budget_item_id=?", (item_id,)
        ).fetchone()[0]
        if used:
            raise ValidationError("budget item with transactions cannot be deleted")
        g.db.execute("DELETE FROM money_budget_items WHERE id=?", (item_id,))
        g.db.commit()
        return jsonify({"ok": True, "deleted": item_id})

    @app.get("/api/v1/money/transactions")
    def list_money_transactions():
        month = request.args.get("month", date.today().isoformat()[:7])
        rows = g.db.execute(
            """SELECT * FROM money_transactions WHERE substr(occurred_on,1,7)=?
               ORDER BY occurred_on DESC,created_at DESC""",
            (month,),
        )
        return jsonify({"ok": True, "transactions": db.rows_dict(rows)})

    @app.get("/api/v1/time/overview")
    def get_time_overview():
        start = request.args.get("week_start", week_start_for(date.today()))
        return jsonify(
            {
                "ok": True,
                "time": time_overview(g.db, start, request.args.get("as_of")),
            }
        )

    @app.get("/api/v1/time/budgets")
    def list_time_budgets():
        start = request.args.get("week_start", week_start_for(date.today()))
        rows = g.db.execute(
            "SELECT * FROM time_budget_items WHERE week_start=? ORDER BY sort_order,label",
            (start,),
        )
        return jsonify({"ok": True, "budget_items": db.rows_dict(rows)})

    @app.post("/api/v1/time/budgets")
    def create_time_budget():
        payload = _json()
        start = str(payload.get("week_start", ""))
        if parse_date(start, "week_start").weekday() != 0:
            raise ValidationError("week_start must be a Monday")
        label = str(payload.get("label", "")).strip()
        category = str(payload.get("category", "")).strip()
        protection = str(payload.get("protection", "flexible"))
        if not label or not category:
            raise ValidationError("label and category are required")
        if protection not in {"committed", "protected", "flexible"}:
            raise ValidationError("invalid protection")
        try:
            minutes = int(payload.get("weekly_minutes"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("weekly_minutes must be an integer") from exc
        if minutes < 0:
            raise ValidationError("weekly_minutes cannot be negative")
        item_id = str(payload.get("id", "")).strip() or db.new_id("time_budget")
        now = db.utc_now()
        order = g.db.execute(
            "SELECT COALESCE(MAX(sort_order),-1)+1 FROM time_budget_items"
        ).fetchone()[0]
        g.db.execute(
            """INSERT INTO time_budget_items
               (id,week_start,label,category,weekly_minutes,protection,sort_order,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (item_id, start, label, category, minutes, protection, order, now, now),
        )
        g.db.commit()
        return jsonify({"ok": True, "budget_item_id": item_id}), 201

    @app.patch("/api/v1/time/budgets/<item_id>")
    def patch_time_budget(item_id: str):
        _require_row(g.db, "time_budget_items", item_id, "time budget item")
        payload = _json()
        allowed = {"label", "category", "weekly_minutes", "protection", "sort_order"}
        if not payload or set(payload) - allowed:
            raise ValidationError("invalid time budget patch fields")
        for field in ("label", "category"):
            if field in payload:
                payload[field] = str(payload[field]).strip()
                if not payload[field]:
                    raise ValidationError(f"{field} cannot be empty")
        if "weekly_minutes" in payload:
            payload["weekly_minutes"] = int(payload["weekly_minutes"])
            if payload["weekly_minutes"] < 0:
                raise ValidationError("weekly_minutes cannot be negative")
        if "protection" in payload and payload["protection"] not in {
            "committed",
            "protected",
            "flexible",
        }:
            raise ValidationError("invalid protection")
        payload["updated_at"] = db.utc_now()
        _update_fields(g.db, "time_budget_items", item_id, payload)
        return jsonify(
            {
                "ok": True,
                "budget_item": dict(
                    _require_row(g.db, "time_budget_items", item_id, "time budget item")
                ),
            }
        )

    @app.delete("/api/v1/time/budgets/<item_id>")
    def delete_time_budget(item_id: str):
        _require_row(g.db, "time_budget_items", item_id, "time budget item")
        used = g.db.execute(
            "SELECT COUNT(*) FROM time_entries WHERE budget_item_id=?", (item_id,)
        ).fetchone()[0]
        if used:
            raise ValidationError("budget item with time entries cannot be deleted")
        g.db.execute("DELETE FROM time_budget_items WHERE id=?", (item_id,))
        g.db.commit()
        return jsonify({"ok": True, "deleted": item_id})

    @app.get("/api/v1/time/entries")
    def list_time_entries():
        start = request.args.get("week_start", week_start_for(date.today()))
        day = parse_date(start, "week_start")
        end = day.fromordinal(day.toordinal() + 6).isoformat()
        rows = g.db.execute(
            """SELECT * FROM time_entries WHERE entry_date BETWEEN ? AND ?
               ORDER BY entry_date DESC,created_at DESC""",
            (start, end),
        )
        return jsonify({"ok": True, "entries": db.rows_dict(rows)})

    @app.post("/api/v1/<kind>/proposals")
    def preview(kind: str):
        proposal = preview_proposal(g.db, kind, _json())
        return jsonify({"ok": True, "proposal": proposal}), 201 if proposal[
            "status"
        ] == "pending" else 200

    @app.get("/api/v1/proposals")
    def list_proposals():
        status = request.args.get("status", "pending")
        if status not in {"pending", "committed"}:
            raise ValidationError("status must be pending or committed")
        rows = g.db.execute(
            "SELECT * FROM ledger_proposals WHERE status=? ORDER BY created_at DESC", (status,)
        )
        return jsonify({"ok": True, "proposals": [proposal_dict(row) for row in rows]})

    @app.get("/api/v1/proposals/<proposal_id>")
    def get_proposal(proposal_id: str):
        row = g.db.execute("SELECT * FROM ledger_proposals WHERE id=?", (proposal_id,)).fetchone()
        if not row:
            raise ValidationError("proposal not found")
        return jsonify({"ok": True, "proposal": proposal_dict(row)})

    @app.post("/api/v1/<kind>/proposals/<proposal_id>/commit")
    def commit(kind: str, proposal_id: str):
        row = g.db.execute(
            "SELECT kind FROM ledger_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
        if not row:
            raise ValidationError("proposal not found")
        if row["kind"] != kind:
            raise ValidationError("proposal kind does not match endpoint")
        return jsonify({"ok": True, "proposal": commit_proposal(g.db, proposal_id)})

    @app.post("/api/v1/budget-adjustments")
    def create_budget_adjustment():
        proposal = propose_budget_adjustment(g.db, _json())
        status = 201 if proposal["status"] == "pending" else 200
        return jsonify({"ok": True, "proposal": proposal}), status

    @app.get("/api/v1/budget-adjustments")
    def list_budget_adjustments():
        status = request.args.get("status", "pending")
        if status not in {"pending", "committed", "rejected"}:
            raise ValidationError("status must be pending, committed, or rejected")
        rows = g.db.execute(
            """SELECT * FROM budget_adjustment_proposals
               WHERE status=? ORDER BY created_at DESC""",
            (status,),
        )
        return jsonify(
            {"ok": True, "proposals": [budget_adjustment_dict(row) for row in rows]}
        )

    @app.post("/api/v1/budget-adjustments/<proposal_id>/<decision>")
    def decide_adjustment(proposal_id: str, decision: str):
        return jsonify(
            {
                "ok": True,
                "proposal": decide_budget_adjustment(g.db, proposal_id, decision),
            }
        )

    return app


def _json() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("JSON object required")
    return payload


def _task(conn, task_id: str) -> dict:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise ValidationError("task not found")
    return task_to_dict(row)


def _require_row(conn, table: str, item_id: str, label: str):
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
    if not row:
        raise ValidationError(f"{label} not found")
    return row


def _update_fields(conn, table: str, item_id: str, fields: dict) -> None:
    assignments = ",".join(f"{key}=?" for key in fields)
    conn.execute(f"UPDATE {table} SET {assignments} WHERE id=?", (*fields.values(), item_id))
    conn.commit()


def _validate_currency(value: str) -> None:
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValidationError("currency must be a three-letter ISO 4217 code")


def _currency_symbol(currency: str) -> str:
    return {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥"}.get(
        currency, f"{currency} "
    )


def _compact_money(value: str) -> str:
    whole, _, decimals = str(value).partition(".")
    rendered = f"{int(whole):,}"
    return rendered if decimals == "00" else f"{rendered}.{decimals}"


def _duration(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours}h {rest}m"
    if hours:
        return f"{hours}h"
    return f"{rest}m"
