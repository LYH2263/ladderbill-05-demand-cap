from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _client():
    # Context manager triggers the startup event (seed.init_db).
    return TestClient(app)


def _seeded_accounts():
    with _client() as c:
        return c.get("/api/accounts").json()["items"]


def test_put_then_get_cap():
    accts = _seeded_accounts()
    aid = accts[0]["id"]
    r = client.put(
        f"/api/accounts/{aid}/demand-caps/2026-09",
        json={"demand_kw": 120, "threshold_kw": 100, "conversion_factor": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["period"] == "2026-09"
    assert body["demand_kw"] == 120

    got = client.get(f"/api/accounts/{aid}/demand-caps/2026-09")
    assert got.status_code == 200
    assert got.json()["threshold_kw"] == 100


def test_update_existing_cap_overwrites():
    aid = _seeded_accounts()[0]["id"]
    client.put(
        f"/api/accounts/{aid}/demand-caps/2026-10",
        json={"demand_kw": 90, "threshold_kw": 100, "conversion_factor": 2},
    )
    r = client.put(
        f"/api/accounts/{aid}/demand-caps/2026-10",
        json={"demand_kw": 130, "threshold_kw": 110, "conversion_factor": 3},
    )
    assert r.status_code == 200
    rows = client.get(f"/api/accounts/{aid}/demand-caps").json()["items"]
    assert len([x for x in rows if x["period"] == "2026-10"]) == 1
    assert r.json()["demand_kw"] == 130


def test_validation_error_shape_with_code_and_field():
    aid = _seeded_accounts()[0]["id"]
    cases = [
        ({"demand_kw": -5, "threshold_kw": 100, "conversion_factor": 2}, "DEMAND_NEGATIVE", "demand_kw"),
        ({"demand_kw": 120, "threshold_kw": 0, "conversion_factor": 2}, "THRESHOLD_INVALID", "threshold_kw"),
        ({"demand_kw": 120, "threshold_kw": 100, "conversion_factor": 999}, "FACTOR_OUT_OF_RANGE", "conversion_factor"),
    ]
    for payload, code, field in cases:
        r = client.put(f"/api/accounts/{aid}/demand-caps/2026-09", json=payload)
        assert r.status_code == 422, payload
        err = r.json()["error"]
        assert err["code"] == code
        assert err["field"] == field
        assert err["message"]


def test_put_unknown_account_422():
    r = client.put(
        "/api/accounts/99999/demand-caps/2026-09",
        json={"demand_kw": 120, "threshold_kw": 100, "conversion_factor": 2},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_bill_with_cap_splits_base_additional_net():
    # Seed account 2 has a 2026-09 cap: 120 demand / 100 threshold / factor 2
    # -> excess 20 kW -> 40 kWh additional.
    aid = next(a["id"] for a in _seeded_accounts() if "种子" in a["name"])
    r = client.post(
        "/api/bill",
        json={"account_id": aid, "period": "2026-09", "kwh": 400, "peak": False, "persist": False},
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["base_kwh"] == 400
    assert b["additional_kwh"] == 40
    assert b["net_kwh"] == 440
    assert b["kwh"] == 440  # backward-compatible top-level kwh tracks net
    assert b["demand_cap"]["capped"] is True
    assert sum(s["qty"] for s in b["segments"]) == 440


def test_bill_below_cap_returns_zero_additional_but_fields_present():
    aid = next(a["id"] for a in _seeded_accounts() if "种子" in a["name"])
    client.put(
        f"/api/accounts/{aid}/demand-caps/2026-08",
        json={"demand_kw": 50, "threshold_kw": 100, "conversion_factor": 2},
    )
    r = client.post(
        "/api/bill",
        json={"account_id": aid, "period": "2026-08", "kwh": 120, "peak": False, "persist": False},
    )
    b = r.json()
    assert b["additional_kwh"] == 0
    assert b["net_kwh"] == 120
    assert b["base_kwh"] == 120
    assert b["demand_cap"]["capped"] is False
    # Fields still present even when not triggered.
    assert "additional_kwh" in b and "demand_cap" in b


def test_trial_is_read_only():
    accts = _seeded_accounts()
    aid = next(a["id"] for a in accts if "种子" in a["name"])
    before = client.get("/api/history").json()["items"]
    caps_before = client.get(f"/api/accounts/{aid}/demand-caps").json()["items"]

    r = client.post(
        "/api/demand-cap/trial",
        json={"account_id": aid, "period": "2026-09", "kwh": 400, "peak": False},
    )
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["persisted"] is False
    assert t["run_id"] is None
    assert t["source"] == "stored"
    assert t["demand_cap"]["capped"] is True
    assert t["additional_kwh"] == 40
    assert t["net_kwh"] == 440

    after = client.get("/api/history").json()["items"]
    caps_after = client.get(f"/api/accounts/{aid}/demand-caps").json()["items"]
    assert len(after) == len(before)
    assert caps_after == caps_before


def test_trial_with_override_does_not_persist_params():
    aid = next(a["id"] for a in _seeded_accounts() if "种子" in a["name"])
    r = client.post(
        "/api/demand-cap/trial",
        json={
            "account_id": aid,
            "period": "2030-01",
            "kwh": 100,
            "demand_kw": 200,
            "threshold_kw": 80,
            "conversion_factor": 1.5,
        },
    )
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["source"] == "trial"
    assert t["demand_cap"]["excess_kw"] == 120
    assert t["additional_kwh"] == 180
    # The trial period must not have been created as a stored cap.
    assert client.get(f"/api/accounts/{aid}/demand-caps/2030-01").status_code == 404


def test_trial_missing_cap_is_422():
    aid = _seeded_accounts()[0]["id"]
    r = client.post(
        "/api/demand-cap/trial",
        json={"account_id": aid, "period": "2024-01", "kwh": 100},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "CAP_NOT_CONFIGURED"
