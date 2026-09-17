import re

from fastapi import APIRouter, HTTPException

from app.engines.demand_cap import DemandCapError
from app.schemas.demand_cap import DemandCapBody, DemandCapProbe
from app.services.billing_service import BillingService

router = APIRouter(tags=["demand-cap"])

_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _check_period(period: str):
    if not _PERIOD_RE.match(period or ""):
        raise DemandCapError(
            "INVALID_PERIOD", "period", "账期格式应为 YYYY-MM，例如 2026-09"
        )


def _require_account(svc: BillingService, account_id: int):
    if not svc.get_account(account_id):
        raise HTTPException(404, "account not found")


@router.get("/accounts/{account_id}/demand-caps")
def list_demand_caps(account_id: int):
    with BillingService() as svc:
        _require_account(svc, account_id)
        return {"items": svc.list_demand_caps(account_id)}


@router.put("/accounts/{account_id}/demand-caps/{period}")
def put_demand_cap(account_id: int, period: str, body: DemandCapBody):
    """录入或更新某户某账期的需量封顶参数（upsert）。"""
    try:
        _check_period(period)
        with BillingService() as svc:
            _require_account(svc, account_id)
            return svc.upsert_demand_cap(
                account_id, period, body.demand_kw, body.cap_kw, body.convert_coef
            )
    except DemandCapError as exc:
        raise HTTPException(422, exc.to_dict())


@router.post("/demand-cap/probe")
def probe_demand_cap(body: DemandCapProbe):
    """只读探针：校验是否触发封顶及附加量。不写运行记录、不改户参数。"""
    override = (body.demand_kw, body.cap_kw, body.convert_coef)
    given = [v is not None for v in override]
    has_override = any(given)
    try:
        if body.period:
            _check_period(body.period)
        if has_override and not all(given):
            raise DemandCapError(
                "INCOMPLETE_PARAMS",
                "convert_coef",
                "现场试算需同时提供 demand_kw、cap_kw、convert_coef",
            )
        if body.account_id is None and not has_override:
            raise DemandCapError(
                "MISSING_PARAMS",
                "account_id",
                "探针需指定 account_id（读取已存参数）或同时提供三个封顶参数",
            )
        with BillingService() as svc:
            if body.account_id is not None:
                _require_account(svc, body.account_id)
            return svc.probe_demand_cap(
                body.account_id,
                body.period,
                body.kwh,
                body.peak,
                override if has_override else (None, None, None),
            )
    except DemandCapError as exc:
        raise HTTPException(422, exc.to_dict())
