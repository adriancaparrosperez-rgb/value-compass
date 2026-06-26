from __future__ import annotations
from collections.abc import Iterable
from src.decision.enums import (
    DataQualityStatus,
    EvidenceConfidence,
    ExistingHolderAction,
    GateSeverity,
    MoatStrength,
    MoatTrend,
    NewInvestorAction,
    RiskLevel,
    ValuationStatus,
)
from src.decision.gates import (
    evaluate_master_gates,
    get_blocking_failures,
)
from src.decision.models import (
    GateResult,
    MasterAnalysisInput,
    MasterDecisionResult,
)
from src.decision.ranking import (
    RankingResult,
    calculate_ranking,
)
ATTRACTIVE_VALUATIONS = {
    ValuationStatus.UNDERVALUED,
    ValuationStatus.VERY_ATTRACTIVE,
    ValuationStatus.ATTRACTIVE,
}
REASONABLE_VALUATIONS = {
    ValuationStatus.FAIRLY_VALUED,
    ValuationStatus.REASONABLE,
}
EXPENSIVE_VALUATIONS = {
    ValuationStatus.OVERVALUED,
    ValuationStatus.EXPENSIVE,
    ValuationStatus.VERY_EXPENSIVE,
}
DETERIORATING_MOAT_TRENDS = {
    MoatTrend.DETERIORATING,
    MoatTrend.RAPIDLY_DETERIORATING,
}
def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            float(value),
        ),
    )
def _average_available(
    values: Iterable[float | None],
) -> float | None:
    available_values = [
        _clamp(value)
        for value in values
        if value is not None
    ]
    if not available_values:
        return None
    return sum(
        available_values
    ) / len(available_values)
def _deduplicate(
    values: Iterable[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized_value = value.strip()
        if not normalized_value:
            continue
        if normalized_value in seen:
            continue
        seen.add(normalized_value)
        result.append(normalized_value)
    return result
def _has_unreliable_data(
    analysis: MasterAnalysisInput,
) -> bool:
    return (
        analysis.data_quality.status
        == DataQualityStatus.UNRELIABLE
    )
def _has_insufficient_data(
    analysis: MasterAnalysisInput,
) -> bool:
    return (
        analysis.data_quality.status
        == DataQualityStatus.INSUFFICIENT
    )
def _is_attractive_valuation(
    status: ValuationStatus,
) -> bool:
    return status in ATTRACTIVE_VALUATIONS
def _is_reasonable_valuation(
    status: ValuationStatus,
) -> bool:
    return status in REASONABLE_VALUATIONS
def _is_expensive_valuation(
    status: ValuationStatus,
) -> bool:
    return status in EXPENSIVE_VALUATIONS
def _business_quality_score(
    analysis: MasterAnalysisInput,
) -> float | None:
    return _average_available(
        [
            analysis.business.operating_quality_score,
            analysis.business.organic_growth_score,
            analysis.business.balance_score,
            analysis.business.cash_score,
            analysis.business.capital_allocation_score,
            analysis.accounting.accounting_quality_score,
            analysis.per_share.per_share_value_score,
            (
                analysis.moat.reviewed_score
                if analysis.moat.reviewed_score
                is not None
                else analysis.moat.preliminary_score
            ),
        ]
    )
def _determine_company_quality(
    analysis: MasterAnalysisInput,
) -> str:
    quality_score = _business_quality_score(
        analysis
    )
    if quality_score is None:
        return "NO EVALUABLE"
    if (
        analysis.moat.strength
        == MoatStrength.WEAK
    ):
        quality_score -= 8.0
    if (
        analysis.moat.trend
        == MoatTrend.DETERIORATING
    ):
        quality_score -= 7.0
    elif (
        analysis.moat.trend
        == MoatTrend.RAPIDLY_DETERIORATING
    ):
        quality_score -= 15.0
    quality_score = _clamp(
        quality_score
    )
    if quality_score >= 85:
        return "EXCELENTE"
    if quality_score >= 72:
        return "ALTA"
    if quality_score >= 55:
        return "MEDIA"
    return "BAJA"
def _determine_confidence(
    analysis: MasterAnalysisInput,
    ranking: RankingResult,
) -> EvidenceConfidence:
    if _has_unreliable_data(
        analysis
    ):
        return EvidenceConfidence.NOT_EVALUABLE
    if (
        ranking.score is None
        or ranking.coverage <= 0
    ):
        return EvidenceConfidence.NOT_EVALUABLE
    if _has_insufficient_data(
        analysis
    ):
        return EvidenceConfidence.LOW
    confidence_points = 0
    if (
        analysis.data_quality.status
        == DataQualityStatus.VALIDATED
    ):
        confidence_points += 3
    elif (
        analysis.data_quality.status
        == DataQualityStatus.PARTIALLY_VALIDATED
    ):
        confidence_points += 2
    if ranking.coverage >= 0.90:
        confidence_points += 3
    elif ranking.coverage >= 0.70:
        confidence_points += 2
    elif ranking.coverage >= 0.50:
        confidence_points += 1
    if (
        analysis.moat.confidence
        == EvidenceConfidence.HIGH
    ):
        confidence_points += 2
    elif (
        analysis.moat.confidence
        == EvidenceConfidence.MEDIUM
    ):
        confidence_points += 1
    if confidence_points >= 7:
        return EvidenceConfidence.HIGH
    if confidence_points >= 4:
        return EvidenceConfidence.MEDIUM
    return EvidenceConfidence.LOW
def _blocking_failures(
    gates: list[GateResult],
) -> list[GateResult]:
    return [
        gate
        for gate in get_blocking_failures(gates)
        if not gate.passed
    ]
def _warning_failures(
    gates: list[GateResult],
) -> list[GateResult]:
    return [
        gate
        for gate in gates
        if (
            not gate.passed
            and gate.severity
            == GateSeverity.WARNING
        )
    ]
def _determine_risk_level(
    analysis: MasterAnalysisInput,
    gates: list[GateResult],
) -> RiskLevel:
    if _has_unreliable_data(
        analysis
    ):
        return RiskLevel.NOT_EVALUATED
    risk_points = 0
    blocking = _blocking_failures(
        gates
    )
    warnings = _warning_failures(
        gates
    )
    risk_points += min(
        len(blocking) * 3,
        6,
    )
    risk_points += min(
        len(warnings),
        3,
    )
    business_risk = (
        analysis.business.risk_score
    )
    if business_risk is not None:
        normalized_business_risk = _clamp(
            business_risk
        )
        if normalized_business_risk >= 85:
            risk_points += 5
        elif normalized_business_risk >= 70:
            risk_points += 4
        elif normalized_business_risk >= 55:
            risk_points += 2
        elif normalized_business_risk >= 40:
            risk_points += 1
    if (
        analysis.moat.trend
        == MoatTrend.RAPIDLY_DETERIORATING
    ):
        risk_points += 5
    elif (
        analysis.moat.trend
        == MoatTrend.DETERIORATING
    ):
        risk_points += 3
    disruption_risk = (
        analysis.moat.disruption_risk_score
    )
    if disruption_risk is not None:
        disruption_risk = _clamp(
            disruption_risk
        )
        if disruption_risk >= 85:
            risk_points += 4
        elif disruption_risk >= 70:
            risk_points += 2
    substitution_risk = (
        analysis.moat.substitution_risk_score
    )
    if substitution_risk is not None:
        substitution_risk = _clamp(
            substitution_risk
        )
        if substitution_risk >= 85:
            risk_points += 3
        elif substitution_risk >= 70:
            risk_points += 2
    accounting_quality = (
        analysis.accounting.accounting_quality_score
    )
    if accounting_quality is not None:
        accounting_quality = _clamp(
            accounting_quality
        )
        if accounting_quality < 30:
            risk_points += 4
        elif accounting_quality < 45:
            risk_points += 2
        elif accounting_quality < 60:
            risk_points += 1
    dilution = (
        analysis.per_share.share_count_growth
    )
    if dilution is not None:
        if dilution >= 0.10:
            risk_points += 3
        elif dilution >= 0.05:
            risk_points += 1
    sbc_to_revenue = (
        analysis.accounting.sbc_to_revenue
    )
    if sbc_to_revenue is not None:
        if sbc_to_revenue >= 0.20:
            risk_points += 3
        elif sbc_to_revenue >= 0.10:
            risk_points += 1
    if risk_points >= 10:
        return RiskLevel.CRITICAL
    if risk_points >= 6:
        return RiskLevel.HIGH
    if risk_points >= 3:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
def _decide_new_investor_action(
    analysis: MasterAnalysisInput,
    ranking: RankingResult,
    blocking: list[GateResult],
    risk_level: RiskLevel,
    confidence: EvidenceConfidence,
) -> NewInvestorAction:
    if _has_unreliable_data(
        analysis
    ):
        return NewInvestorAction.UNRELIABLE_DATA
    if _has_insufficient_data(
        analysis
    ):
        return NewInvestorAction.MASTER_REVIEW
    if blocking:
        return NewInvestorAction.AVOID
    if (
        ranking.score is None
        or ranking.coverage < 0.50
    ):
        return NewInvestorAction.MASTER_REVIEW
    if confidence == EvidenceConfidence.NOT_EVALUABLE:
        return NewInvestorAction.MASTER_REVIEW
    if risk_level in {
        RiskLevel.CRITICAL,
        RiskLevel.HIGH,
    }:
        return NewInvestorAction.AVOID
    score = ranking.score
    valuation_status = analysis.valuation.status
    moat_is_acceptable = (
        analysis.moat.strength
        in {
            MoatStrength.STRONG,
            MoatStrength.MODERATE,
        }
    )
    moat_is_stable = (
        analysis.moat.trend
        not in DETERIORATING_MOAT_TRENDS
    )
    if (
        score >= 85
        and _is_attractive_valuation(
            valuation_status
        )
        and moat_is_acceptable
        and moat_is_stable
        and risk_level == RiskLevel.LOW
        and confidence
        in {
            EvidenceConfidence.HIGH,
            EvidenceConfidence.MEDIUM,
        }
    ):
        return NewInvestorAction.STRONG_BUY
    if (
        score >= 74
        and _is_attractive_valuation(
            valuation_status
        )
        and moat_is_acceptable
        and moat_is_stable
        and risk_level
        in {
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
        }
    ):
        return NewInvestorAction.BUY
    if (
        score >= 65
        and valuation_status
        in (
            ATTRACTIVE_VALUATIONS
            | REASONABLE_VALUATIONS
        )
        and risk_level
        in {
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
        }
    ):
        return NewInvestorAction.PARTIAL_BUY
    return NewInvestorAction.WAIT
def _decide_existing_holder_action(
    analysis: MasterAnalysisInput,
    ranking: RankingResult,
    blocking: list[GateResult],
    risk_level: RiskLevel,
) -> ExistingHolderAction:
    if _has_unreliable_data(
        analysis
    ):
        return ExistingHolderAction.UNRELIABLE_DATA
    if _has_insufficient_data(
        analysis
    ):
        return ExistingHolderAction.REVIEW_THESIS
    if ranking.score is None:
        return ExistingHolderAction.REVIEW_THESIS
    if blocking:
        return ExistingHolderAction.REVIEW_THESIS
    if (
        analysis.moat.trend
        == MoatTrend.RAPIDLY_DETERIORATING
        and risk_level
        in {
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        }
    ):
        return ExistingHolderAction.EXIT
    if risk_level == RiskLevel.CRITICAL:
        return ExistingHolderAction.EXIT
    if (
        analysis.moat.trend
        == MoatTrend.DETERIORATING
        or risk_level == RiskLevel.HIGH
    ):
        return ExistingHolderAction.REDUCE
    score = ranking.score
    valuation_status = analysis.valuation.status
    if (
        score >= 82
        and _is_attractive_valuation(
            valuation_status
        )
        and risk_level == RiskLevel.LOW
        and analysis.moat.trend
        not in DETERIORATING_MOAT_TRENDS
    ):
        return ExistingHolderAction.INCREASE
    if (
        score >= 55
        and risk_level
        in {
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
        }
    ):
        return ExistingHolderAction.HOLD
    if (
        score < 45
        and _is_expensive_valuation(
            valuation_status
        )
    ):
        return ExistingHolderAction.REDUCE
    if score < 40:
        return ExistingHolderAction.REVIEW_THESIS
    return ExistingHolderAction.HOLD
def _build_thesis(
    analysis: MasterAnalysisInput,
    ranking: RankingResult,
    company_quality: str,
) -> list[str]:
    thesis: list[str] = []
    thesis.append(
        f"La calidad empresarial se clasifica como "
        f"{company_quality.lower()}."
    )
    if ranking.score is not None:
        thesis.append(
            "El ranking auxiliar alcanza "
            f"{ranking.score:.1f} puntos sobre 100, "
            f"con una cobertura del "
            f"{ranking.coverage * 100:.0f} %."
        )
    if (
        analysis.moat.strength
        != MoatStrength.NOT_EVALUATED
    ):
        thesis.append(
            "La fortaleza del moat es "
            f"{analysis.moat.strength.value.lower()}."
        )
    if (
        analysis.moat.trend
        != MoatTrend.NOT_EVALUATED
    ):
        thesis.append(
            "La tendencia del moat es "
            f"{analysis.moat.trend.value.lower()}."
        )
    if (
        analysis.valuation.status
        != ValuationStatus.NOT_EVALUATED
    ):
        thesis.append(
            "La valoración actual se clasifica como "
            f"{analysis.valuation.status.value.lower()}."
        )
    if (
        analysis.accounting.accounting_quality_score
        is not None
    ):
        thesis.append(
            "La calidad contable obtiene "
            f"{analysis.accounting.accounting_quality_score:.1f} "
            "puntos sobre 100."
        )
    if (
        analysis.per_share.per_share_value_score
        is not None
    ):
        thesis.append(
            "La creación de valor por acción obtiene "
            f"{analysis.per_share.per_share_value_score:.1f} "
            "puntos sobre 100."
        )
    return _deduplicate(
        thesis
    )
def _build_reasons(
    gates: list[GateResult],
    ranking: RankingResult,
) -> list[str]:
    reasons = [
        gate.message
        for gate in gates
        if not gate.passed
    ]
    reasons.extend(
        ranking.penalties
    )
    return _deduplicate(
        reasons
    )
def _build_warnings(
    analysis: MasterAnalysisInput,
    ranking: RankingResult,
) -> list[str]:
    warning_groups = [
        analysis.data_quality.warnings,
        analysis.data_quality.blocking_issues,
        analysis.business.warnings,
        analysis.accounting.warnings,
        analysis.per_share.warnings,
        analysis.moat.warnings,
        analysis.valuation.warnings,
        ranking.warnings,
    ]
    warnings: list[str] = []
    for group in warning_groups:
        warnings.extend(
            group
        )
    return _deduplicate(
        warnings
    )
def _conditions_to_buy(
    analysis: MasterAnalysisInput,
    confidence: EvidenceConfidence,
) -> list[str]:
    conditions: list[str] = []
    if (
        analysis.valuation.status
        == ValuationStatus.NOT_EVALUATED
    ):
        conditions.append(
            "Completar la valoración antes de abrir posición."
        )
    elif _is_expensive_valuation(
        analysis.valuation.status
    ):
        conditions.append(
            "Esperar una valoración más atractiva o "
            "un mayor margen de seguridad."
        )
    if (
        analysis.moat.trend
        in DETERIORATING_MOAT_TRENDS
    ):
        conditions.append(
            "Confirmar que se detiene el deterioro "
            "de la ventaja competitiva."
        )
    if (
        analysis.moat.strength
        == MoatStrength.WEAK
    ):
        conditions.append(
            "Exigir evidencia de una ventaja competitiva "
            "más resistente."
        )
    accounting_quality = (
        analysis.accounting.accounting_quality_score
    )
    if (
        accounting_quality is not None
        and accounting_quality < 60
    ):
        conditions.append(
            "Mejorar la calidad contable y la conversión "
            "de beneficios en caja."
        )
    dilution = (
        analysis.per_share.share_count_growth
    )
    if (
        dilution is not None
        and dilution >= 0.05
    ):
        conditions.append(
            "Reducir la dilución y demostrar crecimiento "
            "real por acción."
        )
    if confidence in {
        EvidenceConfidence.LOW,
        EvidenceConfidence.NOT_EVALUABLE,
    }:
        conditions.append(
            "Aumentar la cobertura y fiabilidad de "
            "los datos disponibles."
        )
    if not conditions:
        conditions.append(
            "Mantener los fundamentales actuales y "
            "conservar un margen de seguridad suficiente."
        )
    return _deduplicate(
        conditions
    )
def _conditions_to_reduce(
    analysis: MasterAnalysisInput,
    risk_level: RiskLevel,
) -> list[str]:
    conditions: list[str] = []
    if (
        analysis.moat.trend
        == MoatTrend.DETERIORATING
    ):
        conditions.append(
            "Reducir si continúa el deterioro del moat."
        )
    if (
        analysis.moat.trend
        == MoatTrend.RAPIDLY_DETERIORATING
    ):
        conditions.append(
            "Salir si no se revierte rápidamente "
            "el deterioro del moat."
        )
    if (
        analysis.business.risk_score
        is not None
        and analysis.business.risk_score >= 65
    ):
        conditions.append(
            "Reducir si los riesgos empresariales "
            "permanecen elevados."
        )
    if (
        analysis.valuation.status
        in {
            ValuationStatus.OVERVALUED,
            ValuationStatus.VERY_EXPENSIVE,
        }
    ):
        conditions.append(
            "Reducir si la valoración extrema deja de "
            "estar respaldada por los fundamentales."
        )
    if risk_level in {
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    }:
        conditions.append(
            "Revisar la posición si no disminuyen los "
            "principales factores de riesgo."
        )
    if not conditions:
        conditions.append(
            "Reducir únicamente ante un deterioro material "
            "de la tesis de inversión."
        )
    return _deduplicate(
        conditions
    )
def make_master_decision(
    analysis: MasterAnalysisInput,
) -> MasterDecisionResult:
    gates = evaluate_master_gates(
        analysis
    )
    blocking = _blocking_failures(
        gates
    )
    ranking = calculate_ranking(
        analysis
    )
    confidence = _determine_confidence(
        analysis,
        ranking,
    )
    risk_level = _determine_risk_level(
        analysis,
        gates,
    )
    company_quality = _determine_company_quality(
        analysis
    )
    new_investor_action = (
        _decide_new_investor_action(
            analysis=analysis,
            ranking=ranking,
            blocking=blocking,
            risk_level=risk_level,
            confidence=confidence,
        )
    )
    existing_holder_action = (
        _decide_existing_holder_action(
            analysis=analysis,
            ranking=ranking,
            blocking=blocking,
            risk_level=risk_level,
        )
    )
    return MasterDecisionResult(
        ticker=analysis.ticker,
        new_investor_action=new_investor_action,
        existing_holder_action=(
            existing_holder_action
        ),
        confidence=confidence,
        risk_level=risk_level,
        company_quality=company_quality,
        valuation_status=analysis.valuation.status,
        moat_strength=analysis.moat.strength,
        moat_trend=analysis.moat.trend,
        ranking_score=ranking.score,
        gates=gates,
        thesis=_build_thesis(
            analysis,
            ranking,
            company_quality,
        ),
        reasons=_build_reasons(
            gates,
            ranking,
        ),
        warnings=_build_warnings(
            analysis,
            ranking,
        ),
        conditions_to_buy=_conditions_to_buy(
            analysis,
            confidence,
        ),
        conditions_to_reduce=(
            _conditions_to_reduce(
                analysis,
                risk_level,
            )
        ),
        raw_components={
            "ranking_coverage": ranking.coverage,
            "ranking_components": [
                {
                    "name": component.name,
                    "raw_score": component.raw_score,
                    "weight": component.weight,
                    "weighted_score": (
                        component.weighted_score
                    ),
                    "available": component.available,
                    "reason": component.reason,
                }
                for component in ranking.components
            ],
            "ranking_penalties": list(
                ranking.penalties
            ),
            "blocking_gate_codes": [
                gate.code
                for gate in blocking
            ],
            "failed_gate_codes": [
                gate.code
                for gate in gates
                if not gate.passed
            ],
        },
        model_version=analysis.model_version,
    )
