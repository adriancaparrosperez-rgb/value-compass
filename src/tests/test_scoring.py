from src.models import CompanySnapshot
from src.scoring.engine import score_snapshot

def test_low_quality_blocks_entry():
    s = CompanySnapshot(ticker="X", price=10, market_cap=100, data_quality=20)
    card = score_snapshot(s, {"valuation":.25,"quality":.2,"cash":.15,"balance":.15,"growth":.1,"capital_allocation":.05,"momentum_fundamental":.05,"risk":.05}, {"strong_entry":80,"entry":70,"watch":58}, 55)
    assert card.recommendation == "DATOS INSUFICIENTES"
