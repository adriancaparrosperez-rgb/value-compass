from __future__ import annotations

import re
from io import StringIO
from typing import Any

import pandas as pd
import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/125 Safari/537.36"
    )
}


def _flatten_column(column: Any) -> str:
    if isinstance(column, tuple):
        values = [
            str(value).strip()
            for value in column
            if str(value).strip().lower() != "nan"
        ]
        return " ".join(values)

    return str(column).strip()


def _clean_symbol(value: Any) -> str:
    if pd.isna(value):
        return ""

    symbol = str(value).strip().upper()

    symbol = re.sub(r"\[[^\]]*\]", "", symbol)
    symbol = re.sub(r"\([^)]*\)", "", symbol)
    symbol = symbol.replace("\xa0", "")
    symbol = symbol.replace(" ", "")
    symbol = symbol.strip(".,;:")

    return symbol


def _find_symbol_column(
    tables: list[pd.DataFrame],
    candidates: list[str],
) -> tuple[pd.DataFrame, str] | None:
    normalized_candidates = {
        candidate.strip().lower()
        for candidate in candidates
    }

    for table in tables:
        current = table.copy()

        current.columns = [
            _flatten_column(column)
            for column in current.columns
        ]

        for column in current.columns:
            normalized_column = column.strip().lower()

            if normalized_column in normalized_candidates:
                return current, column

        for column in current.columns:
            normalized_column = column.strip().lower()

            if any(
                candidate in normalized_column
                for candidate in normalized_candidates
            ):
                return current, column

    return None


def _apply_symbol_rules(
    symbols: list[str],
    definition: dict[str, Any],
) -> list[str]:
    suffix = str(definition.get("suffix", ""))
    pad_length = definition.get("pad_length")
    replace_dot = bool(
        definition.get("replace_dot_with_dash", False)
    )

    cleaned: list[str] = []

    for raw_symbol in symbols:
        symbol = _clean_symbol(raw_symbol)

        if not symbol:
            continue

        if symbol in {"NAN", "NONE", "-", "—"}:
            continue

        if replace_dot:
            symbol = symbol.replace(".", "-")

        if pad_length and symbol.isdigit():
            symbol = symbol.zfill(int(pad_length))

        if suffix and not symbol.endswith(suffix.upper()):
            symbol = f"{symbol}{suffix}"

        cleaned.append(symbol)

    return list(dict.fromkeys(cleaned))


def _load_wikipedia_universe(
    definition: dict[str, Any],
) -> list[str]:
    url = definition["url"]

    response = requests.get(
        url,
        headers=DEFAULT_HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    tables = pd.read_html(
        StringIO(response.text),
    )

    result = _find_symbol_column(
        tables=tables,
        candidates=definition.get(
            "symbol_columns",
            ["Ticker", "Symbol", "Code"],
        ),
    )

    if result is None:
        raise ValueError(
            "No se encontró una columna de tickers "
            f"en {url}."
        )

    table, symbol_column = result

    raw_symbols = table[symbol_column].tolist()

    symbols = _apply_symbol_rules(
        raw_symbols,
        definition,
    )

    minimum_size = int(
        definition.get("minimum_size", 3)
    )

    if len(symbols) < minimum_size:
        raise ValueError(
            "La tabla encontrada no contiene suficientes tickers."
        )

    return symbols


def load_universe(
    definition: dict[str, Any],
) -> tuple[list[str], str]:
    source = definition.get("source", "static")

    if source == "static":
        tickers = definition.get(
            "tickers",
            definition.get("fallback", []),
        )

        return (
            _apply_symbol_rules(
                list(tickers),
                {
                    **definition,
                    "suffix": "",
                    "pad_length": None,
                },
            ),
            "static",
        )

    if source == "wikipedia":
        try:
            tickers = _load_wikipedia_universe(
                definition,
            )

            return tickers, "remote"

        except Exception:
            fallback = definition.get("fallback", [])

            if not fallback:
                raise

            return (
                _apply_symbol_rules(
                    list(fallback),
                    {
                        **definition,
                        "suffix": "",
                        "pad_length": None,
                    },
                ),
                "fallback",
            )

    raise ValueError(
        f"Tipo de fuente no admitido: {source}"
    )
