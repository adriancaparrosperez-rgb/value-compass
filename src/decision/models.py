from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from src.decision.enums import (
    DataQualityStatus,
    EvidenceConfidence,
    ExistingHolderAction,
    GateSeverity,
    MoatStrength,
    MoatTrend,
    NewInvestorAction,
    RadarSignal,
    RiskLevel,
    ValuationStatus,
)
def _serialize_value(value: Any) -> Any:
    """
    Convierte recursivamente dataclasses ya transformadas con
    asdict(), enums y estructuras anidadas en valores compatibles
    con JSON y SQLite.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {
            key: _serialize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _serialize_value(item)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _serialize_value(item)
            for item in value
        ]
    return value
@dataclass
class SourceReference:
    name: str
    source_type: str
    url: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    is_official: bool = False
@dataclass
class DataQualityAssessment:
    status: DataQualityStatus = (
        DataQualityStatus.INSUFFICIENT
    )
    coverage_score: float = 0.0
    freshness_score: float = 0.0
    consistency_score: float = 0.0
    source_quality_score: float = 0.0
    price_validated: bool = False
    currency_validated: bool = False
    ticker_validated: bool = False
    market_cap_validated: bool = False
    fundamentals_validated: bool = False
    price_date: str | None = None
    fundamentals_date: str | None = None
    source_count: int = 0
    official_source_count: int = 0
    warnings: list[str] = field(
        default_factory=list
    )
    blocking_issues: list[str] = field(
        default_factory=list
    )
    @property
    def overall_score(self) -> float:
        score = (
            0.25 * self.coverage_score
            + 0.25 * self.freshness_score
            + 0.25 * self.consistency_score
            + 0.25 * self.source_quality_score
        )
        return round(
            max(
                0.0,
                min(
                    100.0,
                    score,
                ),
            ),
            1,
        )
@dataclass
class AccountingAssessment:
    gaap_earnings: float | None = None
    adjusted_earnings: float | None = None
    gaap_eps: float | None = None
    adjusted_eps: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    reported_fcf: float | None = None
    economic_fcf: float | None = None
    stock_based_compensation: float | None = None
    sbc_to_revenue: float | None = None
    sbc_to_reported_fcf: float | None = None
    recurring_adjustments: float | None = None
    acquisition_related_adjustments: float | None = None
    restructuring_adjustments: float | None = None
    impairment_adjustments: float | None = None
    cash_conversion_score: float | None = None
    earnings_quality_score: float | None = None
    accounting_quality_score: float | None = None
    uses_sbc_adjusted_fcf: bool = False
    warnings: list[str] = field(
        default_factory=list
    )
    notes: list[str] = field(
        default_factory=list
    )
@dataclass
class PerShareAssessment:
    diluted_shares: float | None = None
    diluted_shares_previous: float | None = None
    share_count_growth: float | None = None
    revenue_per_share: float | None = None
    revenue_per_share_growth: float | None = None
    gaap_eps_growth: float | None = None
    adjusted_eps_growth: float | None = None
    reported_fcf_per_share: float | None = None
    economic_fcf_per_share: float | None = None
    fcf_per_share_growth: float | None = None
    buybacks: float | None = None
    net_buybacks_after_sbc: float | None = None
    net_debt_per_share: float | None = None
    per_share_value_score: float | None = None
    warnings: list[str] = field(
        default_factory=list
    )
    notes: list[str] = field(
        default_factory=list
    )
@dataclass
class MoatAssessment:
    strength: MoatStrength = (
        MoatStrength.NOT_EVALUATED
    )
    trend: MoatTrend = (
        MoatTrend.NOT_EVALUATED
    )
    confidence: EvidenceConfidence = (
        EvidenceConfidence.NOT_EVALUABLE
    )
    switching_costs_score: float | None = None
    network_effects_score: float | None = None
    brand_score: float | None = None
    scale_score: float | None = None
    data_advantage_score: float | None = None
    intellectual_property_score: float | None = None
    distribution_score: float | None = None
    regulatory_advantage_score: float | None = None
    substitution_risk_score: float | None = None
    disruption_risk_score: float | None = None
    preliminary_score: float | None = None
    reviewed_score: float | None = None
    evidence: list[str] = field(
        default_factory=list
    )
    threats: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    notes: list[str] = field(
        default_factory=list
    )
@dataclass
class BusinessAssessment:
    sector: str | None = None
    industry: str | None = None
    business_model: str | None = None
    operating_quality_score: float | None = None
    organic_growth_score: float | None = None
    balance_score: float | None = None
    cash_score: float | None = None
    capital_allocation_score: float | None = None
    risk_score: float | None = None
    revenue_growth: float | None = None
    organic_revenue_growth: float | None = None
    operating_margin: float | None = None
    return_on_invested_capital: float | None = None
    customer_concentration_risk: float | None = None
    supplier_concentration_risk: float | None = None
    platform_dependency_risk: float | None = None
    regulatory_risk: float | None = None
    warnings: list[str] = field(
        default_factory=list
    )
    notes: list[str] = field(
        default_factory=list
    )
@dataclass
class ValuationScenario:
    name: str
    intrinsic_value_per_share: float | None = None
    revenue_growth: float | None = None
    margin: float | None = None
    terminal_growth: float | None = None
    discount_rate: float | None = None
    assumptions: dict[str, Any] = field(
        default_factory=dict
    )
@dataclass
class ValuationAssessment:
    current_price: float | None = None
    currency: str | None = None
    conservative: ValuationScenario | None = None
    base: ValuationScenario | None = None
    optimistic: ValuationScenario | None = None
    reverse_dcf_growth: float | None = None
    reverse_dcf_margin: float | None = None
    reverse_dcf_status: str | None = None
    multiples_score: float | None = None
    valuation_score: float | None = None
    margin_of_safety_conservative: float | None = None
    margin_of_safety_base: float | None = None
    status: ValuationStatus = (
        ValuationStatus.NOT_EVALUATED
    )
    warnings: list[str] = field(
        default_factory=list
    )
    notes: list[str] = field(
        default_factory=list
    )
@dataclass
class GateResult:
    code: str
    passed: bool
    severity: GateSeverity
    message: str
@dataclass
class RadarAssessment:
    ticker: str
    signal: RadarSignal
    quantitative_score: float | None = None
    data_quality_status: DataQualityStatus = (
        DataQualityStatus.INSUFFICIENT
    )
    reason: str = ""
    requires_master_analysis: bool = True
    warnings: list[str] = field(
        default_factory=list
    )
@dataclass
class MasterAnalysisInput:
    ticker: str
    company_name: str | None = None
    data_quality: DataQualityAssessment = field(
        default_factory=DataQualityAssessment
    )
    business: BusinessAssessment = field(
        default_factory=BusinessAssessment
    )
    accounting: AccountingAssessment = field(
        default_factory=AccountingAssessment
    )
    per_share: PerShareAssessment = field(
        default_factory=PerShareAssessment
    )
    moat: MoatAssessment = field(
        default_factory=MoatAssessment
    )
    valuation: ValuationAssessment = field(
        default_factory=ValuationAssessment
    )
    sources: list[SourceReference] = field(
        default_factory=list
    )
    model_version: str = "0.1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(
            asdict(self)
        )
@dataclass
class MasterDecisionResult:
    ticker: str
    new_investor_action: NewInvestorAction
    existing_holder_action: ExistingHolderAction
    confidence: EvidenceConfidence
    risk_level: RiskLevel
    company_quality: str
    valuation_status: ValuationStatus
    moat_strength: MoatStrength
    moat_trend: MoatTrend
    ranking_score: float | None = None
    gates: list[GateResult] = field(
        default_factory=list
    )
    thesis: list[str] = field(
        default_factory=list
    )
    reasons: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    conditions_to_buy: list[str] = field(
        default_factory=list
    )
    conditions_to_reduce: list[str] = field(
        default_factory=list
    )
    raw_components: dict[str, Any] = field(
        default_factory=dict
    )
    model_version: str = "0.1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(
            asdict(self)
        )
