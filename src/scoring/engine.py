from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from src.models import CompanySnapshot, ScoreCard


SCORING_VERSION = "2.0.0"

RADAR_PRIORITY = "CANDIDATA PRIORITARIA"
RADAR_CANDIDATE = "CANDIDATA"
RADAR_WATCH = "VIGILAR"
RADAR_DISCARD = "DESCARTAR EN PRECRIBADO"
RADAR_UNRELIABLE = "DATOS NO FIABLES"

DIMENSION_NAMES = (
    "valuation",
    "quality",
    "cash",
    "balance",
    "growth",
    "capital_allocation",
    "momentum_fundamental",
    "risk",
)

DEFAULT_THRESHOLDS = {
    "priority": 80.0,
    "candidate": 70.0,
    "watch": 58.0,
}

DEFAULT_MIN_CONFIDENCE = 55.0
DEFAULT_MIN_COVERAGE = 50.0


def _number(
    value: Any,
) -> float | None:
    """
    Convierte un valor a float finito.

    Los booleanos, NaN, infinitos y valores no numéricos
    se consideran ausentes.
    """
    if value is None or isinstance(value, bool):
        return None

    try:
        numeric_value = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if not math.isfinite(
        numeric_value
    ):
        return None

    return numeric_value


def _bounded_score(
    value: Any,
    default: float = 0.0,
) -> float:
    numeric_value = _number(
        value
    )

    if numeric_value is None:
        return default

    return max(
        0.0,
        min(
            100.0,
            numeric_value,
        ),
    )


def _linear_score(
    value: Any,
    low: float,
    high: float,
    *,
    reverse: bool = False,
) -> float | None:
    """
    Transforma una métrica disponible en una puntuación 0–100.

    Un dato ausente devuelve None, no una puntuación neutral.
    Esto permite medir correctamente la cobertura.
    """
    numeric_value = _number(
        value
    )

    if numeric_value is None:
        return None

    if (
        not math.isfinite(
            low
        )
        or not math.isfinite(
            high
        )
    ):
        return None

    if high <= low:
        return None

    score = (
        (numeric_value - low)
        / (high - low)
        * 100.0
    )

    bounded = max(
        0.0,
        min(
            100.0,
            score,
        ),
    )

    if reverse:
        return 100.0 - bounded

    return bounded


def _safe_ratio(
    numerator: Any,
    denominator: Any,
    *,
    denominator_must_be_positive: bool = False,
) -> float | None:
    normalized_numerator = _number(
        numerator
    )
    normalized_denominator = _number(
        denominator
    )

    if (
        normalized_numerator is None
        or normalized_denominator is None
    ):
        return None

    if normalized_denominator == 0:
        return None

    if (
        denominator_must_be_positive
        and normalized_denominator <= 0
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


def _normalize_debt_to_equity(
    value: Any,
) -> tuple[
    float | None,
    str | None,
]:
    """
    Normaliza debt-to-equity con prudencia.

    Yahoo suele expresarlo como porcentaje, pero no siempre es
    posible distinguir entre porcentaje y ratio en valores altos.
    """
    numeric_value = _number(
        value
    )

    if numeric_value is None:
        return (
            None,
            None,
        )

    if numeric_value < 0:
        return (
            None,
            (
                "El debt-to-equity es negativo y requiere "
                "revisión del patrimonio."
            ),
        )

    if numeric_value > 10:
        normalized_value = (
            numeric_value
            / 100.0
        )

        warning = (
            "El debt-to-equity se ha interpretado como "
            "porcentaje de Yahoo y se ha dividido entre 100."
        )

        return (
            normalized_value,
            warning,
        )

    return (
        numeric_value,
        None,
    )


def _dimension_result(
    metrics: Mapping[
        str,
        float | None,
    ],
) -> tuple[
    float,
    float,
    list[str],
]:
    """
    Calcula puntuación y cobertura de una dimensión.

    La puntuación se obtiene únicamente con métricas disponibles.
    La cobertura expresa qué proporción de métricas estaba presente.
    """
    if not metrics:
        return (
            50.0,
            0.0,
            [],
        )

    available_scores = [
        score
        for score in metrics.values()
        if score is not None
    ]

    missing_metrics = [
        metric_name
        for metric_name, score
        in metrics.items()
        if score is None
    ]

    coverage = (
        100.0
        * len(
            available_scores
        )
        / len(
            metrics
        )
    )

    if not available_scores:
        return (
            50.0,
            round(
                coverage,
                1,
            ),
            missing_metrics,
        )

    score = (
        sum(
            available_scores
        )
        / len(
            available_scores
        )
    )

    return (
        round(
            _bounded_score(
                score,
                default=50.0,
            ),
            1,
        ),
        round(
            coverage,
            1,
        ),
        missing_metrics,
    )


def _normalize_weights(
    weights: Mapping[
        str,
        Any,
    ],
) -> tuple[
    dict[str, float],
    list[str],
]:
    """
    Valida y normaliza los pesos disponibles.

    Los pesos ausentes, negativos o no numéricos se convierten
    en cero. Los pesos válidos se normalizan para sumar 1.
    """
    warnings: list[str] = []
    raw_weights: dict[
        str,
        float,
    ] = {}

    for dimension in DIMENSION_NAMES:
        raw_value = _number(
            weights.get(
                dimension
            )
        )

        if raw_value is None:
            raw_weights[
                dimension
            ] = 0.0

            warnings.append(
                "No se proporcionó un peso válido para "
                f"{dimension}."
            )

            continue

        if raw_value < 0:
            raw_weights[
                dimension
            ] = 0.0

            warnings.append(
                f"El peso de {dimension} era negativo "
                "y se ha descartado."
            )

            continue

        raw_weights[
            dimension
        ] = raw_value

    total_weight = sum(
        raw_weights.values()
    )

    if total_weight <= 0:
        equal_weight = (
            1.0
            / len(
                DIMENSION_NAMES
            )
        )

        warnings.append(
            "No había pesos válidos; se aplicó una "
            "ponderación uniforme."
        )

        return (
            {
                dimension: equal_weight
                for dimension
                in DIMENSION_NAMES
            },
            warnings,
        )

    normalized_weights = {
        dimension: (
            weight
            / total_weight
        )
        for dimension, weight
        in raw_weights.items()
    }

    return (
        normalized_weights,
        warnings,
    )


def _threshold(
    thresholds: Mapping[
        str,
        Any,
    ],
    new_key: str,
    legacy_key: str | None,
    default: float,
) -> float:
    value = _number(
        thresholds.get(
            new_key
        )
    )

    if (
        value is None
        and legacy_key is not None
    ):
        value = _number(
            thresholds.get(
                legacy_key
            )
        )

    if value is None:
        value = default

    return _bounded_score(
        value,
        default=default,
    )


def _normalize_thresholds(
    thresholds: Mapping[
        str,
        Any,
    ],
) -> tuple[
    dict[str, float],
    list[str],
]:
    warnings: list[str] = []

    normalized = {
        "priority": _threshold(
            thresholds,
            "priority",
            "strong_entry",
            DEFAULT_THRESHOLDS[
                "priority"
            ],
        ),
        "candidate": _threshold(
            thresholds,
            "candidate",
            "entry",
            DEFAULT_THRESHOLDS[
                "candidate"
            ],
        ),
        "watch": _threshold(
            thresholds,
            "watch",
            None,
            DEFAULT_THRESHOLDS[
                "watch"
            ],
        ),
    }

    if not (
        normalized[
            "priority"
        ]
        >= normalized[
            "candidate"
        ]
        >= normalized[
            "watch"
        ]
    ):
        warnings.append(
            "Los umbrales no estaban ordenados y se "
            "han sustituido por los valores por defecto."
        )

        normalized = dict(
            DEFAULT_THRESHOLDS
        )

    return (
        normalized,
        warnings,
    )


def _overall_coverage(
    dimension_coverage: Mapping[
        str,
        float,
    ],
    normalized_weights: Mapping[
        str,
        float,
    ],
) -> float:
    coverage = sum(
        _bounded_score(
            dimension_coverage.get(
                dimension,
                0.0,
            )
        )
        * normalized_weights.get(
            dimension,
            0.0,
        )
        for dimension
        in DIMENSION_NAMES
    )

    return round(
        _bounded_score(
            coverage
        ),
        1,
    )


def _effective_confidence(
    snapshot: CompanySnapshot,
    overall_coverage: float,
) -> float:
    """
    Combina calidad del proveedor y cobertura del scoring.

    La confianza nunca puede superar de forma artificial la
    información realmente disponible.
    """
    provider_quality = _bounded_score(
        snapshot.data_quality
    )

    confidence = (
        0.65
        * provider_quality
        + 0.35
        * overall_coverage
    )

    if snapshot.errors:
        confidence = min(
            confidence,
            20.0,
        )

    if snapshot.critical_missing_fields:
        confidence = min(
            confidence,
            45.0,
        )

    return round(
        _bounded_score(
            confidence
        ),
        1,
    )


def _radar_recommendation(
    *,
    global_score: float,
    valuation: float,
    balance: float,
    confidence: float,
    overall_coverage: float,
    thresholds: Mapping[
        str,
        float,
    ],
    min_confidence: float,
    min_coverage: float,
    snapshot: CompanySnapshot,
) -> str:
    """
    Clasifica una empresa para priorizar análisis posterior.

    No formula una recomendación definitiva de inversión.
    """
    if (
        snapshot.errors
        or confidence
        < min_confidence
        or overall_coverage
        < min_coverage
        or snapshot.price is None
    ):
        return RADAR_UNRELIABLE

    if (
        global_score
        >= thresholds[
            "priority"
        ]
        and valuation >= 70.0
        and balance >= 50.0
    ):
        return RADAR_PRIORITY

    if (
        global_score
        >= thresholds[
            "candidate"
        ]
        and valuation >= 55.0
    ):
        return RADAR_CANDIDATE

    if (
        global_score
        >= thresholds[
            "watch"
        ]
    ):
        return RADAR_WATCH

    return RADAR_DISCARD


def _dimension_label(
    dimension: str,
) -> str:
    labels = {
        "valuation": "valoración",
        "quality": "calidad",
        "cash": "caja",
        "balance": "balance",
        "growth": "crecimiento",
        "capital_allocation": (
            "asignación de capital"
        ),
        "momentum_fundamental": (
            "momentum fundamental"
        ),
        "risk": "riesgo",
    }

    return labels.get(
        dimension,
        dimension,
    )


def _build_rationale(
    parts: Mapping[
        str,
        float,
    ],
    dimension_coverage: Mapping[
        str,
        float,
    ],
    recommendation: str,
) -> str:
    ordered_parts = sorted(
        parts.items(),
        key=lambda item: item[
            1
        ],
        reverse=True,
    )

    strongest = ordered_parts[
        :2
    ]

    weakest = ordered_parts[
        -2:
    ]

    strengths_text = ", ".join(
        (
            f"{_dimension_label(name)} "
            f"{score:.0f}"
        )
        for name, score
        in strongest
    )

    weaknesses_text = ", ".join(
        (
            f"{_dimension_label(name)} "
            f"{score:.0f}"
        )
        for name, score
        in weakest
    )

    low_coverage_dimensions = [
        _dimension_label(
            dimension
        )
        for dimension, coverage
        in dimension_coverage.items()
        if coverage < 50.0
    ]

    rationale = (
        f"Clasificación de radar: {recommendation}. "
        f"Fortalezas relativas: {strengths_text}. "
        f"Áreas más débiles: {weaknesses_text}."
    )

    if low_coverage_dimensions:
        rationale += (
            " Cobertura limitada en: "
            + ", ".join(
                low_coverage_dimensions
            )
            + "."
        )

    return rationale


def _deduplicate_strings(
    values: Sequence[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = (
            value.strip()
            if isinstance(
                value,
                str,
            )
            else ""
        )

        if not normalized:
            continue

        comparison_key = (
            normalized.casefold()
        )

        if comparison_key in seen:
            continue

        seen.add(
            comparison_key
        )

        result.append(
            normalized
        )

    return result


def score_snapshot(
    snapshot: CompanySnapshot,
    weights: Mapping[
        str,
        Any,
    ],
    thresholds: Mapping[
        str,
        Any,
    ],
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> ScoreCard:
    """
    Ejecuta el precribado cuantitativo de una compañía.

    El resultado sirve para priorizar análisis. No sustituye
    el análisis maestro ni una recomendación final de inversión.
    """
    if not isinstance(
        snapshot,
        CompanySnapshot,
    ):
        raise TypeError(
            "snapshot debe ser una instancia "
            "de CompanySnapshot."
        )

    if not isinstance(
        weights,
        Mapping,
    ):
        raise TypeError(
            "weights debe ser un diccionario."
        )

    if not isinstance(
        thresholds,
        Mapping,
    ):
        raise TypeError(
            "thresholds debe ser un diccionario."
        )

    normalized_min_confidence = (
        _bounded_score(
            min_confidence,
            default=(
                DEFAULT_MIN_CONFIDENCE
            ),
        )
    )

    normalized_min_coverage = (
        _bounded_score(
            min_coverage,
            default=(
                DEFAULT_MIN_COVERAGE
            ),
        )
    )

    (
        normalized_weights,
        weight_warnings,
    ) = _normalize_weights(
        weights
    )

    (
        normalized_thresholds,
        threshold_warnings,
    ) = _normalize_thresholds(
        thresholds
    )

    (
        debt_to_equity,
        debt_warning,
    ) = _normalize_debt_to_equity(
        snapshot.debt_to_equity
    )

    fcf_conversion = _safe_ratio(
        snapshot.free_cash_flow,
        snapshot.net_income,
    )

    net_cash = (
        snapshot.total_cash
        - snapshot.total_debt
        if (
            snapshot.total_cash
            is not None
            and snapshot.total_debt
            is not None
        )
        else None
    )

    net_cash_to_market_cap = _safe_ratio(
        net_cash,
        snapshot.market_cap,
        denominator_must_be_positive=True,
    )

    analyst_upside = _safe_ratio(
        (
            snapshot.analyst_target
            - snapshot.price
        )
        if (
            snapshot.analyst_target
            is not None
            and snapshot.price
            is not None
        )
        else None,
        snapshot.price,
        denominator_must_be_positive=True,
    )

    dimension_metrics: dict[
        str,
        dict[
            str,
            float | None,
        ],
    ] = {
        "valuation": {
            "fcf_yield": _linear_score(
                snapshot.fcf_yield,
                0.01,
                0.10,
            ),
            "earnings_yield": _linear_score(
                snapshot.earnings_yield,
                0.02,
                0.10,
            ),
            "forward_pe": _linear_score(
                snapshot.forward_pe,
                8.0,
                30.0,
                reverse=True,
            ),
            "ev_to_ebitda": _linear_score(
                snapshot.ev_to_ebitda,
                5.0,
                20.0,
                reverse=True,
            ),
        },
        "quality": {
            "roe": _linear_score(
                snapshot.roe,
                0.05,
                0.30,
            ),
            "roa": _linear_score(
                snapshot.roa,
                0.02,
                0.15,
            ),
            "operating_margin": _linear_score(
                snapshot.operating_margin,
                0.05,
                0.30,
            ),
            "net_margin": _linear_score(
                snapshot.net_margin,
                0.02,
                0.20,
            ),
        },
        "cash": {
            "fcf_yield": _linear_score(
                snapshot.fcf_yield,
                0.0,
                0.10,
            ),
            "fcf_conversion": _linear_score(
                fcf_conversion,
                0.5,
                1.5,
            ),
        },
        "balance": {
            "debt_to_equity": _linear_score(
                debt_to_equity,
                0.2,
                2.5,
                reverse=True,
            ),
            "current_ratio": _linear_score(
                snapshot.current_ratio,
                0.7,
                2.0,
            ),
            "net_cash_to_market_cap": (
                _linear_score(
                    net_cash_to_market_cap,
                    -0.6,
                    0.2,
                )
            ),
        },
        "growth": {
            "revenue_growth": _linear_score(
                snapshot.revenue_growth,
                -0.05,
                0.20,
            ),
            "earnings_growth": _linear_score(
                snapshot.earnings_growth,
                -0.10,
                0.25,
            ),
        },
        "capital_allocation": {
            "dividend_yield": _linear_score(
                snapshot.dividend_yield,
                0.0,
                0.06,
            ),
            "roe_proxy": _linear_score(
                snapshot.roe,
                0.05,
                0.30,
            ),
        },
        "momentum_fundamental": {
            "earnings_growth": _linear_score(
                snapshot.earnings_growth,
                -0.15,
                0.25,
            ),
            "analyst_upside": _linear_score(
                analyst_upside,
                -0.15,
                0.30,
            ),
        },
        "risk": {
            "debt_to_equity": _linear_score(
                debt_to_equity,
                0.2,
                3.0,
                reverse=True,
            ),
            "balance_liquidity": _linear_score(
                snapshot.current_ratio,
                0.7,
                2.0,
            ),
            "provider_quality": _linear_score(
                snapshot.data_quality,
                0.0,
                100.0,
            ),
        },
    }

    parts: dict[
        str,
        float,
    ] = {}

    dimension_coverage: dict[
        str,
        float,
    ] = {}

    missing_metrics: list[str] = []

    for (
        dimension,
        metrics,
    ) in dimension_metrics.items():
        (
            dimension_score,
            coverage,
            missing,
        ) = _dimension_result(
            metrics
        )

        parts[
            dimension
        ] = dimension_score

        dimension_coverage[
            dimension
        ] = coverage

        missing_metrics.extend(
            f"{dimension}.{metric}"
            for metric
            in missing
        )

    overall_coverage = _overall_coverage(
        dimension_coverage,
        normalized_weights,
    )

    global_score = sum(
        parts[
            dimension
        ]
        * normalized_weights[
            dimension
        ]
        for dimension
        in DIMENSION_NAMES
    )

    global_score = round(
        _bounded_score(
            global_score
        ),
        1,
    )

    confidence = _effective_confidence(
        snapshot,
        overall_coverage,
    )

    recommendation = _radar_recommendation(
        global_score=global_score,
        valuation=parts[
            "valuation"
        ],
        balance=parts[
            "balance"
        ],
        confidence=confidence,
        overall_coverage=overall_coverage,
        thresholds=normalized_thresholds,
        min_confidence=(
            normalized_min_confidence
        ),
        min_coverage=(
            normalized_min_coverage
        ),
        snapshot=snapshot,
    )

    warnings: list[str] = []

    warnings.extend(
        snapshot.warnings
    )

    warnings.extend(
        weight_warnings
    )

    warnings.extend(
        threshold_warnings
    )

    if debt_warning:
        warnings.append(
            debt_warning
        )

    if overall_coverage < 70.0:
        warnings.append(
            "La cobertura del scoring es parcial; "
            "la clasificación debe interpretarse "
            "con prudencia."
        )

    if (
        recommendation
        == RADAR_UNRELIABLE
    ):
        warnings.append(
            "El resultado no debe utilizarse para "
            "priorizar una inversión hasta validar "
            "los datos."
        )

    if (
        dimension_coverage.get(
            "capital_allocation",
            0.0,
        )
        > 0.0
    ):
        warnings.append(
            "La asignación de capital es una aproximación "
            "preliminar basada en dividendos y ROE."
        )

    if analyst_upside is not None:
        warnings.append(
            "El precio objetivo de analistas solo se utiliza "
            "como señal secundaria de precribado."
        )

    rationale = _build_rationale(
        parts=parts,
        dimension_coverage=(
            dimension_coverage
        ),
        recommendation=(
            recommendation
        ),
    )

    return ScoreCard(
        ticker=snapshot.ticker,
        valuation=parts[
            "valuation"
        ],
        quality=parts[
            "quality"
        ],
        cash=parts[
            "cash"
        ],
        balance=parts[
            "balance"
        ],
        growth=parts[
            "growth"
        ],
        capital_allocation=parts[
            "capital_allocation"
        ],
        momentum_fundamental=parts[
            "momentum_fundamental"
        ],
        risk=parts[
            "risk"
        ],
        confidence=confidence,
        global_score=global_score,
        recommendation=(
            recommendation
        ),
        rationale=rationale,
        calculated_at=datetime.now(
            timezone.utc
        ).isoformat(),
        overall_coverage=(
            overall_coverage
        ),
        dimension_coverage=(
            dimension_coverage
        ),
        missing_metrics=sorted(
            set(
                missing_metrics
            )
        ),
        warnings=_deduplicate_strings(
            warnings
        ),
        scoring_version=(
            SCORING_VERSION
        ),
    )
