"""Demand cap (需量封顶).

Each account/period carries a demand reading (kW), a cap threshold (kW) and a
conversion factor. Demand above the threshold is treated as excess demand and
converted into additional energy (kWh)::

    additional_kwh = max(demand_kw - threshold_kw, 0) * conversion_factor

The additional energy is merged into net energy before tier/peak billing.
"""

import math

from app.engines.helpers import kwh_qty

# Reasonable band for the excess-demand conversion factor (kWh per excess kW).
FACTOR_MIN_EXCLUSIVE = 0.0
FACTOR_MAX_INCLUSIVE = 100.0


class DomainValidationError(ValueError):
    """A billing-domain rule violation with a readable code and field name."""

    def __init__(self, code: str, field: str, message: str):
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_cap_params(demand_kw, threshold_kw, conversion_factor) -> None:
    """Raise DomainValidationError(code, field, message) on invalid input."""
    if not _is_number(demand_kw) or demand_kw < 0:
        raise DomainValidationError(
            "DEMAND_NEGATIVE",
            "demand_kw",
            "需量读数不能为负",
        )
    if not _is_number(threshold_kw) or threshold_kw <= 0:
        raise DomainValidationError(
            "THRESHOLD_INVALID",
            "threshold_kw",
            "封顶阈值必须大于零",
        )
    if (
        not _is_number(conversion_factor)
        or conversion_factor <= FACTOR_MIN_EXCLUSIVE
        or conversion_factor > FACTOR_MAX_INCLUSIVE
    ):
        raise DomainValidationError(
            "FACTOR_OUT_OF_RANGE",
            "conversion_factor",
            f"折算系数必须在 (0, {FACTOR_MAX_INCLUSIVE:g}] 范围内",
        )


def assess(base_kwh: float, demand_kw, threshold_kw, conversion_factor) -> dict:
    """Validate parameters and compute raw (unrounded) cap quantities."""
    if not _is_number(base_kwh) or base_kwh < 0:
        raise DomainValidationError("BASE_KWH_INVALID", "kwh", "基础电量不能为负")
    validate_cap_params(demand_kw, threshold_kw, conversion_factor)
    capped = demand_kw > threshold_kw
    excess_kw = (demand_kw - threshold_kw) if capped else 0.0
    additional_kwh = excess_kw * conversion_factor
    return {
        "capped": capped,
        "demand_kw": float(demand_kw),
        "threshold_kw": float(threshold_kw),
        "conversion_factor": float(conversion_factor),
        "excess_kw": float(excess_kw),
        "additional_kwh": float(additional_kwh),
        "base_kwh": float(base_kwh),
        "net_kwh": float(base_kwh + additional_kwh),
    }


def cap_view(period, assessment: dict) -> dict:
    """Rounded, API-facing description of a cap evaluation."""
    return {
        "period": period,
        "demand_kw": kwh_qty(assessment["demand_kw"]),
        "threshold_kw": kwh_qty(assessment["threshold_kw"]),
        "conversion_factor": float(assessment["conversion_factor"]),
        "capped": assessment["capped"],
        "excess_kw": kwh_qty(assessment["excess_kw"]),
        "additional_kwh": kwh_qty(assessment["additional_kwh"]),
    }
