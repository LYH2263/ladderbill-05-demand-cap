import math

import pytest

from app.engines.demand_cap import (
    DomainValidationError,
    assess,
    cap_view,
    validate_cap_params,
)


def test_under_cap_adds_nothing_but_keeps_net():
    r = assess(base_kwh=120, demand_kw=80, threshold_kw=100, conversion_factor=2)
    assert r["capped"] is False
    assert r["excess_kw"] == 0
    assert r["additional_kwh"] == 0
    assert r["net_kwh"] == 120


def test_over_cap_converts_excess_at_factor():
    # 120 kW vs 100 kW threshold -> 20 kW excess * factor 2 -> 40 kWh added
    r = assess(base_kwh=400, demand_kw=120, threshold_kw=100, conversion_factor=2)
    assert r["capped"] is True
    assert r["excess_kw"] == 20
    assert r["additional_kwh"] == 40
    assert r["net_kwh"] == 440


def test_demand_equal_to_threshold_does_not_cap():
    r = assess(100, demand_kw=100, threshold_kw=100, conversion_factor=2)
    assert r["capped"] is False
    assert r["additional_kwh"] == 0


@pytest.mark.parametrize(
    "demand,threshold,factor,code,field",
    [
        (-1, 100, 2, "DEMAND_NEGATIVE", "demand_kw"),
        (120, 0, 2, "THRESHOLD_INVALID", "threshold_kw"),
        (120, -5, 2, "THRESHOLD_INVALID", "threshold_kw"),
        (120, 100, 0, "FACTOR_OUT_OF_RANGE", "conversion_factor"),
        (120, 100, -1.5, "FACTOR_OUT_OF_RANGE", "conversion_factor"),
        (120, 100, 100.01, "FACTOR_OUT_OF_RANGE", "conversion_factor"),
    ],
)
def test_invalid_params_return_code_and_field(demand, threshold, factor, code, field):
    with pytest.raises(DomainValidationError) as exc:
        validate_cap_params(demand, threshold, factor)
    assert exc.value.code == code
    assert exc.value.field == field


def test_factor_upper_bound_is_inclusive():
    validate_cap_params(120, 100, 100.0)  # should not raise


def test_non_finite_and_bool_rejected():
    with pytest.raises(DomainValidationError) as exc:
        validate_cap_params(math.nan, 100, 2)
    assert exc.value.code == "DEMAND_NEGATIVE"
    with pytest.raises(DomainValidationError):
        validate_cap_params(True, 100, 2)  # bool must not be treated as number


def test_negative_base_kwh_rejected():
    with pytest.raises(DomainValidationError) as exc:
        assess(-1, 120, 100, 2)
    assert exc.value.field == "kwh"


def test_cap_view_shape_is_rounded():
    r = assess(12.3456, demand_kw=120.0, threshold_kw=100.0, conversion_factor=1.25)
    view = cap_view("2026-09", r)
    assert view["period"] == "2026-09"
    assert view["capped"] is True
    assert view["excess_kw"] == 20
    assert view["additional_kwh"] == 25
    assert set(view) == {
        "period",
        "demand_kw",
        "threshold_kw",
        "conversion_factor",
        "capped",
        "excess_kw",
        "additional_kwh",
    }
