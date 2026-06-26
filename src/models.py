from __future__ import annotations
import math
from dataclasses import asdict, dataclass, field
from typing import Any
def _bounded_score(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Normaliza una puntuación al intervalo 0–100.
    Los valores ausentes, booleanos, no numéricos, NaN
    o infinitos utilizan el valor por defecto.
    """
    if value is None or isinstance(value, bool):
        return default
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric_value):
        return default
    return round(
        max(
            0.0,
            min(
                100.0,
                numeric_value,
            ),
        ),
        1,
    )
@dataclass
class CompanySnapshot:
    ticker: str
    name: str = ""
    currency: str = ""
    sector: str = ""
    industry: str = ""
    price: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    revenue: float | None = None
    ebitda: float | None = None
    ebit: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    capex: float | None = None
    free_cash_flow: float | None = None
    total_cash: float | None = None
    total_debt: float | None = None
    shares: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    roa: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    interest_coverage: float | None = None
    pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    ev_to_ebitda: float | None = None
    fcf_yield: float | None = None
    earnings_yield: float | None = None
    dividend_yield: float | None = None
    fifty_two_week_change: float | None = None
    analyst_target: float | None = None
    analyst_count: int | None = None
    source: str = ""
    fetched_at: str = ""
    price_date: str | None = None
    fundamentals_date: str | None = None
    data_quality: float = 0.0
    coverage_score: float = 0.0
    validity_score: float = 0.0
    consistency_score: float = 0.0
    missing_fields: list[str] = field(
        default_factory=list
    )
    critical_missing_fields: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    provider_metadata: dict[str, Any] = field(
        default_factory=dict
    )
    errors: str = ""
    def __post_init__(self) -> None:
        self.ticker = (
            self.ticker.strip().upper()
            if isinstance(self.ticker, str)
            else str(self.ticker)
        )
        self.data_quality = _bounded_score(
            self.data_quality
        )
        self.coverage_score = _bounded_score(
            self.coverage_score
        )
        self.validity_score = _bounded_score(
            self.validity_score
        )
        self.consistency_score = _bounded_score(
            self.consistency_score
        )
    @property
    def has_errors(self) -> bool:
        return bool(
            isinstance(self.errors, str)
            and self.errors.strip()
        )
    @property
    def has_warnings(self) -> bool:
        return bool(
            self.warnings
        )
    @property
    def is_usable(self) -> bool:
        """
        Indica si el snapshot contiene los mínimos necesarios
        para ser utilizado en un precribado prudente.
        """
        return (
            bool(self.ticker)
            and self.price is not None
            and not self.critical_missing_fields
            and not self.has_errors
        )
    def add_warning(
        self,
        message: str,
    ) -> None:
        normalized_message = (
            message.strip()
            if isinstance(message, str)
            else ""
        )
        if not normalized_message:
            return
        if normalized_message.casefold() in {
            warning.casefold()
            for warning in self.warnings
        }:
            return
        self.warnings.append(
            normalized_message
        )
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
@dataclass
class ScoreCard:
    ticker: str
    valuation: float
    quality: float
    cash: float
    balance: float
    growth: float
    capital_allocation: float
    momentum_fundamental: float
    risk: float
    confidence: float
    global_score: float
    recommendation: str
    rationale: str
    calculated_at: str = ""
    overall_coverage: float = 0.0
    dimension_coverage: dict[str, float] = field(
        default_factory=dict
    )
    missing_metrics: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    scoring_version: str = "1.0.0"
    def __post_init__(self) -> None:
        self.ticker = (
            self.ticker.strip().upper()
            if isinstance(self.ticker, str)
            else str(self.ticker)
        )
        self.valuation = _bounded_score(
            self.valuation,
            default=50.0,
        )
        self.quality = _bounded_score(
            self.quality,
            default=50.0,
        )
        self.cash = _bounded_score(
            self.cash,
            default=50.0,
        )
        self.balance = _bounded_score(
            self.balance,
            default=50.0,
        )
        self.growth = _bounded_score(
            self.growth,
            default=50.0,
        )
        self.capital_allocation = _bounded_score(
            self.capital_allocation,
            default=50.0,
        )
        self.momentum_fundamental = _bounded_score(
            self.momentum_fundamental,
            default=50.0,
        )
        self.risk = _bounded_score(
            self.risk,
            default=50.0,
        )
        self.confidence = _bounded_score(
            self.confidence
        )
        self.global_score = _bounded_score(
            self.global_score
        )
        self.overall_coverage = _bounded_score(
            self.overall_coverage
        )
        self.dimension_coverage = {
            str(name): _bounded_score(
                coverage
            )
            for name, coverage in (
                self.dimension_coverage.items()
            )
        }
    @property
    def is_reliable(self) -> bool:
        return (
            self.confidence >= 55.0
            and self.overall_coverage >= 50.0
        )
    def add_warning(
        self,
        message: str,
    ) -> None:
        normalized_message = (
            message.strip()
            if isinstance(message, str)
            else ""
        )
        if not normalized_message:
            return
        if normalized_message.casefold() in {
            warning.casefold()
            for warning in self.warnings
        }:
            return
        self.warnings.append(
            normalized_message
        )
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
