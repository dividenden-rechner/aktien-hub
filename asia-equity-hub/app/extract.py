"""Conservative, auditable PDF-text candidate extraction.

Not an audited XBRL parser: never turn ambiguous PDF table text into trusted
financial statements. All results are candidates with page/line evidence.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from .providers import valid_symbol
from .reports import ROOT, load_catalog, report_key

FIELDS = {
    'revenue': r'(?:revenue|turnover|營業收入|营业收入|收益)',
    'net_income': r'(?:profit attributable to (?:owners|shareholders)|net profit|淨利潤|净利润|本公司擁有人應佔溢利)',
    'operating_profit': r'(?:operating profit|profit from operations|經營溢利|经营利润)',
    'total_assets': r'(?:total assets|資產總額|资产总计)',
    'total_liabilities': r'(?:total liabilities|負債總額|负债合计)',
    'cash': r'(?:cash and cash equivalents|現金及現金等價物|现金及现金等价物)',
    'operating_cash_flow': r'(?:net cash (?:generated from|from|provided by) operating activities|經營活動產生的現金淨額|经营活动产生的现金流量净额)',
}
NUM = re.compile(r'(?<![\w])\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|(?<![\w])\(?-?\d+(?:\.\d+)?\)?')
CURRENCY = re.compile(r'\b(?:HKD|RMB|CNY|SGD|USD|HK\$|S\$|US\$)\b|港元|人民幣|人民币', re.I)
SCALE = re.compile(r'\b(?:million|billion|thousand)\b|百萬元|百万元|千元|億元|亿元', re.I)

def candidates_from_pages(pages: list[dict], max_per_field: int = 25) -> dict:
    """Extract *evidence*, not verified numerical values.

    Table columns often contain multiple years; selecting the first number
    without table geometry would silently create wrong facts.
    """
    output = {field: [] for field in FIELDS}
    patterns = {key: re.compile(expr, re.I) for key, expr in FIELDS.items()}
    for page in pages:
        number = page.get('page')
        for line_number, raw in enumerate(str(page.get('text') or '').splitlines(), 1):
            line = ' '.join(raw.split())[:500]
            if not line:
                continue
            for field, pattern in patterns.items():
                if not pattern.search(line) or len(output[field]) >= max_per_field:
                    continue
                # Keep only lines with at least one numeric token, but never
                # assert a year, unit, or value from a flattened PDF table.
                if not NUM.search(line):
                    continue
                output[field].append({'page':number,'line':line_number,'evidence':line,
                    'numeric_tokens':NUM.findall(line)[:12],
                    'currency_tokens':CURRENCY.findall(line),
                    'scale_tokens':SCALE.findall(line),
                    'verification_status':'requires_manual_table_review'})
    return {'status':'unverified_candidates','fields':output,
            'warning':'PDF text loses table layout. Numeric tokens are not mapped to fiscal years, units, currencies or financial values.'}

def extract_registered(symbol: str, fiscal_year: int | None = None) -> dict:
    symbol = valid_symbol(symbol)
    records=[]
    for entry in load_catalog():
        if entry['symbol'] != symbol or (fiscal_year is not None and entry['fiscal_year'] != fiscal_year):
            continue
        key=report_key(entry)
        path=ROOT/'cache'/f'{key}.pages.json'
        if not path.is_file():
            records.append({'id':key,'fiscal_year':entry['fiscal_year'],'status':'not_ingested'})
            continue
        pages=json.loads(path.read_text(encoding='utf-8'))
        extraction=candidates_from_pages(pages)
        records.append({'id':key,'fiscal_year':entry['fiscal_year'],
                        'source_url':entry['url'], **extraction})
    return {'symbol':symbol,'reports':records}
