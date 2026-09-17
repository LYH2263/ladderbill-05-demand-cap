"""需量封顶（demand cap）。

账期需量（kW）超过封顶阈值时，把超额需量按折算系数换算成附加电量（kWh），
附加电量并入净电量后再走阶梯与尖峰计费。

本模块为纯计算 + 参数校验，不依赖 Web 框架，便于单元测试与仓库层复用。
"""

import math
from datetime import datetime

from app.engines.helpers import kwh_qty


def current_period(now: datetime | None = None) -> str:
    """当前账期标识，格式 YYYY-MM（与 readings 粒度匹配的月度账期）。"""
    return (now or datetime.now()).strftime("%Y-%m")

# 折算系数的合理区间（含端点）。负系数会产生负电量，超过上限视为录入异常。
COEF_MIN = 0.0
COEF_MAX = 10.0

# 判定“刚好相等/极小浮点误差”时视为未超额。
_EPS = 1e-9


class DemandCapError(ValueError):
    """带可读错误码与字段名的业务校验异常。"""

    def __init__(self, code: str, field: str, message: str):
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message

    def to_dict(self) -> dict:
        return {"code": self.code, "field": self.field, "message": self.message}


def _finite(value, field: str, code: str = "INVALID_NUMBER") -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise DemandCapError(code, field, f"{field} 必须是数字")
    if not math.isfinite(num):
        raise DemandCapError(code, field, f"{field} 必须是有限数字")
    return num


def validate_demand_cap(demand_kw, cap_kw, convert_coef) -> tuple[float, float, float]:
    """校验需量封顶三参数，返回规整后的 (需量, 阈值, 系数)。

    错误以 DemandCapError 抛出，携带错误码与字段名：
    - demand_kw < 0        -> DEMAND_NEGATIVE
    - cap_kw <= 0          -> CAP_ZERO
    - convert_coef 越界    -> COEF_OUT_OF_RANGE
    """
    demand = _finite(demand_kw, "demand_kw")
    cap = _finite(cap_kw, "cap_kw")
    coef = _finite(convert_coef, "convert_coef")

    if demand < 0:
        raise DemandCapError(
            "DEMAND_NEGATIVE", "demand_kw", "账期需量不能为负"
        )
    if cap <= 0:
        raise DemandCapError(
            "CAP_ZERO", "cap_kw", "封顶阈值必须大于 0，不能为零或负数"
        )
    if coef < COEF_MIN or coef > COEF_MAX:
        raise DemandCapError(
            "COEF_OUT_OF_RANGE",
            "convert_coef",
            f"折算系数需在合理范围 {COEF_MIN:g}~{COEF_MAX:g} 之间",
        )
    return demand, cap, coef


def apply_demand_cap(demand_kw, cap_kw, convert_coef) -> dict:
    """校验并计算超额需量与附加电量（不做计费）。"""
    demand, cap, coef = validate_demand_cap(demand_kw, cap_kw, convert_coef)
    excess_raw = max(0.0, demand - cap)
    capped = excess_raw > _EPS
    excess = kwh_qty(excess_raw) if capped else 0.0
    extra = kwh_qty(excess_raw * coef) if capped else 0.0
    source = (
        f"超额需量 {excess}kW × 折算系数 {round(coef, 4)} = 附加电量 {extra}kWh"
        if capped
        else None
    )
    return {
        "capped": capped,
        "demand_kw": kwh_qty(demand),
        "cap_kw": kwh_qty(cap),
        "convert_coef": round(coef, 4),
        "excess_kw": excess,
        "extra_kwh": extra,
        "extra_source": source,
    }


def empty_cap_block() -> dict:
    """未配置/未传参时的中性封顶块：字段齐全，附加电量为 0。"""
    return {
        "applied": False,
        "capped": False,
        "period": None,
        "demand_kw": None,
        "cap_kw": None,
        "convert_coef": None,
        "excess_kw": 0.0,
        "extra_kwh": 0.0,
        "extra_source": None,
    }
