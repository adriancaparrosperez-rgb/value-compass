from src.valuation.dcf import dcf_value

def test_dcf_positive():
    result = dcf_value(100, 0.05, 5, 0.09, 0.02, 100, 10)
    assert result.enterprise_value > 0
    assert result.value_per_share is not None

def test_wacc_must_exceed_terminal_growth():
    try:
        dcf_value(100, 0.05, 5, 0.02, 0.03)
        assert False
    except ValueError:
        assert True
