from __future__ import annotations

from datetime import date, timedelta

import pytest

from agentic_life_os import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DB_PATH": str(tmp_path / "lifeos.sqlite"),
            "DEFAULT_CURRENCY": "USD",
            "DEFAULT_TIMEZONE": "UTC",
            "DEMO": True,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def today():
    return date.today().isoformat()


@pytest.fixture
def week_start():
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()
