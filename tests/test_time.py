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

    client.post(f"/api/v1/time/proposals/{preview['id']}/commit", json={})
    after = client.get(f"/api/v1/time/overview?week_start={week_start}").json["time"]
    assert after["clock_minutes"] == before["clock_minutes"] + 60
    assert after["allocation_minutes"] == before["allocation_minutes"] + 105
    assert after["overlap_minutes"] == before["overlap_minutes"] + 45


def test_time_overview_has_physical_ranking_without_overlap_double_count(
    client, today, week_start
):
    overview = client.get(
        f"/api/v1/time/overview?week_start={week_start}&as_of={today}"
    ).json["time"]
    consumption = overview["consumption"]
    item_ranking = consumption["views"]["items"]["ranking"]
    category_ranking = consumption["views"]["categories"]["ranking"]

    assert consumption["default_view"] == "categories"
    assert item_ranking[0]["budget_item_id"] == "time_sleep"
    assert sum(row["physical_minutes"] for row in item_ranking) == overview["clock_minutes"]
    assert sum(row["physical_minutes"] for row in category_ranking) == overview[
        "clock_minutes"
    ]
    assert "time_learning" not in {row["budget_item_id"] for row in item_ranking}
    assert next(item for item in overview["items"] if item["id"] == "time_learning")[
        "actual_minutes"
    ] > 0
    wellbeing = next(row for row in category_ranking if row["category"] == "wellbeing")
    assert wellbeing["item_labels"] == ["Sleep", "Health"]
    assert wellbeing["physical_minutes"] == sum(
        row["physical_minutes"]
        for row in item_ranking
        if row["category"] == "wellbeing"
    )
    assert 0 < consumption["coverage_percent"] <= 100
    assert consumption["views"]["categories"]["top_three_share_percent"] <= 100
    assert consumption["views"]["items"]["top_three_share_percent"] <= 100


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
    before = client.get(f"/api/v1/time/overview?week_start={week_start}").json["time"]
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
    assert overview["clock_minutes"] == before["clock_minutes"] + 25


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
