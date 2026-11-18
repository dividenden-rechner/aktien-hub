"""Download all registered annual reports (v1.1: 5 issuers, SHA-256 pinned).

Kept for backwards compatibility; prefer `python process_reports.py --download`.
"""
import logging
from app.reports import load_catalog, sync_report

if __name__ == "__main__":
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    for entry in load_catalog():
        try:
            meta = sync_report(entry)
            print(entry["symbol"], "OK", meta["page_count"], "pages", meta["sha256"][:12])
        except Exception as exc:
            print(entry["symbol"], "FAILED", type(exc).__name__, str(exc))
