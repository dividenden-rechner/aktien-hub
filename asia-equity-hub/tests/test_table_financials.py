from app.table_financials import extract_year_tables
from app.statement_metrics import calculate_reviewed

def test_aligned_rows():
    pages=[{'page':5,'text':'Consolidated income statement\nHKD million\n2025    2024\nRevenue    12,500    11,000\nNet profit    (500)    300'}]
    r=extract_year_tables(pages,'https://www1.hkexnews.hk/report.pdf')
    assert len(r['facts'])==4
    assert next(x for x in r['facts'] if x['field']=='revenue' and x['fiscal_year']==2025)['value']=='12500000000'
    assert next(x for x in r['facts'] if x['field']=='net_income' and x['fiscal_year']==2025)['value']=='-500000000'
    assert all(x['verification_status']=='machine_extracted_requires_review' for x in r['facts'])

def test_no_units_no_facts():
    assert extract_year_tables([{'page':1,'text':'2025    2024\nRevenue    500    400'}])['facts']==[]

def test_conflicts_are_excluded():
    p=[{'page':1,'text':'HKD million\n2025    2024\nRevenue    500    400'}, {'page':2,'text':'HKD million\n2025    2024\nRevenue    600    400'}]
    r=extract_year_tables(p)
    assert len(r['conflicts'])==1
    assert not any(f['fiscal_year']==2025 for f in r['facts'])

def test_unverified_cannot_create_metrics():
    f=[{'field':'revenue','fiscal_year':2025,'currency':'HKD','value':'100','verification_status':'machine_extracted_requires_review'},
       {'field':'net_income','fiscal_year':2025,'currency':'HKD','value':'20','verification_status':'verified'}]
    assert calculate_reviewed(f)['years'][0]['net_margin'] is None
    f[0]['verification_status']='verified'
    assert calculate_reviewed(f)['years'][0]['net_margin']=='0.2000'
