from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .db import json_text, new_id, row_dict, rows_dict, transaction, utc_now


class ValidationError(ValueError):
    pass


def parse_date(value: str, field: str = "date") -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be YYYY-MM-DD") from exc


def week_start_for(value: str | date) -> str:
    day = parse_date(value) if isinstance(value, str) else value
    return (day - timedelta(days=day.weekday())).isoformat()


def month_for(value: str | date) -> str:
    day = parse_date(value) if isinstance(value, str) else value
    return day.isoformat()[:7]


def amount_to_minor(value) -> int:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError("amount must be a number") from exc
    if amount <= 0:
        raise ValidationError("amount must be greater than zero")
    return int(amount * 100)


def minor_to_amount(value: int) -> str:
    return f"{Decimal(value) / 100:.2f}"


def _money_account(conn, account_id: str) -> dict:
    row = conn.execute("SELECT * FROM money_accounts WHERE id=?", (account_id,)).fetchone()
    if not row:
        raise ValidationError(f"unknown account_id: {account_id}")
    return dict(row)


def _money_budget(conn, item_id: str | None) -> dict | None:
    if not item_id:
        return None
    row = conn.execute("SELECT * FROM money_budget_items WHERE id=?", (item_id,)).fetchone()
    if not row:
        raise ValidationError(f"unknown budget_item_id: {item_id}")
    return dict(row)


def normalize_money(conn: sqlite3.Connection, payload: dict) -> dict:
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("entries must be a non-empty array")
    normalized = []
    impact: dict[str, int] = {}
    seen_external_ids: set[str] = set()
    for index, raw in enumerate(entries):
        if not isinstance(raw, dict):
            raise ValidationError(f"entry {index} must be an object")
        kind = str(raw.get("kind", "")).lower()
        if kind not in {"expense", "income", "refund", "transfer"}:
            raise ValidationError(f"entry {index} has invalid kind")
        account = _money_account(conn, str(raw.get("account_id", "")))
        requested_currency = str(raw.get("currency", account["currency"])).upper()
        if requested_currency != account["currency"]:
            raise ValidationError("entry currency must match the selected account")
        to_account = None
        if kind == "transfer":
            to_account = _money_account(conn, str(raw.get("to_account_id", "")))
            if to_account["id"] == account["id"]:
                raise ValidationError(f"entry {index} transfer accounts must differ")
            if to_account["currency"] != account["currency"]:
                raise ValidationError("v1 transfers must use the same currency")
        elif raw.get("to_account_id"):
            raise ValidationError(f"entry {index} to_account_id is transfer-only")
        if kind == "income" and account["account_type"] != "asset":
            raise ValidationError("income must enter an asset account")

        occurred_on = str(raw.get("occurred_on", ""))
        parse_date(occurred_on, "occurred_on")
        amount_minor = amount_to_minor(raw.get("amount"))
        category = str(raw.get("category", "")).strip()
        note = str(raw.get("note", "")).strip()
        if not category or not note:
            raise ValidationError(f"entry {index} needs category and note")
        budget = _money_budget(conn, raw.get("budget_item_id"))
        if budget:
            if budget["currency"] != account["currency"]:
                raise ValidationError("budget and account currencies must match")
            if budget["category"] != category:
                raise ValidationError("category must match the selected budget item")
            if budget["month"] != occurred_on[:7]:
                raise ValidationError("transaction date must fall in the budget month")

        external_id = str(raw.get("external_id", "")).strip() or None
        if external_id and external_id in seen_external_ids:
            raise ValidationError(f"duplicate external_id in proposal: {external_id}")
        if external_id:
            seen_external_ids.add(external_id)
        item = {
            "external_id": external_id,
            "occurred_on": occurred_on,
            "kind": kind,
            "account_id": account["id"],
            "to_account_id": to_account["id"] if to_account else None,
            "amount_minor": amount_minor,
            "amount": minor_to_amount(amount_minor),
            "currency": account["currency"],
            "category": category,
            "budget_item_id": budget["id"] if budget else None,
            "note": note,
        }
        existing = None
        if external_id:
            existing = conn.execute(
                "SELECT * FROM money_transactions WHERE external_id=?", (external_id,)
            ).fetchone()
        if existing:
            compared = {
                "occurred_on": existing["occurred_on"],
                "kind": existing["kind"],
                "account_id": existing["account_id"],
                "to_account_id": existing["to_account_id"],
                "amount_minor": existing["amount_minor"],
                "currency": existing["currency"],
                "category": existing["category"],
                "budget_item_id": existing["budget_item_id"],
                "note": existing["note"],
            }
            if any(item[key] != value for key, value in compared.items()):
                raise ValidationError(
                    f"external_id already has different money data: {external_id}"
                )
            item["duplicate"] = True
            normalized.append(item)
            continue
        normalized.append(item)
        for account_id, delta in money_deltas(item, account, to_account).items():
            impact[account_id] = impact.get(account_id, 0) + delta

    for account_id, delta in impact.items():
        account = _money_account(conn, account_id)
        if account["balance_minor"] + delta < 0:
            raise ValidationError(f"proposal would make {account_id} negative")
    return {
        "entries": normalized,
        "account_impact": [
            {
                "account_id": key,
                "delta_minor": value,
                "delta": minor_to_amount(abs(value)),
                "direction": "+" if value >= 0 else "-",
            }
            for key, value in sorted(impact.items())
        ],
    }


def money_deltas(item: dict, account: dict, to_account: dict | None) -> dict[str, int]:
    amount = item["amount_minor"]
    kind = item["kind"]
    if kind == "expense":
        return {account["id"]: -amount if account["account_type"] == "asset" else amount}
    if kind == "income":
        return {account["id"]: amount}
    if kind == "refund":
        return {account["id"]: amount if account["account_type"] == "asset" else -amount}
    return {
        account["id"]: -amount if account["account_type"] == "asset" else amount,
        to_account["id"]: amount if to_account["account_type"] == "asset" else -amount,
    }


def normalize_time(conn: sqlite3.Connection, payload: dict) -> dict:
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("entries must be a non-empty array")
    normalized = []
    clock_groups = set()
    new_clock_by_date: dict[str, int] = {}
    seen_external_ids: set[str] = set()
    for index, raw in enumerate(entries):
        if not isinstance(raw, dict):
            raise ValidationError(f"entry {index} must be an object")
        entry_date = str(raw.get("date", ""))
        parse_date(entry_date)
        try:
            minutes = int(raw.get("minutes"))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"entry {index} minutes must be an integer") from exc
        if minutes <= 0:
            raise ValidationError(f"entry {index} minutes must be positive")
        activity = str(raw.get("activity", "")).strip()
        if not activity:
            raise ValidationError(f"entry {index} needs activity")
        counts = raw.get("counts_toward_clock", True)
        if not isinstance(counts, bool):
            raise ValidationError("counts_toward_clock must be true or false")
        overlap_group = str(raw.get("overlap_group", "")).strip() or None
        if not counts and not overlap_group:
            raise ValidationError("non-clock allocation needs overlap_group")
        budget_item_id = str(raw.get("budget_item_id", "")).strip() or None
        unbudgeted = raw.get("unbudgeted", False)
        if budget_item_id:
            budget = conn.execute(
                "SELECT * FROM time_budget_items WHERE id=?", (budget_item_id,)
            ).fetchone()
            if not budget:
                raise ValidationError(f"unknown budget_item_id: {budget_item_id}")
            if week_start_for(entry_date) != budget["week_start"]:
                raise ValidationError("time entry date must fall in the budget week")
            unbudgeted = False
        elif unbudgeted is not True:
            raise ValidationError("entry needs budget_item_id or unbudgeted: true")
        external_id = str(raw.get("external_id", "")).strip() or None
        if external_id and external_id in seen_external_ids:
            raise ValidationError(f"duplicate external_id in proposal: {external_id}")
        if external_id:
            seen_external_ids.add(external_id)
        item = {
            "external_id": external_id,
            "date": entry_date,
            "minutes": minutes,
            "budget_item_id": budget_item_id,
            "activity": activity,
            "counts_toward_clock": counts,
            "overlap_group": overlap_group,
            "unbudgeted": bool(unbudgeted),
            "note": str(raw.get("note", "")).strip(),
        }
        existing = None
        if external_id:
            existing = conn.execute(
                "SELECT * FROM time_entries WHERE external_id=?", (external_id,)
            ).fetchone()
        if existing:
            compared = {
                "date": existing["entry_date"],
                "minutes": existing["minutes"],
                "budget_item_id": existing["budget_item_id"],
                "activity": existing["activity"],
                "counts_toward_clock": bool(existing["counts_toward_clock"]),
                "overlap_group": existing["overlap_group"],
                "unbudgeted": bool(existing["unbudgeted"]),
                "note": existing["note"],
            }
            if any(item[key] != value for key, value in compared.items()):
                raise ValidationError(f"external_id already has different time data: {external_id}")
            item["duplicate"] = True
            normalized.append(item)
            continue
        normalized.append(item)
        if counts:
            new_clock_by_date[entry_date] = new_clock_by_date.get(entry_date, 0) + minutes
            if overlap_group:
                clock_groups.add((entry_date, overlap_group))
    for item in normalized:
        if item.get("duplicate"):
            continue
        if (
            not item["counts_toward_clock"]
            and (item["date"], item["overlap_group"]) not in clock_groups
        ):
            raise ValidationError("overlap allocation needs a clock-counted peer in the same batch")
    for entry_date, minutes in new_clock_by_date.items():
        existing = conn.execute(
            """SELECT COALESCE(SUM(minutes),0) FROM time_entries
               WHERE entry_date=? AND counts_toward_clock=1""",
            (entry_date,),
        ).fetchone()[0]
        if existing + minutes > 1440:
            raise ValidationError(f"clock time exceeds 24 hours on {entry_date}")
    return {
        "entries": normalized,
        "clock_minutes": sum(x["minutes"] for x in normalized if x["counts_toward_clock"]),
        "allocation_minutes": sum(x["minutes"] for x in normalized),
        "overlap_minutes": sum(x["minutes"] for x in normalized if not x["counts_toward_clock"]),
    }


def preview_proposal(conn: sqlite3.Connection, kind: str, payload: dict) -> dict:
    if kind not in {"money", "time"}:
        raise ValidationError("kind must be money or time")
    preview = normalize_money(conn, payload) if kind == "money" else normalize_time(conn, payload)
    canonical = json_text({"kind": kind, "payload": payload})
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    existing = conn.execute(
        "SELECT * FROM ledger_proposals WHERE kind=? AND payload_hash=?", (kind, digest)
    ).fetchone()
    if existing:
        return proposal_dict(existing)
    proposal_id = new_id("proposal")
    now = utc_now()
    conn.execute(
        """INSERT INTO ledger_proposals
           (id,kind,status,payload_hash,payload_json,preview_json,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (proposal_id, kind, "pending", digest, json_text(payload), json_text(preview), now),
    )
    conn.commit()
    return proposal_dict(
        conn.execute("SELECT * FROM ledger_proposals WHERE id=?", (proposal_id,)).fetchone()
    )


def proposal_dict(row) -> dict:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    item["preview"] = json.loads(item.pop("preview_json"))
    result = item.pop("result_json")
    item["result"] = json.loads(result) if result else None
    item.pop("payload_hash", None)
    return item


def commit_proposal(conn: sqlite3.Connection, proposal_id: str) -> dict:
    row = conn.execute("SELECT * FROM ledger_proposals WHERE id=?", (proposal_id,)).fetchone()
    if not row:
        raise ValidationError("proposal not found")
    if row["status"] == "committed":
        return proposal_dict(row)
    payload = json.loads(row["payload_json"])
    preview = (
        normalize_money(conn, payload) if row["kind"] == "money" else normalize_time(conn, payload)
    )
    created_ids = []
    now = utc_now()
    with transaction(conn):
        if row["kind"] == "money":
            for item in preview["entries"]:
                duplicate = None
                if item["external_id"]:
                    duplicate = conn.execute(
                        "SELECT id FROM money_transactions WHERE external_id=?",
                        (item["external_id"],),
                    ).fetchone()
                if duplicate:
                    created_ids.append(duplicate["id"])
                    continue
                account = _money_account(conn, item["account_id"])
                to_account = (
                    _money_account(conn, item["to_account_id"]) if item["to_account_id"] else None
                )
                for account_id, delta in money_deltas(item, account, to_account).items():
                    conn.execute(
                        """UPDATE money_accounts
                           SET balance_minor=balance_minor+?, updated_at=? WHERE id=?""",
                        (delta, now, account_id),
                    )
                item_id = new_id("txn")
                conn.execute(
                    """INSERT INTO money_transactions
                       (id,external_id,occurred_on,kind,account_id,to_account_id,amount_minor,currency,
                        category,budget_item_id,note,proposal_id,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item_id,
                        item["external_id"],
                        item["occurred_on"],
                        item["kind"],
                        item["account_id"],
                        item["to_account_id"],
                        item["amount_minor"],
                        item["currency"],
                        item["category"],
                        item["budget_item_id"],
                        item["note"],
                        proposal_id,
                        now,
                    ),
                )
                created_ids.append(item_id)
        else:
            for item in preview["entries"]:
                duplicate = None
                if item["external_id"]:
                    duplicate = conn.execute(
                        "SELECT id FROM time_entries WHERE external_id=?", (item["external_id"],)
                    ).fetchone()
                if duplicate:
                    created_ids.append(duplicate["id"])
                    continue
                item_id = new_id("time")
                conn.execute(
                    """INSERT INTO time_entries
                       (id,external_id,entry_date,minutes,budget_item_id,activity,counts_toward_clock,
                        overlap_group,unbudgeted,note,proposal_id,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item_id,
                        item["external_id"],
                        item["date"],
                        item["minutes"],
                        item["budget_item_id"],
                        item["activity"],
                        int(item["counts_toward_clock"]),
                        item["overlap_group"],
                        int(item["unbudgeted"]),
                        item["note"],
                        proposal_id,
                        now,
                    ),
                )
                created_ids.append(item_id)
        result = {"created_ids": created_ids, "entry_count": len(created_ids)}
        conn.execute(
            """UPDATE ledger_proposals
               SET status='committed', result_json=?, committed_at=? WHERE id=?""",
            (json_text(result), now, proposal_id),
        )
    return proposal_dict(
        conn.execute("SELECT * FROM ledger_proposals WHERE id=?", (proposal_id,)).fetchone()
    )


def _adjustment_evidence(payload: dict) -> dict:
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise ValidationError("evidence must be an object")
    summary = str(evidence.get("summary", "")).strip()
    alternative = str(evidence.get("alternative", "")).strip()
    try:
        observed_periods = int(evidence.get("observed_periods"))
    except (TypeError, ValueError) as exc:
        raise ValidationError("evidence.observed_periods must be a positive integer") from exc
    if not summary or not alternative or observed_periods <= 0:
        raise ValidationError(
            "evidence needs summary, positive observed_periods, and an alternative"
        )
    return {
        "summary": summary,
        "observed_periods": observed_periods,
        "alternative": alternative,
    }


def normalize_budget_adjustment(conn: sqlite3.Connection, payload: dict) -> dict:
    kind = str(payload.get("kind", "")).lower()
    action = str(payload.get("action", "")).lower()
    if kind not in {"money", "time"}:
        raise ValidationError("kind must be money or time")
    if action not in {"create", "resize", "retire"}:
        raise ValidationError("action must be create, resize, or retire")
    evidence = _adjustment_evidence(payload)
    change = payload.get("change")
    if not isinstance(change, dict):
        raise ValidationError("change must be an object")

    table = "money_budget_items" if kind == "money" else "time_budget_items"
    target_id = str(payload.get("target_id", "")).strip() or None
    before = None
    if action != "create":
        if not target_id:
            raise ValidationError("target_id is required for resize or retire")
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (target_id,)).fetchone()
        if not row:
            raise ValidationError(f"unknown {kind} budget target: {target_id}")
        before = dict(row)

    if kind == "money":
        if action == "create":
            month = str(change.get("month", ""))
            if not re.fullmatch(r"\d{4}-\d{2}", month):
                raise ValidationError("change.month must be YYYY-MM")
            title = str(change.get("title", "")).strip()
            category = str(change.get("category", "")).strip()
            direction = str(change.get("direction", "expense"))
            currency = str(change.get("currency", "")).upper()
            if not title or not category or len(currency) != 3:
                raise ValidationError("money create needs title, category, and 3-letter currency")
            if direction not in {"expense", "income"}:
                raise ValidationError("direction must be expense or income")
            after = {
                "month": month,
                "title": title,
                "category": category,
                "direction": direction,
                "amount_minor": amount_to_minor(change.get("amount")),
                "currency": currency,
            }
        elif action == "resize":
            after = {**before, "amount_minor": amount_to_minor(change.get("amount"))}
        else:
            used = conn.execute(
                "SELECT COUNT(*) FROM money_transactions WHERE budget_item_id=?", (target_id,)
            ).fetchone()[0]
            if used:
                raise ValidationError("money budget item with transactions cannot be retired")
            after = None
        scope = after or before
        total_before = conn.execute(
            """SELECT COALESCE(SUM(amount_minor),0) FROM money_budget_items
               WHERE month=? AND currency=? AND direction=?""",
            (scope["month"], scope["currency"], scope["direction"]),
        ).fetchone()[0]
        old_amount = before["amount_minor"] if before else 0
        new_amount = after["amount_minor"] if after else 0
        total_after = total_before - old_amount + new_amount
        total = {
            "unit": f"minor-{scope['currency']}",
            "scope": f"{scope['month']}:{scope['direction']}",
            "before": total_before,
            "after": total_after,
            "delta": total_after - total_before,
        }
    else:
        if action == "create":
            week_start = str(change.get("week_start", ""))
            if parse_date(week_start, "change.week_start").weekday() != 0:
                raise ValidationError("change.week_start must be a Monday")
            label = str(change.get("label", "")).strip()
            category = str(change.get("category", "")).strip()
            protection = str(change.get("protection", "flexible"))
            if not label or not category:
                raise ValidationError("time create needs label and category")
            if protection not in {"committed", "protected", "flexible"}:
                raise ValidationError("invalid protection")
            try:
                minutes = int(change.get("weekly_minutes"))
            except (TypeError, ValueError) as exc:
                raise ValidationError("weekly_minutes must be an integer") from exc
            if minutes < 0:
                raise ValidationError("weekly_minutes cannot be negative")
            after = {
                "week_start": week_start,
                "label": label,
                "category": category,
                "weekly_minutes": minutes,
                "protection": protection,
            }
        elif action == "resize":
            try:
                minutes = int(change.get("weekly_minutes"))
            except (TypeError, ValueError) as exc:
                raise ValidationError("weekly_minutes must be an integer") from exc
            if minutes < 0:
                raise ValidationError("weekly_minutes cannot be negative")
            after = {**before, "weekly_minutes": minutes}
        else:
            used = conn.execute(
                "SELECT COUNT(*) FROM time_entries WHERE budget_item_id=?", (target_id,)
            ).fetchone()[0]
            if used:
                raise ValidationError("time budget item with entries cannot be retired")
            after = None
        scope = after or before
        total_before = conn.execute(
            "SELECT COALESCE(SUM(weekly_minutes),0) FROM time_budget_items WHERE week_start=?",
            (scope["week_start"],),
        ).fetchone()[0]
        old_minutes = before["weekly_minutes"] if before else 0
        new_minutes = after["weekly_minutes"] if after else 0
        total_after = total_before - old_minutes + new_minutes
        if total_after > 7 * 24 * 60:
            raise ValidationError("proposed weekly time budget exceeds 168 hours")
        total = {
            "unit": "minutes",
            "scope": scope["week_start"],
            "before": total_before,
            "after": total_after,
            "delta": total_after - total_before,
        }
    return {
        "kind": kind,
        "action": action,
        "target_id": target_id,
        "before": before,
        "after": after,
        "total_effect": total,
        "evidence": evidence,
    }


def budget_adjustment_dict(row) -> dict:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    item["preview"] = json.loads(item.pop("preview_json"))
    result = item.pop("result_json")
    item["result"] = json.loads(result) if result else None
    item.pop("payload_hash", None)
    return item


def propose_budget_adjustment(conn: sqlite3.Connection, payload: dict) -> dict:
    preview = normalize_budget_adjustment(conn, payload)
    canonical = json_text(payload)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    existing = conn.execute(
        "SELECT * FROM budget_adjustment_proposals WHERE payload_hash=?", (digest,)
    ).fetchone()
    if existing:
        return budget_adjustment_dict(existing)
    proposal_id = new_id("budget_adjustment")
    conn.execute(
        """INSERT INTO budget_adjustment_proposals
           (id,kind,action,status,payload_hash,payload_json,preview_json,created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            proposal_id,
            preview["kind"],
            preview["action"],
            "pending",
            digest,
            json_text(payload),
            json_text(preview),
            utc_now(),
        ),
    )
    conn.commit()
    return budget_adjustment_dict(
        conn.execute(
            "SELECT * FROM budget_adjustment_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
    )


def decide_budget_adjustment(
    conn: sqlite3.Connection, proposal_id: str, decision: str
) -> dict:
    if decision not in {"commit", "reject"}:
        raise ValidationError("decision must be commit or reject")
    row = conn.execute(
        "SELECT * FROM budget_adjustment_proposals WHERE id=?", (proposal_id,)
    ).fetchone()
    if not row:
        raise ValidationError("budget adjustment proposal not found")
    if row["status"] != "pending":
        return budget_adjustment_dict(row)
    now = utc_now()
    if decision == "reject":
        conn.execute(
            """UPDATE budget_adjustment_proposals
               SET status='rejected',result_json=?,decided_at=? WHERE id=?""",
            (json_text({"decision": "rejected"}), now, proposal_id),
        )
        conn.commit()
        return budget_adjustment_dict(
            conn.execute(
                "SELECT * FROM budget_adjustment_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
        )

    payload = json.loads(row["payload_json"])
    stored_preview = json.loads(row["preview_json"])
    with transaction(conn):
        current_preview = normalize_budget_adjustment(conn, payload)
        if current_preview != stored_preview:
            raise ValidationError("budget state changed after proposal; create a fresh review")
        after = current_preview["after"]
        kind = current_preview["kind"]
        action = current_preview["action"]
        target_id = current_preview["target_id"]
        table = "money_budget_items" if kind == "money" else "time_budget_items"
        if action == "retire":
            conn.execute(f"DELETE FROM {table} WHERE id=?", (target_id,))
            changed_id = target_id
        elif action == "resize":
            field = "amount_minor" if kind == "money" else "weekly_minutes"
            conn.execute(
                f"UPDATE {table} SET {field}=?,updated_at=? WHERE id=?",
                (after[field], now, target_id),
            )
            changed_id = target_id
        else:
            changed_id = new_id(f"{kind}_budget")
            order = conn.execute(
                f"SELECT COALESCE(MAX(sort_order),-1)+1 FROM {table}"
            ).fetchone()[0]
            if kind == "money":
                conn.execute(
                    """INSERT INTO money_budget_items
                       (id,month,title,category,direction,amount_minor,currency,sort_order,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        changed_id,
                        after["month"],
                        after["title"],
                        after["category"],
                        after["direction"],
                        after["amount_minor"],
                        after["currency"],
                        order,
                        now,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO time_budget_items
                       (id,week_start,label,category,weekly_minutes,protection,sort_order,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        changed_id,
                        after["week_start"],
                        after["label"],
                        after["category"],
                        after["weekly_minutes"],
                        after["protection"],
                        order,
                        now,
                        now,
                    ),
                )
        result = {"decision": "committed", "changed_id": changed_id}
        conn.execute(
            """UPDATE budget_adjustment_proposals
               SET status='committed',result_json=?,decided_at=? WHERE id=?""",
            (json_text(result), now, proposal_id),
        )
    return budget_adjustment_dict(
        conn.execute(
            "SELECT * FROM budget_adjustment_proposals WHERE id=?", (proposal_id,)
        ).fetchone()
    )


def money_overview(conn: sqlite3.Connection, month: str, currency: str) -> dict:
    if len(month) != 7:
        raise ValidationError("month must be YYYY-MM")
    accounts = rows_dict(
        conn.execute(
            "SELECT * FROM money_accounts WHERE currency=? ORDER BY sort_order,name", (currency,)
        )
    )
    for account in accounts:
        account["balance"] = minor_to_amount(account["balance_minor"])
    budgets = rows_dict(
        conn.execute(
            """SELECT * FROM money_budget_items
               WHERE month=? AND currency=? ORDER BY sort_order,title""",
            (month, currency),
        )
    )
    entries = rows_dict(
        conn.execute(
            """SELECT * FROM money_transactions
               WHERE substr(occurred_on,1,7)=? AND currency=?
               ORDER BY occurred_on DESC, created_at DESC""",
            (month, currency),
        )
    )
    actual_by_category: dict[str, int] = {}
    income_actual = 0
    for entry in entries:
        entry["amount"] = minor_to_amount(entry["amount_minor"])
        if entry["kind"] == "expense":
            actual_by_category[entry["category"]] = (
                actual_by_category.get(entry["category"], 0) + entry["amount_minor"]
            )
        elif entry["kind"] == "refund":
            actual_by_category[entry["category"]] = (
                actual_by_category.get(entry["category"], 0) - entry["amount_minor"]
            )
        elif entry["kind"] == "income":
            income_actual += entry["amount_minor"]
    expense_budget = 0
    income_planned = 0
    categories = []
    planned_categories = set()
    for item in budgets:
        item["amount"] = minor_to_amount(item["amount_minor"])
        if item["direction"] == "expense":
            planned_categories.add(item["category"])
            expense_budget += item["amount_minor"]
            actual = actual_by_category.get(item["category"], 0)
            remaining = item["amount_minor"] - actual
            categories.append(
                {
                    **item,
                    "actual_minor": actual,
                    "actual": minor_to_amount(actual),
                    "remaining_minor": remaining,
                    "remaining": minor_to_amount(abs(remaining)),
                    "over": remaining < 0,
                }
            )
        else:
            income_planned += item["amount_minor"]
    for category, actual in actual_by_category.items():
        if category in planned_categories:
            continue
        categories.append(
            {
                "id": None,
                "title": category.replace("_", " ").title(),
                "category": category,
                "direction": "expense",
                "amount_minor": 0,
                "amount": "0.00",
                "actual_minor": actual,
                "actual": minor_to_amount(actual),
                "remaining_minor": -actual,
                "remaining": minor_to_amount(abs(actual)),
                "over": actual > 0,
            }
        )
    expense_actual = sum(actual_by_category.values())
    asset_total = sum(a["balance_minor"] for a in accounts if a["account_type"] == "asset")
    liability_total = sum(a["balance_minor"] for a in accounts if a["account_type"] == "liability")
    return {
        "month": month,
        "currency": currency,
        "accounts": accounts,
        "net_worth_minor": asset_total - liability_total,
        "net_worth": minor_to_amount(asset_total - liability_total),
        "expense_budget_minor": expense_budget,
        "expense_budget": minor_to_amount(expense_budget),
        "expense_actual_minor": expense_actual,
        "expense_actual": minor_to_amount(expense_actual),
        "expense_remaining_minor": expense_budget - expense_actual,
        "expense_remaining": minor_to_amount(expense_budget - expense_actual),
        "income_planned": minor_to_amount(income_planned),
        "income_actual": minor_to_amount(income_actual),
        "categories": categories,
        "transactions": entries,
    }


def _time_consumption(
    items: list[dict],
    entries: list[dict],
    *,
    start: date,
    end: date,
    as_of: date,
) -> dict:
    """Build a screen-time-style physical ranking with neutral budget pace signals."""
    physical_by_id: dict[str, int] = {}
    allocation_by_id: dict[str, int] = {}
    for entry in entries:
        key = entry["budget_item_id"] or "unbudgeted"
        allocation_by_id[key] = allocation_by_id.get(key, 0) + entry["minutes"]
        if entry["counts_toward_clock"]:
            physical_by_id[key] = physical_by_id.get(key, 0) + entry["minutes"]

    if as_of < start:
        elapsed_minutes = 0
    elif as_of > end:
        elapsed_minutes = 7 * 24 * 60
    else:
        elapsed_minutes = ((as_of - start).days + 1) * 24 * 60
    week_progress = elapsed_minutes / (7 * 24 * 60) if elapsed_minutes else 0

    def pace(actual: int, planned: int) -> tuple[str, int]:
        if not planned:
            return "unbudgeted", 0
        expected = round(planned * week_progress)
        delta = actual - expected
        tolerance = max(30, round(expected * 0.2))
        if delta > tolerance:
            return "above", delta
        if delta < -tolerance:
            return "below", delta
        return "on_pace", delta

    total_physical = sum(physical_by_id.values())

    def with_pace(row: dict) -> dict:
        status, delta = pace(row["allocation_minutes"], row["planned_minutes"])
        return {**row, "pace_status": status, "pace_delta_minutes": delta}

    def summarize(rows: list[dict]) -> dict:
        pace_rows = [with_pace(row) for row in rows]
        ranking = sorted(
            (row for row in pace_rows if row["physical_minutes"] > 0),
            key=lambda row: (-row["physical_minutes"], row["label"]),
        )
        largest = max((row["physical_minutes"] for row in ranking), default=0)
        for index, row in enumerate(ranking, start=1):
            row.update(
                {
                    "rank": index,
                    "share_percent": round(row["physical_minutes"] / total_physical * 100)
                    if total_physical
                    else 0,
                    "bar_percent": round(row["physical_minutes"] / largest * 100)
                    if largest
                    else 0,
                }
            )
        above = [row for row in pace_rows if row["pace_status"] == "above"]
        below = [row for row in pace_rows if row["pace_status"] == "below"]
        top_three = sum(row["physical_minutes"] for row in ranking[:3])
        return {
            "ranking": ranking,
            "top": ranking[0] if ranking else None,
            "top_three_share_percent": round(top_three / total_physical * 100)
            if total_physical
            else 0,
            "largest_above_pace": max(
                above, key=lambda row: row["pace_delta_minutes"], default=None
            ),
            "largest_below_pace": min(
                below, key=lambda row: row["pace_delta_minutes"], default=None
            ),
        }

    item_rows = []
    for item in items:
        physical = physical_by_id.get(item["id"], 0)
        allocation = allocation_by_id.get(item["id"], 0)
        item_rows.append(
            {
                "budget_item_id": item["id"],
                "label": item["label"],
                "category": item["category"],
                "category_label": item["category"].replace("_", " ").title(),
                "protection": item["protection"],
                "physical_minutes": physical,
                "allocation_minutes": allocation,
                "overlap_credit_minutes": max(0, allocation - physical),
                "planned_minutes": item["weekly_minutes"],
            }
        )
    if "unbudgeted" in allocation_by_id:
        item_rows.append(
            {
                "budget_item_id": None,
                "label": "Unbudgeted",
                "category": "uncategorized",
                "category_label": "Uncategorized",
                "protection": "unbudgeted",
                "physical_minutes": physical_by_id.get("unbudgeted", 0),
                "allocation_minutes": allocation_by_id["unbudgeted"],
                "overlap_credit_minutes": max(
                    0,
                    allocation_by_id["unbudgeted"]
                    - physical_by_id.get("unbudgeted", 0),
                ),
                "planned_minutes": 0,
            }
        )

    categories: dict[str, dict] = {}
    for item in items:
        key = item["category"] or "uncategorized"
        group = categories.setdefault(
            key,
            {
                "category": key,
                "label": key.replace("_", " ").title(),
                "physical_minutes": 0,
                "allocation_minutes": 0,
                "planned_minutes": 0,
                "item_labels": [],
            },
        )
        group["physical_minutes"] += physical_by_id.get(item["id"], 0)
        group["allocation_minutes"] += allocation_by_id.get(item["id"], 0)
        group["planned_minutes"] += item["weekly_minutes"]
        group["item_labels"].append(item["label"])
    category_rows = []
    for group in categories.values():
        category_rows.append(
            {
                **group,
                "item_count": len(group["item_labels"]),
                "overlap_credit_minutes": max(
                    0, group["allocation_minutes"] - group["physical_minutes"]
                ),
            }
        )
    if "unbudgeted" in allocation_by_id:
        category_rows.append(
            {
                "category": "uncategorized",
                "label": "Uncategorized",
                "physical_minutes": physical_by_id.get("unbudgeted", 0),
                "allocation_minutes": allocation_by_id["unbudgeted"],
                "planned_minutes": 0,
                "item_labels": ["Unbudgeted"],
                "item_count": 1,
                "overlap_credit_minutes": max(
                    0,
                    allocation_by_id["unbudgeted"]
                    - physical_by_id.get("unbudgeted", 0),
                ),
            }
        )

    return {
        "default_view": "categories",
        "views": {
            "categories": summarize(category_rows),
            "items": summarize(item_rows),
        },
        "elapsed_minutes": elapsed_minutes,
        "explained_minutes": total_physical,
        "unexplained_minutes": max(0, elapsed_minutes - total_physical),
        "coverage_available": elapsed_minutes > 0,
        "coverage_percent": min(100, round(total_physical / elapsed_minutes * 100))
        if elapsed_minutes
        else 0,
        "week_progress_percent": round(week_progress * 100),
    }


def time_overview(
    conn: sqlite3.Connection, week_start: str, as_of: str | date | None = None
) -> dict:
    start = parse_date(week_start, "week_start")
    if start.weekday() != 0:
        raise ValidationError("week_start must be a Monday")
    end = start + timedelta(days=6)
    items = rows_dict(
        conn.execute(
            "SELECT * FROM time_budget_items WHERE week_start=? ORDER BY sort_order,label",
            (week_start,),
        )
    )
    entries = rows_dict(
        conn.execute(
            """SELECT * FROM time_entries WHERE entry_date BETWEEN ? AND ?
           ORDER BY entry_date DESC, created_at DESC""",
            (week_start, end.isoformat()),
        )
    )
    actual_by_item: dict[str, int] = {}
    for entry in entries:
        if entry["budget_item_id"]:
            actual_by_item[entry["budget_item_id"]] = (
                actual_by_item.get(entry["budget_item_id"], 0) + entry["minutes"]
            )
    for item in items:
        actual = actual_by_item.get(item["id"], 0)
        item["actual_minutes"] = actual
        item["remaining_minutes"] = item["weekly_minutes"] - actual
    planned = sum(item["weekly_minutes"] for item in items)
    clock = sum(entry["minutes"] for entry in entries if entry["counts_toward_clock"])
    allocation = sum(entry["minutes"] for entry in entries)
    unbudgeted = sum(entry["minutes"] for entry in entries if entry["unbudgeted"])
    consumption = _time_consumption(
        items,
        entries,
        start=start,
        end=end,
        as_of=parse_date(as_of) if isinstance(as_of, str) else as_of or date.today(),
    )
    return {
        "week_start": week_start,
        "week_end": end.isoformat(),
        "planned_minutes": planned,
        "clock_minutes": clock,
        "allocation_minutes": allocation,
        "overlap_minutes": allocation - clock,
        "unbudgeted_minutes": unbudgeted,
        "physical_whitespace_minutes": 7 * 24 * 60 - clock,
        "consumption": consumption,
        "items": items,
        "entries": entries,
    }


def task_to_dict(row) -> dict:
    return row_dict(row)


def context_today(conn: sqlite3.Connection, date_iso: str, currency: str) -> dict:
    day = parse_date(date_iso)
    focus = row_dict(
        conn.execute("SELECT * FROM daily_focus WHERE focus_date=?", (date_iso,)).fetchone()
    )
    tasks = rows_dict(
        conn.execute(
            """SELECT * FROM tasks ORDER BY status='done',
           CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
           sort_order, created_at"""
        )
    )
    proposals = rows_dict(
        conn.execute(
            """SELECT id,kind,status,created_at FROM ledger_proposals
               WHERE status='pending' ORDER BY created_at DESC"""
        )
    )
    return {
        "date": date_iso,
        "focus": focus,
        "tasks": tasks,
        "time": time_overview(conn, week_start_for(day), day),
        "money": money_overview(conn, month_for(day), currency),
        "pending_proposals": proposals,
    }
