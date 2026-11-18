from app.analytics import annual_dividends, annual_growth, build_snapshot, scorecard


def test_dividends_grouped_and_invalid_ignored():
    assert annual_dividends([{'date':'2024-03-01','amount_per_share':1.2},
                             {'date':'2024-09-01','amount_per_share':.5},
                             {'date':'invalid','amount_per_share':10},
                             {'date':'2025-01-01','amount_per_share':-1}]) == [
                                 {'year':2024,'dividend_per_share':1.7}]


def test_growth_requires_exact_fiscal_year():
    years = [{'fiscal_period_end':'2020-12-31','values':{'revenue':100}},
             {'fiscal_period_end':'2025-12-31','values':{'revenue':200}}]
    assert round(annual_growth(years, 'revenue'), 5) == round(2**.2-1, 5)
    assert annual_growth(years[1:], 'revenue') is None


def test_unknown_scorecard():
    assert all(v['status']=='unknown' for v in scorecard({}).values())


def test_snapshot_currency_mismatch_does_not_compute_valuation():
    p={'symbol':'0700.HK','currency':'HKD','market_cap':1000,'enterprise_value':1200,
       'dividend_yield':.03,'data_source':'example'}
    prices={'currency':'HKD','bars':[{'time':'2025-01-01','close':10}, {'time':'2025-01-02','close':11}], 'source':'example'}
    fin={'currency':'CNY','years':[{'fiscal_period_end':'2025-12-31',
         'values':{'revenue':100,'operating_income':20,'operating_cash_flow':10,'capex':-2}}], 'source':'example'}
    s=build_snapshot(p,prices,fin,{'events':[],'source':'example'})
    assert s['metrics']['fcf_yield'] is None
    assert s['metrics']['operating_margin']==.2
    assert s['quote']['change_pct']==.1 or abs(s['quote']['change_pct']-.1)<1e-12
    assert not s['provenance']['cross_currency_ratios_enabled']
