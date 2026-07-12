from __future__ import annotations

import re


def test_dashboard_contains_only_three_product_tabs(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert len(re.findall(r'<button class="tab(?: |")', html)) == 3
    assert 'data-tab="today"' in html
    assert 'data-tab="time"' in html
    assert 'data-tab="money"' in html
    for excluded in ("reports", "seedbed", "habits", "wellbeing", "investments"):
        assert f'data-tab="{excluded}"' not in html


def test_time_panel_contains_weekly_consumption_ranking(client):
    html = client.get("/#time").get_data(as_text=True)
    assert 'id="time-consumption-ranking"' in html
    assert "Where the week went" in html
    assert "TIME EXPLAINED" in html
    assert 'data-ranking-view="categories"' in html
    assert 'data-ranking-view="items"' in html
    assert 'data-ranking-view-panel="categories"' in html
    assert 'data-ranking-view-panel="items" hidden' in html
    assert 'data-ranking-key="wellbeing"' in html
    assert 'data-ranking-key="time_sleep"' in html


def test_dashboard_is_observe_and_confirm_not_direct_entry(client):
    html = client.get("/").get_data(as_text=True)
    assert "AGENT-WRITTEN" in html
    assert "task-form" not in html
    assert "focus-form" not in html
    assert "task-check" not in html
    assert "<input" not in html
    assert "<textarea" not in html


def test_dashboard_keeps_human_confirmation_for_durable_writes(client, today):
    preview = client.post(
        "/api/v1/money/proposals",
        json={
            "entries": [
                {
                    "external_id": "dashboard-confirmation-demo",
                    "occurred_on": today,
                    "kind": "expense",
                    "account_id": "account_checking",
                    "amount": "4.50",
                    "currency": "USD",
                    "category": "food",
                    "budget_item_id": "budget_food",
                    "note": "Synthetic review expense",
                }
            ]
        },
    )
    assert preview.status_code == 201
    assert "Confirm & commit" in client.get("/").get_data(as_text=True)


def test_task_crud_and_completion_are_available_to_agents(client):
    created = client.post(
        "/api/v1/tasks",
        json={"title": "Make the demo legible", "priority": "high", "estimated_minutes": 20},
    )
    assert created.status_code == 201
    task = created.json["task"]
    assert task["status"] == "open"

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"notes": "Use one clear story", "status": "done"}
    )
    assert updated.status_code == 200
    assert updated.json["task"]["completed_at"]

    reopened = client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "open"})
    assert reopened.json["task"]["completed_at"] is None

    deleted = client.delete(f"/api/v1/tasks/{task['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 400


def test_focus_appears_in_combined_context(client, today):
    response = client.put(
        f"/api/v1/today/{today}",
        json={"headline": "Protect the release", "brief": "Verify before publishing."},
    )
    assert response.status_code == 200
    context = client.get(f"/api/v1/context/today?date={today}").json["context"]
    assert context["focus"]["headline"] == "Protect the release"
    assert "tasks" in context and "time" in context and "money" in context


def test_invalid_task_patch_does_not_mutate(client):
    task = client.post("/api/v1/tasks", json={"title": "Keep me"}).json["task"]
    response = client.patch(f"/api/v1/tasks/{task['id']}", json={"priority": "urgent"})
    assert response.status_code == 400
    assert client.get(f"/api/v1/tasks/{task['id']}").json["task"]["priority"] == "medium"
