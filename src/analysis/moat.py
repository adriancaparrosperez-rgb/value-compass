from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any
from src.decision.enums import (
    EvidenceConfidence,
    MoatStrength,
    MoatTrend,
)
from src.decision.models import MoatAssessment
@dataclass
class MoatInput:
    switching_costs_score: float | None = None
    network_effects_score: float | None = None
    brand_score: float | None = None
    scale_score: float | None = None
    data_advantage_score: float | None = None
    intellectual_property_score: float | None = None
    distribution_score: float | None = None
    regulatory_advantage_score: float | None = None
    substitution_risk_score: float | None = None
    disruption_risk_score: float | None = None
    margin_stability_score: float | None = None
    roic_persistence_score: float | None = None
    recurring_revenue_score: float | None = None
    pricing_power_score: float | None = None
    reviewed_score: float | None = None
    reviewed_strength: MoatStrength | None = None
    reviewed_trend: MoatTrend = MoatTrend.NOT_EVALUATED
    reviewed_confidence: EvidenceConfidence = (
        EvidenceConfidence.NOT_EVALUABLE
    )
    evidence: list[str] = field(default_factory=list)
    threats: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
def _is_valid_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric_value)
def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(maximum, float(value)),
    )
def _normalized_score(
    value: float | None,
) -> float | None:
    if not _is_valid_number(value):
        return None
    return _clamp(float(value))
def _weighted_average(
    components: list[tuple[float | None, float]],
) -> float | None:
    valid_components = [
        (float(value), weight)
        for value, weight in components
        if value is not None
    ]
    if not valid_components:
        return None
    total_weight = sum(
        weight
        for _, weight in valid_components
    )
    if total_weight <= 0:
        return None
    return sum(
        value * weight
        for value, weight in valid_components
    ) / total_weight
def _strength_from_score(
    score: float | None,
) -> MoatStrength:
    if score is None:
        return MoatStrength.NOT_EVALUATED
    if score >= 75:
        return MoatStrength.STRONG
    if score >= 55:
        return MoatStrength.MODERATE
    return MoatStrength.WEAK
def _apply_risk_penalty(
    base_score: float | None,
    substitution_risk: float | None,
    disruption_risk: float | None,
) -> float | None:
    if base_score is None:
        return None
    penalty = 0.0
    if substitution_risk is not None:
        if substitution_risk >= 85:
            penalty += 25.0
        elif substitution_risk >= 70:
            penalty += 15.0
        elif substitution_risk >= 50:
            penalty += 7.0
    if disruption_risk is not None:
        if disruption_risk >= 85:
            penalty += 30.0
        elif disruption_risk >= 70:
            penalty += 18.0
        elif disruption_risk >= 50:
            penalty += 8.0
    return _clamp(
        base_score - penalty
    )
def _trend_adjustment(
    score: float | None,
    trend: MoatTrend,
) -> float | None:
    if score is None:
        return None
    if trend == MoatTrend.IMPROVING:
        return _clamp(score + 5.0)
    if trend == MoatTrend.DETERIORATING:
        return _clamp(score - 12.0)
    if trend == MoatTrend.RAPIDLY_DETERIORATING:
        return _clamp(score - 25.0)
    return score
def assess_moat(
    data: MoatInput,
) -> MoatAssessment:
    warnings: list[str] = []
    evidence = list(data.evidence)
    threats = list(data.threats)
    notes = list(data.notes)
    switching_costs = _normalized_score(
        data.switching_costs_score
    )
    network_effects = _normalized_score(
        data.network_effects_score
    )
    brand = _normalized_score(
        data.brand_score
    )
    scale = _normalized_score(
        data.scale_score
    )
    data_advantage = _normalized_score(
        data.data_advantage_score
    )
    intellectual_property = _normalized_score(
        data.intellectual_property_score
    )
    distribution = _normalized_score(
        data.distribution_score
    )
    regulatory_advantage = _normalized_score(
        data.regulatory_advantage_score
    )
    substitution_risk = _normalized_score(
        data.substitution_risk_score
    )
    disruption_risk = _normalized_score(
        data.disruption_risk_score
    )
    margin_stability = _normalized_score(
        data.margin_stability_score
    )
    roic_persistence = _normalized_score(
        data.roic_persistence_score
    )
    recurring_revenue = _normalized_score(
        data.recurring_revenue_score
    )
    pricing_power = _normalized_score(
        data.pricing_power_score
    )
    structural_score = _weighted_average(
        [
            (switching_costs, 0.18),
            (network_effects, 0.16),
            (brand, 0.12),
            (scale, 0.12),
            (data_advantage, 0.10),
            (intellectual_property, 0.12),
            (distribution, 0.12),
            (regulatory_advantage, 0.08),
        ]
    )
    operating_evidence_score = _weighted_average(
        [
            (margin_stability, 0.25),
            (roic_persistence, 0.30),
            (recurring_revenue, 0.20),
            (pricing_power, 0.25),
        ]
    )
    preliminary_score = _weighted_average(
        [
            (structural_score, 0.65),
            (operating_evidence_score, 0.35),
        ]
    )
    preliminary_score = _apply_risk_penalty(
        base_score=preliminary_score,
        substitution_risk=substitution_risk,
        disruption_risk=disruption_risk,
    )
    reviewed_score = _normalized_score(
        data.reviewed_score
    )
    final_score: float | None
    if reviewed_score is not None:
        final_score = _trend_adjustment(
            reviewed_score,
            data.reviewed_trend,
        )
        strength = (
            data.reviewed_strength
            if data.reviewed_strength is not None
            else _strength_from_score(final_score)
        )
        trend = data.reviewed_trend
        confidence = data.reviewed_confidence
        notes.append(
            "La evaluación final del moat utiliza "
            "la revisión cualitativa."
        )
    else:
        final_score = preliminary_score
        strength = _strength_from_score(
            preliminary_score
        )
        trend = MoatTrend.NOT_EVALUATED
        confidence = (
            EvidenceConfidence.LOW
            if preliminary_score is not None
            else EvidenceConfidence.NOT_EVALUABLE
        )
        notes.append(
            "El moat solo dispone de una evaluación preliminar."
        )
    if preliminary_score is None:
        warnings.append(
            "No hay suficientes datos para calcular "
            "un moat preliminar."
        )
    if reviewed_score is None:
        warnings.append(
            "El moat no ha sido revisado cualitativamente."
        )
    if substitution_risk is None:
        warnings.append(
            "El riesgo de sustitución no ha sido evaluado."
        )
    elif substitution_risk >= 70:
        warnings.append(
            "El riesgo de sustitución es elevado."
        )
    if disruption_risk is None:
        warnings.append(
            "El riesgo de disrupción no ha sido evaluado."
        )
    elif disruption_risk >= 70:
        warnings.append(
            "El riesgo de disrupción es elevado."
        )
    if (
        data.reviewed_trend
        == MoatTrend.DETERIORATING
    ):
        warnings.append(
            "El moat presenta señales de deterioro."
        )
    if (
        data.reviewed_trend
        == MoatTrend.RAPIDLY_DETERIORATING
    ):
        warnings.append(
            "El moat se está deteriorando rápidamente."
        )
    moat_dimensions = [
        switching_costs,
        network_effects,
        brand,
        scale,
        data_advantage,
        intellectual_property,
        distribution,
        regulatory_advantage,
    ]
    evaluated_dimensions = sum(
        dimension is not None
        for dimension in moat_dimensions
    )
    if evaluated_dimensions < 3:
        warnings.append(
            "La cobertura de dimensiones estructurales "
            "del moat es insuficiente."
        )
    if (
        final_score is not None
        and final_score >= 75
        and disruption_risk is not None
        and disruption_risk >= 70
    ):
        warnings.append(
            "Existe una contradicción entre el moat elevado "
            "y el riesgo de disrupción alto; debe revisarse."
        )
    return MoatAssessment(
        strength=strength,
        trend=trend,
        confidence=confidence,
        switching_costs_score=switching_costs,
        network_effects_score=network_effects,
        brand_score=brand,
        scale_score=scale,
        data_advantage_score=data_advantage,
        intellectual_property_score=(
            intellectual_property
        ),
        distribution_score=distribution,
        regulatory_advantage_score=(
            regulatory_advantage
        ),
        substitution_risk_score=substitution_risk,
        disruption_risk_score=disruption_risk,
        preliminary_score=(
            round(preliminary_score, 1)
            if preliminary_score is not None
            else None
        ),
        reviewed_score=(
            round(final_score, 1)
            if reviewed_score is not None
            and final_score is not None
            else None
        ),
        evidence=evidence,
        threats=threats,
        warnings=warnings,
        notes=notes,
    )
