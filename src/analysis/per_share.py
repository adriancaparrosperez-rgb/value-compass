from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any
from src.decision.models import PerShareAssessment
@dataclass
class PerShareInput:
    revenue: float | None = None
    revenue_previous: float | None = None
    gaap_earnings: float | None = None
    gaap_earnings_previous: float | None = None
    reported_fcf: float | None = None
    reported_fcf_previous: float | None = None
    economic_fcf: float | None = None
    economic_fcf_previous: float | None = None
    diluted_shares: float | None = None
    diluted_shares_previous: float | None = None
    buybacks: float | None = None
    stock_based_compensation: float | None = None
    net_debt: float | None = None
    notes: list[str] = field(default_factory=list)
def _is_valid_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric_value)
def _positive_or_none(
    value: float | None,
) -> float | None:
    if not _is_valid_number(value):
        return None
    numeric_value = float(value)
    if numeric_value <= 0:
        return None
    return numeric_value
def _safe_divide(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    if not _is_valid_number(numerator):
        return None
    denominator_value = _positive_or_none(
        denominator
    )
    if denominator_value is None:
        return None
    return float(numerator) / denominator_value
def _growth_rate(
    current: float | None,
    previous: float | None,
) -> float | None:
    if not _is_valid_number(current):
        return None
    if not _is_valid_number(previous):
        return None
    previous_value = float(previous)
    if previous_value == 0:
        return None
    return (
        float(current)
        - previous_value
    ) / abs(previous_value)
def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(maximum, float(value)),
    )
def _growth_score(
    growth: float | None,
) -> float | None:
    if growth is None:
        return None
    if growth >= 0.20:
        return 100.0
    if growth >= 0.12:
        return 90.0
    if growth >= 0.07:
        return 80.0
    if growth >= 0.03:
        return 70.0
    if growth >= 0.00:
        return 55.0
    if growth >= -0.05:
        return 40.0
    if growth >= -0.10:
        return 25.0
    return 10.0
def _share_count_score(
    share_count_growth: float | None,
) -> float | None:
    if share_count_growth is None:
        return None
    if share_count_growth <= -0.05:
        return 100.0
    if share_count_growth <= -0.02:
        return 90.0
    if share_count_growth < 0:
        return 80.0
    if share_count_growth == 0:
        return 70.0
    if share_count_growth <= 0.02:
        return 55.0
    if share_count_growth <= 0.05:
        return 35.0
    if share_count_growth <= 0.10:
        return 20.0
    return 5.0
def _net_buybacks_after_sbc(
    buybacks: float | None,
    stock_based_compensation: float | None,
) -> float | None:
    if not _is_valid_number(buybacks):
        return None
    buybacks_value = max(
        0.0,
        float(buybacks),
    )
    if not _is_valid_number(
        stock_based_compensation
    ):
        return buybacks_value
    return (
        buybacks_value
        - max(
            0.0,
            float(stock_based_compensation),
        )
    )
def assess_per_share_value(
    data: PerShareInput,
) -> PerShareAssessment:
    warnings: list[str] = []
    notes = list(data.notes)
    diluted_shares = _positive_or_none(
        data.diluted_shares
    )
    diluted_shares_previous = _positive_or_none(
        data.diluted_shares_previous
    )
    share_count_growth = _growth_rate(
        diluted_shares,
        diluted_shares_previous,
    )
    revenue_per_share = _safe_divide(
        data.revenue,
        diluted_shares,
    )
    revenue_per_share_previous = _safe_divide(
        data.revenue_previous,
        diluted_shares_previous,
    )
    revenue_per_share_growth = _growth_rate(
        revenue_per_share,
        revenue_per_share_previous,
    )
    gaap_eps = _safe_divide(
        data.gaap_earnings,
        diluted_shares,
    )
    gaap_eps_previous = _safe_divide(
        data.gaap_earnings_previous,
        diluted_shares_previous,
    )
    gaap_eps_growth = _growth_rate(
        gaap_eps,
        gaap_eps_previous,
    )
    reported_fcf_per_share = _safe_divide(
        data.reported_fcf,
        diluted_shares,
    )
    reported_fcf_per_share_previous = _safe_divide(
        data.reported_fcf_previous,
        diluted_shares_previous,
    )
    reported_fcf_per_share_growth = _growth_rate(
        reported_fcf_per_share,
        reported_fcf_per_share_previous,
    )
    economic_fcf_per_share = _safe_divide(
        data.economic_fcf,
        diluted_shares,
    )
    economic_fcf_per_share_previous = _safe_divide(
        data.economic_fcf_previous,
        diluted_shares_previous,
    )
    economic_fcf_per_share_growth = _growth_rate(
        economic_fcf_per_share,
        economic_fcf_per_share_previous,
    )
    net_buybacks_after_sbc = (
        _net_buybacks_after_sbc(
            buybacks=data.buybacks,
            stock_based_compensation=(
                data.stock_based_compensation
            ),
        )
    )
    net_debt_per_share = _safe_divide(
        data.net_debt,
        diluted_shares,
    )
    score_components: list[
        tuple[float, float]
    ] = []
    revenue_score = _growth_score(
        revenue_per_share_growth
    )
    if revenue_score is not None:
        score_components.append(
            (revenue_score, 0.20)
        )
    gaap_eps_score = _growth_score(
        gaap_eps_growth
    )
    if gaap_eps_score is not None:
        score_components.append(
            (gaap_eps_score, 0.20)
        )
    reported_fcf_score = _growth_score(
        reported_fcf_per_share_growth
    )
    if reported_fcf_score is not None:
        score_components.append(
            (reported_fcf_score, 0.20)
        )
    economic_fcf_score = _growth_score(
        economic_fcf_per_share_growth
    )
    if economic_fcf_score is not None:
        score_components.append(
            (economic_fcf_score, 0.25)
        )
    share_score = _share_count_score(
        share_count_growth
    )
    if share_score is not None:
        score_components.append(
            (share_score, 0.15)
        )
    if score_components:
        total_weight = sum(
            weight
            for _, weight in score_components
        )
        per_share_value_score = sum(
            score * weight
            for score, weight in score_components
        ) / total_weight
        per_share_value_score = _clamp(
            per_share_value_score
        )
    else:
        per_share_value_score = None
    if diluted_shares is None:
        warnings.append(
            "No se dispone de acciones diluidas actuales."
        )
    if diluted_shares_previous is None:
        warnings.append(
            "No se dispone de acciones diluidas del periodo anterior."
        )
    if (
        share_count_growth is not None
        and share_count_growth > 0.02
    ):
        warnings.append(
            "El número de acciones diluidas crece más de un 2 %."
        )
    if (
        share_count_growth is not None
        and share_count_growth > 0.05
    ):
        warnings.append(
            "La dilución es material y reduce la creación "
            "de valor por acción."
        )
    if revenue_per_share_growth is None:
        warnings.append(
            "No se pudo calcular el crecimiento "
            "de ingresos por acción."
        )
    if gaap_eps_growth is None:
        warnings.append(
            "No se pudo calcular el crecimiento "
            "del beneficio GAAP por acción."
        )
    if reported_fcf_per_share_growth is None:
        warnings.append(
            "No se pudo calcular el crecimiento "
            "del FCF reportado por acción."
        )
    if economic_fcf_per_share_growth is None:
        warnings.append(
            "No se pudo calcular el crecimiento "
            "del FCF económico por acción."
        )
    if (
        net_buybacks_after_sbc is not None
        and net_buybacks_after_sbc < 0
    ):
        warnings.append(
            "Las recompras no compensan el coste económico "
            "de la remuneración en acciones."
        )
    if (
        reported_fcf_per_share_growth is not None
        and economic_fcf_per_share_growth is not None
        and reported_fcf_per_share_growth
        > economic_fcf_per_share_growth + 0.05
    ):
        warnings.append(
            "El crecimiento del FCF reportado por acción "
            "es significativamente superior al crecimiento "
            "del FCF económico por acción."
        )
    if share_count_growth is not None:
        if share_count_growth < 0:
            notes.append(
                "La compañía está reduciendo el número "
                "de acciones diluidas."
            )
        elif share_count_growth == 0:
            notes.append(
                "El número de acciones diluidas se mantiene estable."
            )
    return PerShareAssessment(
        diluted_shares=diluted_shares,
        diluted_shares_previous=(
            diluted_shares_previous
        ),
        share_count_growth=(
            round(share_count_growth, 4)
            if share_count_growth is not None
            else None
        ),
        revenue_per_share=(
            round(revenue_per_share, 4)
            if revenue_per_share is not None
            else None
        ),
        revenue_per_share_growth=(
            round(
                revenue_per_share_growth,
                4,
            )
            if revenue_per_share_growth
            is not None
            else None
        ),
        gaap_eps_growth=(
            round(gaap_eps_growth, 4)
            if gaap_eps_growth is not None
            else None
        ),
        reported_fcf_per_share=(
            round(
                reported_fcf_per_share,
                4,
            )
            if reported_fcf_per_share
            is not None
            else None
        ),
        economic_fcf_per_share=(
            round(
                economic_fcf_per_share,
                4,
            )
            if economic_fcf_per_share
            is not None
            else None
        ),
        fcf_per_share_growth=(
            round(
                economic_fcf_per_share_growth,
                4,
            )
            if economic_fcf_per_share_growth
            is not None
            else (
                round(
                    reported_fcf_per_share_growth,
                    4,
                )
                if reported_fcf_per_share_growth
                is not None
                else None
            )
        ),
        buybacks=data.buybacks,
        net_buybacks_after_sbc=(
            round(
                net_buybacks_after_sbc,
                4,
            )
            if net_buybacks_after_sbc
            is not None
            else None
        ),
        net_debt_per_share=(
            round(net_debt_per_share, 4)
            if net_debt_per_share is not None
            else None
        ),
        per_share_value_score=(
            round(per_share_value_score, 1)
            if per_share_value_score
            is not None
            else None
        ),
        warnings=warnings,
        notes=notes,
    )
