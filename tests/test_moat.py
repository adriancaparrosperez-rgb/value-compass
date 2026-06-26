from __future__ import annotations

from src.analysis.moat import (
    MoatInput,
    assess_moat,
)
from src.decision.enums import (
    EvidenceConfidence,
    MoatStrength,
    MoatTrend,
)


def test_strong_preliminary_moat_is_detected() -> None:
    assessment = assess_moat(
        MoatInput(
            switching_costs_score=85.0,
            network_effects_score=80.0,
            brand_score=75.0,
            scale_score=80.0,
            data_advantage_score=75.0,
            intellectual_property_score=70.0,
            distribution_score=80.0,
            regulatory_advantage_score=60.0,
            margin_stability_score=85.0,
            roic_persistence_score=85.0,
            recurring_revenue_score=90.0,
            pricing_power_score=80.0,
            substitution_risk_score=20.0,
            disruption_risk_score=25.0,
        )
    )

    assert assessment.preliminary_score is not None
    assert assessment.preliminary_score >= 75.0
    assert assessment.strength == MoatStrength.STRONG
    assert assessment.trend == MoatTrend.NOT_EVALUATED
    assert assessment.confidence == EvidenceConfidence.LOW
    assert assessment.reviewed_score is None


def test_high_disruption_risk_reduces_preliminary_score() -> None:
    low_risk = assess_moat(
        MoatInput(
            switching_costs_score=80.0,
            network_effects_score=75.0,
            brand_score=75.0,
            scale_score=75.0,
            margin_stability_score=80.0,
            roic_persistence_score=80.0,
            recurring_revenue_score=85.0,
            pricing_power_score=75.0,
            substitution_risk_score=20.0,
            disruption_risk_score=20.0,
        )
    )

    high_risk = assess_moat(
        MoatInput(
            switching_costs_score=80.0,
            network_effects_score=75.0,
            brand_score=75.0,
            scale_score=75.0,
            margin_stability_score=80.0,
            roic_persistence_score=80.0,
            recurring_revenue_score=85.0,
            pricing_power_score=75.0,
            substitution_risk_score=80.0,
            disruption_risk_score=90.0,
        )
    )

    assert low_risk.preliminary_score is not None
    assert high_risk.preliminary_score is not None
    assert (
        high_risk.preliminary_score
        < low_risk.preliminary_score
    )


def test_reviewed_moat_overrides_preliminary_result() -> None:
    assessment = assess_moat(
        MoatInput(
            switching_costs_score=90.0,
            network_effects_score=85.0,
            brand_score=85.0,
            scale_score=85.0,
            margin_stability_score=90.0,
            roic_persistence_score=90.0,
            recurring_revenue_score=90.0,
            pricing_power_score=85.0,
            substitution_risk_score=60.0,
            disruption_risk_score=70.0,
            reviewed_score=55.0,
            reviewed_strength=MoatStrength.MODERATE,
            reviewed_trend=MoatTrend.DETERIORATING,
            reviewed_confidence=EvidenceConfidence.HIGH,
        )
    )

    assert assessment.reviewed_score == 43.0
    assert assessment.strength == MoatStrength.MODERATE
    assert assessment.trend == MoatTrend.DETERIORATING
    assert assessment.confidence == EvidenceConfidence.HIGH


def test_improving_trend_increases_reviewed_score() -> None:
    assessment = assess_moat(
        MoatInput(
            reviewed_score=70.0,
            reviewed_trend=MoatTrend.IMPROVING,
            reviewed_confidence=EvidenceConfidence.HIGH,
        )
    )

    assert assessment.reviewed_score == 75.0
    assert assessment.trend == MoatTrend.IMPROVING


def test_deteriorating_trend_reduces_reviewed_score() -> None:
    assessment = assess_moat(
        MoatInput(
            reviewed_score=70.0,
            reviewed_trend=MoatTrend.DETERIORATING,
            reviewed_confidence=EvidenceConfidence.MEDIUM,
        )
    )

    assert assessment.reviewed_score == 58.0
    assert any(
        "deterioro" in warning.lower()
        for warning in assessment.warnings
    )


def test_rapid_deterioration_reduces_score_materially() -> None:
    assessment = assess_moat(
        MoatInput(
            reviewed_score=80.0,
            reviewed_trend=(
                MoatTrend.RAPIDLY_DETERIORATING
            ),
            reviewed_confidence=EvidenceConfidence.HIGH,
        )
    )

    assert assessment.reviewed_score == 55.0
    assert any(
        "rápidamente" in warning.lower()
        for warning in assessment.warnings
    )


def test_missing_review_generates_warning() -> None:
    assessment = assess_moat(
        MoatInput(
            switching_costs_score=70.0,
            brand_score=70.0,
            scale_score=70.0,
            margin_stability_score=70.0,
            roic_persistence_score=70.0,
            recurring_revenue_score=70.0,
            pricing_power_score=70.0,
            substitution_risk_score=30.0,
            disruption_risk_score=30.0,
        )
    )

    assert assessment.reviewed_score is None
    assert any(
        "no ha sido revisado" in warning.lower()
        for warning in assessment.warnings
    )


def test_missing_risk_assessments_generate_warnings() -> None:
    assessment = assess_moat(
        MoatInput(
            switching_costs_score=70.0,
            brand_score=70.0,
            scale_score=70.0,
        )
    )

    assert any(
        "sustitución" in warning.lower()
        for warning in assessment.warnings
    )

    assert any(
        "disrupción" in warning.lower()
        for warning in assessment.warnings
    )


def test_insufficient_structural_dimensions_warns() -> None:
    assessment = assess_moat(
        MoatInput(
            switching_costs_score=80.0,
            brand_score=75.0,
            substitution_risk_score=20.0,
            disruption_risk_score=20.0,
        )
    )

    assert any(
        "cobertura de dimensiones estructurales"
        in warning.lower()
        for warning in assessment.warnings
    )


def test_no_data_does_not_create_false_moat() -> None:
    assessment = assess_moat(
        MoatInput()
    )

    assert assessment.preliminary_score is None
    assert assessment.reviewed_score is None
    assert assessment.strength == (
        MoatStrength.NOT_EVALUATED
    )
    assert assessment.confidence == (
        EvidenceConfidence.NOT_EVALUABLE
    )


def test_scores_are_clamped_between_zero_and_one_hundred() -> None:
    assessment = assess_moat(
        MoatInput(
            switching_costs_score=150.0,
            network_effects_score=-20.0,
            brand_score=120.0,
            scale_score=110.0,
            margin_stability_score=150.0,
            roic_persistence_score=150.0,
            recurring_revenue_score=150.0,
            pricing_power_score=150.0,
            substitution_risk_score=-10.0,
            disruption_risk_score=120.0,
        )
    )

    assert assessment.switching_costs_score == 100.0
    assert assessment.network_effects_score == 0.0
    assert assessment.disruption_risk_score == 100.0
    assert assessment.preliminary_score is not None
    assert 0.0 <= assessment.preliminary_score <= 100.0


def test_evidence_and_threats_are_preserved() -> None:
    assessment = assess_moat(
        MoatInput(
            reviewed_score=70.0,
            reviewed_trend=MoatTrend.STABLE,
            reviewed_confidence=EvidenceConfidence.HIGH,
            evidence=[
                "Alta retención de clientes",
                "Ecosistema integrado",
            ],
            threats=[
                "Nuevos competidores",
                "Disrupción tecnológica",
            ],
        )
    )

    assert "Alta retención de clientes" in assessment.evidence
    assert "Disrupción tecnológica" in assessment.threats
