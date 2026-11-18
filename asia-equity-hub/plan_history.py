"""Generate transparent 2020-2025 coverage, never fill missing years with estimates."""
import argparse
from pathlib import Path
from app.coverage import create_coverage

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=2020)
    parser.add_argument('--end', type=int, default=2025)
    args = parser.parse_args()
    result = create_coverage(Path('reports/history/history_2024_2025.json'),
                             Path('reports/coverage/company_queue.json'),
                             Path('reports/coverage/coverage_2020_2025.json'), args.start, args.end)
    print(f"Coverage for {len(result['companies'])} companies, {len(result['target_years'])} fiscal years")
