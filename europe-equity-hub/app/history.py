"""FY2010-FY2025 financial history from official ESEF annual-report XBRL (v0.7).

Input: aktien-hub data/esef/speicher.json, written by tools/esef_fundamentals.py from filings.xbrl.org
(raw IFRS facts per report: concept -> period end -> [value, unit, is_duration]).
Every fact keeps: issuer LEI, fiscal year (year of the period end), fiscal_year_end, value, currency, unit,
XBRL concept, report URL, report period, current-vs-comparative flag, extraction method, human_review=pending.
ESEF exists only from FY2020 (EU mandate) - earlier years remain "missing", never 0.
Derived values (total debt, free cash flow) state their formula and inputs.
"""
from __future__ import annotations

from collections import defaultdict

FILINGS_BASE = 'https://filings.xbrl.org'
YEARS = list(range(2010, 2026))
CONCEPTS = {
    'revenue': ['Revenue', 'RevenueFromContractsWithCustomers'],
    'operating_profit': ['ProfitLossFromOperatingActivities'],
    'net_income': ['ProfitLoss'],
    'net_income_attributable': ['ProfitLossAttributableToOwnersOfParent'],
    'total_assets': ['Assets'],
    'total_equity': ['Equity'],
    'equity_attributable': ['EquityAttributableToOwnersOfParent'],
    'total_liabilities': ['Liabilities'],
    'long_term_borrowings': ['LongtermBorrowings'],
    'short_term_borrowings': ['ShorttermBorrowings'],
    'operating_cash_flow': ['CashFlowsFromUsedInOperatingActivities'],
    'capex_ppe': ['PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'],
    'capex_intangibles': ['PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'],
    'eps_basic': ['BasicEarningsLossPerShare', 'BasicAndDilutedEarningsLossPerShare'],
    'weighted_average_shares': ['WeightedAverageShares'],
    'dps_recognised_in_year': ['DividendsRecognisedAsDistributionsToOwnersPerShare'],
    'dps_proposed_for_year': ['DividendsProposedOrDeclaredBeforeFinancialStatementsAuthorisedForIssueButNotRecognisedAsDistributionToOwnersPerShare'],
    'dividends_paid': ['DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities',
                       'DividendsPaidClassifiedAsFinancingActivities', 'DividendsPaid'],
}
PER_SHARE = {'eps_basic', 'dps_recognised_in_year', 'dps_proposed_for_year'}
REQUIRED_FOR_COVERAGE = ('revenue', 'net_income', 'total_assets', 'total_equity', 'operating_cash_flow')
NOT_AVAILABLE_FROM_ESEF = {'shares_outstanding': 'ESEF facts used here contain weighted-average shares only; '
                                                 'period-end shares outstanding not extracted'}


def _unit(raw: str, field: str) -> tuple[str | None, str]:
    raw = raw or ''
    if raw.startswith('iso4217:'):
        cur = raw.split(':', 1)[1].split('/')[0]
        return cur, 'per_share' if field in PER_SHARE or '/' in raw else 'units'
    if 'shares' in raw:
        return None, 'shares'
    return None, raw or 'unknown'


def facts_from_reports(berichte: dict) -> list[dict]:
    best: dict[tuple, dict] = {}
    for key, rep in berichte.items():
        lei, end = rep.get('lei'), rep.get('ende')
        if not lei or not end:
            continue
        raw = rep.get('roh') or {}
        for field, concepts in CONCEPTS.items():
            concept = next((c for c in concepts if c in raw), None)
            if not concept:
                continue
            for period_end, (value, unit, _is_duration) in raw[concept].items():
                cur, unit_kind = _unit(unit, field)
                fy = int(period_end[:4])
                if fy not in YEARS:
                    continue
                fact = {'issuer_lei': lei, 'field': field, 'fiscal_year': fy, 'fiscal_year_end': period_end,
                        'value': value, 'currency': cur, 'unit': unit_kind, 'xbrl_unit': unit, 'xbrl_concept': f'ifrs-full:{concept}',
                        'report_url': FILINGS_BASE + key, 'report_period_end': end, 'report_type': 'ESEF annual financial report',
                        'is_comparative': period_end != end, 'page': None,
                        'page_note': 'ESEF/iXBRL fact; location is the XBRL concept, not a PDF page',
                        'sha256': None, 'sha256_note': 'not computed: values from repo cache data/esef/speicher.json',
                        'extraction_method': 'esef_xbrl_json_fact', 'verification_status': 'machine_extracted',
                        'human_review': 'pending'}
                k = (lei, field, fy)
                # prefer the report whose own period is this fiscal year (not a comparative); then the latest report
                rank = (not fact['is_comparative'], end)
                if k not in best or rank > best[k]['_rank']:
                    fact['_rank'] = rank
                    best[k] = fact
    out = []
    for f in best.values():
        f.pop('_rank', None)
        out.append(f)
    return sorted(out, key=lambda f: (f['issuer_lei'], f['fiscal_year'], f['field']))


def derive(facts: list[dict]) -> list[dict]:
    by = defaultdict(dict)
    for f in facts:
        by[(f['issuer_lei'], f['fiscal_year'])][f['field']] = f
    out = []
    for (lei, fy), row in by.items():
        lt, st = row.get('long_term_borrowings'), row.get('short_term_borrowings')
        if lt and st and lt['currency'] == st['currency']:
            out.append({**_dbase(lt), 'field': 'total_debt', 'value': lt['value'] + st['value'],
                        'derivation': 'long_term_borrowings + short_term_borrowings (borrowings only, leases excluded)'})
        ocf, cx = row.get('operating_cash_flow'), row.get('capex_ppe')
        if ocf and cx and ocf['currency'] == cx['currency']:
            ci = row.get('capex_intangibles')
            value = ocf['value'] - abs(cx['value']) - (abs(ci['value']) if ci and ci['currency'] == ocf['currency'] else 0)
            out.append({**_dbase(ocf), 'field': 'free_cash_flow', 'value': value,
                        'derivation': 'operating_cash_flow - |capex_ppe| - |capex_intangibles (if reported)|'})
    return out


def _dbase(f: dict) -> dict:
    return {k: f[k] for k in ('issuer_lei', 'fiscal_year', 'fiscal_year_end', 'currency', 'unit', 'report_url',
                              'report_period_end', 'is_comparative')} | {
        'xbrl_concept': None, 'extraction_method': 'derived', 'verification_status': 'derived_from_machine_extracted',
        'human_review': 'pending'}


def plausibility(facts: list[dict]) -> list[dict]:
    by = defaultdict(dict)
    for f in facts:
        by[(f['issuer_lei'], f['fiscal_year'])][f['field']] = f
    issues = []
    for (lei, fy), r in by.items():
        def v(k):
            return r[k]['value'] if k in r else None
        if v('total_assets') is not None and v('total_assets') <= 0:
            issues.append((lei, fy, 'total_assets_not_positive'))
        if v('total_assets') and v('total_equity') is not None and v('total_equity') > v('total_assets'):
            issues.append((lei, fy, 'equity_exceeds_assets'))
        if v('total_assets') and v('net_income') is not None and abs(v('net_income')) > v('total_assets'):
            issues.append((lei, fy, 'net_income_exceeds_assets'))
        if v('net_income_attributable') is not None and v('eps_basic') is not None and \
                v('net_income_attributable') * v('eps_basic') < 0 and abs(v('net_income_attributable')) > 1e6:
            issues.append((lei, fy, 'eps_sign_differs_from_net_income'))
        cur = {r[k]['currency'] for k in r if r[k].get('currency') and k not in PER_SHARE}
        if len(cur) > 1:
            issues.append((lei, fy, f'mixed_currencies:{sorted(cur)}'))
    return [{'issuer_lei': a, 'fiscal_year': b, 'issue': c} for a, b, c in issues]


def coverage(issuer_leis: list[str], facts: list[dict]) -> dict:
    have = defaultdict(set)
    for f in facts:
        have[(f['issuer_lei'], f['fiscal_year'])].add(f['field'])
    matrix, per_year = {}, {y: {'complete': 0, 'partial': 0, 'missing': 0} for y in YEARS}
    for lei in issuer_leis:
        row = {}
        for y in YEARS:
            fields = have.get((lei, y), set())
            status = 'missing' if not fields else ('complete' if all(k in fields for k in REQUIRED_FOR_COVERAGE) else 'partial')
            row[str(y)] = status
            per_year[y][status] += 1
        matrix[lei] = row
    return {'years': YEARS, 'required_fields_for_complete': list(REQUIRED_FOR_COVERAGE),
            'per_year': {str(k): v for k, v in per_year.items()}, 'matrix': matrix}
