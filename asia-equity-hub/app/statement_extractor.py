"""Profile-driven extraction of primary financial statement values from annual-report PDFs.

Design principles (v1.1):

* Nothing is guessed. Every value comes from an explicit, reviewed *issuer profile*
  (``reports/profiles/<symbol>.json``) that names the PDF page, the row label
  pattern, the number of value columns and the column of the fiscal year.
* Every extracted value carries provenance: PDF page (1-based), printed page,
  line number, raw evidence line, source URL, currency, unit and fiscal year.
* A field is rejected (not "fixed") when its label is missing, ambiguous on the
  page, or the row does not contain the expected number of value columns.
* Derived values (e.g. total assets = non-current + current assets) are computed
  only from extracted values and are labelled ``derived`` with their inputs.
* Arithmetic consistency checks (balance-sheet identity, profit split, ...) run
  after extraction. Failing checks downgrade the report status.
* Machine extraction never sets ``verified``. Manual verification is recorded
  separately in the profile (``manual_review``) by a human reviewer.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

DASHES = {'-', '–', '—', '−'}
# Amount token: 1,234 / 1,234.5 / (1,234) / 12.34 / -12 / dash placeholder.
AMOUNT_RE = re.compile(r'^\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?$|^\(?-?\d+(?:\.\d+)?\)?$')
# Currency markers sometimes printed in front of per-share values (e.g. "HK$ 3.09").
CURRENCY_PREFIX_RE = re.compile(r'(?:HK\$|US\$|S\$|RMB|\$)\s*(?=\(?-?\d)')
# "(649,350 )" or "( 197,463,109   )" -> "(649,350)"; occurs in CNINFO/SZSE PDFs.
PAREN_SPACE_RE = re.compile(r'\(\s*(-?[\d,]+(?:\.\d+)?)\s*\)')
# Trailing note references in a row label, e.g. "43(b)", "5(A)", "34 (a)", "(a)", "33(I)".
NOTE_REF_RE = re.compile(r'(?:\s+\d{1,3}\s*\([A-Za-z]{1,4}\)|\s+\([a-z]\)|\s+\d{1,3})+$')

MULTIPLIERS = {'cents': Decimal('0.01'), 'units': Decimal(1), 'thousand': Decimal(1_000),
               'million': Decimal(1_000_000), 'billion': Decimal(1_000_000_000)}


def parse_amount(token: str) -> Decimal | None:
    """Parse one printed amount. Parentheses mean negative; a dash means nil.

    Raises ValueError for anything that is not an amount token.
    """
    token = token.strip()
    if token in DASHES:
        return None
    if not AMOUNT_RE.match(token):
        raise ValueError(f'not an amount token: {token!r}')
    negative = token.startswith('(') and token.endswith(')')
    try:
        value = Decimal(token.strip('()').replace(',', ''))
    except InvalidOperation as exc:  # pragma: no cover - regex already guards
        raise ValueError(f'not an amount token: {token!r}') from exc
    return -value if negative else value


def is_amount_token(token: str) -> bool:
    return token.strip() in DASHES or bool(AMOUNT_RE.match(token.strip()))


def normalize_line(line: str) -> str:
    line = line.replace(' ', ' ').replace('\t', ' ')
    line = PAREN_SPACE_RE.sub(r'(\1)', line)
    line = CURRENCY_PREFIX_RE.sub('', line)
    return ' '.join(line.split())


@dataclass
class Row:
    line_no: int          # 1-based line number within the page text
    raw: str              # original line text
    label: str            # text before the trailing amount tokens (leading amounts removed)
    amounts: list[str]    # trailing amount tokens, in printed order


def split_row(line: str, line_no: int = 0) -> Row:
    norm = normalize_line(line)
    tokens = norm.split(' ') if norm else []
    trailing: list[str] = []
    while tokens and is_amount_token(tokens[-1]):
        trailing.insert(0, tokens.pop())
    # Leading amounts are convenience-translation columns (e.g. CKH prints a US$ column first).
    while tokens and is_amount_token(tokens[0]):
        tokens.pop(0)
    label = NOTE_REF_RE.sub('', ' '.join(tokens)).strip()
    return Row(line_no=line_no, raw=line.strip(), label=label, amounts=trailing)


def page_rows(text: str) -> list[Row]:
    return [split_row(line, i) for i, line in enumerate(text.splitlines(), 1)]


class ExtractionError(ValueError):
    def __init__(self, reason: str, **detail):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _label_candidates(rows: list[Row], index: int, columns: int, max_join: int = 2) -> list[str]:
    """Row label plus labels joined with preceding wrapped lines that carry no full value set."""
    labels = [rows[index].label]
    joined = rows[index].label
    j = index - 1
    while j >= 0 and len(labels) <= max_join:
        prev = rows[j]
        if len(prev.amounts) >= columns:
            break
        if prev.label:
            joined = f'{prev.label} {joined}'.strip()
            labels.append(joined)
        j -= 1
    return labels


def find_row(text: str, label: str, columns: int, after: str | None = None,
             occurrence: int | None = None, max_join: int = 2, after_occurrence: int = 1) -> Row:
    """Locate exactly one table row on a page.

    ``label`` is a regular expression searched in the row label (and in the label
    joined with up to ``max_join`` wrapped preceding lines). ``after`` restricts the
    search to rows following the ``after_occurrence``-th line matching that regex (default:
    the first; v1.6 addition for tables that repeat a segment list). With no explicit
    ``occurrence``, several matches with *different* values are an error.
    """
    rows = page_rows(text)
    start = 0
    if after:
        after_re = re.compile(after, re.I)
        hits = [i for i, r in enumerate(rows) if after_re.search(normalize_line(r.raw))]
        hit = hits[after_occurrence - 1] if 1 <= after_occurrence <= len(hits) else None
        if hit is None:
            raise ExtractionError('anchor_not_found', anchor=after)
        start = hit + 1
    label_re = re.compile(label, re.I)
    matches: list[Row] = []
    for i in range(start, len(rows)):
        row = rows[i]
        if len(row.amounts) < columns:
            continue
        if any(label_re.search(c) for c in _label_candidates(rows, i, columns, max_join)):
            matches.append(row)
            if after and occurrence is None:
                break  # anchored searches take the first row after the anchor
    if not matches:
        raise ExtractionError('label_not_found', label=label)
    if occurrence is not None:
        if occurrence < 1 or occurrence > len(matches):
            raise ExtractionError('occurrence_out_of_range', label=label, found=len(matches))
        return matches[occurrence - 1]
    distinct = {tuple(m.amounts[-columns:]) for m in matches}
    if len(distinct) > 1:
        raise ExtractionError('ambiguous_label', label=label,
                              rows=[m.raw[:160] for m in matches[:5]])
    return matches[0]


def extract_text_value(text: str, pattern: str, group: int = 1) -> tuple[Decimal, int, str, str]:
    """Extract a number stated in prose (e.g. a dividend per share) via an explicit regex."""
    flat_lines = text.splitlines()
    regex = re.compile(pattern, re.I | re.S)
    # Search line windows so that a match can span a line break.
    for i in range(len(flat_lines)):
        window = ' '.join(' '.join(flat_lines[i:i + 3]).split())
        m = regex.search(window)
        if m and m.start() < len(' '.join(flat_lines[i].split())) + 1:
            printed = m.group(group)
            return Decimal(printed.replace(',', '')), i + 1, window[max(0, m.start() - 40):m.end() + 40], printed
    raise ExtractionError('text_pattern_not_found', pattern=pattern)


def _scale(value: Decimal | None, unit: str) -> Decimal | None:
    if value is None:
        return None
    return value * MULTIPLIERS[unit]


def _fmt(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    # Avoid scientific notation for whole numbers such as 1E+3.
    return format(normalized, 'f')


def printed_page(profile: dict, pdf_page: int) -> str | None:
    """Printed page label(s) for a PDF page, from the profile's explicit rule.

    rule {"offset": -2}             -> printed = pdf_page - 2
    rule {"offset": -4, "spread": true} -> two printed pages per PDF page (2*pdf+offset, +1)
    """
    rule = profile.get('printed_page_rule')
    if not rule:
        return None
    if rule.get('spread'):
        first = 2 * pdf_page + int(rule['offset'])
        return f'{first}-{first + 1}' if first >= 1 else None
    number = pdf_page + int(rule['offset'])
    return str(number) if number >= 1 else None  # cover/unnumbered pages


def extract_field(pages: list[str], spec: dict, profile: dict) -> dict:
    page_no = spec['page']
    if not 1 <= page_no <= len(pages):
        raise ExtractionError('page_out_of_range', page=page_no, page_count=len(pages))
    text = pages[page_no - 1]
    statement = profile.get('statements', {}).get(spec.get('statement', ''), {})
    header = spec.get('header_regex') or statement.get('header_regex')
    if header and not re.search(header, ' '.join(text.split()), re.I):
        raise ExtractionError('column_header_not_found', header=header, page=page_no)
    unit = spec.get('unit', profile['unit'])
    kind = spec.get('kind', 'amount')
    base = {
        'field': spec['field'],
        'definition': spec.get('definition'),
        'statement': spec.get('statement'),
        'fiscal_year': profile['fiscal_year'],
        'period_end': profile.get('period_end'),
        'currency': spec.get('currency', profile['currency']),
        'unit': unit,
        'kind': kind,
        'pdf_page': page_no,
        'printed_page': spec.get('printed_page') or printed_page(profile, page_no),
        'source_url': profile['source_url'],
        'method': 'text_regex' if 'pattern' in spec else 'table_row',
        'verification_status': 'machine_extracted',
    }
    if 'pattern' in spec:
        value, line_no, evidence, printed = extract_text_value(text, spec['pattern'], spec.get('group', 1))
        return {**base, 'value': _fmt(value), 'value_in_units': _fmt(_scale(value, unit)),
                'raw_token': printed, 'line': line_no, 'evidence': evidence[:300]}
    columns = int(spec['columns'])
    row = find_row(text, spec['label'], columns, after=spec.get('after'),
                   occurrence=spec.get('occurrence'), max_join=spec.get('max_join', 2))
    values = row.amounts[-columns:]
    column = int(spec.get('column', 0))
    token = values[column]
    value = parse_amount(token)
    if value is not None and spec.get('sign') == 'abs':
        value = abs(value)
    return {**base, 'value': _fmt(value), 'value_in_units': _fmt(_scale(value, unit)),
            'raw_token': token, 'row_values': values, 'column_index': column,
            'line': row.line_no, 'evidence': row.raw[:300]}


def _eval_sum(terms: Iterable[str], facts: dict) -> Decimal | None:
    total = Decimal(0)
    for term in terms:
        sign = Decimal(1)
        name = term
        if term.startswith('-'):
            sign, name = Decimal(-1), term[1:]
        elif term.startswith('+'):
            name = term[1:]
        fact = facts.get(name)
        if fact is None or fact.get('value') is None:
            return None
        total += sign * Decimal(fact['value'])
    return total


def derive_fields(specs: list[dict], facts: dict, profile: dict) -> list[dict]:
    out = []
    for spec in specs:
        value = _eval_sum(spec['sum'], facts)
        unit = spec.get('unit', profile['unit'])
        record = {
            'field': spec['field'], 'definition': spec.get('definition'), 'statement': spec.get('statement'),
            'fiscal_year': profile['fiscal_year'], 'period_end': profile.get('period_end'),
            'currency': spec.get('currency', profile['currency']), 'unit': unit,
            'kind': spec.get('kind', 'amount'),
            'value': _fmt(value), 'value_in_units': _fmt(_scale(value, unit)),
            'method': 'derived', 'derived_from': spec['sum'],
            'pdf_page': sorted({facts[t.lstrip('+-')]['pdf_page'] for t in spec['sum'] if t.lstrip('+-') in facts}) or None,
            'source_url': profile['source_url'],
            'verification_status': 'derived_from_machine_extracted' if value is not None else 'missing_inputs',
        }
        out.append(record)
        if value is not None:
            facts[spec['field']] = record
    return out


def run_checks(specs: list[dict], facts: dict) -> list[dict]:
    """Each check: {"name", "left": [terms], "right": [terms], "tolerance": "1"} (same unit)."""
    results = []
    for spec in specs:
        left = _eval_sum(spec['left'], facts)
        right = _eval_sum(spec['right'], facts)
        if right is not None and 'factor' in spec:
            right = right * Decimal(str(spec['factor']))
        tol = Decimal(str(spec.get('tolerance', '1')))
        if left is None or right is None:
            status = 'not_evaluated'
            diff = None
        else:
            diff = left - right
            status = 'pass' if abs(diff) <= tol else 'fail'
        results.append({'name': spec['name'], 'left': spec['left'], 'right': spec['right'],
                        'factor': spec.get('factor'),
                        'left_value': _fmt(left), 'right_value': _fmt(right),
                        'difference': _fmt(diff), 'tolerance': _fmt(tol), 'status': status})
    return results


def _ratio(facts: dict, num: str, den: str, places: str = '0.0001') -> str | None:
    a, b = facts.get(num), facts.get(den)
    if not a or not b or a.get('value') is None or b.get('value') is None:
        return None
    a_v, b_v = Decimal(a['value']), Decimal(b['value'])
    if b_v == 0 or a.get('unit') != b.get('unit') or a.get('currency') != b.get('currency'):
        return None
    return str((a_v / b_v).quantize(Decimal(places)))


def key_ratios(facts: dict, profile: dict) -> dict:
    """Transparent ratios from the extracted facts. Each ratio states its formula.

    Ratios whose inputs use different units/currencies are returned as null.
    Industry-specific caveats (e.g. banks) come from the profile.
    """
    skip = set(profile.get('ratios_not_meaningful', []))
    formulas = {
        'net_margin': ('net_income_attributable', 'revenue'),
        'operating_margin': ('operating_profit', 'revenue'),
        'return_on_equity_simple': ('net_income_attributable', 'equity_attributable'),
        'equity_ratio': ('total_equity', 'total_assets'),
        'liabilities_to_assets': ('total_liabilities', 'total_assets'),
        'cash_conversion': ('operating_cash_flow', 'net_profit'),
        'payout_ratio_per_share': ('dividend_per_share', 'eps_basic'),
        'cash_dividend_cover': ('free_cash_flow', 'dividends_paid_to_shareholders'),
    }
    for name, pair in profile.get('ratio_overrides', {}).items():
        formulas[name] = tuple(pair)
    out = {}
    for name, (num, den) in formulas.items():
        out[name] = {'value': None if name in skip else _ratio(facts, num, den),
                     'formula': f'{num} / {den}',
                     'note': 'not meaningful for this issuer' if name in skip else None}
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_profile(path: Path) -> dict:
    profile = json.loads(path.read_text(encoding='utf-8'))
    for key in ('symbol', 'fiscal_year', 'currency', 'unit', 'source_url', 'fields'):
        if key not in profile:
            raise ValueError(f'profile {path.name} missing {key}')
    if profile['unit'] not in MULTIPLIERS:
        raise ValueError(f'profile {path.name}: unsupported unit {profile["unit"]}')
    return profile


def extract_report(pages: list[str], profile: dict, pdf_sha256: str | None = None) -> dict:
    """Apply one issuer profile to page texts (index 0 = PDF page 1)."""
    facts: dict[str, dict] = {}
    extracted, errors = [], []
    expected_sha = profile.get('pdf_sha256')
    sha_status = 'not_checked'
    if expected_sha and pdf_sha256:
        sha_status = 'match' if expected_sha == pdf_sha256 else 'mismatch'
    for spec in profile['fields']:
        try:
            record = extract_field(pages, spec, profile)
        except ExtractionError as exc:
            errors.append({'field': spec['field'], 'pdf_page': spec.get('page'), 'reason': exc.reason, **exc.detail})
            continue
        facts[spec['field']] = record
        extracted.append(record)
    derived = derive_fields(profile.get('derived', []), facts, profile)
    checks = run_checks(profile.get('checks', []), facts)
    failed = [c for c in checks if c['status'] == 'fail']
    if sha_status == 'mismatch':
        status = 'document_changed'
    elif errors or failed:
        status = 'extraction_incomplete' if errors else 'consistency_check_failed'
    else:
        status = 'extracted_consistent'
    return {
        'symbol': profile['symbol'], 'company': profile.get('company'),
        'fiscal_year': profile['fiscal_year'], 'period_end': profile.get('period_end'),
        'accounting_standard': profile.get('accounting_standard'),
        'currency': profile['currency'], 'unit': profile['unit'],
        'source_url': profile['source_url'], 'pdf_sha256': pdf_sha256,
        'pdf_sha256_expected': expected_sha, 'pdf_sha256_status': sha_status,
        'page_count': len(pages), 'status': status,
        'facts': extracted, 'derived': derived, 'errors': errors, 'checks': checks,
        'ratios': key_ratios(facts, profile),
        'manual_review': profile.get('manual_review'),
        'caveats': profile.get('caveats', []),
        'warning': ('Machine-extracted values with page/line provenance and arithmetic checks. '
                    'They are not an audited dataset; see manual_review for human verification status.'),
    }
