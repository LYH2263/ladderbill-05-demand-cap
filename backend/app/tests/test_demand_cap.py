import pytest

from app.db import connect
from app.engines.demand_cap import (
    COEF_MAX,
    DemandCapError,
    apply_demand_cap,
    current_period,
    empty_cap_block,
)
from app.repositories import runs as runs_repo
from app.services.billing_service import BillingService

TIERS_NOT_USED = None


# ---------------- 纯引擎 ----------------

def test_cap_triggered_extra_kwh():
    r = apply_demand_cap(50, 40, 3)
    assert r["capped"] is True
    assert r["demand_kw"] == 50
    assert r["cap_kw"] == 40
    assert r["excess_kw"] == 10
    assert r["extra_kwh"] == 30
    assert "超额需量" in r["extra_source"]


def test_cap_not_triggered_extra_zero_but_fields_present():
    r = apply_demand_cap(20, 40, 3)
    assert r["capped"] is False
    assert r["excess_kw"] == 0
    assert r["extra_kwh"] == 0
    assert r["extra_source"] is None
    for key in ("capped", "excess_kw", "extra_kwh", "extra_source"):
        assert key in r


def test_cap_equal_threshold_not_triggered():
    assert apply_demand_cap(40, 40, 3)["capped"] is False


@pytest.mark.parametrize(
    "args,code,field",
    [
        ((-1, 40, 3), "DEMAND_NEGATIVE", "demand_kw"),
        ((10, 0, 3), "CAP_ZERO", "cap_kw"),
        ((10, -5, 3), "CAP_ZERO", "cap_kw"),
        ((10, 40, COEF_MAX + 0.01), "COEF_OUT_OF_RANGE", "convert_coef"),
        ((10, 40, -0.01), "COEF_OUT_OF_RANGE", "convert_coef"),
    ],
)
def test_invalid_params_carry_code_and_field(args, code, field):
    with pytest.raises(DemandCapError) as ei:
        apply_demand_cap(*args)
    assert ei.value.code == code
    assert ei.value.field == field
    assert ei.value.to_dict() == {
        "code": code,
        "field": field,
        "message": ei.value.message,
    }


def test_empty_block_zero_extra():
    b = empty_cap_block()
    assert b["capped"] is False and b["extra_kwh"] == 0
    for key in ("applied", "capped", "period", "demand_kw", "cap_kw",
                "convert_coef", "excess_kw", "extra_kwh", "extra_source"):
        assert key in b


# ---------------- 接口层 ----------------

def _period():
    return current_period()


def test_seed_account_detail_has_demand_caps(client):
    r = client.get("/api/accounts/2")
    assert r.status_code == 200
    caps = r.json()["demand_caps"]
    assert any(c["period"] == _period() for c in caps)


def test_put_creates_then_updates(client):
    period = "2030-01"
    r = client.put(
        f"/api/accounts/1/demand-caps/{period}",
        json={"demand_kw": 55, "cap_kw": 40, "convert_coef": 2.5},
    )
    assert r.status_code == 200, r.text
    assert r.json()["demand_kw"] == 55
    # 同键更新
    r2 = client.put(
        f"/api/accounts/1/demand-caps/{period}",
        json={"demand_kw": 70, "cap_kw": 40, "convert_coef": 2},
    )
    assert r2.status_code == 200
    listing = client.get("/api/accounts/1/demand-caps").json()["items"]
    rows = [c for c in listing if c["period"] == period]
    assert len(rows) == 1 and rows[0]["demand_kw"] == 70 and rows[0]["convert_coef"] == 2


@pytest.mark.parametrize(
    "payload,code,field",
    [
        ({"demand_kw": -3, "cap_kw": 40, "convert_coef": 3}, "DEMAND_NEGATIVE", "demand_kw"),
        ({"demand_kw": 10, "cap_kw": 0, "convert_coef": 3}, "CAP_ZERO", "cap_kw"),
        ({"demand_kw": 10, "cap_kw": 40, "convert_coef": 99}, "COEF_OUT_OF_RANGE", "convert_coef"),
    ],
)
def test_put_validation_error_code_and_field(client, payload, code, field):
    r = client.put("/api/accounts/1/demand-caps/2031-03", json=payload)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == code and detail["field"] == field
    assert detail["message"]


def test_put_bad_period_and_missing_account(client):
    r = client.put(
        "/api/accounts/1/demand-caps/2031/03",
        json={"demand_kw": 10, "cap_kw": 40, "convert_coef": 3},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "INVALID_PERIOD"
    r2 = client.put(
        "/api/accounts/9999/demand-caps/2031-03",
        json={"demand_kw": 10, "cap_kw": 40, "convert_coef": 3},
    )
    assert r2.status_code == 404


def test_probe_triggered_for_seed_account_2(client):
    # 种子户2 需量 50 > 阈值 40，系数 3 -> 超额10 -> 附加30
    with BillingService() as svc:
        before = len(runs_repo.list_recent(svc._conn, 10000))
    r = client.post(
        "/api/demand-cap/probe",
        json={"account_id": 2, "period": _period(), "kwh": 400, "peak": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["read_only"] is True
    assert body["demand_cap"]["capped"] is True
    assert body["extra_kwh"] == 30
    assert body["base_kwh"] == 400 and body["net_kwh"] == 430
    assert body["segments"] and body["total"] > 0
    with BillingService() as svc:
        after = len(runs_repo.list_recent(svc._conn, 10000))
        row = svc.get_demand_cap(2, _period())
    assert after == before, "探针不应写入 calc_runs"
    assert row["demand_kw"] == 50, "探针不得改动户参数"


def test_probe_not_triggered_extra_zero_fields_present(client):
    r = client.post(
        "/api/demand-cap/probe",
        json={"account_id": 1, "period": _period(), "kwh": 120},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["demand_cap"]["capped"] is False
    assert body["extra_kwh"] == 0
    assert body["net_kwh"] == 120
    for key in ("base_kwh", "extra_kwh", "net_kwh", "segments", "demand_cap"):
        assert key in body


def test_probe_adhoc_override_does_not_persist(client):
    r = client.post(
        "/api/demand-cap/probe",
        json={"demand_kw": 80, "cap_kw": 50, "convert_coef": 2, "kwh": 100},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["extra_kwh"] == 60 and body["net_kwh"] == 160
    # 未绑定户号，库里不应出现任何 demand_caps 新行
    conn = connect()
    n = conn.execute("SELECT COUNT(*) c FROM demand_caps WHERE demand_kw=80").fetchone()["c"]
    conn.close()
    assert n == 0


def test_probe_invalid_and_missing_params(client):
    r = client.post(
        "/api/demand-cap/probe",
        json={"demand_kw": 50, "cap_kw": 0, "convert_coef": 3, "kwh": 100},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "CAP_ZERO"
    r2 = client.post("/api/demand-cap/probe", json={})
    assert r2.status_code == 422


def test_bill_merges_extra_and_splits_quantities(client):
    r = client.post(
        "/api/bill",
        json={"account_id": 2, "period": _period(), "kwh": 400, "peak": True, "persist": False},
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["base_kwh"] == 400
    assert b["extra_kwh"] == 30
    assert b["net_kwh"] == 430
    assert b["kwh"] == 430
    assert b["demand_cap"]["capped"] is True
    assert b["segments"]


def test_bill_without_cap_returns_zero_extra_fields(client):
    r = client.post("/api/bill", json={"kwh": 120, "peak": False, "persist": False})
    b = r.json()
    assert b["base_kwh"] == 120 and b["extra_kwh"] == 0 and b["net_kwh"] == 120
    assert b["demand_cap"]["extra_kwh"] == 0
