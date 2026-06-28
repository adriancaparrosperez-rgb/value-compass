from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, TypeAlias

from src.models import CompanySnapshot, ScoreCard


SCORING_VERSION = "2.2.0"

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

MIN_ANALYST_COUNT = 3
MIN_GATE_DIMENSION_COVERAGE = 50.0

MetricSpec: TypeAlias = tuple[
    float | None,
    float,
]

MetricValue: TypeAlias = (
    float
    | None
    | MetricSpec
)


def _number(
    value: Any,
) -> float | None:
    """
    Convierte un valor en un float finito.

    None, booleanos, NaN, infinitos y valores no numéricos
    se consideran datos ausentes.
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

    if not math.isfinite(numeric_value):
        return None

    return numeric_value


def _bounded_score(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Limita una puntuación al intervalo 0–100.
    """
    numeric_value = _number(value)

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
    require_positive: bool = False,
) -> float | None:
    """
    Convierte una métrica en una puntuación lineal 0–100.

    Un valor ausente devuelve None. Cuando reverse=True, un
    valor inferior obtiene una puntuación superior.
    """
    numeric_value = _number(value)

    if numeric_value is None:
        return None

    if (
        require_positive
        and numeric_value <= 0
    ):
        return None

    if (
        not math.isfinite(low)
        or not math.isfinite(high)
        or high <= low
    ):
        return None

    raw_score = (
        (numeric_value - low)
        / (high - low)
        * 100.0
    )

    bounded_score = max(
        0.0,
        min(
            100.0,
            raw_score,
        ),
    )

    if reverse:
        return 100.0 - bounded_score

    return bounded_score


def _safe_ratio(
    numerator: Any,
    denominator: Any,
    *,
    numerator_must_be_positive: bool = False,
    denominator_must_be_positive: bool = False,
) -> float | None:
    """
    Calcula una ratio únicamente con valores finitos.

    No interpreta datos ausentes como cero.
    """
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
        numerator_must_be_positive
        and normalized_numerator <= 0
    ):
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

    if not math.isfinite(result):
        return None

    return result


def _safe_difference(
    minuend: Any,
    subtrahend: Any,
) -> float | None:
    """
    Calcula una diferencia solo cuando existen ambos valores.
    """
    normalized_minuend = _number(
        minuend
    )
    normalized_subtrahend = _number(
        subtrahend
    )

    if (
        normalized_minuend is None
        or normalized_subtrahend is None
    ):
        return None

    result = (
        normalized_minuend
        - normalized_subtrahend
    )

    if not math.isfinite(result):
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

    Yahoo suele expresar esta ratio como porcentaje. El ajuste
    heurístico genera una advertencia para dejar trazabilidad.
    """
    numeric_value = _number(value)

    if numeric_value is None:
        return (
            None,
            None,
        )

    if numeric_value < 0:
        return (
            None,
            (
                "El debt-to-equity es negativo y no se ha "
                "puntuado porque puede reflejar patrimonio "
                "neto negativo."
            ),
        )

    if numeric_value > 10:
        return (
            numeric_value / 100.0,
            (
                "El debt-to-equity se ha interpretado como "
                "porcentaje de Yahoo y se ha dividido entre 100."
            ),
        )

    return (
        numeric_value,
        None,
    )


def _analyst_upside(
    snapshot: CompanySnapshot,
) -> tuple[
    float | None,
    str | None,
]:
    """
    Calcula el potencial frente al precio objetivo.

    La señal se utiliza únicamente cuando existen al menos tres
    analistas, para evitar depender de una estimación aislada.
    """
    target = _number(
        snapshot.analyst_target
    )
    price = _number(
        snapshot.price
    )
    analyst_count = _number(
        snapshot.analyst_count
    )

    if target is None or price is None:
        return (
            None,
            None,
        )

    if (
        analyst_count is None
        or analyst_count < MIN_ANALYST_COUNT
    ):
        return (
            None,
            (
                "El precio objetivo no se ha puntuado porque "
                f"requiere al menos {MIN_ANALYST_COUNT} analistas."
            ),
        )

    upside = _safe_ratio(
        target - price,
        price,
        denominator_must_be_positive=True,
    )

    return (
        upside,
        None,
    )


def _dimension_result(
    metrics: Mapping[
        str,
        MetricValue,
    ],
) -> tuple[
    float,
    float,
    list[str],
]:
    """
    Calcula puntuación y cobertura de una dimensión.

    Admite el contrato histórico:

        {"metric_a": 80.0, "metric_b": None}

    y el contrato ponderado:

        {"metric_a": (80.0, 0.70), "metric_b": (None, 0.30)}

    Las métricas ausentes no reciben una puntuación neutral.
    """
    if not metrics:
        return (
            50.0,
            0.0,
            [],
        )

    normalized_metrics: dict[
        str,
        MetricSpec,
    ] = {}

    for (
        metric_name,
        metric_value,
    ) in metrics.items():
        if (
            isinstance(
                metric_value,
                tuple,
            )
            and len(metric_value) == 2
        ):
            raw_score = metric_value[0]
            raw_weight = _number(
                metric_value[1]
            )

            metric_weight = (
                raw_weight
                if (
                    raw_weight is not None
                    and raw_weight > 0
                )
                else 0.0
            )

            normalized_metrics[
                metric_name
            ] = (
                raw_score,
                metric_weight,
            )
        else:
            normalized_metrics[
                metric_name
            ] = (
                metric_value,
                1.0,
            )

    valid_metrics = {
        metric_name: (
            score,
            metric_weight,
        )
        for metric_name, (
            score,
            metric_weight,
        ) in normalized_metrics.items()
        if metric_weight > 0
    }

    if not valid_metrics:
        return (
            50.0,
            0.0,
            [],
        )

    total_weight = sum(
        metric_weight
        for _, metric_weight
        in valid_metrics.values()
    )

    available_metrics = {
        metric_name: (
            score,
            metric_weight,
        )
        for metric_name, (
            score,
            metric_weight,
        ) in valid_metrics.items()
        if score is not None
    }

    missing_metrics = [
        metric_name
        for metric_name, (
            score,
            _,
        ) in valid_metrics.items()
        if score is None
    ]

    available_weight = sum(
        metric_weight
        for _, metric_weight
        in available_metrics.values()
    )

    coverage = (
        100.0
        * available_weight
        / total_weight
        if total_weight > 0
        else 0.0
    )

    if not available_metrics:
        return (
            50.0,
            round(
                coverage,
                1,
            ),
            missing_metrics,
        )

    weighted_score = sum(
        score * metric_weight
        for score, metric_weight
        in available_metrics.values()
        if score is not None
    )

    dimension_score = (
        weighted_score
        / available_weight
    )

    return (
        round(
            _bounded_score(
                dimension_score,
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
    Valida y normaliza los pesos de las dimensiones.
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
            / len(DIMENSION_NAMES)
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
        normalized["priority"]
        >= normalized["candidate"]
        >= normalized["watch"]
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
    """
    Calcula la proporción ponderada del modelo evaluada.
    """
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


def _observed_global_score(
    parts: Mapping[
        str,
        float,
    ],
    dimension_coverage: Mapping[
        str,
        float,
    ],
    normalized_weights: Mapping[
        str,
        float,
    ],
) -> float:
    """
    Calcula el score con las dimensiones realmente observadas.

    Las dimensiones sin datos no aportan 50 puntos artificiales.
    Sus pesos se excluyen y los restantes se renormalizan.
    """
    observed_dimensions = [
        dimension
        for dimension
        in DIMENSION_NAMES
        if (
            dimension_coverage.get(
                dimension,
                0.0,
            )
            > 0.0
            and normalized_weights.get(
                dimension,
                0.0,
            )
            > 0.0
        )
    ]

    if not observed_dimensions:
        return 0.0

    observed_weight = sum(
        normalized_weights[
            dimension
        ]
        for dimension
        in observed_dimensions
    )

    if observed_weight <= 0:
        return 0.0

    score = sum(
        parts[dimension]
        * (
            normalized_weights[
                dimension
            ]
            / observed_weight
        )
        for dimension
        in observed_dimensions
    )

    return round(
        _bounded_score(
            score
        ),
        1,
    )


def _effective_confidence(
    snapshot: CompanySnapshot,
    overall_coverage: float,
) -> float:
    """
    Combina calidad principal del proveedor y cobertura.

    La calidad de datos no forma parte del riesgo empresarial;
    afecta exclusivamente a la confianza del resultado.
    """
    provider_quality = _bounded_score(
        snapshot.data_quality
    )

    confidence = (
        0.65
        * provider_quality
        + 0.35
        * _bounded_score(
            overall_coverage
        )
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
    dimension_coverage: Mapping[
        str,
        float,
    ]
    | None = None,
) -> str:
    """
    Clasifica una empresa para priorizar análisis posterior.

    dimension_coverage es opcional para mantener compatibilidad
    con llamadas anteriores a esta función auxiliar.
    """
    if (
        snapshot.errors
        or snapshot.critical_missing_fields
        or snapshot.price is None
        or confidence < min_confidence
        or overall_coverage < min_coverage
    ):
        return RADAR_UNRELIABLE

    effective_dimension_coverage = (
        dimension_coverage
        if dimension_coverage is not None
        else {
            "valuation": 100.0,
            "balance": 100.0,
        }
    )

    valuation_coverage = (
        effective_dimension_coverage.get(
            "valuation",
            0.0,
        )
    )

    balance_coverage = (
        effective_dimension_coverage.get(
            "balance",
            0.0,
        )
    )

    if (
        global_score
        >= thresholds["priority"]
        and valuation_coverage
        >= MIN_GATE_DIMENSION_COVERAGE
        and valuation >= 70.0
        and balance_coverage
        >= MIN_GATE_DIMENSION_COVERAGE
        and balance >= 50.0
    ):
        return RADAR_PRIORITY

    if (
        global_score
        >= thresholds["candidate"]
        and valuation_coverage
        >= MIN_GATE_DIMENSION_COVERAGE
        and valuation >= 55.0
    ):
        return RADAR_CANDIDATE

    if global_score >= thresholds["watch"]:
        return RADAR_WATCH

    return RADAR_DISCARD


def _dimension_label(
    dimension: str,
) -> str:
    labels = {
        "valuation": "valoración",
        "quality": "rentabilidad y calidad",
        "cash": "generación de caja",
        "balance": "solidez del balance",
        "growth": "crecimiento",
        "capital_allocation": (
            "asignación de capital"
        ),
        "momentum_fundamental": (
            "momentum fundamental"
        ),
        "risk": (
            "resiliencia financiera"
        ),
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
    """
    Construye la explicación usando solo dimensiones evaluadas.
    """
    observed_parts = {
        dimension: parts[
            dimension
        ]
        for dimension
        in DIMENSION_NAMES
        if dimension_coverage.get(
            dimension,
            0.0,
        )
        > 0.0
    }

    rationale = (
        f"Clasificación de radar: {recommendation}."
    )

    if not observed_parts:
        return (
            rationale
            + " No existen dimensiones evaluadas con datos "
            "suficientes para identificar fortalezas o riesgos."
        )

    ordered_parts = sorted(
        observed_parts.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    strongest = ordered_parts[:2]

    strengths_text = ", ".join(
        (
            f"{_dimension_label(name)} "
            f"{score:.0f}"
        )
        for name, score
        in strongest
    )

    rationale += (
        " Fortalezas relativas: "
        f"{strengths_text}."
    )

    if len(ordered_parts) > 2:
        weakest = ordered_parts[-2:]

        weaknesses_text = ", ".join(
            (
                f"{_dimension_label(name)} "
                f"{score:.0f}"
            )
            for name, score
            in weakest
        )

        rationale += (
            " Áreas más débiles: "
            f"{weaknesses_text}."
        )

    low_coverage_dimensions = [
        _dimension_label(
            dimension
        )
        for dimension, coverage
        in dimension_coverage.items()
        if coverage < 50.0
    ]

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

    El resultado permite priorizar qué empresas merecen un
    análisis maestro completo. No constituye por sí solo una
    recomendación definitiva de inversión.
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
            default=DEFAULT_MIN_CONFIDENCE,
        )
    )

    normalized_min_coverage = (
        _bounded_score(
            min_coverage,
            default=DEFAULT_MIN_COVERAGE,
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

    free_cash_flow = _number(
        snapshot.free_cash_flow
    )

    fcf_conversion = (
        _safe_ratio(
            free_cash_flow,
            snapshot.net_income,
            denominator_must_be_positive=True,
        )
        if (
            free_cash_flow is not None
            and free_cash_flow >= 0
        )
        else None
    )

    operating_cash_conversion = _safe_ratio(
        snapshot.operating_cash_flow,
        snapshot.net_income,
        numerator_must_be_positive=True,
        denominator_must_be_positive=True,
    )

    net_cash = _safe_difference(
        snapshot.total_cash,
        snapshot.total_debt,
    )

    net_cash_to_market_cap = _safe_ratio(
        net_cash,
        snapshot.market_cap,
        denominator_must_be_positive=True,
    )

    (
        analyst_upside,
        analyst_warning,
    ) = _analyst_upside(
        snapshot
    )

    dimension_metrics: dict[
        str,
        dict[
            str,
            MetricSpec,
        ],
    ] = {
        "valuation": {
            "fcf_yield": (
                _linear_score(
                    snapshot.fcf_yield,
                    0.01,
                    0.10,
                ),
                0.30,
            ),
            "earnings_yield": (
                _linear_score(
                    snapshot.earnings_yield,
                    0.02,
                    0.10,
                ),
                0.25,
            ),
            "forward_pe": (
                _linear_score(
                    snapshot.forward_pe,
                    8.0,
                    30.0,
                    reverse=True,
                    require_positive=True,
                ),
                0.25,
            ),
            "ev_to_ebitda": (
                _linear_score(
                    snapshot.ev_to_ebitda,
                    5.0,
                    20.0,
                    reverse=True,
                    require_positive=True,
                ),
                0.20,
            ),
        },
        "quality": {
            "operating_margin": (
                _linear_score(
                    snapshot.operating_margin,
                    0.05,
                    0.30,
                ),
                0.30,
            ),
            "net_margin": (
                _linear_score(
                    snapshot.net_margin,
                    0.02,
                    0.20,
                ),
                0.25,
            ),
            "roa": (
                _linear_score(
                    snapshot.roa,
                    0.02,
                    0.15,
                ),
                0.25,
            ),
            "roe": (
                _linear_score(
                    snapshot.roe,
                    0.05,
                    0.30,
                ),
                0.20,
            ),
        },
        "cash": {
            "fcf_yield": (
                _linear_score(
                    snapshot.fcf_yield,
                    0.0,
                    0.10,
                ),
                0.35,
            ),
            "fcf_conversion": (
                _linear_score(
                    fcf_conversion,
                    0.50,
                    1.30,
                ),
                0.40,
            ),
            "operating_cash_conversion": (
                _linear_score(
                    operating_cash_conversion,
                    0.70,
                    1.50,
                ),
                0.25,
            ),
        },
        "balance": {
            "debt_to_equity": (
                _linear_score(
                    debt_to_equity,
                    0.20,
                    2.50,
                    reverse=True,
                ),
                0.40,
            ),
            "current_ratio": (
                _linear_score(
                    snapshot.current_ratio,
                    0.70,
                    2.00,
                ),
                0.30,
            ),
            "net_cash_to_market_cap": (
                _linear_score(
                    net_cash_to_market_cap,
                    -0.60,
                    0.20,
                ),
                0.30,
            ),
        },
        "growth": {
            "revenue_growth": (
                _linear_score(
                    snapshot.revenue_growth,
                    -0.05,
                    0.20,
                ),
                0.50,
            ),
            "earnings_growth": (
                _linear_score(
                    snapshot.earnings_growth,
                    -0.10,
                    0.25,
                ),
                0.50,
            ),
        },
        "capital_allocation": {
            "dividend_yield": (
                _linear_score(
                    snapshot.dividend_yield,
                    0.0,
                    0.06,
                ),
                0.50,
            ),
            "roe_proxy": (
                _linear_score(
                    snapshot.roe,
                    0.05,
                    0.30,
                ),
                0.50,
            ),
        },
        "momentum_fundamental": {
            "earnings_growth": (
                _linear_score(
                    snapshot.earnings_growth,
                    -0.15,
                    0.25,
                ),
                0.80,
            ),
            "analyst_upside": (
                _linear_score(
                    analyst_upside,
                    -0.15,
                    0.30,
                ),
                0.20,
            ),
        },
        "risk": {
            "debt_to_equity": (
                _linear_score(
                    debt_to_equity,
                    0.20,
                    3.00,
                    reverse=True,
                ),
                0.50,
            ),
            "balance_liquidity": (
                _linear_score(
                    snapshot.current_ratio,
                    0.70,
                    2.00,
                ),
                0.50,
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

    global_score = _observed_global_score(
        parts,
        dimension_coverage,
        normalized_weights,
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
        dimension_coverage=dimension_coverage,
        thresholds=normalized_thresholds,
        min_confidence=normalized_min_confidence,
        min_coverage=normalized_min_coverage,
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

    if analyst_warning:
        warnings.append(
            analyst_warning
        )

    if overall_coverage < 70.0:
        warnings.append(
            "La cobertura del scoring es parcial; "
            "la clasificación debe interpretarse "
            "con prudencia."
        )

    if recommendation == RADAR_UNRELIABLE:
        warnings.append(
            "El resultado no debe utilizarse para priorizar "
            "una inversión hasta validar los datos."
        )

    if any(
        coverage == 0.0
        for coverage
        in dimension_coverage.values()
    ):
        warnings.append(
            "Las dimensiones sin datos no participan "
            "en el score global."
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
            "como señal secundaria del momentum fundamental."
        )

    rationale = _build_rationale(
        parts=parts,
        dimension_coverage=dimension_coverage,
        recommendation=recommendation,
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
        recommendation=recommendation,
        rationale=rationale,
        calculated_at=datetime.now(
            timezone.utc
        ).isoformat(),
        overall_coverage=overall_coverage,
        dimension_coverage=dimension_coverage,
        missing_metrics=sorted(
            set(
                missing_metrics
            )
        ),
        warnings=_deduplicate_strings(
            warnings
        ),
        scoring_version=SCORING_VERSION,
    )
