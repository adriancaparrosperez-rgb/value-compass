from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from src.domain import (
    EligibilityStatus,
    SerializationError,
    to_primitive,
)


@dataclass
class ExampleModel:
    ticker: str
    status: EligibilityStatus
    created_at: datetime
    values: list[float]


def test_to_primitive_serializes_nested_domain_values() -> None:
    model = ExampleModel(
        ticker="META",
        status=EligibilityStatus.ELIGIBLE,
        created_at=datetime(
            2026,
            6,
            28,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        values=[
            10.0,
            20.0,
        ],
    )

    result = to_primitive(model)

    assert result == {
        "ticker": "META",
        "status": "ELEGIBLE",
        "created_at": "2026-06-28T12:00:00+00:00",
        "values": [
            10.0,
            20.0,
        ],
    }


@pytest.mark.parametrize(
    "invalid_value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_to_primitive_rejects_non_finite_numbers(
    invalid_value: float,
) -> None:
    with pytest.raises(
        SerializationError,
        match="NaN",
    ):
        to_primitive(
            {
                "value": invalid_value,
            }
        )


def test_to_primitive_rejects_unknown_objects() -> None:
    with pytest.raises(
        SerializationError,
        match="Tipo no serializable",
    ):
        to_primitive(
            object()
        )
