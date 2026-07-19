def _evidence():
    return {
        "summary": "Work exceeded the plan in three completed weeks.",
        "observed_periods": 3,
        "alternative": "Keep the current allocation and protect a daily stop time.",
    }


def test_time_resize_is_reviewable_and_requires_commit(client):
    before = client.get("/api/v1/time/budgets").json["budget_items"]
    work = next(item for item in before if item["id"] == "time_work")
    response = client.post(
        "/api/v1/budget-adjustments",
        json={
            "kind": "time",
            "action": "resize",
            "target_id": "time_work",
            "change": {"weekly_minutes": work["weekly_minutes"] + 60},
            "evidence": _evidence(),
        },
    )
    assert response.status_code == 201
    proposal = response.json["proposal"]
    assert proposal["preview"]["total_effect"]["delta"] == 60
    unchanged = client.get("/api/v1/time/budgets").json["budget_items"]
    assert next(item for item in unchanged if item["id"] == "time_work")[
        "weekly_minutes"
    ] == work["weekly_minutes"]

    committed = client.post(
        f"/api/v1/budget-adjustments/{proposal['id']}/commit", json={}
    )
    assert committed.status_code == 200
    assert committed.json["proposal"]["status"] == "committed"
    changed = client.get("/api/v1/time/budgets").json["budget_items"]
    assert next(item for item in changed if item["id"] == "time_work")[
        "weekly_minutes"
    ] == work["weekly_minutes"] + 60


def test_rejected_adjustment_never_mutates_budget(client):
    before = client.get("/api/v1/money/budgets").json["budget_items"]
    housing = next(item for item in before if item["id"] == "budget_housing")
    proposal = client.post(
        "/api/v1/budget-adjustments",
        json={
            "kind": "money",
            "action": "resize",
            "target_id": "budget_housing",
            "change": {"amount": "1700.00"},
            "evidence": {
                "summary": "Housing changed across three completed months.",
                "observed_periods": 3,
                "alternative": "Keep the current envelope and reduce another category.",
            },
        },
    ).json["proposal"]

    rejected = client.post(
        f"/api/v1/budget-adjustments/{proposal['id']}/reject", json={}
    )
    assert rejected.json["proposal"]["status"] == "rejected"
    after = client.get("/api/v1/money/budgets").json["budget_items"]
    assert next(item for item in after if item["id"] == "budget_housing")[
        "amount_minor"
    ] == housing["amount_minor"]


def test_stale_adjustment_requires_fresh_review(client):
    work = next(
        item
        for item in client.get("/api/v1/time/budgets").json["budget_items"]
        if item["id"] == "time_work"
    )
    proposal = client.post(
        "/api/v1/budget-adjustments",
        json={
            "kind": "time",
            "action": "resize",
            "target_id": "time_work",
            "change": {"weekly_minutes": work["weekly_minutes"] + 60},
            "evidence": _evidence(),
        },
    ).json["proposal"]
    client.patch(
        "/api/v1/time/budgets/time_work",
        json={"weekly_minutes": work["weekly_minutes"] + 30},
    )

    response = client.post(
        f"/api/v1/budget-adjustments/{proposal['id']}/commit", json={}
    )

    assert response.status_code == 400
    assert "state changed" in response.json["error"]


def test_adjustment_requires_evidence_and_alternative(client):
    response = client.post(
        "/api/v1/budget-adjustments",
        json={
            "kind": "time",
            "action": "resize",
            "target_id": "time_work",
            "change": {"weekly_minutes": 2400},
            "evidence": {"summary": "One observation", "observed_periods": 1},
        },
    )

    assert response.status_code == 400
    assert "alternative" in response.json["error"]
