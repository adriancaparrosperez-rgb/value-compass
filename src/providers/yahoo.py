from __future__ import annotations
from datetime import datetime, timezone
import math
import yfinance as yf
from src.models import CompanySnapshot
from src.providers.base import MarketDataProvider


def _num(value):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

class YahooProvider(MarketDataProvider):
    """Proveedor gratuito de precarga. No sustituye cuentas oficiales."""

    def get_snapshot(self, ticker: str) -> CompanySnapshot:
        snap = CompanySnapshot(ticker=ticker, source="Yahoo Finance (precarga)")
        snap.fetched_at = datetime.now(timezone.utc).isoformat()
        try:
            obj = yf.Ticker(ticker)
            info = obj.info or {}
            fast = obj.fast_info or {}
            price = _num(fast.get("last_price")) or _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
            market_cap = _num(fast.get("market_cap")) or _num(info.get("marketCap"))
            fcf = _num(info.get("freeCashflow"))
            net_income = _num(info.get("netIncomeToCommon"))
            shares = _num(info.get("sharesOutstanding"))
            snap.name = info.get("longName") or info.get("shortName") or ticker
            snap.currency = info.get("currency") or ""
            snap.sector = info.get("sector") or ""
            snap.industry = info.get("industry") or ""
            snap.price = price
            snap.market_cap = market_cap
            snap.enterprise_value = _num(info.get("enterpriseValue"))
            snap.revenue = _num(info.get("totalRevenue"))
            snap.ebitda = _num(info.get("ebitda"))
            snap.ebit = _num(info.get("ebit"))
            snap.net_income = net_income
            snap.operating_cash_flow = _num(info.get("operatingCashflow"))
            snap.capex = None
            snap.free_cash_flow = fcf
            snap.total_cash = _num(info.get("totalCash"))
            snap.total_debt = _num(info.get("totalDebt"))
            snap.shares = shares
            snap.revenue_growth = _num(info.get("revenueGrowth"))
            snap.earnings_growth = _num(info.get("earningsGrowth"))
            snap.gross_margin = _num(info.get("grossMargins"))
            snap.operating_margin = _num(info.get("operatingMargins"))
            snap.net_margin = _num(info.get("profitMargins"))
            snap.roe = _num(info.get("returnOnEquity"))
            snap.roa = _num(info.get("returnOnAssets"))
            snap.debt_to_equity = _num(info.get("debtToEquity"))
            snap.current_ratio = _num(info.get("currentRatio"))
            snap.pe = _num(info.get("trailingPE"))
            snap.forward_pe = _num(info.get("forwardPE"))
            snap.price_to_book = _num(info.get("priceToBook"))
            snap.ev_to_ebitda = _num(info.get("enterpriseToEbitda"))
            snap.fcf_yield = (fcf / market_cap) if fcf and market_cap and market_cap > 0 else None
            snap.earnings_yield = (net_income / market_cap) if net_income and market_cap and market_cap > 0 else None
            snap.dividend_yield = _num(info.get("dividendYield"))
            snap.fifty_two_week_change = _num(info.get("52WeekChange"))
            snap.analyst_target = _num(info.get("targetMeanPrice"))
            snap.analyst_count = int(info.get("numberOfAnalystOpinions")) if info.get("numberOfAnalystOpinions") else None
            fields = [snap.price, snap.market_cap, snap.revenue, snap.net_income, snap.free_cash_flow,
                      snap.total_cash, snap.total_debt, snap.pe, snap.ev_to_ebitda, snap.roe]
            snap.data_quality = round(100 * sum(v is not None for v in fields) / len(fields), 1)
        except Exception as exc:
            snap.errors = f"{type(exc).__name__}: {exc}"
        return snap
