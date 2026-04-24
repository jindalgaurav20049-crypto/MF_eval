from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


def test_fund_search_returns_results():
    resp = client.get("/funds/search?q=axis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "axis"
    assert data["total"] >= 1
    assert len(data["results"]) >= 1


def test_fund_search_no_results():
    resp = client.get("/funds/search?q=xyznonexistent999")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_fund_summary_beginner():
    resp = client.get("/funds/101206/summary?mode=beginner")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == "101206"
    assert data["mode"] == "beginner"
    assert "fund_health_score" in data
    assert "verdict" in data


def test_fund_summary_advanced():
    resp = client.get("/funds/101206/summary?mode=advanced")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "advanced"
    assert "return_metrics" in data
    assert "risk_metrics" in data


def test_fund_summary_not_found():
    resp = client.get("/funds/000000/summary")
    assert resp.status_code == 404


def test_compare_funds():
    resp = client.get("/compare?scheme_ids=101206,119598&mode=advanced")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["schemes"]) == 2
