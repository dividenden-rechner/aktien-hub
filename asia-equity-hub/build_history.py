"""Build a first two-year history using only pinned FY2025 extraction evidence."""
import argparse
import json
from pathlib import Path
from app.history import build_history

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, default=Path('reports/extracted'))
    p.add_argument('--out', type=Path, default=Path('reports/history/history_2024_2025.json'))
    args = p.parse_args()
    result = build_history(args.input)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{len(result['companies'])} companies -> {args.out}")
