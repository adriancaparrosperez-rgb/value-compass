from __future__ import annotations

import math
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class SerializationError(ValueError):
    """Error controlado de serialización del dominio."""


def to_primitive(
    value: Any,
) -> Any:
    """
    Convierte recursivamente objetos del dominio en valores
    compatibles con JSON y SQLite.
    """
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if is_dataclass(value):
        return to_primitive(
            asdict(value)
        )

    if isinstance(value, dict):
        return {
            str(key): to_primitive(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            to_primitive(item)
            for item in value
        ]

    if isinstance(value, float):
        if not math.isfinite(value):
            raise SerializationError(
                "No se pueden serializar NaN ni infinitos."
            )

        return value

    if value is None or isinstance(
        value,
        (
            str,
            int,
            bool,
        ),
    ):
        return value

    raise SerializationError(
        "Tipo no serializable: "
        f"{type(value).__name__}."
    )
