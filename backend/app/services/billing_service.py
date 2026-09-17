import json

from app.db import connect
from app.engines.demand_cap import (
    DemandCapError,
    apply_demand_cap,
    current_period,
    empty_cap_block,
)
from app.engines.peak_compare import compare_plain_vs_peak
from app.engines.tier_progressive import calc_bill
from app.repositories import accounts as accounts_repo
from app.repositories import demand_caps as caps_repo
from app.repositories import readings as readings_repo
from app.repositories import runs as runs_repo
from app.repositories import settings as settings_repo
from app.repositories import tiers as tiers_repo


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

    # ---- 需量封顶 -------------------------------------------------

    def list_demand_caps(self, account_id: int):
        return caps_repo.list_for_account(self._conn, account_id)

    def get_demand_cap(self, account_id: int, period: str):
        return caps_repo.get(self._conn, account_id, period)

    def upsert_demand_cap(self, account_id: int, period: str, demand_kw, cap_kw, coef):
        # 先做引擎校验（非法时抛 DemandCapError，携带错误码+字段名），通过后落库。
        info = apply_demand_cap(demand_kw, cap_kw, coef)
        return caps_repo.upsert(
            self._conn,
            account_id,
            period,
            info["demand_kw"],
            info["cap_kw"],
            info["convert_coef"],
        )

    def _resolve_cap(self, account_id, period, override):
        """返回 (cap_block, configured)。override 为三元组或全 None。"""
        demand_kw, cap_kw, coef = override
        given = [v is not None for v in override]
        if any(given) and not all(given):
            raise DemandCapError(
                "INCOMPLETE_PARAMS",
                "convert_coef",
                "临时封顶参数需同时提供 demand_kw、cap_kw、convert_coef",
            )
        if demand_kw is not None and cap_kw is not None and coef is not None:
            info = apply_demand_cap(demand_kw, cap_kw, coef)
            info["applied"] = True
            info["period"] = period
            return info, True
        if account_id is not None and period:
            row = caps_repo.get(self._conn, account_id, period)
            if row:
                info = apply_demand_cap(row["demand_kw"], row["cap_kw"], row["convert_coef"])
                info["applied"] = True
                info["period"] = period
                return info, True
        return empty_cap_block(), False

    def _bill_with_cap(self, kwh: float, peak: bool, account_id, period, override):
        block, configured = self._resolve_cap(account_id, period, override)
        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        factor = pf if peak else 1.0
        base = float(kwh)
        extra = float(block["extra_kwh"])
        net = base + extra
        result = calc_bill(net, tiers, factor)
        return {
            "kwh": result["kwh"],
            "base_kwh": round(base, 3),
            "extra_kwh": round(extra, 3),
            "net_kwh": result["kwh"],
            "peak_factor": result["peak_factor"],
            "total": result["total"],
            "segments": result["segments"],
            "demand_cap": block,
        }, configured

    def run_bill(self, kwh: float, peak: bool, account_id, persist: bool,
                 period: str | None = None, demand_kw=None, cap_kw=None, convert_coef=None):
        period = period or current_period()
        result, _ = self._bill_with_cap(
            kwh, peak, account_id, period, (demand_kw, cap_kw, convert_coef)
        )
        run_id = None
        if persist:
            run_id = runs_repo.insert(
                self._conn,
                "bill",
                {
                    "kwh": kwh,
                    "peak": peak,
                    "account_id": account_id,
                    "period": period,
                    "demand_cap": result["demand_cap"],
                },
                result,
                account_id,
            )
        return {"run_id": run_id, **result}

    def probe_demand_cap(self, account_id, period, kwh, peak, override):
        """只读探针：校验是否触发封顶及附加量。绝不写 calc_runs，也不改户参数。"""
        period = period or current_period()
        if kwh is not None and float(kwh) < 0:
            raise DemandCapError("KWH_NEGATIVE", "kwh", "电量不能为负")
        out = {"read_only": True, "period": period}
        if kwh is not None:
            result, configured = self._bill_with_cap(
                kwh, peak, account_id, period, override
            )
            out.update(result)
            out["configured"] = configured
        else:
            block, configured = self._resolve_cap(account_id, period, override)
            out.update({"configured": configured, "demand_cap": block,
                        "base_kwh": None, "extra_kwh": block["extra_kwh"],
                        "net_kwh": None})
        return out

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
