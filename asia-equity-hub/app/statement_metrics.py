"""Calculate transparent ratios from reviewed annual facts only."""
from decimal import Decimal

def calculate_reviewed(facts: list[dict]) -> dict:
    approved=[f for f in facts if f.get('verification_status')=='verified']
    groups={}
    for f in approved:
        groups.setdefault((f['fiscal_year'],f['currency']),{})[f['field']]=Decimal(str(f['value']))
    result=[]
    for (year,currency),v in sorted(groups.items()):
        def ratio(a,b):
            if a not in v or b not in v or v[b]==0: return None
            return str((v[a]/v[b]).quantize(Decimal('0.0001')))
        result.append({'fiscal_year':year,'currency':currency,'net_margin':ratio('net_income','revenue'),
                       'operating_margin':ratio('operating_profit','revenue'),
                       'debt_to_assets':ratio('total_liabilities','total_assets'),
                       'cash_to_assets':ratio('cash','total_assets'),
                       'status':'calculated_from_verified_facts'})
    return {'years':result,'warning':'Only manually verified, same-currency annual inputs are used.'}
