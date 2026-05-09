from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.models import AMC, NAVHistoryDaily, Scheme
from app.db.session import SessionLocal, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        amc = AMC(amfi_code="TEST", name="Test AMC", short_name="Test")
        db.add(amc)
        db.flush()
        scheme = Scheme(
            amfi_scheme_code="101206",
            amc_id=amc.id,
            scheme_name="Axis Bluechip Fund - Direct Plan Growth",
            sebi_category="Equity",
            sebi_sub_category="Large Cap",
            plan="Direct",
            option="Growth",
            inception_date=date.today(),
        )
        db.add(scheme)
        db.flush()
        db.add(
            NAVHistoryDaily(
                scheme_id=scheme.id,
                nav_date=date.today(),
                nav=54.32,
            )
        )
        db.commit()
    with TestClient(app) as test_client:
        yield test_client


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


def test_fund_search_returns_results(client):
    resp = client.get("/funds/search?q=axis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "axis"
    assert data["total"] >= 1
    assert len(data["results"]) >= 1


def test_fund_search_no_results(client):
    resp = client.get("/funds/search?q=xyznonexistent999")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_fund_summary_beginner(client):
    resp = client.get("/funds/101206/summary?mode=beginner")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == "101206"
    assert data["mode"] == "beginner"
    assert "fund_health_score" in data
    assert "verdict" in data


def test_fund_summary_advanced(client):
    resp = client.get("/funds/101206/summary?mode=advanced")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "advanced"
    assert "return_metrics" in data
    assert "risk_metrics" in data


def test_fund_summary_not_found(client):
    resp = client.get("/funds/000000/summary")
    assert resp.status_code == 404


def test_compare_funds(client):
    resp = client.get("/compare?scheme_ids=101206&mode=advanced")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["schemes"]) == 1
