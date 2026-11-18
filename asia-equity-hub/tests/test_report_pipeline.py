from app.reports import load_catalog
import json
from pathlib import Path
from app.report_pipeline import compare_facts, process_cached, run_pipeline
from app.reports import report_key


def test_compare_never_auto_verifies():
    candidates = [{'field':'revenue','fiscal_year':2025,'currency':'HKD','value':'1000000','page':5}]
    refs = [{'field':'revenue','fiscal_year':2025,'currency':'HKD','value':'1000000'}]
    result = compare_facts(candidates, refs)
    assert result[0]['comparison'] == 'within_tolerance'
    assert result[0]['verification_status'] == 'requires_manual_review'


def test_comparison_mismatch_and_missing():
    c = [{'field':'revenue','fiscal_year':2025,'currency':'HKD','value':'100'},
         {'field':'net_income','fiscal_year':2025,'currency':'HKD','value':'20'}]
    r = [{'field':'revenue','fiscal_year':2025,'currency':'HKD','value':'200'}]
    assert [x['comparison'] for x in compare_facts(c, r)] == ['mismatch','no_reference']


def test_cached_pipeline(tmp_path):
    entry={'symbol':'0019.HK','fiscal_year':2025,'report_type':'annual','url':'https://www1.hkexnews.hk/example.pdf'}
    key=report_key(entry)
    (tmp_path/'cache').mkdir()
    (tmp_path/'cache'/f'{key}.pages.json').write_text(json.dumps([
        {'page':17,'text':'HKD million\n2025  2024\nRevenue  90,467  85,000\nOperating profit  4,454  4,000'}
    ]))
    result=process_cached(entry,root=tmp_path,reference_rows=[{'symbol':'0019.HK','field':'revenue','fiscal_year':2025,'currency':'HKD','value':'90467000000'}])
    assert result['status']=='requires_review'
    assert result['reference_comparisons'][0]['comparison']=='within_tolerance'
    assert result['metrics']['years']==[]
    assert (tmp_path/'review'/f'{key}.review.json').exists()


def test_missing_reports_are_explicit():
    result=run_pipeline(download=False)
    assert result['summary']['total'] == len(load_catalog())
    assert all(x['status'] in ('not_ingested','requires_review') for x in result['results'])
