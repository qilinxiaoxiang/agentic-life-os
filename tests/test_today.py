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
    for excluded in ("Reports", "Seedbed", "Habits", "Wellbeing", "Investments"):
        assert excluded not in html


def test_task_crud_and_completion_are_direct(client):
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
