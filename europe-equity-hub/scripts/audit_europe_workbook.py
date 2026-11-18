#!/usr/bin/env python3
"""Read-only audit of the Europe workbook. Never promotes verification status."""
import argparse
import collections
import csv
import json
from pathlib import Path
from openpyxl import load_workbook

CANDIDATE_TABS = ('Ergaenzung_IT_PL_GR','Ergaenzung_ES_IE_CH_AT','Ergaenzung_FR_GB_Nordics')

def audit(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    report = {'source': Path(path).name, 'sheets': {}, 'candidate_rows': 0, 'existing_rows': 0,
              'countries': {}, 'missing_isin_candidates': 0, 'verified_candidates': 0,
              'warning': 'Counts are listing/candidate rows, not unique verified issuers.'}
    rows = []
    country_count = collections.Counter()
    for sheet in wb:
        sheet.reset_dimensions()
        iterator = sheet.iter_rows(values_only=True)
        header = next(iterator, ())
        headers = [str(x) if x is not None else '' for x in header]
        count = 0
        for values in iterator:
            if not any(x is not None for x in values):
                continue
            count += 1
            if sheet.title in CANDIDATE_TABS:
                d = dict(zip(headers, values))
                country = str(d.get('country') or '')
                country_count[country] += 1
                report['candidate_rows'] += 1
                if not d.get('isin'):
                    report['missing_isin_candidates'] += 1
                if str(d.get('verification_status') or '').strip().lower() == 'verified':
                    report['verified_candidates'] += 1
                rows.append({'source_tab': sheet.title, 'country': country,
                             'company_candidate': d.get('company_candidate') or '',
                             'isin': d.get('isin') or '', 'ticker': d.get('ticker') or '',
                             'verification_status': d.get('verification_status') or 'unverified',
                             'human_review': d.get('human_review') or 'pending'})
            elif sheet.title == 'Bestand_422':
                report['existing_rows'] += 1
        report['sheets'][sheet.title] = count
    report['countries'] = dict(sorted(country_count.items()))
    wb.close()
    return report, rows

def main():
    p = argparse.ArgumentParser()
    p.add_argument('workbook')
    p.add_argument('--out', default='artifacts/europe')
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary, rows = audit(args.workbook)
    (out / 'audit_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    with (out / 'candidate_review_queue.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['source_tab','country','company_candidate','isin','ticker','verification_status','human_review'])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
