from __future__ import annotations
from datetime import datetime, timezone
from src.models import CompanySnapshot, ScoreCard


def _linear(value, low, high, reverse=False, neutral=50):
    if value is None:
        return neutral
    if high == low:
        return neutral
    score = max(0.0, min(100.0, (value - low) / (high - low) * 100))
    return 100 - score if reverse else score


def _avg(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else 50.0


def score_snapshot(s: CompanySnapshot, weights: dict, thresholds: dict, min_confidence: float = 55) -> ScoreCard:
    valuation = _avg([
        _linear(s.fcf_yield, 0.01, 0.10),
        _linear(s.earnings_yield, 0.02, 0.10),
        _linear(s.forward_pe, 8, 30, reverse=True),
        _linear(s.ev_to_ebitda, 5, 20, reverse=True),
    ])
    quality = _avg([
        _linear(s.roe, 0.05, 0.30),
        _linear(s.roa, 0.02, 0.15),
        _linear(s.operating_margin, 0.05, 0.30),
        _linear(s.net_margin, 0.02, 0.20),
    ])
    cash = _avg([
        _linear(s.fcf_yield, 0.0, 0.10),
        _linear((s.free_cash_flow / s.net_income) if s.free_cash_flow and s.net_income and s.net_income != 0 else None, 0.5, 1.5),
    ])
    debt_to_equity = (s.debt_to_equity / 100) if s.debt_to_equity and s.debt_to_equity > 10 else s.debt_to_equity
    balance = _avg([
        _linear(debt_to_equity, 0.2, 2.5, reverse=True),
        _linear(s.current_ratio, 0.7, 2.0),
        _linear(((s.total_cash or 0) - (s.total_debt or 0)) / s.market_cap if s.market_cap else None, -0.6, 0.2),
    ])
    growth = _avg([
        _linear(s.revenue_growth, -0.05, 0.20),
        _linear(s.earnings_growth, -0.10, 0.25),
    ])
    capital_allocation = _avg([
        _linear(s.dividend_yield, 0.0, 0.06),
        _linear(s.roe, 0.05, 0.30),
    ])
    momentum = _avg([
        _linear(s.earnings_growth, -0.15, 0.25),
        _linear((s.analyst_target / s.price - 1) if s.analyst_target and s.price else None, -0.15, 0.30),
    ])
    risk = _avg([
        _linear(debt_to_equity, 0.2, 3.0, reverse=True),
        _linear(s.fifty_two_week_change, -0.50, 0.50),
        s.data_quality,
    ])
    parts = {
        "valuation": valuation, "quality": quality, "cash": cash, "balance": balance,
        "growth": growth, "capital_allocation": capital_allocation,
        "momentum_fundamental": momentum, "risk": risk,
    }
    global_score = sum(parts[k] * float(weights.get(k, 0)) for k in parts)
    confidence = s.data_quality
    if confidence < min_confidence:
        recommendation = "DATOS INSUFICIENTES"
    elif global_score >= thresholds.get("strong_entry", 80) and valuation >= 70 and balance >= 50:
        recommendation = "ENTRADA CLARA"
    elif global_score >= thresholds.get("entry", 70) and valuation >= 60:
        recommendation = "ENTRADA / COMPRA PARCIAL"
    elif global_score >= thresholds.get("watch", 58):
        recommendation = "VIGILAR / ESPERAR PRECIO"
    elif global_score >= 45:
        recommendation = "MANTENER / SIN ENTRADA"
    else:
        recommendation = "EVITAR / REVISAR"
    reasons = sorted(parts.items(), key=lambda x: x[1], reverse=True)
    rationale = f"Fortalezas: {reasons[0][0]} {reasons[0][1]:.0f}, {reasons[1][0]} {reasons[1][1]:.0f}. Debilidades: {reasons[-1][0]} {reasons[-1][1]:.0f}."
    return ScoreCard(
        ticker=s.ticker, valuation=round(valuation,1), quality=round(quality,1), cash=round(cash,1),
        balance=round(balance,1), growth=round(growth,1), capital_allocation=round(capital_allocation,1),
        momentum_fundamental=round(momentum,1), risk=round(risk,1), confidence=round(confidence,1),
        global_score=round(global_score,1), recommendation=recommendation, rationale=rationale,
        calculated_at=datetime.now(timezone.utc).isoformat())
