from __future__ import annotations

import math
from typing import Any

import pytest

from src.models import CompanySnapshot
from src.scoring.engine import (
    RADAR_CANDIDATE,
    RADAR_DISCARD,
    RADAR_PRIORITY,
    RADAR_UNRELIABLE,
    RADAR_WATCH,
    score_snapshot,
)


DEFAULT_WEIGHTS: dict[str, float] = {
    "valuation": 0.25,
    "quality": 0.20,
    "cash": 0.15,
    "balance": 0.15,
    "growth": 0.10,
    "capital_allocation": 0.05,
    "momentum_fundamental": 0.05,
    "risk": 0.05,
}


DEFAULT_THRESHOLDS: dict[str, float] = {
    "priority": 80.0,
    "candidate": 70.0,
    "watch": 58.0,
}


LEGACY_THRESHOLDS: dict[str, float] = {
    "strong_entry": 80.0,
    "entry": 70.0,
    "watch": 58.0,
}


VALID_RADAR_RECOMMENDATIONS = {
    RADAR_PRIORITY,
    RADAR_CANDIDATE,
    RADAR_WATCH,
    RADAR_DISCARD,
}


def build_snapshot(
    **overrides: Any,
) -> CompanySnapshot:
    """
    Genera un snapshot completo y estable para los tests.

    Los valores pueden modificarse mediante overrides sin
    repetir toda la construcción del objeto.
    """
    values: dict[str, Any] = {
        "ticker": "TEST",
        "name": "Test Company",
        "currency": "USD",
        "sector": "Technology",
        "industry": "Software",
        "price": 100.0,
        "market_cap": 100_000.0,
        "enterprise_value": 90_000.0,
        "revenue": 20_000.0,
        "ebitda": 5_000.0,
        "ebit": 4_000.0,
        "net_income": 3_000.0,
        "operating_cash_flow": 4_000.0,
        "capex": 1_000.0,
        "free_cash_flow": 3_000.0,
        "total_cash": 20_000.0,
        "total_debt": 10_000.0,
        "shares": 1_000.0,
        "revenue_growth": 0.15,
        "earnings_growth": 0.18,
        "gross_margin": 0.60,
        "operating_margin": 0.20,
        "net_margin": 0.15,
        "roe": 0.22,
        "roa": 0.10,
        "debt_to_equity": 0.50,
        "current_ratio": 1.50,
        "interest_coverage": 10.0,
        "pe": 20.0,
        "forward_pe": 15.0,
        "price_to_book": 4.0,
        "ev_to_ebitda": 10.0,
        "fcf_yield": 0.07,
        "earnings_yield": 0.06,
        "dividend_yield": 0.02,
        "fifty_two_week_change": 0.10,
        "analyst_target": 120.0,
        "analyst_count": 20,
        "source": "test",
        "data_quality": 90.0,
        "coverage_score": 90.0,
        "validity_score": 90.0,
        "consistency_score": 90.0,
    }

    values.update(
        overrides
    )

    return CompanySnapshot(
        **values
    )


def run_scoring(
    snapshot: CompanySnapshot,
    *,
    weights: dict[str, Any] | None = None,
    thresholds: dict[str, Any] | None = None,
    min_confidence: float = 55.0,
    min_coverage: float = 50.0,
):
    """
    Ejecuta el scoring con una configuración homogénea.
    """
    return score_snapshot(
        snapshot,
        weights or DEFAULT_WEIGHTS,
        thresholds or DEFAULT_THRESHOLDS,
        min_confidence=min_confidence,
        min_coverage=min_coverage,
    )


# ============================================================
# CONTRATO GENERAL
# ============================================================


def test_complete_snapshot_generates_reliable_radar_result() -> None:
    card = run_scoring(
        build_snapshot()
    )

    assert card.recommendation in (
        VALID_RADAR_RECOMMENDATIONS
    )
    assert card.overall_coverage == 100.0
    assert card.confidence >= 55.0
    assert not card.missing_metrics
    assert card.scoring_version == "2.0.0"


def test_sparse_snapshot_is_classified_as_unreliable() -> None:
    snapshot = CompanySnapshot(
        ticker="X",
        price=10.0,
        market_cap=100.0,
        data_quality=20.0,
    )

    card = run_scoring(
        snapshot
    )

    assert card.recommendation == RADAR_UNRELIABLE
    assert card.recommendation == "DATOS NO FIABLES"
    assert card.confidence < 55.0
    assert card.overall_coverage == 0.0
    assert card.missing_metrics


def test_missing_price_blocks_radar_classification() -> None:
    card = run_scoring(
        build_snapshot(
            price=None
        )
    )

    assert card.recommendation == RADAR_UNRELIABLE


def test_provider_error_limits_confidence() -> None:
    card = run_scoring(
        build_snapshot(
            errors="Provider failure"
        )
    )

    assert card.recommendation == RADAR_UNRELIABLE
    assert card.confidence <= 20.0


def test_critical_missing_fields_limit_confidence() -> None:
    card = run_scoring(
        build_snapshot(
            critical_missing_fields=[
                "price",
            ]
        )
    )

    assert card.recommendation == RADAR_UNRELIABLE
    assert card.confidence <= 45.0


# ============================================================
# COBERTURA Y DATOS AUSENTES
# ============================================================


def test_snapshot_without_metrics_has_zero_coverage() -> None:
    snapshot = CompanySnapshot(
        ticker="EMPTY",
        price=10.0,
        market_cap=100.0,
        data_quality=100.0,
    )

    card = run_scoring(
        snapshot
    )

    assert card.overall_coverage == 0.0
    assert card.recommendation == RADAR_UNRELIABLE

    assert all(
        coverage == 0.0
        for coverage
        in card.dimension_coverage.values()
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "invalid_value",
        "expected_missing_metrics",
    ),
    [
        (
            "roe",
            None,
            {
                "quality.roe",
                "capital_allocation.roe_proxy",
            },
        ),
        (
            "fcf_yield",
            math.nan,
            {
                "valuation.fcf_yield",
                "cash.fcf_yield",
            },
        ),
        (
            "forward_pe",
            math.inf,
            {
                "valuation.forward_pe",
            },
        ),
        (
            "earnings_growth",
            True,
            {
                "growth.earnings_growth",
                "momentum_fundamental.earnings_growth",
            },
        ),
    ],
)
def test_invalid_metrics_are_treated_as_missing(
    field_name: str,
    invalid_value: Any,
    expected_missing_metrics: set[str],
) -> None:
    snapshot = build_snapshot(
        **{
            field_name: invalid_value,
        }
    )

    card = run_scoring(
        snapshot
    )

    assert expected_missing_metrics.issubset(
        set(
            card.missing_metrics
        )
    )


def test_partial_coverage_generates_warning() -> None:
    snapshot = CompanySnapshot(
        ticker="PARTIAL",
        price=100.0,
        market_cap=1_000.0,
        forward_pe=15.0,
        data_quality=90.0,
    )

    card = run_scoring(
        snapshot
    )

    assert card.overall_coverage < 70.0

    assert any(
        "cobertura del scoring es parcial"
        in warning.casefold()
        for warning in card.warnings
    )


# ============================================================
# DEUDA Y BALANCE
# ============================================================


def test_negative_debt_to_equity_is_rejected() -> None:
    card = run_scoring(
        build_snapshot(
            debt_to_equity=-0.50
        )
    )

    assert (
        "balance.debt_to_equity"
        in card.missing_metrics
    )

    assert (
        "risk.debt_to_equity"
        in card.missing_metrics
    )

    assert any(
        "debt-to-equity es negativo"
        in warning.casefold()
        for warning in card.warnings
    )


def test_yahoo_percentage_debt_to_equity_is_normalized() -> None:
    card = run_scoring(
        build_snapshot(
            debt_to_equity=50.0
        )
    )

    assert (
        "balance.debt_to_equity"
        not in card.missing_metrics
    )

    assert any(
        "interpretado como porcentaje"
        in warning.casefold()
        for warning in card.warnings
    )


# ============================================================
# CONFIGURACIÓN
# ============================================================


def test_legacy_threshold_names_remain_supported() -> None:
    card = run_scoring(
        build_snapshot(),
        thresholds=LEGACY_THRESHOLDS,
    )

    assert card.recommendation in (
        VALID_RADAR_RECOMMENDATIONS
    )


def test_invalid_threshold_order_uses_defaults() -> None:
    card = run_scoring(
        build_snapshot(),
        thresholds={
            "priority": 50.0,
            "candidate": 80.0,
            "watch": 60.0,
        },
    )

    assert any(
        "umbrales no estaban ordenados"
        in warning.casefold()
        for warning in card.warnings
    )


def test_invalid_weights_use_uniform_distribution() -> None:
    invalid_weights = {
        dimension: None
        for dimension
        in DEFAULT_WEIGHTS
    }

    card = run_scoring(
        build_snapshot(),
        weights=invalid_weights,
    )

    assert any(
        "ponderación uniforme"
        in warning.casefold()
        for warning in card.warnings
    )


@pytest.mark.parametrize(
    (
        "snapshot",
        "weights",
        "thresholds",
        "expected_message",
    ),
    [
        (
            {},
            DEFAULT_WEIGHTS,
            DEFAULT_THRESHOLDS,
            "CompanySnapshot",
        ),
        (
            build_snapshot(),
            [],
            DEFAULT_THRESHOLDS,
            "weights",
        ),
        (
            build_snapshot(),
            DEFAULT_WEIGHTS,
            [],
            "thresholds",
        ),
    ],
)
def test_invalid_argument_types_raise_type_error(
    snapshot: Any,
    weights: Any,
    thresholds: Any,
    expected_message: str,
) -> None:
    with pytest.raises(
        TypeError,
        match=expected_message,
    ):
        score_snapshot(
            snapshot,
            weights,
            thresholds,
        )


# ============================================================
# VALORES Y LÍMITES
# ============================================================


def test_all_scores_remain_between_zero_and_one_hundred() -> None:
    card = run_scoring(
        build_snapshot(
            fcf_yield=1000.0,
            roe=1000.0,
            revenue_growth=1000.0,
            current_ratio=1000.0,
        )
    )

    scores = [
        card.valuation,
        card.quality,
        card.cash,
        card.balance,
        card.growth,
        card.capital_allocation,
        card.momentum_fundamental,
        card.risk,
        card.confidence,
        card.global_score,
        card.overall_coverage,
    ]

    assert all(
        0.0 <= score <= 100.0
        for score in scores
    )


def test_analyst_target_is_only_a_secondary_signal() -> None:
    card = run_scoring(
        build_snapshot(
            analyst_target=125.0
        )
    )

    assert (
        "momentum_fundamental.analyst_upside"
        not in card.missing_metrics
    )

    assert any(
        "precio objetivo de analistas"
        in warning.casefold()
        for warning in card.warnings
    )


def test_missing_analyst_target_reduces_momentum_coverage() -> None:
    card = run_scoring(
        build_snapshot(
            analyst_target=None
        )
    )

    assert (
        "momentum_fundamental.analyst_upside"
        in card.missing_metrics
    )

    assert (
        card.dimension_coverage[
            "momentum_fundamental"
        ]
        == 50.0
    )


def test_capital_allocation_is_explicitly_preliminary() -> None:
    card = run_scoring(
        build_snapshot()
    )

    assert any(
        "asignación de capital es una aproximación"
        in warning.casefold()
        for warning in card.warnings
    )


# ============================================================
# DEUDA TÉCNICA METODOLÓGICA
#
# Estos tests documentan comportamientos que deben corregirse.
# Se marcan como xfail para mantener la integración continua
# operativa hasta modificar models.py y scoring/engine.py.
# ============================================================


@pytest.mark.xfail(
    strict=True,
    reason=(
        "La caja neta se calcula actualmente aunque falte "
        "la deuda. Debe requerir caja y deuda."
    ),
)
def test_net_cash_requires_cash_and_debt() -> None:
    card = run_scoring(
        build_snapshot(
            total_cash=20_000.0,
            total_debt=None,
        )
    )

    assert (
        "balance.net_cash_to_market_cap"
        in card.missing_metrics
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "La conversión FCF puede resultar positiva cuando "
        "FCF y beneficio neto son negativos."
    ),
)
def test_negative_profit_does_not_create_valid_fcf_conversion() -> None:
    card = run_scoring(
        build_snapshot(
            net_income=-50.0,
            free_cash_flow=-100.0,
        )
    )

    assert (
        "cash.fcf_conversion"
        in card.missing_metrics
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "La calidad del proveedor pertenece a confianza, "
        "no a riesgo empresarial."
    ),
)
def test_risk_score_does_not_depend_on_provider_quality() -> None:
    high_quality_card = run_scoring(
        build_snapshot(
            data_quality=100.0
        )
    )

    low_quality_card = run_scoring(
        build_snapshot(
            data_quality=20.0
        )
    )

    assert (
        high_quality_card.risk
        == low_quality_card.risk
    )

    assert (
        high_quality_card.confidence
        != low_quality_card.confidence
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Las dimensiones sin datos reciben actualmente 50 "
        "puntos y afectan al score global."
    ),
)
def test_unobserved_dimensions_do_not_add_neutral_points() -> None:
    snapshot = CompanySnapshot(
        ticker="ONLY-VALUATION",
        price=100.0,
        market_cap=1_000.0,
        forward_pe=15.0,
        data_quality=100.0,
    )

    card = run_scoring(
        snapshot,
        min_coverage=0.0,
        min_confidence=0.0,
    )

    assert card.global_score == pytest.approx(
        card.valuation,
        abs=0.1,
    )
