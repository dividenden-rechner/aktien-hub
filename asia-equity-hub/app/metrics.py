from __future__ import annotations

def ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator

def cagr(first, last, years):
    if first is None or last is None or years <= 0 or first <= 0 or last < 0:
        return None
    return (last / first) ** (1 / years) - 1

def derived(financials: dict, market_cap=None, enterprise_value=None):
    g = financials.get
    revenue, net_income = g('revenue'), g('net_income')
    ocf, capex = g('operating_cash_flow'), g('capex')
    fcf = ocf - abs(capex) if ocf is not None and capex is not None else None
    debt, cash = g('total_debt'), g('cash')
    net_debt = debt - cash if debt is not None and cash is not None else None
    ebitda = g('ebitda')
    operating_income = g('operating_income')
    interest_expense = g('interest_expense')
    return {
        'free_cash_flow': fcf,
        'gross_margin': ratio(g('gross_profit'), revenue),
        'operating_margin': ratio(operating_income, revenue),
        'net_margin': ratio(net_income, revenue),
        'ebitda_margin': ratio(ebitda, revenue),
        'roe': ratio(net_income, g('equity')),
        'current_ratio': ratio(g('current_assets'), g('current_liabilities')),
        'net_debt': net_debt,
        'net_debt_to_ebitda': ratio(net_debt, ebitda),
        'interest_coverage': ratio(operating_income, abs(interest_expense) if interest_expense is not None else None),
        'fcf_yield': ratio(fcf, market_cap),
        'price_to_fcf': ratio(market_cap, fcf),
        'ev_to_ebitda': ratio(enterprise_value, ebitda),
        'dividend_fcf_coverage': ratio(fcf, abs(g('dividends_paid')) if g('dividends_paid') is not None else None),
        'capex_to_revenue': ratio(abs(capex) if capex is not None else None, revenue),
    }
