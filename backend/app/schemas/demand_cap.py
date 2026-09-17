from pydantic import BaseModel


class DemandCapBody(BaseModel):
    # Bounds are enforced in the domain layer so violations return readable
    # codes (DEMAND_NEGATIVE / THRESHOLD_INVALID / FACTOR_OUT_OF_RANGE).
    demand_kw: float
    threshold_kw: float
    conversion_factor: float


class DemandCapOut(BaseModel):
    id: int
    account_id: int
    period: str
    demand_kw: float
    threshold_kw: float
    conversion_factor: float
    updated_at: str | None = None


class DemandCapTrialRequest(BaseModel):
    account_id: int
    # Period format (YYYY-MM) is validated in the service so it returns the
    # same readable {code, field, message} envelope as the other rules.
    period: str
    # kwh bound likewise enforced in the domain (BASE_KWH_INVALID).
    kwh: float
    peak: bool = False
    # Optional override set: when all three are supplied the probe runs purely
    # on the trial values; otherwise the stored cap for the period is used.
    demand_kw: float | None = None
    threshold_kw: float | None = None
    conversion_factor: float | None = None
