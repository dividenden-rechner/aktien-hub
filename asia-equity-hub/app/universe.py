"""Lossless requested-company universe; identity and ticker resolution are separate steps."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

MARKETS = {"Hongkong": "HKEX", "Singapur": "SGX", "China": "SSE_OR_SZSE", "Japan": "TSE", "Südkorea": "KRX"}


def parse_requested_companies(text: str) -> list[dict]:
    entries = []
    market = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            market = line[1:-1]
            if market not in MARKETS:
                raise ValueError(f"Unknown market: {market}")
            continue
        if market is None:
            raise ValueError("Company without market heading")
        for name in line.rstrip('.').split(', '):
            name = name.strip()
            if not name:
                raise ValueError("Empty company name")
            entries.append({
                "id": f"{market.lower().replace('ü','ue')}-{len(entries)+1:04d}",
                "requested_name": name,
                "market": market,
                "exchange": MARKETS[market],
                "ticker": None,
                "ticker_status": "unresolved",
                "issuer_identity_status": "unresolved",
                "data_status": "not_imported",
                "human_review": "pending",
                "target_fiscal_years": list(range(2016, 2026)),
            })
    return entries


def potential_cross_market_duplicates(entries: list[dict]) -> list[dict]:
    by_name = {}
    for entry in entries:
        by_name.setdefault(entry['requested_name'].casefold(), []).append(entry)
    return [{"name": group[0]['requested_name'], "markets": [e['market'] for e in group],
             "entry_ids": [e['id'] for e in group], "status": "requires_identity_review"}
            for group in by_name.values() if len({e['market'] for e in group}) > 1]


def build_universe(source: Path, output: Path) -> dict:
    entries = parse_requested_companies(source.read_text(encoding='utf-8'))
    if not entries:
        raise ValueError('Empty universe')
    counts = dict(Counter(e['market'] for e in entries))
    result = {"schema_version": 1, "source": source.name, "entries": entries,
              "counts_by_market": counts, "total_listings_requested": len(entries),
              "possible_cross_market_duplicates": potential_cross_market_duplicates(entries),
              "note": "Requested listing candidates, not verified issuer identities or extracted financial data."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result
