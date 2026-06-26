from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.decision.enums import ValuationStatus
from src.decision.models import (
    ValuationAssessment,
    ValuationScenario,
)


@dataclass
class ScenarioAssumptions:
    name: str

    revenue_growth: float
    operating_margin: float
    tax_rate: float
    reinvestment_rate: float

    discount_rate: float
    terminal_growth: float

    explicit_years: int = 5

    notes: list[str] = field(
        default_factory=list
    )


@dataclass
class ScenarioValuationInput:
    current_price: float
    diluted_shares: float

    current_revenue: float

    net_debt: float = 0.0

    conservative: ScenarioAssumptions | None = None
    base: ScenarioAssumptions | None = None
    optimistic: ScenarioAssumptions | None = None


def _is_valid_number(
    value: Any,
) -> bool:
    if value is None or isinstance(value, bool):
        return False

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(numeric_value)


def _validate_rate(
    value: float,
    name: str,
    minimum: float = -1.0,
    maximum: float = 1.0,
) -> None:
    if not _is_valid_number(value):
        raise ValueError(
            f"{name} debe ser numéricamente válido."
        )

    if value < minimum or value > maximum:
        raise ValueError(
            f"{name} debe estar entre "
            f"{minimum:.2f} y {maximum:.2f}."
        )


def _validate_assumptions(
    assumptions: ScenarioAssumptions,
) -> None:
    if not assumptions.name.strip():
        raise ValueError(
            "El escenario debe tener un nombre."
        )

    _validate_rate(
        assumptions.revenue_growth,
        "El crecimiento de ingresos",
        minimum=-0.50,
        maximum=1.00,
    )

    _validate_rate(
        assumptions.operating_margin,
        "El margen operativo",
        minimum=-0.50,
        maximum=1.00,
    )

    _validate_rate(
        assumptions.tax_rate,
        "La tasa fiscal",
        minimum=0.00,
        maximum=0.60,
    )

    _validate_rate(
        assumptions.reinvestment_rate,
        "La tasa de reinversión",
        minimum=0.00,
        maximum=1.00,
    )

    _validate_rate(
        assumptions.discount_rate,
        "La tasa de descuento",
        minimum=0.001,
        maximum=1.00,
    )

    _validate_rate(
        assumptions.terminal_growth,
        "El crecimiento terminal",
        minimum=-0.10,
        maximum=0.10,
    )

    if (
        assumptions.discount_rate
        <= assumptions.terminal_growth
    ):
        raise ValueError(
            "La tasa de descuento debe ser superior "
            "al crecimiento terminal."
        )

    if assumptions.explicit_years < 1:
        raise ValueError(
            "El número de años explícitos debe ser "
            "al menos uno."
        )

    if assumptions.explicit_years > 20:
        raise ValueError(
            "El número de años explícitos no puede "
            "superar veinte."
        )


def _validate_input(
    data: ScenarioValuationInput,
) -> None:
    if not _is_valid_number(data.current_price):
        raise ValueError(
            "El precio actual debe ser válido."
        )

    if data.current_price <= 0:
        raise ValueError(
            "El precio actual debe ser superior a cero."
        )

    if not _is_valid_number(data.diluted_shares):
        raise ValueError(
            "Las acciones diluidas deben ser válidas."
        )

    if data.diluted_shares <= 0:
        raise ValueError(
            "Las acciones diluidas deben ser "
            "superiores a cero."
        )

    if not _is_valid_number(data.current_revenue):
        raise ValueError(
            "Los ingresos actuales deben ser válidos."
        )

    if data.current_revenue <= 0:
        raise ValueError(
            "Los ingresos actuales deben ser "
            "superiores a cero."
        )

    if not _is_valid_number(data.net_debt):
        raise ValueError(
            "La deuda neta debe ser válida."
        )

    scenarios = [
        data.conservative,
        data.base,
        data.optimistic,
    ]

    if all(
        scenario is None
        for scenario in scenarios
    ):
        raise ValueError(
            "Debe proporcionarse al menos un escenario."
        )

    for scenario in scenarios:
        if scenario is not None:
            _validate_assumptions(
                scenario
            )


def calculate_scenario_value(
    current_revenue: float,
    diluted_shares: float,
    net_debt: float,
    assumptions: ScenarioAssumptions,
) -> ValuationScenario:
    _validate_assumptions(
        assumptions
    )

    if current_revenue <= 0:
        raise ValueError(
            "Los ingresos actuales deben ser positivos."
        )

    if diluted_shares <= 0:
        raise ValueError(
            "Las acciones diluidas deben ser positivas."
        )

    projected_revenue = float(
        current_revenue
    )

    present_value_explicit = 0.0
    projected_free_cash_flow = 0.0

    yearly_projections: list[
        dict[str, float]
    ] = []

    for year in range(
        1,
        assumptions.explicit_years + 1,
    ):
        projected_revenue *= (
            1.0
            + assumptions.revenue_growth
        )

        operating_profit = (
            projected_revenue
            * assumptions.operating_margin
        )

        after_tax_operating_profit = (
            operating_profit
            * (
                1.0
                - assumptions.tax_rate
            )
        )

        reinvestment = (
            after_tax_operating_profit
            * assumptions.reinvestment_rate
        )

        projected_free_cash_flow = (
            after_tax_operating_profit
            - reinvestment
        )

        discounted_free_cash_flow = (
            projected_free_cash_flow
            / (
                (
                    1.0
                    + assumptions.discount_rate
                )
                ** year
            )
        )

        present_value_explicit += (
            discounted_free_cash_flow
        )

        yearly_projections.append(
            {
                "year": float(year),
                "revenue": round(
                    projected_revenue,
                    4,
                ),
                "operating_profit": round(
                    operating_profit,
                    4,
                ),
                "after_tax_operating_profit": round(
                    after_tax_operating_profit,
                    4,
                ),
                "reinvestment": round(
                    reinvestment,
                    4,
                ),
                "free_cash_flow": round(
                    projected_free_cash_flow,
                    4,
                ),
                "discounted_free_cash_flow": round(
                    discounted_free_cash_flow,
                    4,
                ),
            }
        )

    terminal_free_cash_flow = (
        projected_free_cash_flow
        * (
            1.0
            + assumptions.terminal_growth
        )
    )

    terminal_value = (
        terminal_free_cash_flow
        / (
            assumptions.discount_rate
            - assumptions.terminal_growth
        )
    )

    present_value_terminal = (
        terminal_value
        / (
            (
                1.0
                + assumptions.discount_rate
            )
            ** assumptions.explicit_years
        )
    )

    enterprise_value = (
        present_value_explicit
        + present_value_terminal
    )

    equity_value = (
        enterprise_value
        - net_debt
    )

    intrinsic_value_per_share = (
        equity_value
        / diluted_shares
    )

    return ValuationScenario(
        name=assumptions.name,
        intrinsic_value_per_share=round(
            intrinsic_value_per_share,
            4,
        ),
        revenue_growth=(
            assumptions.revenue_growth
        ),
        margin=(
            assumptions.operating_margin
        ),
        terminal_growth=(
            assumptions.terminal_growth
        ),
        discount_rate=(
            assumptions.discount_rate
        ),
        assumptions={
            "tax_rate": (
                assumptions.tax_rate
            ),
            "reinvestment_rate": (
                assumptions.reinvestment_rate
            ),
            "explicit_years": (
                assumptions.explicit_years
            ),
            "enterprise_value": round(
                enterprise_value,
                4,
            ),
            "equity_value": round(
                equity_value,
                4,
            ),
            "net_debt": round(
                net_debt,
                4,
            ),
            "present_value_explicit": round(
                present_value_explicit,
                4,
            ),
            "present_value_terminal": round(
                present_value_terminal,
                4,
            ),
            "yearly_projections": (
                yearly_projections
            ),
            "notes": list(
                assumptions.notes
            ),
        },
    )


def _margin_of_safety(
    intrinsic_value: float | None,
    current_price: float,
) -> float | None:
    if intrinsic_value is None:
        return None

    if current_price <= 0:
        return None

    return round(
        (
            intrinsic_value
            - current_price
        )
        / current_price,
        4,
    )


def _valuation_score(
    conservative_margin: float | None,
    base_margin: float | None,
) -> float | None:
    valid_margins = [
        margin
        for margin in [
            conservative_margin,
            base_margin,
        ]
        if margin is not None
    ]

    if not valid_margins:
        return None

    average_margin = (
        sum(valid_margins)
        / len(valid_margins)
    )

    score = (
        50.0
        + average_margin * 100.0
    )

    return round(
        max(
            0.0,
            min(
                100.0,
                score,
            ),
        ),
        1,
    )


def _classify_valuation(
    conservative_margin: float | None,
    base_margin: float | None,
) -> ValuationStatus:
    if (
        conservative_margin is None
        and base_margin is None
    ):
        return ValuationStatus.NOT_EVALUATED

    if (
        conservative_margin is not None
        and conservative_margin >= 0.20
    ):
        return ValuationStatus.UNDERVALUED

    if (
        base_margin is not None
        and base_margin >= 0.15
    ):
        return ValuationStatus.UNDERVALUED

    if (
        base_margin is not None
        and base_margin <= -0.20
    ):
        return ValuationStatus.OVERVALUED

    if (
        conservative_margin is not None
        and conservative_margin <= -0.30
    ):
        return ValuationStatus.OVERVALUED

    return ValuationStatus.FAIRLY_VALUED


def assess_valuation_scenarios(
    data: ScenarioValuationInput,
) -> ValuationAssessment:
    _validate_input(
        data
    )

    warnings: list[str] = []
    notes: list[str] = []

    conservative_result = (
        calculate_scenario_value(
            current_revenue=data.current_revenue,
            diluted_shares=data.diluted_shares,
            net_debt=data.net_debt,
            assumptions=data.conservative,
        )
        if data.conservative is not None
        else None
    )

    base_result = (
        calculate_scenario_value(
            current_revenue=data.current_revenue,
            diluted_shares=data.diluted_shares,
            net_debt=data.net_debt,
            assumptions=data.base,
        )
        if data.base is not None
        else None
    )

    optimistic_result = (
        calculate_scenario_value(
            current_revenue=data.current_revenue,
            diluted_shares=data.diluted_shares,
            net_debt=data.net_debt,
            assumptions=data.optimistic,
        )
        if data.optimistic is not None
        else None
    )

    conservative_margin = _margin_of_safety(
        (
            conservative_result
            .intrinsic_value_per_share
            if conservative_result is not None
            else None
        ),
        data.current_price,
    )

    base_margin = _margin_of_safety(
        (
            base_result
            .intrinsic_value_per_share
            if base_result is not None
            else None
        ),
        data.current_price,
    )

    if conservative_result is None:
        warnings.append(
            "No se ha calculado un escenario conservador."
        )

    if base_result is None:
        warnings.append(
            "No se ha calculado un escenario base."
        )

    if optimistic_result is None:
        warnings.append(
            "No se ha calculado un escenario optimista."
        )

    if (
        conservative_result is not None
        and base_result is not None
        and conservative_result
        .intrinsic_value_per_share
        > base_result
        .intrinsic_value_per_share
    ):
        warnings.append(
            "El escenario conservador ofrece un valor "
            "superior al escenario base."
        )

    if (
        base_result is not None
        and optimistic_result is not None
        and base_result
        .intrinsic_value_per_share
        > optimistic_result
        .intrinsic_value_per_share
    ):
        warnings.append(
            "El escenario base ofrece un valor superior "
            "al escenario optimista."
        )

    valuation_score = _valuation_score(
        conservative_margin,
        base_margin,
    )

    status = _classify_valuation(
        conservative_margin,
        base_margin,
    )

    notes.append(
        "La valoración utiliza un DCF simplificado "
        "basado en ingresos, margen operativo, "
        "impuestos y reinversión."
    )

    return ValuationAssessment(
        current_price=round(
            data.current_price,
            4,
        ),
        conservative=conservative_result,
        base=base_result,
        optimistic=optimistic_result,
        valuation_score=valuation_score,
        margin_of_safety_conservative=(
            conservative_margin
        ),
        margin_of_safety_base=(
            base_margin
        ),
        status=status,
        warnings=warnings,
        notes=notes,
    )
