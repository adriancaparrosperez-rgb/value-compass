from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any


def finite_number(
    value: Any,
) -> float | None:
    """
    Convierte un valor a float finito.

    Rechaza:
    - None
    - booleanos
    - valores no numéricos
    - NaN
    - infinitos
    """
    if value is None or isinstance(value, bool):
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(numeric_value):
        return None

    return numeric_value


def bounded_score(
    value: Any,
    *,
    default: float | None = None,
    decimals: int = 1,
) -> float | None:
    """
    Normaliza una puntuación al intervalo 0–100.

    Si el valor no es válido, devuelve `default`.
    """
    numeric_value = finite_number(value)

    if numeric_value is None:
        return default

    return round(
        max(
            0.0,
            min(
                100.0,
                numeric_value,
            ),
        ),
        decimals,
    )


def bounded_ratio(
    value: Any,
    *,
    minimum: float = 0.0,
    maximum: float = 1.0,
    default: float | None = None,
    decimals: int = 6,
) -> float | None:
    """
    Normaliza ratios expresados en tanto por uno.

    No convierte automáticamente porcentajes 0–100 a 0–1.
    Esa conversión debe realizarse explícitamente en el
    adaptador del proveedor para evitar ambigüedades.
    """
    numeric_value = finite_number(value)

    if numeric_value is None:
        return default

    if minimum > maximum:
        raise ValueError(
            "minimum no puede ser mayor que maximum."
        )

    return round(
        max(
            minimum,
            min(
                maximum,
                numeric_value,
            ),
        ),
        decimals,
    )


def normalize_text(
    value: Any,
    *,
    maximum_length: int | None = None,
    allow_non_string: bool = False,
) -> str | None:
    """
    Normaliza texto eliminando espacios exteriores.

    Por defecto solo acepta cadenas.
    """
    if value is None:
        return None

    if isinstance(value, str):
        normalized_value = value.strip()
    elif allow_non_string:
        normalized_value = str(value).strip()
    else:
        return None

    if not normalized_value:
        return None

    if maximum_length is not None:
        if maximum_length < 1:
            raise ValueError(
                "maximum_length debe ser mayor que cero."
            )

        if len(normalized_value) > maximum_length:
            if maximum_length == 1:
                return "…"

            normalized_value = (
                normalized_value[: maximum_length - 1]
                + "…"
            )

    return normalized_value


def normalize_ticker(
    value: Any,
    *,
    maximum_length: int = 30,
    strict: bool = True,
) -> str:
    """
    Normaliza un ticker.

    En modo estricto:
    - exige texto;
    - rechaza vacío;
    - rechaza espacios internos;
    - rechaza longitud excesiva.
    """
    if strict and not isinstance(value, str):
        raise ValueError(
            "El ticker debe ser una cadena de texto."
        )

    normalized_value = normalize_text(
        value,
        maximum_length=None,
        allow_non_string=not strict,
    )

    if not normalized_value:
        raise ValueError(
            "El ticker no puede estar vacío."
        )

    normalized_value = normalized_value.upper()

    if len(normalized_value) > maximum_length:
        raise ValueError(
            f"El ticker no puede superar "
            f"{maximum_length} caracteres."
        )

    if any(
        character.isspace()
        for character in normalized_value
    ):
        raise ValueError(
            "El ticker no puede contener espacios."
        )

    return normalized_value


def deduplicate_strings(
    values: Iterable[Any],
) -> list[str]:
    """
    Normaliza y deduplica textos preservando el orden.

    La comparación no distingue mayúsculas/minúsculas.
    """
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue

        normalized_value = value.strip()

        if not normalized_value:
            continue

        comparison_key = normalized_value.casefold()

        if comparison_key in seen:
            continue

        seen.add(comparison_key)
        result.append(normalized_value)

    return result


def parse_datetime_utc(
    value: Any,
) -> datetime | None:
    """
    Convierte una fecha ISO-8601 a datetime UTC.

    Las fechas sin zona horaria se interpretan como UTC.
    """
    if isinstance(value, datetime):
        parsed_value = value
    elif isinstance(value, str):
        normalized_value = value.strip()

        if not normalized_value:
            return None

        try:
            parsed_value = datetime.fromisoformat(
                normalized_value.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None
    else:
        return None

    if parsed_value.tzinfo is None:
        parsed_value = parsed_value.replace(
            tzinfo=timezone.utc
        )

    return parsed_value.astimezone(
        timezone.utc
    )


def iso_datetime_utc(
    value: Any,
) -> str | None:
    """
    Devuelve una fecha normalizada en ISO-8601 UTC.
    """
    parsed_value = parse_datetime_utc(value)

    if parsed_value is None:
        return None

    return parsed_value.isoformat()


def utc_now_iso() -> str:
    """
    Devuelve el instante actual en ISO-8601 UTC.
    """
    return datetime.now(
        timezone.utc
    ).isoformat()
