"""Pure analytics for Asian listed equities. Missing data is never imputed."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from .metrics import cagr, derived, ratio


def annual_dividends(events):
    totals = defaultdict(float)
    for event in events:
        date, amount = event.get('date'), event.get('amount_per_share')
        if not date or not isinstance(amount, (int, float)) or amount < 0:
            continue
        try:
            year = datetime.fromisoformat(date[:10]).year
        except ValueError:
            continue
        totals[year] += amount
    return [{'year': year, 'dividend_per_share': round(value, 8)} for year, value in sorted(totals.items())]


def annual_growth(years, key, horizon=5):
    points = [(str(y['fiscal_period_end'])[:4], y.get('values', {}).get(key)) for y in years]
    points = [(int(year), value) for year, value in points if year.isdigit() and isinstance(value, (int, float))]
    if len(points) < 2:
        return None
    points.sort()
    last_year, last_value = points[-1]
    earlier = next(((year, value) for year, value in points if year == last_year - horizon), None)
    return cagr(earlier[1], last_value, horizon) if earlier else None


def classify(value, good, moderate, higher=True):
    if value is None:
        return {'status': 'unknown', 'reason': 'Not enough verified data'}
    if higher:
        status = 'green' if value >= good else 'yellow' if value >= moderate else 'red'
    else:
        status = 'green' if value <= good else 'yellow' if value <= moderate else 'red'
    return {'status': status, 'value': value}


def scorecard(metrics, revenue_growth=None, eps_growth=None, dividend_yield=None):
    # Simple transparent heuristics, not recommendations or forecasts.
    return {
        'profitability': classify(metrics.get('operating_margin'), .20, .10),
        'balance_sheet': classify(metrics.get('net_debt_to_ebitda'), 2, 4, higher=False),
        'dividend_coverage': classify(metrics.get('dividend_fcf_coverage'), 1.5, 1),
        'revenue_growth_5y': classify(revenue_growth, .10, .04),
        'expected_return_proxy': classify(
            dividend_yield + eps_growth if dividend_yield is not None and eps_growth is not None else None,
            .10, .05),
    }


def build_snapshot(profile, prices, financials, dividends):
    years = financials.get('years') or []
    years = sorted(years, key=lambda y: str(y.get('fiscal_period_end', '')))
    latest = years[-1] if years else None
    financial_currency = financials.get('currency')
    price_currency = prices.get('currency') or profile.get('currency')
    same_currency = bool(financial_currency and price_currency and financial_currency == price_currency)
    metrics = derived(latest['values']) if latest else {}
    # Cross-source ratios only when currencies are confirmed equal.
    if latest and same_currency:
        metrics = derived(latest['values'], profile.get('market_cap'), profile.get('enterprise_value'))
    bars = prices.get('bars') or []
    latest_bar = bars[-1] if bars else None
    prior_bar = bars[-2] if len(bars) > 1 else None
    close = latest_bar.get('close') if latest_bar else None
    prior = prior_bar.get('close') if prior_bar else None
    price_change = ratio(close - prior, prior) if isinstance(close, (int, float)) and isinstance(prior, (int, float)) else None
    rev_growth = annual_growth(years, 'revenue')
    eps_growth = annual_growth(years, 'diluted_eps')
    div_yield = profile.get('dividend_yield')
    return {
        'symbol': profile.get('symbol'), 'profile': profile,
        'quote': {'last_close': close, 'previous_close': prior, 'change_pct': price_change,
                  'as_of': latest_bar.get('time') if latest_bar else None, 'currency': price_currency,
                  'is_realtime': False},
        'annual_financials': years, 'annual_dividends': annual_dividends(dividends.get('events') or []),
        'metrics': metrics, 'growth': {'revenue_cagr_5y': rev_growth, 'eps_cagr_5y': eps_growth},
        'scorecard': scorecard(metrics, rev_growth, eps_growth, div_yield),
        'provenance': {'profile': profile.get('data_source'), 'prices': prices.get('source'),
                       'financials': financials.get('source'), 'dividends': dividends.get('source'),
                       'financial_period_end': latest.get('fiscal_period_end') if latest else None,
                       'financial_currency': financial_currency, 'price_currency': price_currency,
                       'cross_currency_ratios_enabled': same_currency},
        'warnings': ['Unofficial delayed data; verify against exchange filings before publication.',
                     'Five-year growth requires matching fiscal years; no missing years are estimated.']
                    + ([] if same_currency else ['Price and financial currencies differ or are unknown; cross-currency valuation ratios omitted.'])
    }
