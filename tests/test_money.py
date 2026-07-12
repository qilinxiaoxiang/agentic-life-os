from __future__ import annotations


def money_entry(today, **overrides):
    entry = {
        "external_id": f"meal-{today}",
        "occurred_on": today,
        "kind": "expense",
        "account_id": "account_checking",
        "amount": "12.50",
        "currency": "USD",
        "category": "food",
        "budget_item_id": "budget_food",
        "note": "Lunch during the demo review",
    }
    entry.update(overrides)
    return entry


def account_balance(client, account_id):
    accounts = client.get("/api/v1/money/accounts").json["accounts"]
    return next(item["balance_minor"] for item in accounts if item["id"] == account_id)


def test_preview_does_not_mutate_and_commit_is_idempotent(client, today):
    before = account_balance(client, "account_checking")
    preview = client.post("/api/v1/money/proposals", json={"entries": [money_entry(today)]})
    assert preview.status_code == 201
    proposal = preview.json["proposal"]
    assert proposal["status"] == "pending"
    assert account_balance(client, "account_checking") == before
    assert (
        client.get(f"/api/v1/money/overview?month={today[:7]}").json["money"][
            "expense_actual_minor"
        ]
        == 0
    )

    first = client.post(f"/api/v1/money/proposals/{proposal['id']}/commit", json={})
    assert first.status_code == 200
    assert account_balance(client, "account_checking") == before - 1250
    second = client.post(f"/api/v1/money/proposals/{proposal['id']}/commit", json={})
    assert second.json["proposal"]["result"] == first.json["proposal"]["result"]
    assert account_balance(client, "account_checking") == before - 1250


def test_transfer_moves_balances_but_not_budget_actual(client, today):
    checking = account_balance(client, "account_checking")
    savings = account_balance(client, "account_savings")
    payload = {
        "entries": [
            money_entry(
                today,
                external_id=f"transfer-{today}",
                kind="transfer",
                to_account_id="account_savings",
                amount="100.00",
                category="transfer",
                budget_item_id=None,
                note="Move cash to savings",
            )
        ]
    }
    proposal = client.post("/api/v1/money/proposals", json=payload).json["proposal"]
    client.post(f"/api/v1/money/proposals/{proposal['id']}/commit", json={})
    assert account_balance(client, "account_checking") == checking - 10_000
    assert account_balance(client, "account_savings") == savings + 10_000
    overview = client.get(f"/api/v1/money/overview?month={today[:7]}").json["money"]
    assert overview["expense_actual_minor"] == 0


def test_refund_reduces_actual_spending(client, today):
    expense = client.post(
        "/api/v1/money/proposals", json={"entries": [money_entry(today, amount="20.00")]}
    ).json["proposal"]
    client.post(f"/api/v1/money/proposals/{expense['id']}/commit", json={})
    refund = client.post(
        "/api/v1/money/proposals",
        json={
            "entries": [
                money_entry(
                    today,
                    external_id=f"refund-{today}",
                    kind="refund",
                    amount="5.00",
                    note="Partial lunch refund",
                )
            ]
        },
    ).json["proposal"]
    client.post(f"/api/v1/money/proposals/{refund['id']}/commit", json={})
    overview = client.get(f"/api/v1/money/overview?month={today[:7]}").json["money"]
    assert overview["expense_actual_minor"] == 1500


def test_invalid_batch_is_atomic(client, today):
    before = account_balance(client, "account_checking")
    response = client.post(
        "/api/v1/money/proposals",
        json={"entries": [money_entry(today), money_entry(today, external_id="bad", amount="-1")]},
    )
    assert response.status_code == 400
    assert account_balance(client, "account_checking") == before
    assert client.get("/api/v1/proposals").json["proposals"] == []


def test_external_id_conflict_is_rejected(client, today):
    proposal = client.post("/api/v1/money/proposals", json={"entries": [money_entry(today)]}).json[
        "proposal"
    ]
    client.post(f"/api/v1/money/proposals/{proposal['id']}/commit", json={})
    conflict = client.post(
        "/api/v1/money/proposals", json={"entries": [money_entry(today, amount="99.00")]}
    )
    assert conflict.status_code == 400
    assert "different money data" in conflict.json["error"]


def test_primary_currency_cannot_change_after_money_exists(client):
    response = client.patch("/api/v1/settings", json={"currency": "EUR"})
    assert response.status_code == 400
    assert "before financial data exists" in response.json["error"]


def test_account_and_budget_crud(client, today):
    account = client.post(
        "/api/v1/money/accounts",
        json={"name": "Envelope", "account_type": "asset", "opening_balance": "25.00"},
    )
    assert account.status_code == 201
    account_id = account.json["account"]["id"]
    renamed = client.patch(f"/api/v1/money/accounts/{account_id}", json={"name": "Travel envelope"})
    assert renamed.json["account"]["name"] == "Travel envelope"
    assert client.delete(f"/api/v1/money/accounts/{account_id}").status_code == 200

    budget = client.post(
        "/api/v1/money/budgets",
        json={
            "month": today[:7],
            "title": "Books",
            "category": "books",
            "direction": "expense",
            "amount": "40.00",
        },
    )
    item_id = budget.json["budget_item_id"]
    changed = client.patch(f"/api/v1/money/budgets/{item_id}", json={"amount": "55.00"})
    assert changed.json["budget_item"]["amount_minor"] == 5500
    listed = client.get(f"/api/v1/money/budgets?month={today[:7]}").json["budget_items"]
    assert any(item["id"] == item_id for item in listed)
    assert client.delete(f"/api/v1/money/budgets/{item_id}").status_code == 200
