from app.extract import candidates_from_pages

def test_candidates_are_not_reported_as_verified_financials():
    pages=[{'page':7,'text':'Revenue 2025 2024\nRevenue 47,900 43,100\nTotal assets 300 250\nNet profit (2,300) 2,100'}]
    result=candidates_from_pages(pages)
    assert result['status']=='unverified_candidates'
    assert result['fields']['revenue'][0]['page']==7
    assert result['fields']['revenue'][0]['verification_status']=='requires_manual_table_review'
    assert result['fields']['revenue'][0]['numeric_tokens']==['2025','2024']
    assert 'value' not in result['fields']['revenue'][0]

def test_no_guess_when_no_evidence():
    result=candidates_from_pages([{'page':1,'text':'Revenue\n2025 2024\nNo numbers in the label'}])
    assert result['fields']['revenue']==[]

def test_chinese_evidence():
    result=candidates_from_pages([{'page':12,'text':'营业收入 1,234 1,100'}])
    assert result['fields']['revenue'][0]['page']==12
