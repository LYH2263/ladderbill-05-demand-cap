from fastapi import APIRouter, HTTPException

from app.engines.demand_cap import DemandCapError
from app.schemas.billing import BillRequest, CompareRequest
from app.services.billing_service import BillingService

router = APIRouter(tags=["billing"])


@router.post("/bill")
def post_bill(body: BillRequest):
    with BillingService() as svc:
        try:
            return svc.run_bill(
                body.kwh,
                body.peak,
                body.account_id,
                body.persist,
                period=body.period,
                demand_kw=body.demand_kw,
                cap_kw=body.cap_kw,
                convert_coef=body.convert_coef,
            )
        except DemandCapError as exc:
            raise HTTPException(422, exc.to_dict())


@router.post("/compare")
def post_compare(body: CompareRequest):
    with BillingService() as svc:
        return svc.run_compare(body.kwh, body.persist)
