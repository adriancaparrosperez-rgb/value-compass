from __future__ import annotations
import json
import math
from typing import Any
import pytest
from src.models import CompanySnapshot, ScoreCard
from src.scoring.engine import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_COVERAGE,
    DIMENSION_NAMES,
    RADAR_CANDIDATE,
    RADAR_DISCARD,
    RADAR_PRIORITY,
    RADAR_UNRELIABLE,
    RADAR_WATCH,
    SCORING_VERSION,
    _bounded_score,
    _deduplicate_strings,
    _dimension_result,
    _effective_confidence,
    _linear_score,
    _normalize_debt_to_equity,
    _normalize_thresholds,
    _normalize_weights,
    _number,
    _overall_coverage,
    _radar_recommendation,
    _safe_ratio,
    score_snapshot,
)
def _complete_snapshot(
    **overrides: Any,
) -> CompanySnapshot:
    values: dict[str, Any] = {
        "ticker": " TEST ",
        "name": "Test Company",
        "currency": "EUR",
        "price": 100.0,
        "market_cap": 1_000_000_000.0,
        "enterprise_value": 1_100_000_000.0,
        "revenue": 500_000_000.0,
        "ebitda": 100_000_000.0,
        "ebit": 80_000_000.0,
        "net_income": 50_000_000.0,
        "operating_cash_flow": 90_000_000.0,
        "free_cash_flow": 60_000_000.0,
        "total_cash": 120_000_000.0,
        "total_debt": 220_000_000.0,
        "shares": 10_000_000.0,
        "revenue_growth": 0.12,
        "earnings_growth": 0.15,
        "gross_margin": 0.45,
        "operating_margin": 0.20,
        "net_margin": 0.10,
        "roe": 0.22,
        "roa": 0.10,
        "debt_to_equity": 55.0,
        "current_ratio": 1.5,
        "pe": 18.0,
        "forward_pe": 16.0,
        "price_to_book": 3.0,
        "ev_to_ebitda": 10.0,
        "fcf_yield": 0.06,
        "earnings_yield": 0.05,
        "dividend_yield": 0.025,
        "fifty_two_week_change": 0.15,
        "analyst_target": 115.0,
        "analyst_count": 12,
        "data_quality": 90.0,
        "coverage_score": 90.0,
        "validity_score": 100.0,
        "consistency_score": 100.0,
        "warnings": [],
        "critical_missing_fields": [],
        "errors": "",
    }
    values.update(overrides)
    return CompanySnapshot(
        **values
    )
def _weights() -> dict[str, float]:
    return {
        "valuation": 0.20,
        "quality": 0.20,
        "cash": 0.15,
        "balance": 0.15,
        "growth": 0.10,
        "capital_allocation": 0.05,
        "momentum_fundamental": 0.05,
        "risk": 0.10,
    }
def _thresholds() -> dict[str, float]:
    return {
        "priority": 80.0,
        "candidate": 70.0,
        "watch": 58.0,
    }
def _score(
    snapshot: CompanySnapshot | None = None,
    *,
    weights: dict[str, Any] | None = None,
    thresholds: dict[str, Any] | None = None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> ScoreCard:
    return score_snapshot(
        snapshot or _complete_snapshot(),
        weights if weights is not None else _weights(),
        thresholds if thresholds is not None else _thresholds(),
        min_confidence=min_confidence,
        min_coverage=min_coverage,
    )
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10, 10.0),
        ("10.5", 10.5),
        (0, 0.0),
        (-5, -5.0),
        (None, None),
        (True, None),
        (False, None),
        ("invalid", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
    ],
)
def test_number_accepts_only_finite_numeric_values(
    value: Any,
    expected: float | None,
) -> None:
    assert _number(value) == expected
@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (-10, 0.0, 0.0),
        (0, 0.0, 0.0),
        (55.5, 0.0, 55.5),
        (100, 0.0, 100.0),
        (150, 0.0, 100.0),
        (None, 30.0, 30.0),
        ("invalid", 25.0, 25.0),
        (True, 40.0, 40.0),
    ],
)
def test_bounded_score(
    value: Any,
    default: float,
    expected: float,
) -> None:
    assert _bounded_score(
        value,
        default=default,
    ) == expected
def test_linear_score_returns_none_for_missing_value() -> None:
    assert _linear_score(
        None,
        0.0,
        1.0,
    ) is None
def test_linear_score_maps_range_to_zero_and_one_hundred() -> None:
    assert _linear_score(
        0.0,
        0.0,
        10.0,
    ) == 0.0
    assert _linear_score(
        5.0,
        0.0,
        10.0,
    ) == 50.0
    assert _linear_score(
        10.0,
        0.0,
        10.0,
    ) == 100.0
def test_linear_score_clamps_extreme_values() -> None:
    assert _linear_score(
        -100.0,
        0.0,
        10.0,
    ) == 0.0
    assert _linear_score(
        100.0,
        0.0,
        10.0,
    ) == 100.0
def test_linear_score_can_reverse_result() -> None:
    assert _linear_score(
        0.0,
        0.0,
        10.0,
        reverse=True,
    ) == 100.0
    assert _linear_score(
        10.0,
        0.0,
        10.0,
        reverse=True,
    ) == 0.0
@pytest.mark.parametrize(
    ("low", "high"),
    [
        (1.0, 1.0),
        (2.0, 1.0),
        (float("nan"), 1.0),
        (0.0, float("inf")),
    ],
)
def test_linear_score_rejects_invalid_range(
    low: float,
    high: float,
) -> None:
    assert _linear_score(
        0.5,
        low,
        high,
    ) is None
@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (0, 10, 0.0),
        (5, 10, 0.5),
        (-5, 10, -0.5),
        (5, 0, None),
        (5, None, None),
        (None, 5, None),
        (True, 5, None),
        (5, float("inf"), None),
    ],
)
def test_safe_ratio(
    numerator: Any,
    denominator: Any,
    expected: float | None,
) -> None:
    assert _safe_ratio(
        numerator,
        denominator,
    ) == expected
def test_safe_ratio_can_require_positive_denominator() -> None:
    assert _safe_ratio(
        5,
        -10,
        denominator_must_be_positive=True,
    ) is None
    assert _safe_ratio(
        5,
        10,
        denominator_must_be_positive=True,
    ) == 0.5
@pytest.mark.parametrize(
    ("value", "expected", "has_warning"),
    [
        (None, None, False),
        (-1.0, None, True),
        (0.0, 0.0, False),
        (2.5, 2.5, False),
        (10.0, 10.0, False),
        (55.0, 0.55, True),
        (250.0, 2.5, True),
        ("invalid", None, False),
    ],
)
def test_normalize_debt_to_equity(
    value: Any,
    expected: float | None,
    has_warning: bool,
) -> None:
    normalized, warning = (
        _normalize_debt_to_equity(
            value
        )
    )
    assert normalized == expected
    assert (warning is not None) is has_warning
def test_dimension_result_uses_only_available_metrics() -> None:
    score, coverage, missing = _dimension_result(
        {
            "metric_a": 80.0,
            "metric_b": None,
            "metric_c": 40.0,
            "metric_d": None,
        }
    )
    assert score == 60.0
    assert coverage == 50.0
    assert missing == [
        "metric_b",
        "metric_d",
    ]
def test_dimension_result_without_available_metrics_is_neutral_but_uncovered() -> None:
    score, coverage, missing = _dimension_result(
        {
            "metric_a": None,
            "metric_b": None,
        }
    )
    assert score == 50.0
    assert coverage == 0.0
    assert missing == [
        "metric_a",
        "metric_b",
    ]
def test_dimension_result_empty_mapping() -> None:
    score, coverage, missing = _dimension_result(
        {}
    )
    assert score == 50.0
    assert coverage == 0.0
    assert missing == []
def test_normalize_weights_preserves_proportions() -> None:
    normalized, warnings = _normalize_weights(
        {
            "valuation": 2,
            "quality": 1,
            "cash": 1,
            "balance": 0,
            "growth": 0,
            "capital_allocation": 0,
            "momentum_fundamental": 0,
            "risk": 0,
        }
    )
    assert sum(
        normalized.values()
    ) == pytest.approx(1.0)
    assert normalized["valuation"] == pytest.approx(
        0.50
    )
    assert normalized["quality"] == pytest.approx(
        0.25
    )
    assert normalized["cash"] == pytest.approx(
        0.25
    )
    assert warnings == []
def test_normalize_weights_discards_invalid_and_negative_values() -> None:
    normalized, warnings = _normalize_weights(
        {
            "valuation": -1,
            "quality": "invalid",
            "cash": 1,
        }
    )
    assert normalized["cash"] == pytest.approx(
        1.0
    )
    assert normalized["valuation"] == 0.0
    assert normalized["quality"] == 0.0
    assert any(
        "negativo"
        in warning.casefold()
        for warning in warnings
    )
    assert any(
        "peso válido"
        in warning.casefold()
        for warning in warnings
    )
def test_normalize_weights_uses_uniform_distribution_when_none_are_valid() -> None:
    normalized, warnings = _normalize_weights(
        {}
    )
    expected_weight = (
        1.0
        / len(DIMENSION_NAMES)
    )
    assert all(
        weight == pytest.approx(
            expected_weight
        )
        for weight in normalized.values()
    )
    assert sum(
        normalized.values()
    ) == pytest.approx(1.0)
    assert any(
        "ponderación uniforme"
        in warning.casefold()
        for warning in warnings
    )
def test_normalize_thresholds_supports_legacy_keys() -> None:
    normalized, warnings = _normalize_thresholds(
        {
            "strong_entry": 82,
            "entry": 71,
            "watch": 59,
        }
    )
    assert normalized == {
        "priority": 82.0,
        "candidate": 71.0,
        "watch": 59.0,
    }
    assert warnings == []
def test_normalize_thresholds_replaces_invalid_order() -> None:
    normalized, warnings = _normalize_thresholds(
        {
            "priority": 60,
            "candidate": 80,
            "watch": 70,
        }
    )
    assert normalized == {
        "priority": 80.0,
        "candidate": 70.0,
        "watch": 58.0,
    }
    assert any(
        "no estaban ordenados"
        in warning.casefold()
        for warning in warnings
    )
def test_overall_coverage_is_weighted() -> None:
    coverage = _overall_coverage(
        {
            "valuation": 100.0,
            "quality": 50.0,
            "cash": 0.0,
            "balance": 0.0,
            "growth": 0.0,
            "capital_allocation": 0.0,
            "momentum_fundamental": 0.0,
            "risk": 0.0,
        },
        {
            "valuation": 0.50,
            "quality": 0.50,
            "cash": 0.0,
            "balance": 0.0,
            "growth": 0.0,
            "capital_allocation": 0.0,
            "momentum_fundamental": 0.0,
            "risk": 0.0,
        },
    )
    assert coverage == 75.0
def test_effective_confidence_combines_quality_and_coverage() -> None:
    snapshot = _complete_snapshot(
        data_quality=80.0
    )
    confidence = _effective_confidence(
        snapshot,
        overall_coverage=60.0,
    )
    assert confidence == 73.0
def test_effective_confidence_is_capped_by_provider_error() -> None:
    snapshot = _complete_snapshot(
        data_quality=100.0,
        errors="Provider error",
    )
    confidence = _effective_confidence(
        snapshot,
        overall_coverage=100.0,
    )
    assert confidence == 20.0
def test_effective_confidence_is_capped_by_critical_missing_fields() -> None:
    snapshot = _complete_snapshot(
        data_quality=100.0,
        critical_missing_fields=[
            "price",
        ],
    )
    confidence = _effective_confidence(
        snapshot,
        overall_coverage=100.0,
    )
    assert confidence == 45.0
def test_complete_snapshot_builds_score_card() -> None:
    result = _score()
    assert isinstance(
        result,
        ScoreCard,
    )
    assert result.ticker == "TEST"
    assert result.scoring_version == SCORING_VERSION
    assert set(
        result.dimension_coverage
    ) == set(
        DIMENSION_NAMES
    )
    assert 0.0 <= result.global_score <= 100.0
    assert 0.0 <= result.confidence <= 100.0
    assert 0.0 <= result.overall_coverage <= 100.0
    assert result.calculated_at
    assert result.rationale
def test_complete_snapshot_has_full_dimension_coverage() -> None:
    result = _score()
    assert all(
        coverage == 100.0
        for coverage in (
            result.dimension_coverage.values()
        )
    )
    assert result.overall_coverage == 100.0
    assert result.missing_metrics == []
def test_zero_free_cash_flow_is_not_treated_as_missing() -> None:
    snapshot = _complete_snapshot(
        free_cash_flow=0.0,
        fcf_yield=0.0,
    )
    result = _score(
        snapshot
    )
    assert (
        "valuation.fcf_yield"
        not in result.missing_metrics
    )
    assert (
        "cash.fcf_yield"
        not in result.missing_metrics
    )
    assert (
        "cash.fcf_conversion"
        not in result.missing_metrics
    )
def test_zero_net_income_makes_fcf_conversion_unavailable() -> None:
    snapshot = _complete_snapshot(
        net_income=0.0,
        earnings_yield=0.0,
    )
    result = _score(
        snapshot
    )
    assert (
        "cash.fcf_conversion"
        in result.missing_metrics
    )
    assert (
        "valuation.earnings_yield"
        not in result.missing_metrics
    )
def test_missing_metrics_reduce_dimension_and_overall_coverage() -> None:
    snapshot = _complete_snapshot(
        fcf_yield=None,
        earnings_yield=None,
        forward_pe=None,
        ev_to_ebitda=None,
    )
    result = _score(
        snapshot
    )
    assert (
        result.dimension_coverage[
            "valuation"
        ]
        == 0.0
    )
    assert result.valuation == 50.0
    assert result.overall_coverage < 100.0
    assert {
        "valuation.fcf_yield",
        "valuation.earnings_yield",
        "valuation.forward_pe",
        "valuation.ev_to_ebitda",
    }.issubset(
        set(
            result.missing_metrics
        )
    )
def test_missing_all_metrics_produces_unreliable_result() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        price=100.0,
        data_quality=0.0,
    )
    result = _score(
        snapshot
    )
    assert result.recommendation == RADAR_UNRELIABLE
    assert result.overall_coverage < 50.0
    assert result.confidence < DEFAULT_MIN_CONFIDENCE
    assert any(
        "no debe utilizarse"
        in warning.casefold()
        for warning in result.warnings
    )
def test_snapshot_error_forces_unreliable_classification() -> None:
    snapshot = _complete_snapshot(
        errors="Provider error",
    )
    result = _score(
        snapshot
    )
    assert result.recommendation == RADAR_UNRELIABLE
    assert result.confidence <= 20.0
def test_missing_price_forces_unreliable_classification() -> None:
    snapshot = _complete_snapshot(
        price=None,
    )
    result = _score(
        snapshot
    )
    assert result.recommendation == RADAR_UNRELIABLE
def test_low_confidence_forces_unreliable_classification() -> None:
    snapshot = _complete_snapshot(
        data_quality=20.0,
    )
    result = _score(
        snapshot,
        min_confidence=55.0,
    )
    assert result.recommendation == RADAR_UNRELIABLE
def test_low_coverage_forces_unreliable_classification() -> None:
    snapshot = _complete_snapshot(
        fcf_yield=None,
        earnings_yield=None,
        forward_pe=None,
        ev_to_ebitda=None,
        roe=None,
        roa=None,
        operating_margin=None,
        net_margin=None,
    )
    result = _score(
        snapshot,
        min_coverage=90.0,
    )
    assert result.overall_coverage < 90.0
    assert result.recommendation == RADAR_UNRELIABLE
def test_priority_classification() -> None:
    recommendation = _radar_recommendation(
        global_score=85.0,
        valuation=80.0,
        balance=70.0,
        confidence=90.0,
        overall_coverage=90.0,
        thresholds=_thresholds(),
        min_confidence=55.0,
        min_coverage=50.0,
        snapshot=_complete_snapshot(),
    )
    assert recommendation == RADAR_PRIORITY
def test_candidate_classification() -> None:
    recommendation = _radar_recommendation(
        global_score=74.0,
        valuation=60.0,
        balance=40.0,
        confidence=90.0,
        overall_coverage=90.0,
        thresholds=_thresholds(),
        min_confidence=55.0,
        min_coverage=50.0,
        snapshot=_complete_snapshot(),
    )
    assert recommendation == RADAR_CANDIDATE
def test_watch_classification() -> None:
    recommendation = _radar_recommendation(
        global_score=62.0,
        valuation=40.0,
        balance=40.0,
        confidence=90.0,
        overall_coverage=90.0,
        thresholds=_thresholds(),
        min_confidence=55.0,
        min_coverage=50.0,
        snapshot=_complete_snapshot(),
    )
    assert recommendation == RADAR_WATCH
def test_discard_classification() -> None:
    recommendation = _radar_recommendation(
        global_score=40.0,
        valuation=40.0,
        balance=40.0,
        confidence=90.0,
        overall_coverage=90.0,
        thresholds=_thresholds(),
        min_confidence=55.0,
        min_coverage=50.0,
        snapshot=_complete_snapshot(),
    )
    assert recommendation == RADAR_DISCARD
def test_priority_requires_valuation_and_balance_conditions() -> None:
    recommendation = _radar_recommendation(
        global_score=90.0,
        valuation=69.9,
        balance=100.0,
        confidence=100.0,
        overall_coverage=100.0,
        thresholds=_thresholds(),
        min_confidence=55.0,
        min_coverage=50.0,
        snapshot=_complete_snapshot(),
    )
    assert recommendation == RADAR_CANDIDATE
def test_candidate_requires_minimum_valuation() -> None:
    recommendation = _radar_recommendation(
        global_score=75.0,
        valuation=54.9,
        balance=100.0,
        confidence=100.0,
        overall_coverage=100.0,
        thresholds=_thresholds(),
        min_confidence=55.0,
        min_coverage=50.0,
        snapshot=_complete_snapshot(),
    )
    assert recommendation == RADAR_WATCH
def test_legacy_threshold_configuration_remains_compatible() -> None:
    result = _score(
        thresholds={
            "strong_entry": 80.0,
            "entry": 70.0,
            "watch": 58.0,
        }
    )
    assert result.recommendation in {
        RADAR_PRIORITY,
        RADAR_CANDIDATE,
        RADAR_WATCH,
        RADAR_DISCARD,
        RADAR_UNRELIABLE,
    }
def test_invalid_weights_do_not_break_scoring() -> None:
    result = _score(
        weights={}
    )
    assert isinstance(
        result,
        ScoreCard,
    )
    assert 0.0 <= result.global_score <= 100.0
    assert any(
        "ponderación uniforme"
        in warning.casefold()
        for warning in result.warnings
    )
def test_invalid_threshold_order_uses_defaults() -> None:
    result = _score(
        thresholds={
            "priority": 50.0,
            "candidate": 80.0,
            "watch": 70.0,
        }
    )
    assert isinstance(
        result,
        ScoreCard,
    )
    assert any(
        "umbrales no estaban ordenados"
        in warning.casefold()
        for warning in result.warnings
    )
def test_snapshot_warnings_are_propagated_and_deduplicated() -> None:
    snapshot = _complete_snapshot(
        warnings=[
            "Dato secundario.",
            "dato secundario.",
        ]
    )
    result = _score(
        snapshot
    )
    assert sum(
        warning.casefold()
        == "dato secundario."
        for warning in result.warnings
    ) == 1
def test_debt_to_equity_normalization_warning_is_exposed() -> None:
    snapshot = _complete_snapshot(
        debt_to_equity=55.0
    )
    result = _score(
        snapshot
    )
    assert any(
        "dividido entre 100"
        in warning.casefold()
        for warning in result.warnings
    )
def test_negative_debt_to_equity_becomes_missing() -> None:
    snapshot = _complete_snapshot(
        debt_to_equity=-5.0
    )
    result = _score(
        snapshot
    )
    assert (
        "balance.debt_to_equity"
        in result.missing_metrics
    )
    assert (
        "risk.debt_to_equity"
        in result.missing_metrics
    )
    assert any(
        "patrimonio"
        in warning.casefold()
        for warning in result.warnings
    )
def test_analyst_target_warning_is_only_added_when_used() -> None:
    with_target = _score(
        _complete_snapshot(
            analyst_target=115.0
        )
    )
    without_target = _score(
        _complete_snapshot(
            analyst_target=None
        )
    )
    assert any(
        "precio objetivo"
        in warning.casefold()
        for warning in with_target.warnings
    )
    assert not any(
        "precio objetivo"
        in warning.casefold()
        for warning in without_target.warnings
    )
def test_capital_allocation_proxy_warning_is_included() -> None:
    result = _score()
    assert any(
        "asignación de capital"
        in warning.casefold()
        for warning in result.warnings
    )
def test_risk_dimension_does_not_use_market_price_momentum() -> None:
    low_change = _score(
        _complete_snapshot(
            fifty_two_week_change=-0.90
        )
    )
    high_change = _score(
        _complete_snapshot(
            fifty_two_week_change=2.00
        )
    )
    assert low_change.risk == high_change.risk
def test_global_score_is_normalized_when_weights_do_not_sum_to_one() -> None:
    standard_result = _score()
    scaled_result = _score(
        weights={
            name: value * 100
            for name, value in _weights().items()
        }
    )
    assert scaled_result.global_score == pytest.approx(
        standard_result.global_score
    )
def test_minimum_confidence_and_coverage_are_bounded() -> None:
    result = _score(
        min_confidence=150.0,
        min_coverage=-10.0,
    )
    assert result.recommendation == RADAR_UNRELIABLE
@pytest.mark.parametrize(
    ("snapshot", "weights", "thresholds", "message"),
    [
        (
            {},
            _weights(),
            _thresholds(),
            "CompanySnapshot",
        ),
        (
            _complete_snapshot(),
            [],
            _thresholds(),
            "weights",
        ),
        (
            _complete_snapshot(),
            _weights(),
            [],
            "thresholds",
        ),
    ],
)
def test_score_snapshot_validates_input_types(
    snapshot: Any,
    weights: Any,
    thresholds: Any,
    message: str,
) -> None:
    expected_exception = (
        TypeError
    )
    with pytest.raises(
        expected_exception,
        match=message,
    ):
        score_snapshot(
            snapshot,
            weights,
            thresholds,
        )
def test_deduplicate_strings_trims_and_ignores_invalid_values() -> None:
    result = _deduplicate_strings(
        [
            " Primero ",
            "primero",
            "",
            "   ",
            "Segundo",
        ]
    )
    assert result == [
        "Primero",
        "Segundo",
    ]
def test_score_card_is_json_serializable() -> None:
    result = _score()
    serialized = json.dumps(
        result.to_dict(),
        ensure_ascii=False,
    )
    assert isinstance(
        serialized,
        str,
    )
    assert "TEST" in serialized
    assert SCORING_VERSION in serialized
def test_all_scores_are_finite() -> None:
    result = _score(
        _complete_snapshot(
            forward_pe=float("inf"),
            ev_to_ebitda=float("nan"),
            roe=float("-inf"),
        )
    )
    values = [
        result.valuation,
        result.quality,
        result.cash,
        result.balance,
        result.growth,
        result.capital_allocation,
        result.momentum_fundamental,
        result.risk,
        result.confidence,
        result.global_score,
        result.overall_coverage,
    ]
    assert all(
        math.isfinite(value)
        for value in values
    )
def test_rationale_identifies_radar_classification() -> None:
    result = _score()
    assert (
        f"Clasificación de radar: "
        f"{result.recommendation}"
        in result.rationale
    )
    assert "Fortalezas relativas" in result.rationale
    assert "Áreas más débiles" in result.rationale
def test_low_dimension_coverage_is_mentioned_in_rationale() -> None:
    snapshot = _complete_snapshot(
        fcf_yield=None,
        earnings_yield=None,
        forward_pe=None,
        ev_to_ebitda=None,
    )
    result = _score(
        snapshot
    )
    assert (
        "Cobertura limitada en"
        in result.rationale
    )
    assert "valoración" in result.rationale.casefold()
