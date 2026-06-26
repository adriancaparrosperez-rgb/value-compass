from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class ReverseDCFInput:
    current_price: float
    diluted_shares: float
    normalized_fcf: float

    net_debt: float = 0.0

    explicit_years: int = 5
    discount_rate: float = 0.09
    terminal_growth: float = 0.025

    minimum_growth: float = -0.50
    maximum_growth: float = 0.75

    tolerance: float = 0.000001
    maximum_iterations: int = 200


@dataclass
class ReverseDCFResult:
    implied_growth: float | None
    market_equity_value: float | None
    implied_enterprise_value: float | None

    calculated_enterprise_value: float | None
    valuation_gap: float | None

    status: str
    converged: bool
    iterations: int

    lower_bound_value: float | None = None
    upper_bound_value: float | None = None

    warning: str | None = None


def _is_finite_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(numeric_value)


def _validate_input(data: ReverseDCFInput) -> None:
    if not _is_finite_number(data.current_price):
        raise ValueError(
            "El precio actual debe ser numéricamente válido."
        )

    if data.current_price <= 0:
        raise ValueError(
            "El precio actual debe ser superior a cero."
        )

    if not _is_finite_number(data.diluted_shares):
        raise ValueError(
            "Las acciones diluidas deben ser válidas."
        )

    if data.diluted_shares <= 0:
        raise ValueError(
            "Las acciones diluidas deben ser superiores a cero."
        )

    if not _is_finite_number(data.normalized_fcf):
        raise ValueError(
            "El FCF normalizado debe ser válido."
        )

    if data.normalized_fcf <= 0:
        raise ValueError(
            "El reverse DCF requiere un FCF normalizado positivo."
        )

    if not _is_finite_number(data.net_debt):
        raise ValueError(
            "La deuda neta debe ser numéricamente válida."
        )

    if data.explicit_years < 1:
        raise ValueError(
            "El número de años explícitos debe ser al menos uno."
        )

    if data.explicit_years > 20:
        raise ValueError(
            "El número de años explícitos no puede superar veinte."
        )

    if not _is_finite_number(data.discount_rate):
        raise ValueError(
            "La tasa de descuento debe ser válida."
        )

    if data.discount_rate <= 0:
        raise ValueError(
            "La tasa de descuento debe ser superior a cero."
        )

    if not _is_finite_number(data.terminal_growth):
        raise ValueError(
            "El crecimiento terminal debe ser válido."
        )

    if data.discount_rate <= data.terminal_growth:
        raise ValueError(
            "La tasa de descuento debe ser superior "
            "al crecimiento terminal."
        )

    if data.minimum_growth >= data.maximum_growth:
        raise ValueError(
            "El crecimiento mínimo debe ser inferior al máximo."
        )

    if data.tolerance <= 0:
        raise ValueError(
            "La tolerancia debe ser superior a cero."
        )

    if data.maximum_iterations < 1:
        raise ValueError(
            "El número máximo de iteraciones debe ser positivo."
        )


def enterprise_value_from_growth(
    normalized_fcf: float,
    growth_rate: float,
    explicit_years: int,
    discount_rate: float,
    terminal_growth: float,
) -> float:
    if normalized_fcf <= 0:
        raise ValueError(
            "El FCF normalizado debe ser positivo."
        )

    if explicit_years < 1:
        raise ValueError(
            "Los años explícitos deben ser positivos."
        )

    if discount_rate <= terminal_growth:
        raise ValueError(
            "La tasa de descuento debe superar "
            "el crecimiento terminal."
        )

    present_value_explicit = 0.0
    projected_fcf = float(normalized_fcf)

    for year in range(
        1,
        explicit_years + 1,
    ):
        projected_fcf *= 1.0 + growth_rate

        present_value_explicit += (
            projected_fcf
            / ((1.0 + discount_rate) ** year)
        )

    terminal_fcf = (
        projected_fcf
        * (1.0 + terminal_growth)
    )

    terminal_value = (
        terminal_fcf
        / (discount_rate - terminal_growth)
    )

    present_value_terminal = (
        terminal_value
        / (
            (1.0 + discount_rate)
            ** explicit_years
        )
    )

    return (
        present_value_explicit
        + present_value_terminal
    )


def _classify_implied_growth(
    implied_growth: float | None,
) -> str:
    if implied_growth is None:
        return "NO EVALUABLE"

    if implied_growth < -0.10:
        return "DESCUENTA DETERIORO SEVERO"

    if implied_growth < 0.00:
        return "DESCUENTA CONTRACCIÓN"

    if implied_growth <= 0.03:
        return "EXPECTATIVAS MUY BAJAS"

    if implied_growth <= 0.07:
        return "EXPECTATIVAS MODERADAS"

    if implied_growth <= 0.12:
        return "EXPECTATIVAS EXIGENTES"

    if implied_growth <= 0.20:
        return "EXPECTATIVAS MUY EXIGENTES"

    return "EXPECTATIVAS EXTREMAS"


def solve_implied_growth(
    data: ReverseDCFInput,
) -> ReverseDCFResult:
    _validate_input(data)

    market_equity_value = (
        float(data.current_price)
        * float(data.diluted_shares)
    )

    implied_enterprise_value = (
        market_equity_value
        + float(data.net_debt)
    )

    if implied_enterprise_value <= 0:
        return ReverseDCFResult(
            implied_growth=None,
            market_equity_value=market_equity_value,
            implied_enterprise_value=(
                implied_enterprise_value
            ),
            calculated_enterprise_value=None,
            valuation_gap=None,
            status="NO EVALUABLE",
            converged=False,
            iterations=0,
            warning=(
                "El valor empresarial implícito no es positivo."
            ),
        )

    lower_growth = float(
        data.minimum_growth
    )

    upper_growth = float(
        data.maximum_growth
    )

    lower_value = enterprise_value_from_growth(
        normalized_fcf=data.normalized_fcf,
        growth_rate=lower_growth,
        explicit_years=data.explicit_years,
        discount_rate=data.discount_rate,
        terminal_growth=data.terminal_growth,
    )

    upper_value = enterprise_value_from_growth(
        normalized_fcf=data.normalized_fcf,
        growth_rate=upper_growth,
        explicit_years=data.explicit_years,
        discount_rate=data.discount_rate,
        terminal_growth=data.terminal_growth,
    )

    if implied_enterprise_value < lower_value:
        return ReverseDCFResult(
            implied_growth=None,
            market_equity_value=market_equity_value,
            implied_enterprise_value=(
                implied_enterprise_value
            ),
            calculated_enterprise_value=lower_value,
            valuation_gap=(
                lower_value
                - implied_enterprise_value
            ),
            status="POR DEBAJO DEL RANGO",
            converged=False,
            iterations=0,
            lower_bound_value=lower_value,
            upper_bound_value=upper_value,
            warning=(
                "El precio descuenta un crecimiento inferior "
                "al límite mínimo configurado."
            ),
        )

    if implied_enterprise_value > upper_value:
        return ReverseDCFResult(
            implied_growth=None,
            market_equity_value=market_equity_value,
            implied_enterprise_value=(
                implied_enterprise_value
            ),
            calculated_enterprise_value=upper_value,
            valuation_gap=(
                upper_value
                - implied_enterprise_value
            ),
            status="POR ENCIMA DEL RANGO",
            converged=False,
            iterations=0,
            lower_bound_value=lower_value,
            upper_bound_value=upper_value,
            warning=(
                "El precio exige un crecimiento superior "
                "al límite máximo configurado."
            ),
        )

    middle_growth = 0.0
    middle_value = 0.0

    for iteration in range(
        1,
        data.maximum_iterations + 1,
    ):
        middle_growth = (
            lower_growth
            + upper_growth
        ) / 2.0

        middle_value = enterprise_value_from_growth(
            normalized_fcf=data.normalized_fcf,
            growth_rate=middle_growth,
            explicit_years=data.explicit_years,
            discount_rate=data.discount_rate,
            terminal_growth=data.terminal_growth,
        )

        absolute_gap = abs(
            middle_value
            - implied_enterprise_value
        )

        relative_gap = (
            absolute_gap
            / implied_enterprise_value
        )

        if relative_gap <= data.tolerance:
            implied_growth = middle_growth

            return ReverseDCFResult(
                implied_growth=round(
                    implied_growth,
                    6,
                ),
                market_equity_value=round(
                    market_equity_value,
                    4,
                ),
                implied_enterprise_value=round(
                    implied_enterprise_value,
                    4,
                ),
                calculated_enterprise_value=round(
                    middle_value,
                    4,
                ),
                valuation_gap=round(
                    middle_value
                    - implied_enterprise_value,
                    4,
                ),
                status=_classify_implied_growth(
                    implied_growth
                ),
                converged=True,
                iterations=iteration,
                lower_bound_value=round(
                    lower_value,
                    4,
                ),
                upper_bound_value=round(
                    upper_value,
                    4,
                ),
            )

        if middle_value < implied_enterprise_value:
            lower_growth = middle_growth
        else:
            upper_growth = middle_growth

    return ReverseDCFResult(
        implied_growth=round(
            middle_growth,
            6,
        ),
        market_equity_value=round(
            market_equity_value,
            4,
        ),
        implied_enterprise_value=round(
            implied_enterprise_value,
            4,
        ),
        calculated_enterprise_value=round(
            middle_value,
            4,
        ),
        valuation_gap=round(
            middle_value
            - implied_enterprise_value,
            4,
        ),
        status=_classify_implied_growth(
            middle_growth
        ),
        converged=False,
        iterations=data.maximum_iterations,
        lower_bound_value=round(
            lower_value,
            4,
        ),
        upper_bound_value=round(
            upper_value,
            4,
        ),
        warning=(
            "El cálculo alcanzó el máximo de iteraciones "
            "sin cumplir la tolerancia configurada."
        ),
    )
