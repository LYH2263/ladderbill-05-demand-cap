import json
import re

from app.db import connect
from app.engines.demand_cap import DomainValidationError, assess, cap_view, validate_cap_params
from app.engines.helpers import kwh_qty
from app.engines.peak_compare import compare_plain_vs_peak
from app.engines.tier_progressive import calc_bill
from app.repositories import accounts as accounts_repo
from app.repositories import demand_caps as caps_repo
from app.repositories import readings as readings_repo
from app.repositories import runs as runs_repo
from app.repositories import settings as settings_repo
from app.repositories import tiers as tiers_repo

PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class BillingService:
    def __init__(self):
        self._conn = connect()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def list_accounts(self):
        return accounts_repo.list_all(self._conn)

    def get_account(self, account_id: int):
        return accounts_repo.get(self._conn, account_id)

    def list_tiers(self):
        return tiers_repo.list_ordered(self._conn)

    def list_readings(self):
        return readings_repo.list_all(self._conn)

    def readings_for_account(self, account_id: int):
        return readings_repo.for_account(self._conn, account_id)

    def settings_map(self):
        return settings_repo.get_map(self._conn)

    # ---- demand cap maintenance -------------------------------------------------

    def list_demand_caps(self, account_id: int):
        return caps_repo.for_account(self._conn, account_id)

    def get_demand_cap(self, account_id: int, period: str):
        return caps_repo.get(self._conn, account_id, period)

    def _validate_period(self, period: str):
        if not isinstance(period, str) or not PERIOD_RE.match(period):
            raise DomainValidationError(
                "PERIOD_INVALID", "period", "账期格式必须为 YYYY-MM"
            )

    def upsert_demand_cap(
        self, account_id: int, period: str, demand_kw: float, threshold_kw: float, conversion_factor: float
    ) -> dict:
        """Create or replace an account/period cap. Domain-invalid input raises."""
        if not accounts_repo.get(self._conn, account_id):
            raise DomainValidationError("ACCOUNT_NOT_FOUND", "account_id", "户号不存在")
        self._validate_period(period)
        # Raises DEMAND_NEGATIVE / THRESHOLD_INVALID / FACTOR_OUT_OF_RANGE.
        validate_cap_params(demand_kw, threshold_kw, conversion_factor)
        return caps_repo.upsert(self._conn, account_id, period, demand_kw, threshold_kw, conversion_factor)

    # ---- billing ----------------------------------------------------------------

    def run_bill(self, kwh: float, peak: bool, account_id: int | None, persist: bool, period: str | None = None):
        if period is not None:
            return self._run_bill_with_cap(kwh, peak, account_id, period, persist)
        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        factor = pf if peak else 1.0
        result = calc_bill(kwh, tiers, factor)
        run_id = None
        if persist:
            run_id = runs_repo.insert(
                self._conn,
                "bill",
                {"kwh": kwh, "peak": peak, "account_id": account_id},
                result,
                account_id,
            )
        return {"run_id": run_id, **result}

    def _run_bill_with_cap(self, kwh, peak, account_id, period, persist):
        if account_id is None:
            raise DomainValidationError(
                "ACCOUNT_REQUIRED", "account_id", "按账期封顶计费必须指定户号"
            )
        self._validate_period(period)
        cap_row = caps_repo.get(self._conn, account_id, period)
        if cap_row is None:
            raise DomainValidationError(
                "CAP_NOT_CONFIGURED", "period", f"账期 {period} 尚未配置需量封顶参数"
            )
        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        factor = pf if peak else 1.0
        evaluation = assess(kwh, cap_row["demand_kw"], cap_row["threshold_kw"], cap_row["conversion_factor"])
        billed = calc_bill(evaluation["net_kwh"], tiers, factor)
        result = {
            "kwh": billed["kwh"],  # net, kept for backward compatibility
            "base_kwh": kwh_qty(kwh),
            "additional_kwh": kwh_qty(evaluation["additional_kwh"]),
            "net_kwh": billed["kwh"],
            "peak_factor": billed["peak_factor"],
            "total": billed["total"],
            "segments": billed["segments"],
            "demand_cap": cap_view(period, evaluation),
        }
        run_id = None
        if persist:
            run_id = runs_repo.insert(
                self._conn,
                "bill",
                {"kwh": kwh, "peak": peak, "account_id": account_id, "period": period},
                result,
                account_id,
            )
        return {"run_id": run_id, **result}

    def trial_demand_cap(self, req) -> dict:
        """Read-only probe: reports whether the cap fires and the added energy.

        Never inserts a calc run and never creates/updates cap parameters.
        ``req`` is DemandCapTrialRequest.
        """
        account_id = req.account_id
        if not accounts_repo.get(self._conn, account_id):
            raise DomainValidationError("ACCOUNT_NOT_FOUND", "account_id", "户号不存在")
        self._validate_period(req.period)
        if not isinstance(req.kwh, (int, float)) or req.kwh < 0:
            raise DomainValidationError("BASE_KWH_INVALID", "kwh", "基础电量不能为负")

        overrides = (req.demand_kw, req.threshold_kw, req.conversion_factor)
        if any(v is not None for v in overrides):
            if not all(v is not None for v in overrides):
                raise DomainValidationError(
                    "TRIAL_OVERRIDE_INCOMPLETE",
                    "conversion_factor",
                    "试算覆盖参数需同时提供 demand_kw、threshold_kw、conversion_factor",
                )
            source = "trial"
            demand_kw, threshold_kw, conversion_factor = overrides
        else:
            cap_row = caps_repo.get(self._conn, account_id, req.period)
            if cap_row is None:
                raise DomainValidationError(
                    "CAP_NOT_CONFIGURED", "period", f"账期 {req.period} 尚未配置需量封顶参数"
                )
            source = "stored"
            demand_kw = cap_row["demand_kw"]
            threshold_kw = cap_row["threshold_kw"]
            conversion_factor = cap_row["conversion_factor"]

        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        factor = pf if req.peak else 1.0
        evaluation = assess(req.kwh, demand_kw, threshold_kw, conversion_factor)
        billed = calc_bill(evaluation["net_kwh"], tiers, factor)
        return {
            "run_id": None,
            "persisted": False,
            "source": source,
            "kwh": billed["kwh"],
            "base_kwh": kwh_qty(req.kwh),
            "additional_kwh": kwh_qty(evaluation["additional_kwh"]),
            "net_kwh": billed["kwh"],
            "peak_factor": billed["peak_factor"],
            "total": billed["total"],
            "segments": billed["segments"],
            "demand_cap": cap_view(req.period, evaluation),
        }

    def run_compare(self, kwh: float, persist: bool):
        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        result = compare_plain_vs_peak(kwh, tiers, pf)
        run_id = None
        if persist:
            run_id = runs_repo.insert(self._conn, "compare", {"kwh": kwh}, result, None)
        return {"run_id": run_id, **result}

    def list_history(self, limit: int = 50):
        return runs_repo.list_recent(self._conn, limit)

    def get_run(self, run_id: int):
        return runs_repo.get(self._conn, run_id)

    def dashboard_stats(self):
        accounts = accounts_repo.list_all(self._conn)
        readings = readings_repo.list_all(self._conn)
        clean = [a for a in accounts if "种子" not in a.get("name", "")]
        dirty = [a for a in accounts if "种子" in a.get("name", "")]
        return {
            "account_count": len(accounts),
            "reading_count": len(readings),
            "clean_accounts": len(clean),
            "dirty_accounts": len(dirty),
            "recent_runs": len(runs_repo.list_recent(self._conn, 5)),
        }
