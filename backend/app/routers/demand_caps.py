from fastapi import APIRouter, HTTPException

from app.schemas.demand_cap import DemandCapBody, DemandCapTrialRequest
from app.services.billing_service import BillingService

router = APIRouter(tags=["demand-cap"])


@router.get("/accounts/{account_id}/demand-caps")
def list_demand_caps(account_id: int):
    with BillingService() as svc:
        if not svc.get_account(account_id):
            raise HTTPException(404, "account not found")
        return {"items": svc.list_demand_caps(account_id)}


@router.put("/accounts/{account_id}/demand-caps/{period}")
def put_demand_cap(account_id: int, period: str, body: DemandCapBody):
    """Create or update the demand-cap parameters for one account/period.

    Domain violations return 422 with {error: {code, field, message}}.
    """
    with BillingService() as svc:
        row = svc.upsert_demand_cap(
            account_id, period, body.demand_kw, body.threshold_kw, body.conversion_factor
        )
        return row


@router.get("/accounts/{account_id}/demand-caps/{period}")
def get_demand_cap(account_id: int, period: str):
    with BillingService() as svc:
        row = svc.get_demand_cap(account_id, period)
        if not row:
            raise HTTPException(404, "demand cap not found")
        return row


@router.post("/demand-cap/trial")
def post_demand_cap_trial(body: DemandCapTrialRequest):
    """Read-only probe: does the cap fire and how much energy is added?

    Never writes a calc run and never changes account cap parameters.
    """
    with BillingService() as svc:
        return svc.trial_demand_cap(body)
