from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import pytest

from src.domain import (
    bounded_ratio,
    bounded_score,
    deduplicate_strings,
    finite_number,
    iso_datetime_utc,
    normalize_text,
    normalize_ticker,
    parse_datetime_utc,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10, 10.0),
        ("10.5", 10.5),
        (None, None),
        (True, None),
        ("invalid", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
    ],
)
def test_finite_number(
    value: Any,
    expected: float | None,
) -> None:
    assert finite_number(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-10, 0.0),
        (0, 0.0),
        (45.56, 45.6),
        (100, 100.0),
        (150, 100.0),
        (None, None),
        (True, None),
        ("invalid", None),
        (float("nan"), None),
    ],
)
def test_bounded_score(
    value: Any,
    expected: float | None,
) -> None:
    assert bounded_score(value) == expected


def test_bounded_score_supports_explicit_default() -> None:
    assert bounded_score(
        None,
        default=50.0,
    ) == 50.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-1, 0.0),
        (0.25, 0.25),
        (1, 1.0),
        (2, 1.0),
        (None, None),
        (True, None),
        (float("nan"), None),
    ],
)
def test_bounded_ratio(
    value: Any,
    expected: float | None,
) -> None:
    assert bounded_ratio(value) == expected


def test_bounded_ratio_rejects_invalid_bounds() -> None:
    with pytest.raises(
        ValueError,
        match="minimum",
    ):
        bounded_ratio(
            0.5,
            minimum=1.0,
            maximum=0.0,
        )


def test_normalize_text() -> None:
    assert normalize_text(
        "  Empresa  "
    ) == "Empresa"

    assert normalize_text(
        ""
    ) is None

    assert normalize_text(
        123
    ) is None

    assert normalize_text(
        123,
        allow_non_string=True,
    ) == "123"


def test_normalize_text_truncates_safely() -> None:
    assert normalize_text(
        "abcdef",
        maximum_length=4,
    ) == "abc…"


def test_normalize_ticker_strict() -> None:
    assert normalize_ticker(
        "  itx.mc  "
    ) == "ITX.MC"


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        123,
        "",
        "   ",
        "BRK B",
    ],
)
def test_normalize_ticker_rejects_invalid_values(
    value: Any,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        normalize_ticker(value)


def test_normalize_ticker_legacy_mode() -> None:
    assert normalize_ticker(
        123,
        strict=False,
    ) == "123"


def test_deduplicate_strings_preserves_order() -> None:
    assert deduplicate_strings(
        [
            " Aviso ",
            "aviso",
            "",
            None,
            "Segundo",
            "SEGUNDO",
        ]
    ) == [
        "Aviso",
        "Segundo",
    ]


def test_parse_datetime_utc_accepts_iso_and_datetime() -> None:
    parsed_text = parse_datetime_utc(
        "2026-06-28T12:00:00Z"
    )

    parsed_datetime = parse_datetime_utc(
        datetime(
            2026,
            6,
            28,
            12,
            0,
            tzinfo=timezone.utc,
        )
    )

    assert parsed_text == parsed_datetime
    assert parsed_text is not None
    assert parsed_text.tzinfo == timezone.utc


def test_parse_datetime_utc_assumes_utc_for_naive_values() -> None:
    parsed = parse_datetime_utc(
        "2026-06-28T12:00:00"
    )

    assert parsed is not None
    assert parsed.tzinfo == timezone.utc


def test_invalid_datetime_returns_none() -> None:
    assert parse_datetime_utc(
        "not-a-date"
    ) is None


def test_iso_datetime_utc_returns_normalized_string() -> None:
    result = iso_datetime_utc(
        "2026-06-28T12:00:00Z"
    )

    assert result == "2026-06-28T12:00:00+00:00"


def test_normalized_numbers_are_finite() -> None:
    values = [
        bounded_score(float("nan")),
        bounded_score(float("inf")),
        bounded_ratio(float("-inf")),
    ]

    assert all(
        value is None
        or math.isfinite(value)
        for value in values
    )
