"""Conservative extraction of year-aligned financial rows from PDF text.

Only emits values where a table header explicitly supplies years and units.
Flattened or ambiguous rows are rejected, not guessed.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation

LABELS = {
    'revenue': [r'revenue', r'turnover', r'营业收入', r'營業收入'],
    'net_income': [r'profit attributable to (?:owners|shareholders)', r'net profit', r'净利润', r'淨利潤'],
    'operating_profit': [r'operating profit', r'profit from operations', r'经营利润', r'經營溢利'],
    'total_assets': [r'total assets', r'资产总计', r'資產總額'],
    'total_liabilities': [r'total liabilities', r'负债合计', r'負債總額'],
    'cash': [r'cash and cash equivalents', r'现金及现金等价物', r'現金及現金等價物'],
    'operating_cash_flow': [r'net cash (?:generated from|provided by|from) operating activities'],
    'capex': [r'purchase of (?:property,? plant and equipment|fixed assets)', r'capital expenditure'],
    'dividends_paid': [r'dividends paid'],
}
LABEL_RE = {k: re.compile(r'^(?:'+'|'.join(v)+r')\s*[:：]?\s+', re.I) for k,v in LABELS.items()}
NUMBER = r'(?:\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|\(?-?\d+(?:\.\d+)?\)?)'
ROW_VALUES = re.compile(r'^\s*('+NUMBER+r'|[—–-])(?:\s{2,}('+NUMBER+r'|[—–-]))?\s*$')
HEADER = re.compile(r'\b(20\d{2})\s{2,}(20\d{2})\b')
UNIT = re.compile(r'(?i)\b(HKD|CNY|RMB|SGD|USD)\s*(million|billion|thousand)\b|\b(HK\$|S\$|US\$)\s*(million|billion|thousand)\b')
MULTIPLIERS = {'thousand':1000, 'million':1000000, 'billion':1000000000}
CURRENCIES = {'RMB':'CNY','HK$':'HKD','S$':'SGD','US$':'USD'}

def parse_number(token: str):
    token=token.strip()
    if token in ('-','—','–'): return None
    negative=token.startswith('(') and token.endswith(')')
    try:
        v=Decimal(token.strip('()').replace(',',''))
    except InvalidOperation:
        return None
    return -v if negative else v

def extract_year_tables(pages: list[dict], source_url: str | None = None) -> dict:
    """Strictly requires a two-year header, explicit unit and two aligned numbers.

    This parser handles text-preserved two-column tables, not arbitrary PDF layouts.
    """
    facts=[]; rejected=[]
    for page in pages:
        lines=str(page.get('text') or '').splitlines()
        for i,line in enumerate(lines):
            header=HEADER.search(line)
            if not header: continue
            years=[int(header.group(1)),int(header.group(2))]
            if years[0]==years[1] or abs(years[0]-years[1])>2: continue
            context=' '.join(lines[max(0,i-5):i+2])
            unit=UNIT.search(context)
            if not unit: continue
            currency=(unit.group(1) or unit.group(3)).upper()
            currency=CURRENCIES.get(currency,currency)
            scale=(unit.group(2) or unit.group(4)).lower()
            multiplier=MULTIPLIERS[scale]
            for row_index in range(i+1,min(len(lines),i+32)):
                row=lines[row_index]
                if HEADER.search(row): break
                matched=None
                for field,pattern in LABEL_RE.items():
                    matched=pattern.match(row)
                    if matched: break
                if not matched: continue
                remainder=row[matched.end():]
                values=ROW_VALUES.fullmatch(remainder)
                if not values or values.group(2) is None:
                    rejected.append({'page':page.get('page'),'line':row_index+1,'field':field,'reason':'not_two_aligned_columns'})
                    continue
                for year,token in zip(years,values.groups()):
                    value=parse_number(token)
                    if value is None: continue
                    facts.append({'field':field,'fiscal_year':year,'value':str(value*multiplier),
                                  'currency':currency,'unit':'currency_units', 'source_url':source_url,
                                  'page':page.get('page'),'line':row_index+1,
                                  'evidence':row.strip()[:350], 'header_evidence':line.strip()[:200],
                                  'verification_status':'machine_extracted_requires_review'})
    # Contradictory observations are not resolved automatically.
    grouped={}
    for fact in facts:
        grouped.setdefault((fact['field'],fact['fiscal_year'],fact['currency']),[]).append(fact)
    accepted=[]; conflicts=[]
    for key,items in grouped.items():
        distinct={x['value'] for x in items}
        if len(distinct)>1:
            conflicts.append({'field':key[0],'fiscal_year':key[1],'currency':key[2], 'values':sorted(distinct)})
        else: accepted.append(items[0])
    return {'status':'requires_review','facts':accepted,'conflicts':conflicts,'rejected_rows':rejected,
            'warning':'Only explicitly labeled two-year rows with a nearby currency/scale are extracted. Results require verification against the original PDF.'}
