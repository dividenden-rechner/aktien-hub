from pathlib import Path
from app.universe import build_universe

if __name__ == '__main__':
    result = build_universe(Path('reports/universe/requested_companies.txt'), Path('reports/universe/companies.json'))
    print('Listings:', result['total_listings_requested'], 'Markets:', result['counts_by_market'])
