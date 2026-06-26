from __future__ import annotations
import logging
import math
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
import yfinance as yf
from src.models import CompanySnapshot
from src.providers.base import MarketDataProvider
PROVIDER_NAME = "Yahoo Finance"
PROVIDER_SOURCE = (
    "Yahoo Finance (precarga; fuente secundaria)"
)
logger = logging.getLogger(__name__)
def _normalize_ticker(
    ticker: Any,
) -> str:
    """
    Normaliza y valida el ticker antes de realizar peticiones.
    """
    if not isinstance(ticker, str):
        raise ValueError(
            "El ticker debe ser una cadena de texto."
        )
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise ValueError(
            "El ticker no puede estar vacío."
        )
    if len(normalized_ticker) > 30:
        raise ValueError(
            "El ticker no puede superar 30 caracteres."
        )
    if any(
        character.isspace()
        for character in normalized_ticker
    ):
        raise ValueError(
            "El ticker no puede contener espacios."
        )
    return normalized_ticker
def _num(
    value: Any,
) -> float | None:
    """
    Convierte un valor a float y rechaza booleanos,
    NaN, infinitos y valores no numéricos.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(
        numeric_value
    ):
        return None
    return numeric_value
def _integer(
    value: Any,
) -> int | None:
    """
    Convierte un valor a entero no negativo únicamente
    cuando representa realmente un número entero.
    """
    numeric_value = _num(
        value
    )
    if numeric_value is None:
        return None
    if numeric_value < 0:
        return None
    if not numeric_value.is_integer():
        return None
    return int(
        numeric_value
    )
def _text(
    value: Any,
    default: str = "",
    maximum_length: int = 500,
) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        normalized_value = value.strip()
    else:
        normalized_value = str(value).strip()
    if not normalized_value:
        return default
    if len(normalized_value) > maximum_length:
        return (
            normalized_value[: maximum_length - 1]
            + "…"
        )
    return normalized_value
def _safe_get(
    container: Any,
    key: str,
) -> Any:
    """
    Obtiene un valor de estructuras tipo diccionario sin dejar
    que un campo defectuoso interrumpa toda la precarga.
    """
    if container is None:
        return None
    try:
        if isinstance(
            container,
            Mapping,
        ):
            return container.get(
                key
            )
        getter = getattr(
            container,
            "get",
            None,
        )
        if callable(getter):
            return getter(
                key
            )
        return getattr(
            container,
            key,
            None,
        )
    except Exception:
        return None
def _first_not_none(
    *values: Any,
) -> Any:
    """
    Devuelve el primer valor que no sea None.
    No utiliza `or`, por lo que conserva correctamente
    valores numéricos iguales a cero.
    """
    for value in values:
        if value is not None:
            return value
    return None
def _unix_timestamp_to_iso(
    value: Any,
) -> str | None:
    timestamp = _num(
        value
    )
    if timestamp is None or timestamp <= 0:
        return None
    try:
        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).isoformat()
    except (
        OverflowError,
        OSError,
        ValueError,
    ):
        return None
def _positive_or_none(
    value: Any,
) -> float | None:
    numeric_value = _num(
        value
    )
    if (
        numeric_value is None
        or numeric_value <= 0
    ):
        return None
    return numeric_value
def _non_negative_or_none(
    value: Any,
) -> float | None:
    numeric_value = _num(
        value
    )
    if (
        numeric_value is None
        or numeric_value < 0
    ):
        return None
    return numeric_value
def _ratio(
    numerator: Any,
    denominator: Any,
) -> float | None:
    normalized_numerator = _num(
        numerator
    )
    normalized_denominator = _num(
        denominator
    )
    if (
        normalized_numerator is None
        or normalized_denominator is None
        or normalized_denominator <= 0
    ):
        return None
    result = (
        normalized_numerator
        / normalized_denominator
    )
    if not math.isfinite(
        result
    ):
        return None
    return result
def _load_fast_info(
    yahoo_ticker: Any,
    snapshot: CompanySnapshot,
) -> Any:
    try:
        fast_info = yahoo_ticker.fast_info
    except Exception:
        logger.exception(
            "No se pudo cargar fast_info de Yahoo "
            "para %s.",
            snapshot.ticker,
        )
        snapshot.add_warning(
            "Yahoo no pudo proporcionar los datos rápidos "
            "del mercado."
        )
        snapshot.provider_metadata[
            "fast_info_error"
        ] = True
        return {}
    if fast_info is None:
        snapshot.add_warning(
            "Yahoo no devolvió datos rápidos del mercado."
        )
        snapshot.provider_metadata[
            "fast_info_available"
        ] = False
        return {}
    snapshot.provider_metadata[
        "fast_info_available"
    ] = True
    return fast_info
def _load_info(
    yahoo_ticker: Any,
    snapshot: CompanySnapshot,
) -> Mapping[str, Any]:
    try:
        info = yahoo_ticker.info
    except Exception:
        logger.exception(
            "No se pudo cargar info de Yahoo para %s.",
            snapshot.ticker,
        )
        snapshot.add_warning(
            "Yahoo no pudo proporcionar la ficha fundamental."
        )
        snapshot.provider_metadata[
            "info_error"
        ] = True
        return {}
    if not isinstance(
        info,
        Mapping,
    ):
        snapshot.add_warning(
            "Yahoo devolvió la ficha fundamental "
            "en un formato no válido."
        )
        snapshot.provider_metadata[
            "info_available"
        ] = False
        return {}
    snapshot.provider_metadata[
        "info_available"
    ] = bool(
        info
    )
    return info
def _assign_identity_fields(
    snapshot: CompanySnapshot,
    info: Mapping[str, Any],
) -> None:
    snapshot.name = _text(
        _first_not_none(
            _safe_get(
                info,
                "longName",
            ),
            _safe_get(
                info,
                "shortName",
            ),
            snapshot.ticker,
        ),
        default=snapshot.ticker,
        maximum_length=250,
    )
    snapshot.currency = _text(
        _safe_get(
            info,
            "currency",
        ),
        maximum_length=20,
    ).upper()
    snapshot.sector = _text(
        _safe_get(
            info,
            "sector",
        ),
        maximum_length=150,
    )
    snapshot.industry = _text(
        _safe_get(
            info,
            "industry",
        ),
        maximum_length=200,
    )
def _assign_market_fields(
    snapshot: CompanySnapshot,
    fast_info: Any,
    info: Mapping[str, Any],
) -> None:
    fast_price = _positive_or_none(
        _safe_get(
            fast_info,
            "last_price",
        )
    )
    current_price = _positive_or_none(
        _safe_get(
            info,
            "currentPrice",
        )
    )
    regular_market_price = _positive_or_none(
        _safe_get(
            info,
            "regularMarketPrice",
        )
    )
    snapshot.price = _first_not_none(
        fast_price,
        current_price,
        regular_market_price,
    )
    if fast_price is not None:
        price_source = "fast_info.last_price"
    elif current_price is not None:
        price_source = "info.currentPrice"
    elif regular_market_price is not None:
        price_source = (
            "info.regularMarketPrice"
        )
    else:
        price_source = None
    snapshot.provider_metadata[
        "price_source"
    ] = price_source
    fast_market_cap = _positive_or_none(
        _safe_get(
            fast_info,
            "market_cap",
        )
    )
    info_market_cap = _positive_or_none(
        _safe_get(
            info,
            "marketCap",
        )
    )
    snapshot.market_cap = _first_not_none(
        fast_market_cap,
        info_market_cap,
    )
    snapshot.provider_metadata[
        "market_cap_source"
    ] = (
        "fast_info.market_cap"
        if fast_market_cap is not None
        else (
            "info.marketCap"
            if info_market_cap is not None
            else None
        )
    )
    snapshot.enterprise_value = (
        _positive_or_none(
            _safe_get(
                info,
                "enterpriseValue",
            )
        )
    )
    snapshot.fifty_two_week_change = _num(
        _safe_get(
            info,
            "52WeekChange",
        )
    )
    snapshot.analyst_target = (
        _positive_or_none(
            _safe_get(
                info,
                "targetMeanPrice",
            )
        )
    )
    snapshot.analyst_count = _integer(
        _safe_get(
            info,
            "numberOfAnalystOpinions",
        )
    )
    snapshot.price_date = (
        _unix_timestamp_to_iso(
            _first_not_none(
                _safe_get(
                    fast_info,
                    "last_price_time",
                ),
                _safe_get(
                    info,
                    "regularMarketTime",
                ),
            )
        )
    )
def _assign_fundamental_fields(
    snapshot: CompanySnapshot,
    info: Mapping[str, Any],
) -> None:
    snapshot.revenue = _num(
        _safe_get(
            info,
            "totalRevenue",
        )
    )
    snapshot.ebitda = _num(
        _safe_get(
            info,
            "ebitda",
        )
    )
    snapshot.ebit = _num(
        _safe_get(
            info,
            "ebit",
        )
    )
    snapshot.net_income = _num(
        _safe_get(
            info,
            "netIncomeToCommon",
        )
    )
    snapshot.operating_cash_flow = _num(
        _safe_get(
            info,
            "operatingCashflow",
        )
    )
    snapshot.free_cash_flow = _num(
        _safe_get(
            info,
            "freeCashflow",
        )
    )
    snapshot.capex = None
    snapshot.total_cash = (
        _non_negative_or_none(
            _safe_get(
                info,
                "totalCash",
            )
        )
    )
    snapshot.total_debt = (
        _non_negative_or_none(
            _safe_get(
                info,
                "totalDebt",
            )
        )
    )
    snapshot.shares = _positive_or_none(
        _safe_get(
            info,
            "sharesOutstanding",
        )
    )
    snapshot.revenue_growth = _num(
        _safe_get(
            info,
            "revenueGrowth",
        )
    )
    snapshot.earnings_growth = _num(
        _safe_get(
            info,
            "earningsGrowth",
        )
    )
    snapshot.gross_margin = _num(
        _safe_get(
            info,
            "grossMargins",
        )
    )
    snapshot.operating_margin = _num(
        _safe_get(
            info,
            "operatingMargins",
        )
    )
    snapshot.net_margin = _num(
        _safe_get(
            info,
            "profitMargins",
        )
    )
    snapshot.roe = _num(
        _safe_get(
            info,
            "returnOnEquity",
        )
    )
    snapshot.roa = _num(
        _safe_get(
            info,
            "returnOnAssets",
        )
    )
    snapshot.debt_to_equity = _num(
        _safe_get(
            info,
            "debtToEquity",
        )
    )
    snapshot.current_ratio = _num(
        _safe_get(
            info,
            "currentRatio",
        )
    )
    snapshot.pe = _positive_or_none(
        _safe_get(
            info,
            "trailingPE",
        )
    )
    snapshot.forward_pe = (
        _positive_or_none(
            _safe_get(
                info,
                "forwardPE",
            )
        )
    )
    snapshot.price_to_book = _num(
        _safe_get(
            info,
            "priceToBook",
        )
    )
    snapshot.ev_to_ebitda = _num(
        _safe_get(
            info,
            "enterpriseToEbitda",
        )
    )
    snapshot.dividend_yield = _num(
        _safe_get(
            info,
            "dividendYield",
        )
    )
    snapshot.fundamentals_date = (
        _unix_timestamp_to_iso(
            _safe_get(
                info,
                "mostRecentQuarter",
            )
        )
    )
def _calculate_derived_fields(
    snapshot: CompanySnapshot,
) -> None:
    snapshot.fcf_yield = _ratio(
        snapshot.free_cash_flow,
        snapshot.market_cap,
    )
    snapshot.earnings_yield = _ratio(
        snapshot.net_income,
        snapshot.market_cap,
    )
def _validate_value_ranges(
    snapshot: CompanySnapshot,
) -> list[str]:
    invalid_fields: list[str] = []
    percentage_fields = {
        "revenue_growth": snapshot.revenue_growth,
        "earnings_growth": snapshot.earnings_growth,
        "gross_margin": snapshot.gross_margin,
        "operating_margin": snapshot.operating_margin,
        "net_margin": snapshot.net_margin,
        "roe": snapshot.roe,
        "roa": snapshot.roa,
        "dividend_yield": snapshot.dividend_yield,
        "fifty_two_week_change": (
            snapshot.fifty_two_week_change
        ),
    }
    for field_name, value in (
        percentage_fields.items()
    ):
        if value is None:
            continue
        if abs(value) > 20:
            invalid_fields.append(
                field_name
            )
            snapshot.add_warning(
                f"El campo {field_name} presenta un valor "
                "extremo y requiere verificación."
            )
    if (
        snapshot.current_ratio is not None
        and snapshot.current_ratio < 0
    ):
        invalid_fields.append(
            "current_ratio"
        )
        snapshot.add_warning(
            "El current ratio es negativo y no se "
            "considera fiable."
        )
        snapshot.current_ratio = None
    if (
        snapshot.analyst_target is not None
        and snapshot.price is not None
        and snapshot.analyst_target
        > snapshot.price * 20
    ):
        invalid_fields.append(
            "analyst_target"
        )
        snapshot.add_warning(
            "El precio objetivo de analistas presenta "
            "una diferencia extrema respecto al precio."
        )
    return invalid_fields
def _validate_market_cap_consistency(
    snapshot: CompanySnapshot,
) -> float:
    if (
        snapshot.price is None
        or snapshot.shares is None
        or snapshot.market_cap is None
    ):
        return 100.0
    estimated_market_cap = (
        snapshot.price
        * snapshot.shares
    )
    if estimated_market_cap <= 0:
        return 100.0
    relative_difference = abs(
        snapshot.market_cap
        - estimated_market_cap
    ) / max(
        snapshot.market_cap,
        estimated_market_cap,
    )
    snapshot.provider_metadata[
        "market_cap_relative_difference"
    ] = round(
        relative_difference,
        4,
    )
    if relative_difference > 0.50:
        snapshot.add_warning(
            "La capitalización no coincide de forma "
            "razonable con precio por acciones en circulación. "
            "Puede existir una diferencia de clase, ADR, fecha "
            "o unidad."
        )
        return 40.0
    if relative_difference > 0.20:
        snapshot.add_warning(
            "La capitalización presenta una diferencia "
            "relevante respecto a precio por acciones."
        )
        return 70.0
    return 100.0
def _calculate_coverage_score(
    snapshot: CompanySnapshot,
) -> float:
    weighted_fields: dict[str, tuple[Any, float]] = {
        "price": (
            snapshot.price,
            15.0,
        ),
        "market_cap": (
            snapshot.market_cap,
            12.0,
        ),
        "currency": (
            snapshot.currency or None,
            5.0,
        ),
        "revenue": (
            snapshot.revenue,
            10.0,
        ),
        "net_income": (
            snapshot.net_income,
            8.0,
        ),
        "free_cash_flow": (
            snapshot.free_cash_flow,
            10.0,
        ),
        "total_cash": (
            snapshot.total_cash,
            7.0,
        ),
        "total_debt": (
            snapshot.total_debt,
            7.0,
        ),
        "shares": (
            snapshot.shares,
            8.0,
        ),
        "pe": (
            snapshot.pe,
            4.0,
        ),
        "ev_to_ebitda": (
            snapshot.ev_to_ebitda,
            4.0,
        ),
        "roe": (
            snapshot.roe,
            5.0,
        ),
        "operating_margin": (
            snapshot.operating_margin,
            5.0,
        ),
    }
    available_weight = sum(
        weight
        for value, weight in (
            weighted_fields.values()
        )
        if value is not None
    )
    total_weight = sum(
        weight
        for _, weight in (
            weighted_fields.values()
        )
    )
    snapshot.missing_fields = [
        field_name
        for field_name, (
            value,
            _,
        ) in weighted_fields.items()
        if value is None
    ]
    if total_weight <= 0:
        return 0.0
    return round(
        100.0
        * available_weight
        / total_weight,
        1,
    )
def _calculate_quality_scores(
    snapshot: CompanySnapshot,
    invalid_fields: list[str],
    consistency_score: float,
) -> None:
    snapshot.coverage_score = (
        _calculate_coverage_score(
            snapshot
        )
    )
    snapshot.validity_score = round(
        max(
            0.0,
            100.0
            - 15.0 * len(
                set(
                    invalid_fields
                )
            ),
        ),
        1,
    )
    snapshot.consistency_score = round(
        max(
            0.0,
            min(
                100.0,
                consistency_score,
            ),
        ),
        1,
    )
    quality_score = (
        0.50
        * snapshot.coverage_score
        + 0.25
        * snapshot.validity_score
        + 0.25
        * snapshot.consistency_score
    )
    snapshot.critical_missing_fields = []
    if snapshot.price is None:
        snapshot.critical_missing_fields.append(
            "price"
        )
    if snapshot.market_cap is None:
        snapshot.critical_missing_fields.append(
            "market_cap"
        )
    if "price" in snapshot.critical_missing_fields:
        quality_score = min(
            quality_score,
            30.0,
        )
    elif (
        "market_cap"
        in snapshot.critical_missing_fields
    ):
        quality_score = min(
            quality_score,
            55.0,
        )
    if snapshot.errors:
        quality_score = min(
            quality_score,
            20.0,
        )
    snapshot.data_quality = round(
        max(
            0.0,
            min(
                100.0,
                quality_score,
            ),
        ),
        1,
    )
    snapshot.provider_metadata[
        "invalid_fields"
    ] = sorted(
        set(
            invalid_fields
        )
    )
def _finalize_snapshot(
    snapshot: CompanySnapshot,
) -> None:
    invalid_fields = (
        _validate_value_ranges(
            snapshot
        )
    )
    consistency_score = (
        _validate_market_cap_consistency(
            snapshot
        )
    )
    _calculate_quality_scores(
        snapshot=snapshot,
        invalid_fields=invalid_fields,
        consistency_score=consistency_score,
    )
    if snapshot.capex is None:
        snapshot.add_warning(
            "El CAPEX no se obtiene de forma fiable en "
            "esta precarga y permanece sin evaluar."
        )
    if not snapshot.currency:
        snapshot.add_warning(
            "La moneda no ha podido validarse con Yahoo."
        )
    if snapshot.fundamentals_date is None:
        snapshot.add_warning(
            "Yahoo no proporcionó una fecha fiable para "
            "los fundamentales."
        )
class YahooProvider(
    MarketDataProvider
):
    """
    Proveedor gratuito para precarga y precribado.
    Los datos de Yahoo Finance son secundarios y no sustituyen
    los estados financieros ni las comunicaciones oficiales.
    """
    def get_snapshot(
        self,
        ticker: str,
    ) -> CompanySnapshot:
        normalized_ticker = (
            _normalize_ticker(
                ticker
            )
        )
        snapshot = CompanySnapshot(
            ticker=normalized_ticker,
            source=PROVIDER_SOURCE,
        )
        snapshot.fetched_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )
        snapshot.provider_metadata = {
            "provider": PROVIDER_NAME,
            "provider_role": "preload",
            "is_official_source": False,
        }
        try:
            yahoo_ticker = yf.Ticker(
                normalized_ticker
            )
        except Exception:
            logger.exception(
                "No se pudo crear el objeto Yahoo "
                "para %s.",
                normalized_ticker,
            )
            snapshot.errors = (
                "No se pudo inicializar el proveedor "
                "de datos."
            )
            _finalize_snapshot(
                snapshot
            )
            return snapshot
        fast_info = _load_fast_info(
            yahoo_ticker,
            snapshot,
        )
        info = _load_info(
            yahoo_ticker,
            snapshot,
        )
        if (
            not fast_info
            and not info
        ):
            snapshot.errors = (
                "Yahoo no devolvió información utilizable "
                "para el ticker solicitado."
            )
        try:
            _assign_identity_fields(
                snapshot,
                info,
            )
            _assign_market_fields(
                snapshot,
                fast_info,
                info,
            )
            _assign_fundamental_fields(
                snapshot,
                info,
            )
            _calculate_derived_fields(
                snapshot
            )
        except Exception:
            logger.exception(
                "Error inesperado al normalizar datos "
                "de Yahoo para %s.",
                normalized_ticker,
            )
            snapshot.errors = (
                "Se produjo un error al normalizar "
                "los datos recibidos."
            )
        _finalize_snapshot(
            snapshot
        )
        return snapshot
