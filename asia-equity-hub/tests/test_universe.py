import json
from pathlib import Path
import pytest
from app.universe import build_universe, parse_requested_companies, potential_cross_market_duplicates

ROOT = Path(__file__).resolve().parents[1]


def test_all_five_markets_and_immutable_source():
    data = json.loads((ROOT / 'reports/universe/companies.json').read_text(encoding='utf-8'))
    source = parse_requested_companies((ROOT / 'reports/universe/requested_companies.txt').read_text(encoding='utf-8'))
    assert data['entries'] == source
    assert set(data['counts_by_market']) == {'Hongkong', 'Singapur', 'China', 'Japan', 'Südkorea'}
    assert data['total_listings_requested'] == len(source)
    assert len({x['id'] for x in source}) == len(source)


def test_no_invented_tickers_or_facts():
    data = json.loads((ROOT / 'reports/universe/companies.json').read_text(encoding='utf-8'))
    assert all(x['ticker'] is None and x['ticker_status'] == 'unresolved' for x in data['entries'])
    assert all(x['human_review'] == 'pending' and x['data_status'] == 'not_imported' for x in data['entries'])
    assert all(x['target_fiscal_years'] == list(range(2016, 2026)) for x in data['entries'])


def test_cross_listings_not_silently_merged():
    data = json.loads((ROOT / 'reports/universe/companies.json').read_text(encoding='utf-8'))
    assert any(x['name'] == 'Bank of China' and set(x['markets']) == {'Hongkong', 'China'} for x in data['possible_cross_market_duplicates'])
    assert len([x for x in data['entries'] if x['requested_name'] == 'Bank of China']) == 2


def test_invalid_market_rejected():
    with pytest.raises(ValueError):
        parse_requested_companies('[Mars]\nExample')


def test_jardine_and_samsung_present():
    data = json.loads((ROOT / 'reports/universe/companies.json').read_text(encoding='utf-8'))
    names = {x['requested_name'] for x in data['entries']}
    assert {'Jardine Matheson Holdings', 'Samsung Electronics', 'Toyota Motor', 'Tencent Holdings', 'BYD'} <= names


def test_universe_history_plan_has_no_fake_zeroes():
    data = json.loads((ROOT / 'reports/coverage/universe_history_2016_2025.json').read_text(encoding='utf-8'))
    universe = json.loads((ROOT / 'reports/universe/companies.json').read_text(encoding='utf-8'))
    assert len(data['entries']) == len(universe['entries'])
    assert all(len(e['years']) == 10 for e in data['entries'])
    assert all(y['status'] == 'not_assessed' and y['facts'] is None for e in data['entries'] for y in e['years'].values())
