from __future__ import annotations

import pytest

from src.valuation.reverse_dcf import (
    ReverseDCFInput,
    enterprise_value_from_growth,
    solve_implied_growth,
)


def test_enterprise_value_increases_with_growth() -> None:
    low_growth_value = enterprise_value_from_growth(
        normalized_fcf=1_000.0,
        growth_rate=0.02,
        explicit_years=5,
        discount_rate=0.09,
        terminal_growth=0.025,
    )

    high_growth_value = enterprise_value_from_growth(
        normalized_fcf=1_000.0,
        growth_rate=0.10,
        explicit_years=5,
        discount_rate=0.09,
        terminal_growth=0.025,
    )

    assert high_growth_value > low_growth_value


def test_reverse_dcf_recovers_known_growth() -> None:
    target_growth = 0.08

    enterprise_value = enterprise_value_from_growth(
        normalized_fcf=1_000.0,
        growth_rate=target_growth,
        explicit_years=5,
        discount_rate=0.09,
        terminal_growth=0.025,
    )

    result = solve_implied_growth(
        ReverseDCFInput(
            current_price=enterprise_value / 100.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
            net_debt=0.0,
            explicit_years=5,
            discount_rate=0.09,
            terminal_growth=0.025,
        )
    )

    assert result.converged is True
    assert result.implied_growth is not None
    assert result.implied_growth == pytest.approx(
        target_growth,
        abs=0.00001,
    )


def test_net_debt_increases_implied_enterprise_value() -> None:
    result_without_debt = solve_implied_growth(
        ReverseDCFInput(
            current_price=100.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
            net_debt=0.0,
        )
    )

    result_with_debt = solve_implied_growth(
        ReverseDCFInput(
            current_price=100.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
            net_debt=2_000.0,
        )
    )

    assert (
        result_with_debt.implied_enterprise_value
        > result_without_debt.implied_enterprise_value
    )


def test_negative_net_debt_is_allowed() -> None:
    result = solve_implied_growth(
        ReverseDCFInput(
            current_price=100.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
            net_debt=-2_000.0,
        )
    )

    assert result.implied_enterprise_value == 8_000.0


def test_growth_below_range_is_detected() -> None:
    lower_value = enterprise_value_from_growth(
        normalized_fcf=1_000.0,
        growth_rate=-0.20,
        explicit_years=5,
        discount_rate=0.09,
        terminal_growth=0.025,
    )

    result = solve_implied_growth(
        ReverseDCFInput(
            current_price=(lower_value * 0.50) / 100.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
            minimum_growth=-0.20,
            maximum_growth=0.30,
        )
    )

    assert result.converged is False
    assert result.implied_growth is None
    assert result.status == "POR DEBAJO DEL RANGO"
    assert result.warning is not None


def test_growth_above_range_is_detected() -> None:
    upper_value = enterprise_value_from_growth(
        normalized_fcf=1_000.0,
        growth_rate=0.20,
        explicit_years=5,
        discount_rate=0.09,
        terminal_growth=0.025,
    )

    result = solve_implied_growth(
        ReverseDCFInput(
            current_price=(upper_value * 1.50) / 100.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
            minimum_growth=-0.20,
            maximum_growth=0.20,
        )
    )

    assert result.converged is False
    assert result.implied_growth is None
    assert result.status == "POR ENCIMA DEL RANGO"
    assert result.warning is not None


def test_invalid_price_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="precio actual",
    ):
        solve_implied_growth(
            ReverseDCFInput(
                current_price=0.0,
                diluted_shares=100.0,
                normalized_fcf=1_000.0,
            )
        )


def test_invalid_share_count_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="acciones diluidas",
    ):
        solve_implied_growth(
            ReverseDCFInput(
                current_price=100.0,
                diluted_shares=0.0,
                normalized_fcf=1_000.0,
            )
        )


def test_negative_fcf_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="FCF normalizado",
    ):
        solve_implied_growth(
            ReverseDCFInput(
                current_price=100.0,
                diluted_shares=100.0,
                normalized_fcf=-1_000.0,
            )
        )


def test_discount_rate_must_exceed_terminal_growth() -> None:
    with pytest.raises(
        ValueError,
        match="tasa de descuento",
    ):
        solve_implied_growth(
            ReverseDCFInput(
                current_price=100.0,
                diluted_shares=100.0,
                normalized_fcf=1_000.0,
                discount_rate=0.02,
                terminal_growth=0.025,
            )
        )


def test_invalid_growth_range_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="crecimiento mínimo",
    ):
        solve_implied_growth(
            ReverseDCFInput(
                current_price=100.0,
                diluted_shares=100.0,
                normalized_fcf=1_000.0,
                minimum_growth=0.20,
                maximum_growth=0.10,
            )
        )


def test_non_positive_enterprise_value_is_not_evaluable() -> None:
    result = solve_implied_growth(
        ReverseDCFInput(
            current_price=10.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
            net_debt=-2_000.0,
        )
    )

    assert result.converged is False
    assert result.implied_growth is None
    assert result.status == "NO EVALUABLE"
    assert result.warning is not None


def test_status_classifies_low_expectations() -> None:
    target_growth = 0.02

    enterprise_value = enterprise_value_from_growth(
        normalized_fcf=1_000.0,
        growth_rate=target_growth,
        explicit_years=5,
        discount_rate=0.09,
        terminal_growth=0.025,
    )

    result = solve_implied_growth(
        ReverseDCFInput(
            current_price=enterprise_value / 100.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
        )
    )

    assert result.status == "EXPECTATIVAS MUY BAJAS"


def test_status_classifies_extreme_expectations() -> None:
    target_growth = 0.25

    enterprise_value = enterprise_value_from_growth(
        normalized_fcf=1_000.0,
        growth_rate=target_growth,
        explicit_years=5,
        discount_rate=0.09,
        terminal_growth=0.025,
    )

    result = solve_implied_growth(
        ReverseDCFInput(
            current_price=enterprise_value / 100.0,
            diluted_shares=100.0,
            normalized_fcf=1_000.0,
            maximum_growth=0.40,
        )
    )

    assert result.status == "EXPECTATIVAS EXTREMAS"
