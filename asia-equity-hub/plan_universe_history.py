"""Build an explicit missing-data matrix for every requested listing (no fabricated facts)."""
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    universe = json.loads((root / 'reports/universe/companies.json').read_text(encoding='utf-8'))
    result = {
        'schema_version': 1,
        'purpose': 'Unresolved company-listing coverage plan; does not replace existing issuer history',
        'years': list(range(2016, 2026)),
        'entries': [
            {'id': e['id'], 'requested_name': e['requested_name'], 'market': e['market'],
             'ticker': e['ticker'], 'years': {str(y): {'status': 'not_assessed', 'facts': None,
             'human_review': 'pending'} for y in range(2016, 2026)}}
            for e in universe['entries']
        ],
    }
    output = root / 'reports/coverage/universe_history_2016_2025.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{len(result['entries'])} listings x {len(result['years'])} fiscal years: not assessed")


if __name__ == '__main__':
    main()
