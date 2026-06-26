from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any
from src.decision.models import AccountingAssessment
@dataclass
class AccountingInput:
    revenue: float | None = None
    gaap_earnings: float | None = None
    adjusted_earnings: float | None = None
    gaap_eps: float | None = None
    adjusted_eps: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    stock_based_compensation: float | None = None
    recurring_adjustments: float | None = None
    acquisition_related_adjustments: float | None = None
    restructuring_adjustments: float | None = None
    impairment_adjustments: float | None = None
    diluted_shares: float | None = None
    diluted_shares_previous: float | None = None
    use_sbc_adjusted_fcf: bool = True
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
    if numeric_value < 0:
        return None
    return numeric_value
def _safe_ratio(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    if not _is_valid_number(numerator):
        return None
    if not _is_valid_number(denominator):
        return None
    denominator_value = float(denominator)
    if denominator_value == 0:
        return None
    return float(numerator) / denominator_value
def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(maximum, float(value)),
    )
def calculate_reported_fcf(
    operating_cash_flow: float | None,
    capital_expenditure: float | None,
) -> float | None:
    if not _is_valid_number(operating_cash_flow):
        return None
    if not _is_valid_number(capital_expenditure):
        return None
    operating_cash_flow_value = float(
        operating_cash_flow
    )
    capital_expenditure_value = abs(
        float(capital_expenditure)
    )
    return (
        operating_cash_flow_value
        - capital_expenditure_value
    )
def calculate_economic_fcf(
    reported_fcf: float | None,
    stock_based_compensation: float | None,
    use_sbc_adjusted_fcf: bool,
) -> float | None:
    if not _is_valid_number(reported_fcf):
        return None
    reported_fcf_value = float(reported_fcf)
    if not use_sbc_adjusted_fcf:
        return reported_fcf_value
    if not _is_valid_number(
        stock_based_compensation
    ):
        return reported_fcf_value
    return (
        reported_fcf_value
        - max(
            0.0,
            float(stock_based_compensation),
        )
    )
def _calculate_cash_conversion_score(
    gaap_earnings: float | None,
    operating_cash_flow: float | None,
) -> float | None:
    ratio = _safe_ratio(
        operating_cash_flow,
        gaap_earnings,
    )
    if ratio is None:
        return None
    if ratio < 0:
        return 10.0
    if ratio >= 1.25:
        return 95.0
    if ratio >= 1.0:
        return 85.0
    if ratio >= 0.8:
        return 70.0
    if ratio >= 0.6:
        return 50.0
    return 25.0
def _calculate_earnings_quality_score(
    gaap_earnings: float | None,
    adjusted_earnings: float | None,
    recurring_adjustments: float | None,
    restructuring_adjustments: float | None,
    impairment_adjustments: float | None,
) -> float | None:
    if not _is_valid_number(gaap_earnings):
        return None
    gaap_value = float(gaap_earnings)
    if gaap_value <= 0:
        return 25.0
    score = 85.0
    adjusted_gap = _safe_ratio(
        (
            float(adjusted_earnings)
            - gaap_value
            if _is_valid_number(
                adjusted_earnings
            )
            else None
        ),
        abs(gaap_value),
    )
    if adjusted_gap is not None:
        if adjusted_gap > 0.75:
            score -= 35.0
        elif adjusted_gap > 0.40:
            score -= 25.0
        elif adjusted_gap > 0.20:
            score -= 12.0
    recurring_ratio = _safe_ratio(
        recurring_adjustments,
        abs(gaap_value),
    )
    if recurring_ratio is not None:
        if recurring_ratio > 0.50:
            score -= 25.0
        elif recurring_ratio > 0.25:
            score -= 15.0
        elif recurring_ratio > 0.10:
            score -= 7.0
    restructuring_ratio = _safe_ratio(
        restructuring_adjustments,
        abs(gaap_value),
    )
    if restructuring_ratio is not None:
        if restructuring_ratio > 0.25:
            score -= 10.0
        elif restructuring_ratio > 0.10:
            score -= 5.0
    impairment_ratio = _safe_ratio(
        impairment_adjustments,
        abs(gaap_value),
    )
    if impairment_ratio is not None:
        if impairment_ratio > 0.25:
            score -= 10.0
        elif impairment_ratio > 0.10:
            score -= 5.0
    return _clamp(score)
def _calculate_sbc_penalty(
    sbc_to_revenue: float | None,
    sbc_to_reported_fcf: float | None,
) -> float:
    penalty = 0.0
    if sbc_to_revenue is not None:
        if sbc_to_revenue > 0.20:
            penalty += 25.0
        elif sbc_to_revenue > 0.12:
            penalty += 18.0
        elif sbc_to_revenue > 0.07:
            penalty += 10.0
        elif sbc_to_revenue > 0.03:
            penalty += 4.0
    if sbc_to_reported_fcf is not None:
        if sbc_to_reported_fcf > 0.75:
            penalty += 25.0
        elif sbc_to_reported_fcf > 0.40:
            penalty += 18.0
        elif sbc_to_reported_fcf > 0.20:
            penalty += 10.0
        elif sbc_to_reported_fcf > 0.10:
            penalty += 4.0
    return min(
        35.0,
        penalty,
    )
def _calculate_dilution_penalty(
    diluted_shares: float | None,
    diluted_shares_previous: float | None,
) -> tuple[float, float | None]:
    current = _positive_or_none(
        diluted_shares
    )
    previous = _positive_or_none(
        diluted_shares_previous
    )
    if current is None or previous is None:
        return 0.0, None
    if previous == 0:
        return 0.0, None
    growth = (
        current - previous
    ) / previous
    if growth > 0.10:
        penalty = 25.0
    elif growth > 0.05:
        penalty = 18.0
    elif growth > 0.02:
        penalty = 10.0
    elif growth > 0.0:
        penalty = 4.0
    else:
        penalty = 0.0
    return penalty, growth
def assess_accounting_quality(
    data: AccountingInput,
) -> AccountingAssessment:
    warnings: list[str] = []
    notes = list(data.notes)
    reported_fcf = calculate_reported_fcf(
        operating_cash_flow=(
            data.operating_cash_flow
        ),
        capital_expenditure=(
            data.capital_expenditure
        ),
    )
    economic_fcf = calculate_economic_fcf(
        reported_fcf=reported_fcf,
        stock_based_compensation=(
            data.stock_based_compensation
        ),
        use_sbc_adjusted_fcf=(
            data.use_sbc_adjusted_fcf
        ),
    )
    sbc_to_revenue = _safe_ratio(
        data.stock_based_compensation,
        data.revenue,
    )
    sbc_to_reported_fcf = _safe_ratio(
        data.stock_based_compensation,
        reported_fcf,
    )
    cash_conversion_score = (
        _calculate_cash_conversion_score(
            gaap_earnings=data.gaap_earnings,
            operating_cash_flow=(
                data.operating_cash_flow
            ),
        )
    )
    earnings_quality_score = (
        _calculate_earnings_quality_score(
            gaap_earnings=data.gaap_earnings,
            adjusted_earnings=(
                data.adjusted_earnings
            ),
            recurring_adjustments=(
                data.recurring_adjustments
            ),
            restructuring_adjustments=(
                data.restructuring_adjustments
            ),
            impairment_adjustments=(
                data.impairment_adjustments
            ),
        )
    )
    sbc_penalty = _calculate_sbc_penalty(
        sbc_to_revenue=sbc_to_revenue,
        sbc_to_reported_fcf=(
            sbc_to_reported_fcf
        ),
    )
    dilution_penalty, share_count_growth = (
        _calculate_dilution_penalty(
            diluted_shares=(
                data.diluted_shares
            ),
            diluted_shares_previous=(
                data.diluted_shares_previous
            ),
        )
    )
    score_components: list[tuple[float, float]] = []
    if cash_conversion_score is not None:
        score_components.append(
            (
                cash_conversion_score,
                0.45,
            )
        )
    if earnings_quality_score is not None:
        score_components.append(
            (
                earnings_quality_score,
                0.55,
            )
        )
    if score_components:
        total_weight = sum(
            weight
            for _, weight in score_components
        )
        base_score = sum(
            score * weight
            for score, weight in score_components
        ) / total_weight
        accounting_quality_score = _clamp(
            base_score
            - sbc_penalty
            - dilution_penalty
        )
    else:
        accounting_quality_score = None
    if reported_fcf is None:
        warnings.append(
            "No se pudo calcular el FCF reportado."
        )
    elif reported_fcf <= 0:
        warnings.append(
            "El FCF reportado es negativo o nulo."
        )
    if (
        economic_fcf is not None
        and reported_fcf is not None
        and economic_fcf < reported_fcf * 0.70
    ):
        warnings.append(
            "El FCF económico es materialmente inferior "
            "al FCF reportado."
        )
    if (
        sbc_to_revenue is not None
        and sbc_to_revenue > 0.07
    ):
        warnings.append(
            "La remuneración en acciones representa una "
            "parte elevada de los ingresos."
        )
    if (
        sbc_to_reported_fcf is not None
        and sbc_to_reported_fcf > 0.20
    ):
        warnings.append(
            "La remuneración en acciones consume una "
            "parte material del FCF reportado."
        )
    gaap_non_gaap_gap = _safe_ratio(
        (
            float(data.adjusted_earnings)
            - float(data.gaap_earnings)
            if (
                _is_valid_number(
                    data.adjusted_earnings
                )
                and _is_valid_number(
                    data.gaap_earnings
                )
            )
            else None
        ),
        (
            abs(float(data.gaap_earnings))
            if _is_valid_number(
                data.gaap_earnings
            )
            else None
        ),
    )
    if (
        gaap_non_gaap_gap is not None
        and gaap_non_gaap_gap > 0.20
    ):
        warnings.append(
            "Existe una diferencia material entre "
            "beneficio GAAP y beneficio ajustado."
        )
    if (
        share_count_growth is not None
        and share_count_growth > 0.02
    ):
        warnings.append(
            "El número de acciones diluidas está creciendo "
            "de forma material."
        )
    if data.use_sbc_adjusted_fcf:
        notes.append(
            "El FCF económico descuenta la SBC."
        )
    else:
        notes.append(
            "La SBC no se descuenta del FCF; debe tratarse "
            "mediante la dilución por acción."
        )
    return AccountingAssessment(
        gaap_earnings=data.gaap_earnings,
        adjusted_earnings=(
            data.adjusted_earnings
        ),
        gaap_eps=data.gaap_eps,
        adjusted_eps=data.adjusted_eps,
        operating_cash_flow=(
            data.operating_cash_flow
        ),
        capital_expenditure=(
            data.capital_expenditure
        ),
        reported_fcf=reported_fcf,
        economic_fcf=economic_fcf,
        stock_based_compensation=(
            data.stock_based_compensation
        ),
        sbc_to_revenue=sbc_to_revenue,
        sbc_to_reported_fcf=(
            sbc_to_reported_fcf
        ),
        recurring_adjustments=(
            data.recurring_adjustments
        ),
        acquisition_related_adjustments=(
            data.acquisition_related_adjustments
        ),
        restructuring_adjustments=(
            data.restructuring_adjustments
        ),
        impairment_adjustments=(
            data.impairment_adjustments
        ),
        cash_conversion_score=(
            cash_conversion_score
        ),
        earnings_quality_score=(
            earnings_quality_score
        ),
        accounting_quality_score=(
            round(
                accounting_quality_score,
                1,
            )
            if accounting_quality_score
            is not None
            else None
        ),
        uses_sbc_adjusted_fcf=(
            data.use_sbc_adjusted_fcf
        ),
        warnings=warnings,
        notes=notes,
    )
