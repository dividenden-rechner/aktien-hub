"""Import explicit issuer-published historical series without claiming PDF verification."""
from __future__ import annotations
import json
from pathlib import Path

ALLOWED_UNITS = {'million', 'units', 'cents', 'thousand', 'billion'}


def validate_official_history(payload: dict) -> dict:
    if payload.get('human_review') != 'pending':
        raise ValueError('New issuer-web history must remain pending human review')
    if payload.get('status') != 'issuer_web_transcribed_pending_pdf_review':
        raise ValueError('Issuer-web evidence must not masquerade as PDF-extracted')
    seen = set()
    for item in payload.get('facts', []):
        if not (2020 <= item['fiscal_year'] <= 2025):
            raise ValueError('Fiscal year outside target range')
        if item['currency'] != payload['currency'] or item['unit'] not in ALLOWED_UNITS:
            raise ValueError('Currency/unit mismatch')
        if not item.get('source_url', '').startswith('https://'):
            raise ValueError('Missing official source URL')
        if item.get('human_review') != 'pending' or item.get('verification_status') != 'issuer_web_transcribed':
            raise ValueError('No machine fact may be human verified')
        if not isinstance(item['value'], (int, float)) or isinstance(item['value'], bool):
            raise ValueError('Values must be numeric')
        key = (item['fiscal_year'], item['field'])
        if key in seen:
            raise ValueError('Duplicate metric and year')
        seen.add(key)
    return payload


def load_official_history(path: Path) -> dict:
    return validate_official_history(json.loads(path.read_text(encoding='utf-8')))
