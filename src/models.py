from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

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
    data_quality: float = 0.0
    errors: str = ""

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
