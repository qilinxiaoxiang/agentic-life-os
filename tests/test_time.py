from __future__ import annotations


def test_dual_ledger_preview_and_commit(client, today, week_start):
    payload = {
        "entries": [
            {
                "external_id": f"walk-{today}",
                "date": today,
                "minutes": 60,
                "budget_item_id": "time_health",
                "activity": "Walk while listening to a lecture",
                "counts_toward_clock": True,
                "overlap_group": "walk-learn",
            },
            {
                "external_id": f"learn-{today}",
                "date": today,
                "minutes": 45,
                "budget_item_id": "time_learning",
                "activity": "Lecture during the walk",
                "counts_toward_clock": False,
                "overlap_group": "walk-learn",
            },
        ]
    }
    preview = client.post("/api/v1/time/proposals", json=payload).json["proposal"]
    assert preview["preview"]["clock_minutes"] == 60
    assert preview["preview"]["allocation_minutes"] == 105
    before = client.get(f"/api/v1/time/overview?week_start={week_start}").json["time"]
    assert before["clock_minutes"] == 0

    client.post(f"/api/v1/time/proposals/{preview['id']}/commit", json={})
    after = client.get(f"/api/v1/time/overview?week_start={week_start}").json["time"]
    assert after["clock_minutes"] == 60
    assert after["allocation_minutes"] == 105
    assert after["overlap_minutes"] == 45


def test_non_clock_entry_requires_clock_peer(client, today):
    response = client.post(
        "/api/v1/time/proposals",
        json={
            "entries": [
                {
                    "external_id": f"overlap-only-{today}",
                    "date": today,
                    "minutes": 30,
                    "budget_item_id": "time_learning",
                    "activity": "Learning overlap",
                    "counts_toward_clock": False,
                    "overlap_group": "missing-clock",
                }
            ]
        },
    )
    assert response.status_code == 400
    assert "clock-counted peer" in response.json["error"]


def test_physical_time_cannot_exceed_24_hours(client, today):
    response = client.post(
        "/api/v1/time/proposals",
        json={
            "entries": [
                {
                    "external_id": f"too-long-a-{today}",
                    "date": today,
                    "minutes": 1000,
                    "activity": "First block",
                    "unbudgeted": True,
                },
                {
                    "external_id": f"too-long-b-{today}",
                    "date": today,
                    "minutes": 500,
                    "activity": "Second block",
                    "unbudgeted": True,
                },
            ]
        },
    )
    assert response.status_code == 400
    assert "exceeds 24 hours" in response.json["error"]


def test_unbudgeted_time_consumes_whitespace(client, today, week_start):
    proposal = client.post(
        "/api/v1/time/proposals",
        json={
            "entries": [
                {
                    "external_id": f"unplanned-{today}",
                    "date": today,
                    "minutes": 25,
                    "activity": "Unexpected admin",
                    "unbudgeted": True,
                }
            ]
        },
    ).json["proposal"]
    client.post(f"/api/v1/time/proposals/{proposal['id']}/commit", json={})
    overview = client.get(f"/api/v1/time/overview?week_start={week_start}").json["time"]
    assert overview["unbudgeted_minutes"] == 25
    assert overview["clock_minutes"] == 25


def test_wrong_week_budget_is_rejected(client, week_start):
    response = client.post(
        "/api/v1/time/proposals",
        json={
            "entries": [
                {
                    "external_id": "wrong-week",
                    "date": "2030-01-01",
                    "minutes": 30,
                    "budget_item_id": "time_work",
                    "activity": "Work in a different week",
                }
            ]
        },
    )
    assert response.status_code == 400
    assert "budget week" in response.json["error"]


def test_time_budget_crud(client, week_start):
    created = client.post(
        "/api/v1/time/budgets",
        json={
            "week_start": week_start,
            "label": "Creative work",
            "category": "creative",
            "weekly_minutes": 180,
            "protection": "protected",
        },
    )
    assert created.status_code == 201
    item_id = created.json["budget_item_id"]
    changed = client.patch(f"/api/v1/time/budgets/{item_id}", json={"weekly_minutes": 240})
    assert changed.json["budget_item"]["weekly_minutes"] == 240
    listed = client.get(f"/api/v1/time/budgets?week_start={week_start}").json["budget_items"]
    assert any(item["id"] == item_id for item in listed)
    assert client.delete(f"/api/v1/time/budgets/{item_id}").status_code == 200
