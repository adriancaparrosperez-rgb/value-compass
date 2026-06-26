from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from src.decision.enums import DataQualityStatus
from src.decision.models import DataQualityAssessment
@dataclass
class DataQualityInput:
    ticker: str
    price: float | None = None
    price_date: str | date | datetime | None = None
    currency: str | None = None
    expected_currency: str | None = None
    market_cap: float | None = None
    diluted_shares: float | None = None
    fundamentals_date: str | date | datetime | None = None
    ticker_validated: bool = False
    fundamentals_validated: bool = False
    source_count: int = 0
    official_source_count: int = 0
    required_fields: dict[str, Any] | None = None
    maximum_price_age_days: int = 3
    maximum_fundamentals_age_days: int = 150
    market_cap_tolerance: float = 0.25
def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(maximum, float(value)),
    )
def _is_finite_number(
    value: Any,
) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric_value)
def _parse_datetime(
    value: str | date | datetime | None,
) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(
            value,
            datetime.min.time(),
        )
    elif isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        normalized = normalized.replace(
            "Z",
            "+00:00",
        )
        try:
            parsed = datetime.fromisoformat(
                normalized
            )
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )
    return parsed.astimezone(
        timezone.utc
    )
def _age_in_days(
    value: str | date | datetime | None,
    now: datetime,
) -> int | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    difference = now - parsed
    return max(
        0,
        difference.days,
    )
def _normalize_currency(
    currency: str | None,
) -> str | None:
    if currency is None:
        return None
    normalized = currency.strip().upper()
    return normalized or None
def _coverage_score(
    required_fields: dict[str, Any] | None,
) -> float:
    if not required_fields:
        return 0.0
    total = len(required_fields)
    available = sum(
        1
        for value in required_fields.values()
        if value is not None
        and value != ""
        and not (
            isinstance(value, float)
            and math.isnan(value)
        )
    )
    return _clamp(
        available / total * 100.0
    )
def _freshness_score(
    price_age_days: int | None,
    fundamentals_age_days: int | None,
    maximum_price_age_days: int,
    maximum_fundamentals_age_days: int,
) -> float:
    price_score = 0.0
    fundamentals_score = 0.0
    if price_age_days is not None:
        if price_age_days <= maximum_price_age_days:
            price_score = 100.0
        else:
            price_score = max(
                0.0,
                100.0
                - (
                    price_age_days
                    - maximum_price_age_days
                )
                * 12.5,
            )
    if fundamentals_age_days is not None:
        if (
            fundamentals_age_days
            <= maximum_fundamentals_age_days
        ):
            fundamentals_score = 100.0
        else:
            fundamentals_score = max(
                0.0,
                100.0
                - (
                    fundamentals_age_days
                    - maximum_fundamentals_age_days
                )
                * 0.75,
            )
    return _clamp(
        0.55 * price_score
        + 0.45 * fundamentals_score
    )
def _source_quality_score(
    source_count: int,
    official_source_count: int,
) -> float:
    if source_count <= 0:
        return 0.0
    source_score = min(
        60.0,
        float(source_count) * 20.0,
    )
    official_score = min(
        40.0,
        float(official_source_count) * 20.0,
    )
    return _clamp(
        source_score + official_score
    )
def assess_data_quality(
    data: DataQualityInput,
    now: datetime | None = None,
) -> DataQualityAssessment:
    current_time = now or datetime.now(
        timezone.utc
    )
    warnings: list[str] = []
    blocking_issues: list[str] = []
    price_validated = False
    currency_validated = False
    market_cap_validated = False
    price_age_days = _age_in_days(
        data.price_date,
        current_time,
    )
    fundamentals_age_days = _age_in_days(
        data.fundamentals_date,
        current_time,
    )
    # ---------------------------------------------------------
    # Precio
    # ---------------------------------------------------------
    if not _is_finite_number(data.price):
        blocking_issues.append(
            "PRICE_MISSING_OR_INVALID"
        )
        warnings.append(
            "El precio no está disponible o no es numéricamente válido."
        )
    elif float(data.price) <= 0:
        blocking_issues.append(
            "PRICE_NOT_POSITIVE"
        )
        warnings.append(
            "El precio debe ser superior a cero."
        )
    elif price_age_days is None:
        blocking_issues.append(
            "PRICE_DATE_MISSING"
        )
        warnings.append(
            "No se conoce la fecha de la cotización."
        )
    elif price_age_days > data.maximum_price_age_days:
        blocking_issues.append(
            "PRICE_STALE"
        )
        warnings.append(
            "La cotización está desactualizada."
        )
    else:
        price_validated = True
    # ---------------------------------------------------------
    # Moneda
    # ---------------------------------------------------------
    currency = _normalize_currency(
        data.currency
    )
    expected_currency = _normalize_currency(
        data.expected_currency
    )
    if currency is None:
        blocking_issues.append(
            "CURRENCY_MISSING"
        )
        warnings.append(
            "No se ha identificado la moneda de cotización."
        )
    elif (
        expected_currency is not None
        and currency != expected_currency
    ):
        blocking_issues.append(
            "CURRENCY_MISMATCH"
        )
        warnings.append(
            "La moneda obtenida no coincide con la esperada."
        )
    else:
        currency_validated = True
    # ---------------------------------------------------------
    # Capitalización
    # ---------------------------------------------------------
    if (
        _is_finite_number(data.price)
        and _is_finite_number(
            data.diluted_shares
        )
        and _is_finite_number(
            data.market_cap
        )
        and float(data.price) > 0
        and float(data.diluted_shares) > 0
        and float(data.market_cap) > 0
    ):
        implied_market_cap = (
            float(data.price)
            * float(data.diluted_shares)
        )
        market_cap_difference = abs(
            implied_market_cap
            - float(data.market_cap)
        ) / float(data.market_cap)
        if (
            market_cap_difference
            <= data.market_cap_tolerance
        ):
            market_cap_validated = True
        else:
            blocking_issues.append(
                "MARKET_CAP_INCONSISTENT"
            )
            warnings.append(
                "La capitalización no es coherente con "
                "el precio y las acciones diluidas."
            )
    else:
        warnings.append(
            "No hay datos suficientes para validar "
            "la capitalización."
        )
    # ---------------------------------------------------------
    # Fundamentales
    # ---------------------------------------------------------
    fundamentals_validated = bool(
        data.fundamentals_validated
    )
    if fundamentals_age_days is None:
        fundamentals_validated = False
        blocking_issues.append(
            "FUNDAMENTALS_DATE_MISSING"
        )
        warnings.append(
            "No se conoce la fecha de los fundamentales."
        )
    elif (
        fundamentals_age_days
        > data.maximum_fundamentals_age_days
    ):
        fundamentals_validated = False
        blocking_issues.append(
            "FUNDAMENTALS_STALE"
        )
        warnings.append(
            "Los fundamentales están demasiado desactualizados."
        )
    elif not data.fundamentals_validated:
        warnings.append(
            "Los fundamentales no han sido contrastados."
        )
    # ---------------------------------------------------------
    # Ticker y fuentes
    # ---------------------------------------------------------
    ticker_validated = bool(
        data.ticker_validated
    )
    if not ticker_validated:
        blocking_issues.append(
            "TICKER_NOT_VALIDATED"
        )
        warnings.append(
            "No se ha validado que el ticker corresponda "
            "a la empresa esperada."
        )
    if data.source_count <= 0:
        blocking_issues.append(
            "NO_SOURCES"
        )
        warnings.append(
            "No se han registrado fuentes para los datos."
        )
    elif data.source_count == 1:
        warnings.append(
            "Solo existe una fuente de datos."
        )
    if data.official_source_count <= 0:
        warnings.append(
            "No se ha registrado ninguna fuente oficial."
        )
    # ---------------------------------------------------------
    # Scores
    # ---------------------------------------------------------
    coverage_score = _coverage_score(
        data.required_fields
    )
    freshness_score = _freshness_score(
        price_age_days=price_age_days,
        fundamentals_age_days=(
            fundamentals_age_days
        ),
        maximum_price_age_days=(
            data.maximum_price_age_days
        ),
        maximum_fundamentals_age_days=(
            data.maximum_fundamentals_age_days
        ),
    )
    source_quality_score = _source_quality_score(
        source_count=max(
            0,
            data.source_count,
        ),
        official_source_count=max(
            0,
            data.official_source_count,
        ),
    )
    consistency_components = [
        price_validated,
        currency_validated,
        ticker_validated,
        market_cap_validated,
        fundamentals_validated,
    ]
    consistency_score = (
        sum(consistency_components)
        / len(consistency_components)
        * 100.0
    )
    overall_score = (
        0.25 * coverage_score
        + 0.25 * freshness_score
        + 0.25 * consistency_score
        + 0.25 * source_quality_score
    )
    critical_codes = {
        "PRICE_MISSING_OR_INVALID",
        "PRICE_NOT_POSITIVE",
        "PRICE_DATE_MISSING",
        "PRICE_STALE",
        "CURRENCY_MISSING",
        "CURRENCY_MISMATCH",
        "MARKET_CAP_INCONSISTENT",
        "TICKER_NOT_VALIDATED",
        "NO_SOURCES",
    }
    has_critical_issue = any(
        issue in critical_codes
        for issue in blocking_issues
    )
    if has_critical_issue:
        status = DataQualityStatus.UNRELIABLE
    elif (
        overall_score >= 80
        and price_validated
        and currency_validated
        and ticker_validated
        and fundamentals_validated
    ):
        status = DataQualityStatus.VALIDATED
    elif overall_score >= 55:
        status = (
            DataQualityStatus.PARTIALLY_VALIDATED
        )
    else:
        status = DataQualityStatus.INSUFFICIENT
    return DataQualityAssessment(
        status=status,
        coverage_score=round(
            coverage_score,
            1,
        ),
        freshness_score=round(
            freshness_score,
            1,
        ),
        consistency_score=round(
            consistency_score,
            1,
        ),
        source_quality_score=round(
            source_quality_score,
            1,
        ),
        price_validated=price_validated,
        currency_validated=currency_validated,
        ticker_validated=ticker_validated,
        market_cap_validated=market_cap_validated,
        fundamentals_validated=(
            fundamentals_validated
        ),
        price_date=(
            _parse_datetime(data.price_date)
            .date()
            .isoformat()
            if _parse_datetime(data.price_date)
            else None
        ),
        fundamentals_date=(
            _parse_datetime(
                data.fundamentals_date
            )
            .date()
            .isoformat()
            if _parse_datetime(
                data.fundamentals_date
            )
            else None
        ),
        source_count=max(
            0,
            int(data.source_count),
        ),
        official_source_count=max(
            0,
            int(data.official_source_count),
        ),
        warnings=warnings,
        blocking_issues=blocking_issues,
    )
