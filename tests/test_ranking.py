from __future__ import annotations

import pytest

from src.decision.enums import (
    DataQualityStatus,
    MoatStrength,
    MoatTrend,
    ValuationStatus,
)
from src.decision.models import (
    AccountingAssessment,
    BusinessAssessment,
    DataQualityAssessment,
    MasterAnalysisInput,
    MoatAssessment,
    PerShareAssessment,
    ValuationAssessment,
)
from src.decision.ranking import calculate_ranking


def _complete_analysis() -> MasterAnalysisInput:
    return MasterAnalysisInput(
        ticker="TEST",
        data_quality=DataQualityAssessment(
            status=DataQualityStatus.VALIDATED,
            coverage_score=90.0,
            freshness_score=90.0,
            consistency_score=90.0,
            source_quality_score=90.0,
        ),
        business=BusinessAssessment(
            operating_quality_score=80.0,
            organic_growth_score=75.0,
            balance_score=85.0,
            cash_score=80.0,
            capital_allocation_score=75.0,
            risk_score=25.0,
        ),
        accounting=AccountingAssessment(
            accounting_quality_score=80.0,
            earnings_quality_score=75.0,
            cash_conversion_score=85.0,
            sbc_to_revenue=0.03,
        ),
        per_share=PerShareAssessment(
            per_share_value_score=80.0,
            share_count_growth=0.01,
        ),
        moat=MoatAssessment(
            strength=MoatStrength.STRONG,
            trend=MoatTrend.STABLE,
            reviewed_score=82.0,
            substitution_risk_score=25.0,
            disruption_risk_score=30.0,
        ),
        valuation=ValuationAssessment(
            valuation_score=75.0,
            status=ValuationStatus.ATTRACTIVE,
        ),
    )


def test_complete_analysis_returns_score() -> None:
    result = calculate_ranking(
        _complete_analysis()
    )

    assert result.score is not None
    assert result.score > 70.0
    assert result.coverage == 1.0
    assert len(result.components) == 6
    assert result.penalties == []


def test_score_is_clamped_to_valid_range() -> None:
    analysis = _complete_analysis()
    analysis.business.operating_quality_score = 150.0
    analysis.business.organic_growth_score = 150.0
    analysis.business.balance_score = 150.0
    analysis.business.cash_score = 150.0
    analysis.business.capital_allocation_score = 150.0
    analysis.accounting.accounting_quality_score = 150.0
    analysis.accounting.earnings_quality_score = 150.0
    analysis.accounting.cash_conversion_score = 150.0
    analysis.per_share.per_share_value_score = 150.0
    analysis.moat.reviewed_score = 150.0
    analysis.valuation.valuation_score = 150.0
    analysis.data_quality.coverage_score = 150.0
    analysis.data_quality.freshness_score = 150.0
    analysis.data_quality.consistency_score = 150.0
    analysis.data_quality.source_quality_score = 150.0
    result = calculate_ranking(
        analysis
    )
    assert result.score == 100.0

def test_missing_all_dimensions_returns_none() -> None:
    analysis = MasterAnalysisInput(
        ticker="EMPTY"
    )

    result = calculate_ranking(
        analysis
    )

    assert result.score is None
    assert result.coverage == 0.0
    assert any(
        "no hay dimensiones suficientes"
        in warning.lower()
        for warning in result.warnings
    )


def test_partial_coverage_generates_warning() -> None:
    analysis = MasterAnalysisInput(
        ticker="PARTIAL",
        moat=MoatAssessment(
            reviewed_score=80.0,
            strength=MoatStrength.STRONG,
        ),
        valuation=ValuationAssessment(
            valuation_score=70.0,
            status=ValuationStatus.ATTRACTIVE,
        ),
    )

    result = calculate_ranking(
        analysis
    )

    assert result.score is not None
    assert result.coverage < 0.50
    assert any(
        "inferior al 50"
        in warning.lower()
        for warning in result.warnings
    )


def test_business_risk_reduces_score() -> None:
    low_risk_analysis = _complete_analysis()
    high_risk_analysis = _complete_analysis()

    low_risk_analysis.business.risk_score = 20.0
    high_risk_analysis.business.risk_score = 85.0

    low_risk_result = calculate_ranking(
        low_risk_analysis
    )

    high_risk_result = calculate_ranking(
        high_risk_analysis
    )

    assert high_risk_result.score is not None
    assert low_risk_result.score is not None
    assert high_risk_result.score < low_risk_result.score
    assert any(
        "riesgo empresarial extremo"
        in penalty.lower()
        for penalty in high_risk_result.penalties
    )


def test_deteriorating_moat_applies_penalty() -> None:
    stable_analysis = _complete_analysis()
    deteriorating_analysis = _complete_analysis()

    stable_analysis.moat.trend = MoatTrend.STABLE
    deteriorating_analysis.moat.trend = (
        MoatTrend.DETERIORATING
    )

    stable_result = calculate_ranking(
        stable_analysis
    )

    deteriorating_result = calculate_ranking(
        deteriorating_analysis
    )

    assert stable_result.score is not None
    assert deteriorating_result.score is not None
    assert deteriorating_result.score < stable_result.score
    assert any(
        "moat presenta deterioro"
        in penalty.lower()
        for penalty in deteriorating_result.penalties
    )


def test_rapidly_deteriorating_moat_has_larger_penalty() -> None:
    deteriorating_analysis = _complete_analysis()
    rapid_analysis = _complete_analysis()

    deteriorating_analysis.moat.trend = (
        MoatTrend.DETERIORATING
    )

    rapid_analysis.moat.trend = (
        MoatTrend.RAPIDLY_DETERIORATING
    )

    deteriorating_result = calculate_ranking(
        deteriorating_analysis
    )

    rapid_result = calculate_ranking(
        rapid_analysis
    )

    assert deteriorating_result.score is not None
    assert rapid_result.score is not None
    assert rapid_result.score < deteriorating_result.score


def test_high_disruption_risk_applies_penalty() -> None:
    analysis = _complete_analysis()

    analysis.moat.disruption_risk_score = 90.0

    result = calculate_ranking(
        analysis
    )

    assert any(
        "disrupción extremo"
        in penalty.lower()
        for penalty in result.penalties
    )


def test_high_substitution_risk_applies_penalty() -> None:
    analysis = _complete_analysis()

    analysis.moat.substitution_risk_score = 90.0

    result = calculate_ranking(
        analysis
    )

    assert any(
        "sustitución extremo"
        in penalty.lower()
        for penalty in result.penalties
    )


def test_high_dilution_applies_penalty() -> None:
    analysis = _complete_analysis()

    analysis.per_share.share_count_growth = 0.08

    result = calculate_ranking(
        analysis
    )

    assert any(
        "dilución anual"
        in penalty.lower()
        for penalty in result.penalties
    )


def test_high_sbc_applies_penalty() -> None:
    analysis = _complete_analysis()

    analysis.accounting.sbc_to_revenue = 0.15

    result = calculate_ranking(
        analysis
    )

    assert any(
        "compensación en acciones"
        in penalty.lower()
        for penalty in result.penalties
    )


def test_unreliable_data_generates_warning() -> None:
    analysis = _complete_analysis()

    analysis.data_quality.status = (
        DataQualityStatus.UNRELIABLE
    )

    result = calculate_ranking(
        analysis
    )

    assert any(
        "no son fiables"
        in warning.lower()
        for warning in result.warnings
    )


def test_insufficient_data_generates_warning() -> None:
    analysis = _complete_analysis()

    analysis.data_quality.status = (
        DataQualityStatus.INSUFFICIENT
    )

    result = calculate_ranking(
        analysis
    )

    assert any(
        "calidad de los datos es insuficiente"
        in warning.lower()
        for warning in result.warnings
    )


@pytest.mark.parametrize(
    ("status", "expected_score"),
    [
        (
            ValuationStatus.UNDERVALUED,
            85.0,
        ),
        (
            ValuationStatus.VERY_ATTRACTIVE,
            85.0,
        ),
        (
            ValuationStatus.ATTRACTIVE,
            72.0,
        ),
        (
            ValuationStatus.FAIRLY_VALUED,
            55.0,
        ),
        (
            ValuationStatus.REASONABLE,
            55.0,
        ),
        (
            ValuationStatus.EXPENSIVE,
            35.0,
        ),
        (
            ValuationStatus.OVERVALUED,
            20.0,
        ),
        (
            ValuationStatus.VERY_EXPENSIVE,
            20.0,
        ),
    ],
)
def test_valuation_status_fallback(
    status: ValuationStatus,
    expected_score: float,
) -> None:
    analysis = MasterAnalysisInput(
        ticker="VALUE",
        valuation=ValuationAssessment(
            valuation_score=None,
            status=status,
        ),
    )

    result = calculate_ranking(
        analysis
    )

    valuation_component = next(
        component
        for component in result.components
        if component.name == "Valoración"
    )

    assert valuation_component.raw_score == expected_score


def test_reviewed_moat_score_has_priority() -> None:
    analysis = MasterAnalysisInput(
        ticker="MOAT",
        moat=MoatAssessment(
            reviewed_score=80.0,
            preliminary_score=50.0,
            strength=MoatStrength.WEAK,
        ),
    )

    result = calculate_ranking(
        analysis
    )

    moat_component = next(
        component
        for component in result.components
        if component.name == "Moat"
    )

    assert moat_component.raw_score == 80.0


def test_preliminary_moat_used_without_review() -> None:
    analysis = MasterAnalysisInput(
        ticker="MOAT",
        moat=MoatAssessment(
            reviewed_score=None,
            preliminary_score=65.0,
            strength=MoatStrength.WEAK,
        ),
    )

    result = calculate_ranking(
        analysis
    )

    moat_component = next(
        component
        for component in result.components
        if component.name == "Moat"
    )

    assert moat_component.raw_score == 65.0


def test_strength_used_when_no_moat_scores_exist() -> None:
    analysis = MasterAnalysisInput(
        ticker="MOAT",
        moat=MoatAssessment(
            strength=MoatStrength.STRONG,
        ),
    )

    result = calculate_ranking(
        analysis
    )

    moat_component = next(
        component
        for component in result.components
        if component.name == "Moat"
    )

    assert moat_component.raw_score == 85.0
