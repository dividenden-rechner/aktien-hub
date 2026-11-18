from app.metrics import ratio,cagr,derived
from app.providers import valid_symbol
import pytest

def test_ratio():
    assert ratio(10,2)==5
    assert ratio(1,0) is None
    assert ratio(None,5) is None

def test_cagr():
    assert round(cagr(100,121,2),4)==0.1
    assert cagr(0,100,2) is None

def test_derived():
    d=derived({'revenue':100,'gross_profit':40,'operating_cash_flow':20,'capex':-5,
               'total_debt':40,'cash':10,'ebitda':15,'dividends_paid':-10},1000,1200)
    assert d['free_cash_flow']==15
    assert d['gross_margin']==0.4
    assert d['net_debt_to_ebitda']==2
    assert d['dividend_fcf_coverage']==1.5

def test_tickers():
    assert valid_symbol('0700.hk')=='0700.HK'
    assert valid_symbol('D05.SI')=='D05.SI'
    with pytest.raises(ValueError):valid_symbol('KO')
    with pytest.raises(ValueError):valid_symbol('../secrets')
