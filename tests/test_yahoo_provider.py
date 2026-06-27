from __future__ import annotations

import json
from typing import Any

import pytest

import src.providers.yahoo as yahoo_module
from src.models import CompanySnapshot
from src.providers.yahoo import (
    PROVIDER_NAME,
    PROVIDER_SOURCE,
    YahooProvider,
    _first_not_none,
    _integer,
    _num,
    _normalize_ticker,
    _ratio,
    _unix_timestamp_to_iso,
)


class FakeYahooTicker:
    def __init__(
        self,
        *,
        info: Any = None,
        fast_info: Any = None,
        info_error: Exception | None = None,
        fast_info_error: Exception | None = None,
    ) -> None:
        self._info = info
        self._fast_info = fast_info
        self._info_error = info_error
        self._fast_info_error = fast_info_error

    @property
    def info(self) -> Any:
        if self._info_error is not None:
            raise self._info_error

        return self._info

    @property
    def fast_info(self) -> Any:
        if self._fast_info_error is not None:
            raise self._fast_info_error

        return self._fast_info


def _valid_info() -> dict[str, Any]:
    return {
        "longName": "Test Company",
        "shortName": "Test",
        "currency": "EUR",
        "sector": "Industrials",
        "industry": "Industrial Products",
        "currentPrice": 100.0,
        "regularMarketPrice": 99.0,
        "regularMarketTime": 1_750_000_000,
        "marketCap": 1_000_000_000.0,
        "enterpriseValue": 1_100_000_000.0,
        "totalRevenue": 500_000_000.0,
        "ebitda": 100_000_000.0,
        "ebit": 80_000_000.0,
        "netIncomeToCommon": 50_000_000.0,
        "operatingCashflow": 90_000_000.0,
        "freeCashflow": 60_000_000.0,
        "totalCash": 120_000_000.0,
        "totalDebt": 220_000_000.0,
        "sharesOutstanding": 10_000_000.0,
        "revenueGrowth": 0.08,
        "earningsGrowth": 0.10,
        "grossMargins": 0.40,
        "operatingMargins": 0.16,
        "profitMargins": 0.10,
        "returnOnEquity": 0.18,
        "returnOnAssets": 0.09,
        "debtToEquity": 55.0,
        "currentRatio": 1.4,
        "trailingPE": 20.0,
        "forwardPE": 18.0,
        "priceToBook": 3.0,
        "enterpriseToEbitda": 11.0,
        "dividendYield": 0.025,
        "52WeekChange": 0.15,
        "targetMeanPrice": 115.0,
        "numberOfAnalystOpinions": 12,
        "mostRecentQuarter": 1_748_000_000,
    }


def _valid_fast_info() -> dict[str, Any]:
    return {
        "last_price": 101.0,
        "market_cap": 1_010_000_000.0,
        "last_price_time": 1_750_100_000,
    }


def _patch_ticker(
    monkeypatch: pytest.MonkeyPatch,
    fake_ticker: FakeYahooTicker,
) -> None:
    monkeypatch.setattr(
        yahoo_module.yf,
        "Ticker",
        lambda ticker: fake_ticker,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("itx.mc", "ITX.MC"),
        ("  brk.b  ", "BRK.B"),
        ("AAPL", "AAPL"),
    ],
)
def test_normalize_ticker(
    value: str,
    expected: str,
) -> None:
    assert _normalize_ticker(
        value
    ) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "no puede estar vacío"),
        ("   ", "no puede estar vacío"),
        ("BRK B", "no puede contener espacios"),
        ("A" * 31, "no puede superar 30"),
    ],
)
def test_invalid_ticker_raises_error(
    value: str,
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        _normalize_ticker(
            value
        )


def test_non_string_ticker_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="cadena de texto",
    ):
        _normalize_ticker(
            123
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10, 10.0),
        ("10.5", 10.5),
        (0, 0.0),
        (-4, -4.0),
        (None, None),
        (True, None),
        (False, None),
        ("invalid", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
    ],
)
def test_num_conversion(
    value: Any,
    expected: float | None,
) -> None:
    assert _num(
        value
    ) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (5, 5),
        ("7", 7),
        (7.0, 7),
        (-1, None),
        (1.5, None),
        ("invalid", None),
        (True, None),
        (None, None),
    ],
)
def test_integer_conversion(
    value: Any,
    expected: int | None,
) -> None:
    assert _integer(
        value
    ) == expected


def test_first_not_none_preserves_zero() -> None:
    assert _first_not_none(
        None,
        0.0,
        5.0,
    ) == 0.0


def test_first_not_none_returns_none_when_all_missing() -> None:
    assert _first_not_none(
        None,
        None,
    ) is None


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (0, 100, 0.0),
        (50, 100, 0.5),
        (-50, 100, -0.5),
        (50, 0, None),
        (50, -10, None),
        (None, 100, None),
        (50, None, None),
        (float("inf"), 100, None),
    ],
)
def test_ratio(
    numerator: Any,
    denominator: Any,
    expected: float | None,
) -> None:
    assert _ratio(
        numerator,
        denominator,
    ) == expected


def test_unix_timestamp_to_iso() -> None:
    result = _unix_timestamp_to_iso(
        1_750_000_000
    )

    assert result is not None
    assert result.endswith(
        "+00:00"
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        -1,
        "invalid",
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_timestamp_returns_none(
    value: Any,
) -> None:
    assert (
        _unix_timestamp_to_iso(
            value
        )
        is None
    )


def test_provider_builds_complete_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=_valid_info(),
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        " test "
    )

    assert isinstance(
        snapshot,
        CompanySnapshot,
    )
    assert snapshot.ticker == "TEST"
    assert snapshot.name == "Test Company"
    assert snapshot.currency == "EUR"
    assert snapshot.sector == "Industrials"
    assert snapshot.industry == "Industrial Products"
    assert snapshot.price == 101.0
    assert snapshot.market_cap == 1_010_000_000.0
    assert snapshot.enterprise_value == 1_100_000_000.0
    assert snapshot.revenue == 500_000_000.0
    assert snapshot.net_income == 50_000_000.0
    assert snapshot.operating_cash_flow == 90_000_000.0
    assert snapshot.free_cash_flow == 60_000_000.0
    assert snapshot.total_cash == 120_000_000.0
    assert snapshot.total_debt == 220_000_000.0
    assert snapshot.shares == 10_000_000.0

    assert snapshot.fcf_yield == pytest.approx(
        60_000_000.0
        / 1_010_000_000.0
    )
    assert snapshot.earnings_yield == pytest.approx(
        50_000_000.0
        / 1_010_000_000.0
    )

    assert snapshot.analyst_count == 12
    assert snapshot.source == PROVIDER_SOURCE
    assert snapshot.fetched_at

    metadata = snapshot.provider_metadata

    assert metadata[
        "provider"
    ] == PROVIDER_NAME
    assert metadata[
        "provider_role"
    ] == "preload"
    assert metadata[
        "is_official_source"
    ] is False
    assert metadata[
        "initialization"
    ][
        "status"
    ] == "success"
    assert metadata[
        "normalization"
    ][
        "status"
    ] == "success"
    assert metadata[
        "fast_info_usable"
    ] is True
    assert metadata[
        "info_usable"
    ] is True
    assert metadata[
        "provider_status"
    ] == "success"
    assert metadata[
        "contributing_components"
    ] == [
        "fast_info",
        "info",
    ]
    assert metadata[
        "price_source"
    ] == "fast_info.last_price"
    assert metadata[
        "market_cap_source"
    ] == "fast_info.market_cap"
    assert metadata[
        "validity_status"
    ] == "assessed"
    assert metadata[
        "consistency_status"
    ] == "assessed"

    assert snapshot.price_date is not None
    assert snapshot.fundamentals_date is not None
    assert snapshot.coverage_score > 80
    assert snapshot.validity_score == 100.0
    assert snapshot.consistency_score == 100.0
    assert snapshot.data_quality > 80
    assert snapshot.errors == ""


def test_provider_falls_back_to_info_market_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=_valid_info(),
        fast_info={},
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.price == 100.0
    assert snapshot.market_cap == 1_000_000_000.0
    assert snapshot.provider_metadata[
        "price_source"
    ] == "info.currentPrice"
    assert snapshot.provider_metadata[
        "market_cap_source"
    ] == "info.marketCap"
    assert snapshot.provider_metadata[
        "fast_info_usable"
    ] is False
    assert snapshot.provider_metadata[
        "info_usable"
    ] is True
    assert snapshot.provider_metadata[
        "provider_status"
    ] == "partial"


def test_regular_market_price_is_final_price_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "currentPrice"
    ] = None
    info[
        "regularMarketPrice"
    ] = 98.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info={},
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.price == 98.0
    assert snapshot.provider_metadata[
        "price_source"
    ] == "info.regularMarketPrice"


def test_provider_preserves_zero_fcf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "freeCashflow"
    ] = 0.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.free_cash_flow == 0.0
    assert snapshot.fcf_yield == 0.0
    assert (
        "free_cash_flow"
        not in snapshot.missing_fields
    )


def test_provider_preserves_zero_net_income(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "netIncomeToCommon"
    ] = 0.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.net_income == 0.0
    assert snapshot.earnings_yield == 0.0
    assert (
        "net_income"
        not in snapshot.missing_fields
    )


def test_invalid_numeric_values_are_discarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info.update(
        {
            "totalRevenue": float("nan"),
            "ebitda": float("inf"),
            "netIncomeToCommon": "invalid",
            "freeCashflow": True,
            "targetMeanPrice": float("-inf"),
        }
    )

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.revenue is None
    assert snapshot.ebitda is None
    assert snapshot.net_income is None
    assert snapshot.free_cash_flow is None
    assert snapshot.analyst_target is None


def test_invalid_analyst_count_does_not_break_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "numberOfAnalystOpinions"
    ] = "N/A"

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.analyst_count is None
    assert snapshot.price == 101.0
    assert snapshot.errors == ""


@pytest.mark.parametrize(
    "analyst_count",
    [
        -1,
        1.5,
        True,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_analyst_count_values_return_none(
    monkeypatch: pytest.MonkeyPatch,
    analyst_count: Any,
) -> None:
    info = _valid_info()
    info[
        "numberOfAnalystOpinions"
    ] = analyst_count

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.analyst_count is None


def test_fast_info_failure_allows_info_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=_valid_info(),
        fast_info_error=RuntimeError(
            "fast_info unavailable"
        ),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    metadata = snapshot.provider_metadata

    assert snapshot.price == 100.0
    assert snapshot.market_cap == 1_000_000_000.0
    assert snapshot.errors == ""
    assert metadata[
        "fast_info_error"
    ] is True
    assert metadata[
        "fast_info_usable"
    ] is False
    assert metadata[
        "info_usable"
    ] is True
    assert metadata[
        "provider_status"
    ] == "partial"
    assert metadata[
        "fast_info"
    ][
        "exception_type"
    ] == "RuntimeError"
    assert metadata[
        "fast_info"
    ][
        "message"
    ] == "fast_info unavailable"

    assert any(
        "datos rápidos"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_info_failure_allows_fast_info_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info_error=RuntimeError(
            "info unavailable"
        ),
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    metadata = snapshot.provider_metadata

    assert snapshot.price == 101.0
    assert snapshot.market_cap == 1_010_000_000.0
    assert snapshot.name == "TEST"
    assert metadata[
        "info_error"
    ] is True
    assert metadata[
        "info_usable"
    ] is False
    assert metadata[
        "fast_info_usable"
    ] is True
    assert metadata[
        "provider_status"
    ] == "partial"
    assert metadata[
        "info"
    ][
        "exception_type"
    ] == "RuntimeError"
    assert metadata[
        "info"
    ][
        "message"
    ] == "info unavailable"

    assert any(
        "ficha fundamental"
        in warning.casefold()
        for warning in snapshot.warnings
    )
    assert snapshot.data_quality < 70.0


def test_fast_info_object_can_be_loaded_but_unusable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info_error=RuntimeError(
            "info unavailable"
        ),
        fast_info={
            "last_price": None,
            "market_cap": None,
            "last_price_time": None,
            "exchange": "NMS",
        },
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "META"
    )

    metadata = snapshot.provider_metadata

    assert metadata[
        "fast_info_available"
    ] is True
    assert metadata[
        "fast_info_usable"
    ] is False
    assert metadata[
        "fast_info"
    ][
        "loaded"
    ] is True
    assert metadata[
        "fast_info"
    ][
        "status"
    ] == "unusable"
    assert metadata[
        "fast_info"
    ][
        "useful_field_count"
    ] == 0
    assert metadata[
        "provider_status"
    ] == "failed"
    assert metadata[
        "contributing_components"
    ] == []

    assert snapshot.price is None
    assert snapshot.market_cap is None
    assert snapshot.errors == (
        "Yahoo no devolvió información utilizable "
        "para el ticker solicitado."
    )
    assert snapshot.has_errors is True
    assert snapshot.is_usable is False


def test_fast_info_nan_values_are_not_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info={},
        fast_info={
            "last_price": float("nan"),
            "market_cap": float("inf"),
            "last_price_time": "invalid",
        },
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.provider_metadata[
        "fast_info_usable"
    ] is False
    assert snapshot.provider_metadata[
        "provider_status"
    ] == "failed"
    assert snapshot.price is None
    assert snapshot.market_cap is None
    assert snapshot.errors


def test_non_empty_info_without_usable_fields_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info={
            "irrelevantField": "irrelevant",
            "currentPrice": float("nan"),
            "marketCap": True,
        },
        fast_info={},
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    metadata = snapshot.provider_metadata

    assert metadata[
        "info_available"
    ] is True
    assert metadata[
        "info_usable"
    ] is False
    assert metadata[
        "info"
    ][
        "status"
    ] == "unusable"
    assert metadata[
        "provider_status"
    ] == "failed"
    assert snapshot.errors


def test_both_sources_missing_return_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info={},
        fast_info={},
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.errors == (
        "Yahoo no devolvió información utilizable "
        "para el ticker solicitado."
    )
    assert snapshot.provider_metadata[
        "provider_status"
    ] == "failed"
    assert snapshot.provider_metadata[
        "contributing_component_count"
    ] == 0
    assert snapshot.coverage_score == 0.0
    assert snapshot.validity_score == 0.0
    assert snapshot.consistency_score == 0.0
    assert snapshot.data_quality == 0.0
    assert snapshot.has_errors is True
    assert snapshot.is_usable is False


def test_ticker_creation_failure_returns_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_creation_error(
        ticker: str,
    ) -> Any:
        raise RuntimeError(
            "creation failure"
        )

    monkeypatch.setattr(
        yahoo_module.yf,
        "Ticker",
        raise_creation_error,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert isinstance(
        snapshot,
        CompanySnapshot,
    )
    assert snapshot.ticker == "TEST"
    assert snapshot.errors == (
        "No se pudo inicializar el proveedor "
        "de datos."
    )
    assert snapshot.provider_metadata[
        "initialization"
    ][
        "status"
    ] == "error"
    assert snapshot.provider_metadata[
        "initialization"
    ][
        "exception_type"
    ] == "RuntimeError"
    assert snapshot.provider_metadata[
        "initialization"
    ][
        "message"
    ] == "creation failure"
    assert snapshot.provider_metadata[
        "provider_status"
    ] == "failed"
    assert snapshot.data_quality == 0.0
    assert snapshot.is_usable is False


def test_missing_price_is_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "currentPrice"
    ] = None
    info[
        "regularMarketPrice"
    ] = None

    fast_info = _valid_fast_info()
    fast_info[
        "last_price"
    ] = None

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.price is None
    assert (
        "price"
        in snapshot.critical_missing_fields
    )
    assert snapshot.data_quality <= 30.0
    assert snapshot.is_usable is False


def test_missing_market_cap_caps_quality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "marketCap"
    ] = None

    fast_info = _valid_fast_info()
    fast_info[
        "market_cap"
    ] = None

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.market_cap is None
    assert (
        "market_cap"
        in snapshot.critical_missing_fields
    )
    assert snapshot.data_quality <= 55.0


def test_market_cap_consistency_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "sharesOutstanding"
    ] = 10_000_000.0

    fast_info = _valid_fast_info()
    fast_info[
        "last_price"
    ] = 100.0
    fast_info[
        "market_cap"
    ] = 1_000_000_000.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.consistency_score == 100.0
    assert snapshot.provider_metadata[
        "consistency_status"
    ] == "assessed"
    assert snapshot.provider_metadata[
        "market_cap_consistency_status"
    ] == "assessed"
    assert snapshot.provider_metadata[
        "market_cap_relative_difference"
    ] == 0.0


def test_consistency_is_not_assessable_when_components_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "sharesOutstanding"
    ] = None

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.consistency_score == 0.0
    assert snapshot.provider_metadata[
        "consistency_status"
    ] == "not_assessable"
    assert snapshot.provider_metadata[
        "market_cap_consistency_status"
    ] == "not_assessable"


def test_large_market_cap_difference_generates_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "sharesOutstanding"
    ] = 1_000_000.0

    fast_info = _valid_fast_info()
    fast_info[
        "last_price"
    ] = 100.0
    fast_info[
        "market_cap"
    ] = 1_000_000_000.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.consistency_score == 40.0
    assert any(
        "capitalización no coincide"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_moderate_market_cap_difference_reduces_consistency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "sharesOutstanding"
    ] = 7_000_000.0

    fast_info = _valid_fast_info()
    fast_info[
        "last_price"
    ] = 100.0
    fast_info[
        "market_cap"
    ] = 1_000_000_000.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.consistency_score == 70.0
    assert any(
        "diferencia relevante"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_extreme_percentage_field_generates_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "returnOnEquity"
    ] = 25.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert (
        "roe"
        in snapshot.provider_metadata[
            "invalid_fields"
        ]
    )
    assert snapshot.validity_score == 85.0
    assert any(
        "roe presenta un valor extremo"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_validity_is_not_assessable_without_checkable_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info_error=RuntimeError(
            "info unavailable"
        ),
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.validity_score == 0.0
    assert snapshot.provider_metadata[
        "validity_status"
    ] == "not_assessable"
    assert snapshot.provider_metadata[
        "validity_evaluated_check_count"
    ] == 0


def test_negative_current_ratio_is_discarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "currentRatio"
    ] = -1.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.current_ratio is None
    assert (
        "current_ratio"
        in snapshot.provider_metadata[
            "invalid_fields"
        ]
    )
    assert any(
        "current ratio es negativo"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_extreme_analyst_target_generates_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "targetMeanPrice"
    ] = 3_000.0

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert (
        "analyst_target"
        in snapshot.provider_metadata[
            "invalid_fields"
        ]
    )
    assert any(
        "precio objetivo"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_capex_remains_unavailable_with_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=_valid_info(),
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.capex is None
    assert any(
        "capex"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_missing_currency_generates_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "currency"
    ] = None

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.currency == ""
    assert any(
        "moneda"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_missing_fundamentals_date_generates_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "mostRecentQuarter"
    ] = None

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.fundamentals_date is None
    assert any(
        "fecha fiable"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_provider_does_not_call_yahoo_for_invalid_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_ticker_factory(
        ticker: str,
    ) -> Any:
        nonlocal called
        called = True

        return FakeYahooTicker(
            info={},
            fast_info={},
        )

    monkeypatch.setattr(
        yahoo_module.yf,
        "Ticker",
        fake_ticker_factory,
    )

    with pytest.raises(
        ValueError,
        match="no puede estar vacío",
    ):
        YahooProvider().get_snapshot(
            "   "
        )

    assert called is False


def test_provider_snapshot_is_serializable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=_valid_info(),
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    serialized = json.dumps(
        snapshot.to_dict(),
        ensure_ascii=False,
    )

    assert isinstance(
        serialized,
        str,
    )
    assert "Test Company" in serialized
    assert "provider_status" in serialized
    assert "contributing_components" in serialized
