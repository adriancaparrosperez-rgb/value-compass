from __future__ import annotations

import pytest

from src.decision.enums import ValuationStatus
from src.valuation.scenarios import (
    ScenarioAssumptions,
    ScenarioValuationInput,
    assess_valuation_scenarios,
    calculate_scenario_value,
)


def _conservative_assumptions() -> ScenarioAssumptions:
    return ScenarioAssumptions(
        name="Conservador",
        revenue_growth=0.02,
        operating_margin=0.12,
        tax_rate=0.25,
        reinvestment_rate=0.45,
        discount_rate=0.10,
        terminal_growth=0.02,
        explicit_years=5,
    )


def _base_assumptions() -> ScenarioAssumptions:
    return ScenarioAssumptions(
        name="Base",
        revenue_growth=0.06,
        operating_margin=0.16,
        tax_rate=0.25,
        reinvestment_rate=0.35,
        discount_rate=0.09,
        terminal_growth=0.025,
        explicit_years=5,
    )


def _optimistic_assumptions() -> ScenarioAssumptions:
    return ScenarioAssumptions(
        name="Optimista",
        revenue_growth=0.10,
        operating_margin=0.20,
        tax_rate=0.25,
        reinvestment_rate=0.25,
        discount_rate=0.08,
        terminal_growth=0.03,
        explicit_years=5,
    )


def test_calculate_scenario_returns_positive_value() -> None:
    result = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=1_000.0,
        assumptions=_base_assumptions(),
    )

    assert result.name == "Base"
    assert result.intrinsic_value_per_share is not None
    assert result.intrinsic_value_per_share > 0
    assert result.assumptions["enterprise_value"] > 0
    assert result.assumptions["equity_value"] > 0


def test_optimistic_value_exceeds_base_value() -> None:
    base_result = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=1_000.0,
        assumptions=_base_assumptions(),
    )

    optimistic_result = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=1_000.0,
        assumptions=_optimistic_assumptions(),
    )

    assert (
        optimistic_result.intrinsic_value_per_share
        > base_result.intrinsic_value_per_share
    )


def test_conservative_value_is_below_base_value() -> None:
    conservative_result = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=1_000.0,
        assumptions=_conservative_assumptions(),
    )

    base_result = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=1_000.0,
        assumptions=_base_assumptions(),
    )

    assert (
        conservative_result.intrinsic_value_per_share
        < base_result.intrinsic_value_per_share
    )


def test_net_debt_reduces_intrinsic_value_per_share() -> None:
    without_debt = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=0.0,
        assumptions=_base_assumptions(),
    )

    with_debt = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=2_000.0,
        assumptions=_base_assumptions(),
    )

    assert (
        with_debt.intrinsic_value_per_share
        < without_debt.intrinsic_value_per_share
    )


def test_more_shares_reduce_intrinsic_value_per_share() -> None:
    fewer_shares = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=1_000.0,
        assumptions=_base_assumptions(),
    )

    more_shares = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=200.0,
        net_debt=1_000.0,
        assumptions=_base_assumptions(),
    )

    assert (
        more_shares.intrinsic_value_per_share
        < fewer_shares.intrinsic_value_per_share
    )


def test_assessment_returns_three_scenarios() -> None:
    assessment = assess_valuation_scenarios(
        ScenarioValuationInput(
            current_price=100.0,
            diluted_shares=100.0,
            current_revenue=10_000.0,
            net_debt=1_000.0,
            conservative=_conservative_assumptions(),
            base=_base_assumptions(),
            optimistic=_optimistic_assumptions(),
        )
    )

    assert assessment.conservative is not None
    assert assessment.base is not None
    assert assessment.optimistic is not None
    assert assessment.valuation_score is not None
    assert assessment.status != ValuationStatus.NOT_EVALUATED


def test_missing_conservative_scenario_generates_warning() -> None:
    assessment = assess_valuation_scenarios(
        ScenarioValuationInput(
            current_price=100.0,
            diluted_shares=100.0,
            current_revenue=10_000.0,
            base=_base_assumptions(),
            optimistic=_optimistic_assumptions(),
        )
    )

    assert assessment.conservative is None
    assert any(
        "conservador" in warning.lower()
        for warning in assessment.warnings
    )


def test_missing_base_scenario_generates_warning() -> None:
    assessment = assess_valuation_scenarios(
        ScenarioValuationInput(
            current_price=100.0,
            diluted_shares=100.0,
            current_revenue=10_000.0,
            conservative=_conservative_assumptions(),
            optimistic=_optimistic_assumptions(),
        )
    )

    assert assessment.base is None
    assert any(
        "escenario base" in warning.lower()
        for warning in assessment.warnings
    )


def test_missing_optimistic_scenario_generates_warning() -> None:
    assessment = assess_valuation_scenarios(
        ScenarioValuationInput(
            current_price=100.0,
            diluted_shares=100.0,
            current_revenue=10_000.0,
            conservative=_conservative_assumptions(),
            base=_base_assumptions(),
        )
    )

    assert assessment.optimistic is None
    assert any(
        "optimista" in warning.lower()
        for warning in assessment.warnings
    )


def test_invalid_current_price_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="precio actual",
    ):
        assess_valuation_scenarios(
            ScenarioValuationInput(
                current_price=0.0,
                diluted_shares=100.0,
                current_revenue=10_000.0,
                base=_base_assumptions(),
            )
        )


def test_invalid_share_count_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="acciones diluidas",
    ):
        assess_valuation_scenarios(
            ScenarioValuationInput(
                current_price=100.0,
                diluted_shares=0.0,
                current_revenue=10_000.0,
                base=_base_assumptions(),
            )
        )


def test_invalid_revenue_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="ingresos actuales",
    ):
        assess_valuation_scenarios(
            ScenarioValuationInput(
                current_price=100.0,
                diluted_shares=100.0,
                current_revenue=0.0,
                base=_base_assumptions(),
            )
        )


def test_at_least_one_scenario_is_required() -> None:
    with pytest.raises(
        ValueError,
        match="al menos un escenario",
    ):
        assess_valuation_scenarios(
            ScenarioValuationInput(
                current_price=100.0,
                diluted_shares=100.0,
                current_revenue=10_000.0,
            )
        )


def test_discount_rate_must_exceed_terminal_growth() -> None:
    invalid_assumptions = ScenarioAssumptions(
        name="Inválido",
        revenue_growth=0.05,
        operating_margin=0.15,
        tax_rate=0.25,
        reinvestment_rate=0.30,
        discount_rate=0.02,
        terminal_growth=0.03,
    )

    with pytest.raises(
        ValueError,
        match="tasa de descuento",
    ):
        calculate_scenario_value(
            current_revenue=10_000.0,
            diluted_shares=100.0,
            net_debt=0.0,
            assumptions=invalid_assumptions,
        )


def test_invalid_tax_rate_raises_error() -> None:
    invalid_assumptions = ScenarioAssumptions(
        name="Inválido",
        revenue_growth=0.05,
        operating_margin=0.15,
        tax_rate=0.80,
        reinvestment_rate=0.30,
        discount_rate=0.09,
        terminal_growth=0.02,
    )

    with pytest.raises(
        ValueError,
        match="tasa fiscal",
    ):
        calculate_scenario_value(
            current_revenue=10_000.0,
            diluted_shares=100.0,
            net_debt=0.0,
            assumptions=invalid_assumptions,
        )


def test_yearly_projections_are_stored() -> None:
    result = calculate_scenario_value(
        current_revenue=10_000.0,
        diluted_shares=100.0,
        net_debt=1_000.0,
        assumptions=_base_assumptions(),
    )

    projections = result.assumptions[
        "yearly_projections"
    ]

    assert len(projections) == 5
    assert projections[0]["year"] == 1.0
    assert projections[-1]["year"] == 5.0


def test_valuation_is_undervalued_when_price_is_low() -> None:
    assessment = assess_valuation_scenarios(
        ScenarioValuationInput(
            current_price=10.0,
            diluted_shares=100.0,
            current_revenue=10_000.0,
            net_debt=0.0,
            conservative=_conservative_assumptions(),
            base=_base_assumptions(),
            optimistic=_optimistic_assumptions(),
        )
    )

    assert assessment.status == ValuationStatus.UNDERVALUED
    assert assessment.margin_of_safety_base is not None
    assert assessment.margin_of_safety_base > 0


def test_valuation_is_overvalued_when_price_is_high() -> None:
    assessment = assess_valuation_scenarios(
        ScenarioValuationInput(
            current_price=10_000.0,
            diluted_shares=100.0,
            current_revenue=10_000.0,
            net_debt=1_000.0,
            conservative=_conservative_assumptions(),
            base=_base_assumptions(),
            optimistic=_optimistic_assumptions(),
        )
    )

    assert assessment.status == ValuationStatus.OVERVALUED
    assert assessment.margin_of_safety_base is not None
    assert assessment.margin_of_safety_base < 0


def test_inverted_scenario_order_generates_warning() -> None:
    aggressive_conservative = ScenarioAssumptions(
        name="Conservador",
        revenue_growth=0.15,
        operating_margin=0.25,
        tax_rate=0.20,
        reinvestment_rate=0.20,
        discount_rate=0.07,
        terminal_growth=0.03,
    )

    weak_base = ScenarioAssumptions(
        name="Base",
        revenue_growth=0.01,
        operating_margin=0.08,
        tax_rate=0.30,
        reinvestment_rate=0.60,
        discount_rate=0.12,
        terminal_growth=0.01,
    )

    assessment = assess_valuation_scenarios(
        ScenarioValuationInput(
            current_price=100.0,
            diluted_shares=100.0,
            current_revenue=10_000.0,
            conservative=aggressive_conservative,
            base=weak_base,
        )
    )

    assert any(
        "conservador ofrece un valor superior"
        in warning.lower()
        for warning in assessment.warnings
    )
