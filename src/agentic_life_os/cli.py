from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path


def request_json(base_url: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.load(error)
        except json.JSONDecodeError:
            detail = {"error": str(error)}
        raise SystemExit(json.dumps(detail, indent=2)) from error
    except urllib.error.URLError as error:
        raise SystemExit(f"Cannot reach Agentic Life OS at {base_url}: {error.reason}") from error


def read_payload(path: str) -> dict:
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Could not read JSON payload {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit("Batch payload must be a JSON object")
    today = date.today().isoformat()

    def replace_tokens(item):
        if isinstance(item, dict):
            return {key: replace_tokens(nested) for key, nested in item.items()}
        if isinstance(item, list):
            return [replace_tokens(nested) for nested in item]
        if isinstance(item, str) and "$TODAY" in item:
            return item.replace("$TODAY", today)
        return item

    return replace_tokens(value)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="lifeos", description="Agentic Life OS JSON CLI")
    root.add_argument(
        "--url",
        default=os.environ.get("LIFEOS_URL", "http://127.0.0.1:5050"),
        help="Life OS base URL",
    )
    commands = root.add_subparsers(dest="command", required=True)
    context = commands.add_parser("context", help="Read the combined Today context")
    context.add_argument("--date", default=date.today().isoformat())

    task = commands.add_parser("task", help="Manage actionables")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    task_commands.add_parser("list")
    add = task_commands.add_parser("add")
    add.add_argument("title")
    add.add_argument("--notes", default="")
    add.add_argument("--priority", choices=["low", "medium", "high"], default="medium")
    add.add_argument("--due-date")
    add.add_argument("--minutes", type=int)
    for action in ("complete", "reopen", "delete"):
        sub = task_commands.add_parser(action)
        sub.add_argument("task_id")

    focus = commands.add_parser("focus", help="Set the daily focus")
    focus_commands = focus.add_subparsers(dest="focus_command", required=True)
    set_focus = focus_commands.add_parser("set")
    set_focus.add_argument("headline")
    set_focus.add_argument("--brief", default="")
    set_focus.add_argument("--date", default=date.today().isoformat())

    for kind in ("money", "time"):
        ledger = commands.add_parser(kind, help=f"Read or propose {kind} ledger data")
        ledger_commands = ledger.add_subparsers(dest="ledger_command", required=True)
        overview = ledger_commands.add_parser("overview")
        if kind == "money":
            overview.add_argument("--month", default=date.today().isoformat()[:7])
            overview.add_argument("--currency")
        else:
            today = date.today()
            monday = today - timedelta(days=today.weekday())
            overview.add_argument("--week-start", default=monday.isoformat())
        preview = ledger_commands.add_parser("preview")
        preview.add_argument("json_file")
        commit = ledger_commands.add_parser("commit")
        commit.add_argument("proposal_id")

    proposals = commands.add_parser("proposals", help="List ledger proposals")
    proposals.add_argument("--status", choices=["pending", "committed"], default="pending")
    return root


def run(args: argparse.Namespace) -> dict:
    base = args.url
    if args.command == "context":
        return request_json(base, "GET", f"/api/v1/context/today?date={args.date}")
    if args.command == "task":
        if args.task_command == "list":
            return request_json(base, "GET", "/api/v1/tasks")
        if args.task_command == "add":
            payload = {
                "title": args.title,
                "notes": args.notes,
                "priority": args.priority,
                "due_date": args.due_date,
                "estimated_minutes": args.minutes,
                "source": "lifeos-cli",
            }
            return request_json(
                base, "POST", "/api/v1/tasks", {k: v for k, v in payload.items() if v is not None}
            )
        if args.task_command == "delete":
            return request_json(base, "DELETE", f"/api/v1/tasks/{args.task_id}")
        status = "done" if args.task_command == "complete" else "open"
        return request_json(base, "PATCH", f"/api/v1/tasks/{args.task_id}", {"status": status})
    if args.command == "focus":
        return request_json(
            base,
            "PUT",
            f"/api/v1/today/{args.date}",
            {"headline": args.headline, "brief": args.brief, "source": "lifeos-cli"},
        )
    if args.command in {"money", "time"}:
        if args.ledger_command == "overview":
            if args.command == "money":
                query = {"month": args.month}
                if args.currency:
                    query["currency"] = args.currency
            else:
                query = {"week_start": args.week_start}
            return request_json(
                base, "GET", f"/api/v1/{args.command}/overview?{urllib.parse.urlencode(query)}"
            )
        if args.ledger_command == "preview":
            return request_json(
                base, "POST", f"/api/v1/{args.command}/proposals", read_payload(args.json_file)
            )
        return request_json(
            base,
            "POST",
            f"/api/v1/{args.command}/proposals/{args.proposal_id}/commit",
            {},
        )
    if args.command == "proposals":
        return request_json(base, "GET", f"/api/v1/proposals?status={args.status}")
    raise SystemExit("Unknown command")


def main() -> None:
    try:
        result = run(parser().parse_args())
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
