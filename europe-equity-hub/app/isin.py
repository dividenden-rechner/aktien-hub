"""ISIN format and check-digit validation (ISO 6166, Luhn on the letter-expanded string)."""
from __future__ import annotations

import re

ISIN_RE = re.compile(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$')


def isin_check_digit(body11: str) -> int:
    digits = ''.join(str(int(c, 36)) for c in body11)  # A=10 ... Z=35
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:  # rightmost digit of the expanded body is doubled
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10


def is_valid_isin(value: str | None) -> bool:
    if not value or not ISIN_RE.match(value):
        return False
    return isin_check_digit(value[:11]) == int(value[11])


def isin_country(value: str) -> str | None:
    return value[:2] if is_valid_isin(value) else None
