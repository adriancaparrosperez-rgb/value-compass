from __future__ import annotations

from dataclasses import dataclass, field

from src.decision.enums import (
    DataQualityStatus,
    MoatStrength,
    MoatTrend,
    ValuationStatus,
)
from src.decision.models import MasterAnalysisInput


@dataclass
class RankingComponent:
    name: str
    raw_score: float | None
    weight: float
    weighted_score: float
    available: bool
    reason: str = ""


@dataclass
class RankingResult:
    score: float | None
    coverage: float

    components: list[RankingComponent] = field(
        default_factory=list
    )

    penalties: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )


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
    values: list[float | None],
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
        ]
    )


def _accounting_score(
    analysis: MasterAnalysisInput,
) -> float | None:
    return _average_available(
        [
            analysis.accounting.accounting_quality_score,
            analysis.accounting.earnings_quality_score,
            analysis.accounting.cash_conversion_score,
        ]
    )


def _per_share_score(
    analysis: MasterAnalysisInput,
) -> float | None:
    if (
        analysis.per_share.per_share_value_score
        is None
    ):
        return None

    return _clamp(
        analysis.per_share.per_share_value_score
    )


def _moat_score(
    analysis: MasterAnalysisInput,
) -> float | None:
    if analysis.moat.reviewed_score is not None:
        return _clamp(
            analysis.moat.reviewed_score
        )

    if analysis.moat.preliminary_score is not None:
        return _clamp(
            analysis.moat.preliminary_score
        )

    if (
        analysis.moat.strength
        == MoatStrength.STRONG
    ):
        return 85.0

    if (
        analysis.moat.strength
        == MoatStrength.MODERATE
    ):
        return 65.0

    if (
        analysis.moat.strength
        == MoatStrength.WEAK
    ):
        return 35.0

    return None


def _valuation_score(
    analysis: MasterAnalysisInput,
) -> float | None:
    if (
        analysis.valuation.valuation_score
        is not None
    ):
        return _clamp(
            analysis.valuation.valuation_score
        )

    status = analysis.valuation.status

    if status in {
        ValuationStatus.UNDERVALUED,
        ValuationStatus.VERY_ATTRACTIVE,
    }:
        return 85.0

    if status == ValuationStatus.ATTRACTIVE:
        return 72.0

    if status in {
        ValuationStatus.FAIRLY_VALUED,
        ValuationStatus.REASONABLE,
    }:
        return 55.0

    if status in {
        ValuationStatus.OVERVALUED,
        ValuationStatus.VERY_EXPENSIVE,
    }:
        return 20.0

    if status == ValuationStatus.EXPENSIVE:
        return 35.0

    return None


def _data_quality_score(
    analysis: MasterAnalysisInput,
) -> float | None:
    if (
        analysis.data_quality.status
        in {
            DataQualityStatus.INSUFFICIENT,
            DataQualityStatus.UNRELIABLE,
        }
    ):
        return None

    return _clamp(
        analysis.data_quality.overall_score
    )


def _risk_penalty(
    analysis: MasterAnalysisInput,
) -> tuple[float, list[str]]:
    penalty = 0.0
    reasons: list[str] = []

    business_risk = (
        analysis.business.risk_score
    )

    if business_risk is not None:
        normalized_risk = _clamp(
            business_risk
        )

        if normalized_risk >= 80:
            penalty += 18.0
            reasons.append(
                "Riesgo empresarial extremo."
            )

        elif normalized_risk >= 65:
            penalty += 12.0
            reasons.append(
                "Riesgo empresarial elevado."
            )

        elif normalized_risk >= 50:
            penalty += 6.0
            reasons.append(
                "Riesgo empresarial relevante."
            )

    if (
        analysis.moat.trend
        == MoatTrend.DETERIORATING
    ):
        penalty += 8.0
        reasons.append(
            "El moat presenta deterioro."
        )

    if (
        analysis.moat.trend
        == MoatTrend.RAPIDLY_DETERIORATING
    ):
        penalty += 18.0
        reasons.append(
            "El moat se deteriora rápidamente."
        )

    if (
        analysis.moat.disruption_risk_score
        is not None
    ):
        disruption_risk = _clamp(
            analysis.moat.disruption_risk_score
        )

        if disruption_risk >= 85:
            penalty += 12.0
            reasons.append(
                "Riesgo de disrupción extremo."
            )

        elif disruption_risk >= 70:
            penalty += 7.0
            reasons.append(
                "Riesgo de disrupción elevado."
            )

    if (
        analysis.moat.substitution_risk_score
        is not None
    ):
        substitution_risk = _clamp(
            analysis.moat.substitution_risk_score
        )

        if substitution_risk >= 85:
            penalty += 10.0
            reasons.append(
                "Riesgo de sustitución extremo."
            )

        elif substitution_risk >= 70:
            penalty += 6.0
            reasons.append(
                "Riesgo de sustitución elevado."
            )

    if (
        analysis.per_share.share_count_growth
        is not None
        and analysis.per_share.share_count_growth
        >= 0.05
    ):
        penalty += 6.0
        reasons.append(
            "La dilución anual es elevada."
        )

    if (
        analysis.accounting.sbc_to_revenue
        is not None
        and analysis.accounting.sbc_to_revenue
        >= 0.10
    ):
        penalty += 5.0
        reasons.append(
            "La compensación en acciones es elevada."
        )

    return penalty, reasons


def calculate_ranking(
    analysis: MasterAnalysisInput,
) -> RankingResult:
    component_definitions = [
        (
            "Calidad del negocio",
            _business_quality_score(
                analysis
            ),
            0.25,
        ),
        (
            "Moat",
            _moat_score(
                analysis
            ),
            0.20,
        ),
        (
            "Calidad contable",
            _accounting_score(
                analysis
            ),
            0.15,
        ),
        (
            "Creación de valor por acción",
            _per_share_score(
                analysis
            ),
            0.15,
        ),
        (
            "Valoración",
            _valuation_score(
                analysis
            ),
            0.20,
        ),
        (
            "Calidad de los datos",
            _data_quality_score(
                analysis
            ),
            0.05,
        ),
    ]

    components: list[RankingComponent] = []

    available_weight = 0.0
    weighted_total = 0.0

    for (
        name,
        raw_score,
        weight,
    ) in component_definitions:
        if raw_score is None:
            components.append(
                RankingComponent(
                    name=name,
                    raw_score=None,
                    weight=weight,
                    weighted_score=0.0,
                    available=False,
                    reason=(
                        "No hay datos suficientes "
                        "para esta dimensión."
                    ),
                )
            )

            continue

        normalized_score = _clamp(
            raw_score
        )

        weighted_score = (
            normalized_score
            * weight
        )

        available_weight += weight
        weighted_total += weighted_score

        components.append(
            RankingComponent(
                name=name,
                raw_score=round(
                    normalized_score,
                    1,
                ),
                weight=weight,
                weighted_score=round(
                    weighted_score,
                    2,
                ),
                available=True,
            )
        )

    total_possible_weight = sum(
        weight
        for _, _, weight
        in component_definitions
    )

    coverage = (
        available_weight
        / total_possible_weight
        if total_possible_weight > 0
        else 0.0
    )

    warnings: list[str] = []

    if available_weight == 0:
        return RankingResult(
            score=None,
            coverage=0.0,
            components=components,
            warnings=[
                (
                    "No hay dimensiones suficientes "
                    "para calcular el ranking."
                )
            ],
        )

    normalized_weighted_score = (
        weighted_total
        / available_weight
    )

    penalty, penalty_reasons = _risk_penalty(
        analysis
    )

    final_score = _clamp(
        normalized_weighted_score
        - penalty
    )

    if coverage < 0.50:
        warnings.append(
            "La cobertura del ranking es inferior al 50 %."
        )

    elif coverage < 0.75:
        warnings.append(
            "El ranking se ha calculado con cobertura parcial."
        )

    if (
        analysis.data_quality.status
        == DataQualityStatus.INSUFFICIENT
    ):
        warnings.append(
            "La calidad de los datos es insuficiente."
        )

    if (
        analysis.data_quality.status
        == DataQualityStatus.UNRELIABLE
    ):
        warnings.append(
            "Los datos disponibles no son fiables."
        )

    return RankingResult(
        score=round(
            final_score,
            1,
        ),
        coverage=round(
            coverage,
            4,
        ),
        components=components,
        penalties=penalty_reasons,
        warnings=warnings,
    )
