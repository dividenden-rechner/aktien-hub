# Asia Equity Hub (v1.6)

## v1.6: Identitäten, Berichtsquellen und Zehnjahreshistorie

```bash
python build_identity_map.py --download   # 5 offizielle Listen laden, 451 Einträge zuordnen
python build_report_sources.py            # Jahresberichts-Kandidaten 2016-2025 (HKEXnews, CNINFO)
python build_ten_year_history.py          # 2016-2025 aus Zehnjahresübersichten (PDFs vorher laden)
python -m pytest -q
```

| Ergebnis | Datei |
|---|---|
| 451 Einträge, 364 gegen offizielle Listen bestätigt (HK 50, SG 30, CN 50, JP 234), Korea 73 ungeprüfte Kandidaten | `reports/universe/identity_map.json` |
| Berichtsquellen je Eintrag; HK/CN mit Dokumentkandidaten je Geschäftsjahr | `reports/sources/annual_report_sources.json` |
| 2016–2025 für CK Hutchison, Swire Pacific, First Pacific (420 Werte, alle Prüfungen bestanden) | `reports/history/ten_year_2016_2025.json` |

Details und offene Punkte: `CHANGELOG.md`, `docs/TESTSTATUS.md`.

---

# Asia Equity Hub (v1.1)

Python/FastAPI backend for Asian-listed companies. **v1.1 adds verified extraction of
primary financial statements from official FY2025 annual-report PDFs** for DBS (D05.SI),
BYD (002594.SZ), CK Hutchison (0001.HK), Swire Pacific (0019.HK) and First Pacific (0142.HK).
Only free, official sources are used.

## v1.1 at a glance

```bash
pip install -r requirements.txt
python process_reports.py --download   # download 5 official PDFs (SHA-256 pinned), ~60 MB
python extract_reports.py              # extract, check, cross-verify -> reports/extracted/
python -m pytest -q                    # 85 tests (live PDF test runs only if PDFs are cached)
uvicorn app.main:app --reload          # GET /v1/reports/D05.SI/statements?fiscal_year=2025
python export_aktien_hub.py            # export for the aktien-hub website
```

Results (2026-11-18): 5/5 PDFs downloaded through the project code; 116 table/text values +
12 derived values extracted; 24/24 arithmetic checks pass; a second PDF engine (pdfplumber)
finds every value on the cited page (75 on a row with the matching label); all comparable
IR-website reference values match; key pages were compared with the rendered PDF.
Per-value page/unit/currency/source documentation: `reports/extracted/VERIFIKATION_2025.md`.

- **Tested vs. not tested:** see `docs/TESTSTATUS.md` (German).
- **What changed and which bugs were fixed:** `CHANGELOG.md`.
- **Integration into the GitHub repository (aktien-hub):** `INTEGRATION.md`.

How the extraction works: each issuer has a reviewed profile (`reports/profiles/<symbol>.json`)
naming the PDF page, row label, column count and fiscal-year column. The extractor never guesses:
missing, ambiguous or misaligned rows are reported as errors; column headers are verified;
derived values are labelled as such; balance-sheet identity, profit split, cash reconciliation
and dividend components are checked; the PDF SHA-256 must match the profile. Values are
`machine_extracted`; `manual_review.human_review` stays `pending` until a person signs off.

---

# History (v0.1 - v1.0)

## v0.1 API scaffold

GitHub-ready, standalone Python/FastAPI backend for **Asian-listed companies**. It is not connected to any GitHub account or existing project. Endpoints provide company profile, historical prices, annual financial statements, dividends, and derived financial metrics. The initial provider is Yahoo Finance via `yfinance` for prototyping only.

## Start

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API docs.

## Examples

```bash
curl 'http://127.0.0.1:8000/v1/companies/0700.HK'
curl 'http://127.0.0.1:8000/v1/prices/D05.SI?period=1y'
curl 'http://127.0.0.1:8000/v1/financials/7203.T'
curl 'http://127.0.0.1:8000/v1/dividends/2330.TW'
curl 'http://127.0.0.1:8000/v1/metrics/600519.SS'
```

Other examples: `002594.SZ` (Shenzhen), `005930.KS` (Korea), `RELIANCE.NS` (India). Suffixes are mandatory to disambiguate listings. No name-to-ticker search yet.

## Implemented vs planned

**Implemented**: Asian ticker validation; profile; historical OHLCV; raw annual statements (up to provider coverage); dividend events; derived gross/operating/net/EBITDA margins, ROE, current ratio, net debt, interest coverage, FCF yield, price/FCF, EV/EBITDA, dividend/FCF coverage and capex/revenue; source labels and retrieval timestamps; error handling; unit tests.

**Not yet implemented**: full stock screener; issuer filings from HKEX/SGX/SSE/SZSE/EDINET/DART/MOPS; real-time licensed exchange quotes; financial normalization across IFRS/PRC GAAP/J-GAAP/K-IFRS/Ind AS; split-adjusted dividend growth; ROIC/ROCE/Altman/Piotroski/PEG; news/IR feeds; FX conversion; robust historical financials; local fiscal period normalization; cache/rate limiting; authentication; MCP transport; frontend; production observability. Do not display unimplemented indicators as if verified.

## Data integrity and usage

- **Not a live market-data service.** The MVP uses an unofficial data adapter; coverage, delay, availability, terms and redistribution rights must be verified before deployment.
- Prices and statements can use different reporting dates. Never label current market-cap-to-historical-FCF ratios as synchronized.
- Financial statement labels vary. Missing data is returned as `null`, never zero.
- Cash flow capex is usually negative. We subtract its absolute value to derive FCF.
- Financial statement periods use provider-provided period-end dates. Validate against primary issuer filings before publishing.
- Stock splits, special dividends, cross-listings, share classes, ADRs, differing fiscal years and FX rates need explicit handling in later phases.
- Company announcements should come from official exchange/IR feeds; generic news should be separately labeled.
- **No investment advice.** Derived classifications require transparent, tested thresholds.

## Recommended integration sequence

1. Integrate this standalone API as a backend service in the target GitHub repository.
2. Replace the prototype data adapter with licensed quote providers and official filings adapters per exchange; track source URL, filing date, fiscal period and accounting standard per field.
3. Normalize statements to canonical units, currencies and fiscal periods. Add provenance and validation tests.
4. Add PostgreSQL + Redis caching and scheduled ingestion; implement historical financial charts and metrics.
5. Add authenticated MCP tools (`search_company`, `get_company_profile`, `get_financials`, `get_quote`, `get_dividends`) and a frontend.

## Tests

```bash
pytest -q
```

## Dashboard aggregation (v0.2)

`GET /v1/hub/0700.HK?period=1y` combines profile, delayed daily OHLCV,
annual financials, dividends by calendar year, selected ratios, five-year
CAGRs and a transparent five-part heuristic scorecard. All missing values
remain `null`/`unknown`; a score is not investment advice. Financial statement
currency and price currency must match before market-cap-based ratios are
computed. Each response includes provenance and warnings. The backend does
not yet implement licensed live quotes, official exchange filings, news,
Piotroski/Altman, or the front-end dashboard.

Run tests: `python -m pytest -q`.

## Official Asian annual reports (v0.3)

This release adds an **official-filing ingestion pipeline** for Hong Kong, Singapore,
Shanghai and Shenzhen. It does **not** pretend that exchange-specific automated
filing discovery or audited financial statement parsing is already solved.

1. Find the company's annual report at the official disclosure portal:
   - Hong Kong: https://www.hkexnews.hk/
   - Singapore: https://www.sgx.com/securities/company-announcements
   - Shanghai: https://www.sse.com.cn/
   - Shenzhen: https://www.cninfo.com.cn/
2. Verify the issuer, fiscal year, report type and final official PDF URL.
3. Add a record to `reports/catalog.json`, e.g. (replace the illustrative URL):

```json
[
  {"symbol":"0700.HK","fiscal_year":2025,"report_type":"annual",
   "url":"https://www.hkexnews.hk/REPLACE_WITH_VERIFIED_PDF.pdf"}
]
```

4. Run `python sync_reports.py 0700.HK 2025` to fetch and cache the original
   PDF, SHA-256 checksum, ingestion metadata, and page-level raw text.
5. Use `GET /v1/reports/0700.HK` for the registered filings and status, or
   `GET /v1/reports/0700.HK/sources` for the official search portal.

The registry defaults to empty: **no real issuer filing has been downloaded or
verified in this release**. Sync is an explicit command, not a public write
endpoint. Only allowlisted HTTPS official domains are permitted; redirects are
rejected, downloads limited to 30 MB, and private network destinations blocked.
Scanned reports may produce little or no text; OCR is not yet included.

Next: implement exchange-specific discovery, structured XBRL/table extraction,
consolidated-statement mapping, currency/units validation, and audited metric
provenance. Do not use raw PDF text as verified numeric financial data.

## HKEX annual-report discovery (v0.4 experimental)

A **best-effort, no-cost HKEXnews search adapter** is now included. It queries
HKEX's undocumented title-search endpoint and filters for annual-report PDF
candidates mentioning the requested fiscal year. The endpoint may change,
block automated access, or return incomplete results. **A candidate is not
verified**, and no candidate is automatically added to the registry or ingested.

```bash
python discover_hkex.py 0700.HK 2025
curl 'http://127.0.0.1:8000/v1/reports/0700.HK/discover?fiscal_year=2025'
```

Verify each candidate against the issuer and report period at HKEXnews, then
register the verified URL in `reports/catalog.json` and run:

```bash
python sync_reports.py 0700.HK 2025
```

SGX and mainland China **still require manually verified URLs**. Extracted
PDF text is not yet a normalized financial statement. Do not use it to compute
financial ratios without audited field-level extraction. Live HKEX discovery
was not verified in this build; unit tests mock HTTP responses.

## v0.5: cautious financial-report extraction

After a **verified** report URL is registered in `reports/catalog.json` and
`python sync_reports.py SYMBOL YEAR` has downloaded its PDF, call:

`GET /v1/reports/0700.HK/extract?fiscal_year=2025`

This returns **page-cited candidate lines** for revenue, profit, assets,
liabilities, cash and operating cash flow. It deliberately does **not** infer
numbers, periods or currencies from flattened PDF tables: multi-column
statements require table-aware extraction and validation against the original
filing. Chinese and English labels are supported on a best-effort basis.

**Live verification:** HKEX endpoint connectivity could not be verified in the
build environment (DNS unavailable). The undocumented HKEX title-search may
change; no automatic registration or financial-field approval is performed.

**Next production steps:** verify HKEX discovery against real responses, add
issuer/period validation, structured table/XBRL parsing, explicit currency and
unit handling, year-column alignment, reconciliations, and SGX/CNINFO adapters.

## v0.6: year-aligned financial table candidates

`GET /v1/reports/0700.HK/tables?fiscal_year=2025` reads already ingested PDF page text and extracts *candidate* annual financial values only where an explicit two-year header and a nearby currency/scale are present. Each fact includes page, line, source URL, header and evidence. Conflicting observations are withheld. No auto-approval occurs.

`app.statement_metrics.calculate_reviewed(facts)` computes a small set of ratios only from inputs explicitly marked `verified`. This is a programmatic trust boundary, **not** a verification UI. Manual source-PDF review is still required. Many PDFs flatten tables or have separate year/unit rows and will yield no results; this is intentional. No OCR, live HKEX verification, SGX or mainland-China discovery is claimed in this release.


## Three real HK annual reports (v0.7 source registry)

Registered: CK Hutchison 0001.HK, Swire Pacific A 0019.HK, First Pacific 0142.HK (FY2025).
Sources and URLs are in `reports/catalog.json`. Source-backed selected FY2025 figures were in `reports/verified_facts_2025.json` (v1.1: replaced by `reports/reference_ir_2025.json`, used only as secondary cross-check). The latter are **not automatically extracted**, and should not be mixed across accounting definitions or currencies.

Run `python sync_sample_companies.py` in an environment with internet access to fetch and parse the PDF files. PDFs are NOT bundled: this environment could not resolve the report hosts. Downloads may fail if issuer sites block scripted access. The table parser remains experimental and must be reviewed before publishing numbers.

## v0.8 - report ingestion and comparison pipeline

The three issuers are registered in `reports/catalog.json`:

- CK Hutchison (`0001.HK`)
- Swire Pacific A (`0019.HK`)
- First Pacific (`0142.HK`)

To process locally **after installing dependencies**:

```bash
python process_reports.py --download
```

To inspect already-downloaded reports without networking:

```bash
python process_reports.py
```

The importer downloads a registered PDF, extracts page text, searches for explicit year/scale table rows, checks conflicting observations, compares any normalized references, and writes `reports/review/<report_id>.review.json`. **Comparisons never auto-approve figures**. Source data is considered unverified until manually checked against the original report. Metrics are intentionally empty until approved facts exist. Existing `reports/verified_facts_2025.json` contains issuer-specific metrics with non-equivalent definitions and is not silently normalized into generic financial fields.

A manually triggered GitHub Actions workflow is included in `.github/workflows/report-import.yml`. The report PDFs are not bundled; the workflow needs network access and is subject to the issuers' server availability and access conditions. Results are uploaded as workflow artifacts.

### Known limitations

- PDF servers were not reachable from the development container; no live PDF processing was verified here.
- The parser handles only explicit two-year text-preserved tables. Complex multi-column layouts, scanned pages, and financial-statement context require further work.
- The report importer limits documents to 30 MB and extracts the first 350 pages. Larger reports need explicit operator adjustments.
- This is not an audited or production-ready data pipeline; review original filings before publication or financial decisions.

## v0.9: SGX and mainland China disclosure discovery

`GET /v1/reports/002594.SZ/discover-asia?fiscal_year=2025` searches CNINFO's public
web endpoint for **unverified candidates** (may change or block requests).
`GET /v1/reports/600519.SS/discover-asia?fiscal_year=2025` works similarly.
`GET /v1/reports/D05.SI/discover-asia?fiscal_year=2025` returns the official
SGX announcements portal with `manual_search_required` because a stable,
free public programmatic annual-report search is not established. For HK use
`/v1/reports/0001.HK/discover-asia?fiscal_year=2025`.

**No discovered candidate is automatically added to the verified catalog.**
Verify the company, reporting period, report type, PDF URL and download rights.
The existing PDF pipeline can ingest a registered report afterwards.
The example companies are DBS (D05.SI), OCBC (O39.SI), Singtel (Z74.SI),
BYD (002594.SZ), Moutai (600519.SS) and China Merchants Bank (600036.SS).
These are *test symbols*, not claims of downloaded filings.


## v1.0: Official Singapore and China live-source checks

Two 2025 annual-report URLs have been registered: DBS Group (D05.SI, official issuer PDF) and BYD (002594.SZ, official Shenzhen exchange full annual-report PDF). These are **source-discovery results**, not confirmed local PDF ingestion.

To run real downloads on a network-enabled machine:

```bash
python -m pip install -r requirements.txt
python process_reports.py --download --symbol D05.SI --symbol 002594.SZ
```

`download_failed` means the server or network blocked access; `requires_review` means PDF text was extracted but figures are **not audited**. The existing PDF size/page limits apply. The developer environment DNS could not resolve the official PDF hosts; no local PDF-derived facts are claimed. See `reports/live_test_results.json` for observed results.

## Historie (v1.2)

```bash
python build_history.py
```

Erzeugt `reports/history/history_2024_2025.json` für die fünf bestehenden Unternehmen. 2024-Werte stammen **ausschließlich** aus den im FY2025-Extrakt vorhandenen Vergleichsspalten und sind weder separat durch pdfplumber noch menschlich geprüft. Fehlende und mehrdeutige Felder werden nicht ergänzt. Jardine Matheson (`J36.SI`) ist unter `reports/coverage/company_queue.json` mit offiziellen Berichtsfundstellen vorgemerkt, aber noch nicht importiert.

### Ausbauplan 2020–2025 (v1.3)

`python plan_history.py` generiert die transparente Abdeckungsmatrix unter `reports/coverage/coverage_2020_2025.json`. Die Warteliste enthält Jardine Matheson, OCBC, UOB, Kweichow Moutai und China Merchants Bank. Sie enthält für diese Kandidaten **keine** vorgetäuschten PDF-Downloads oder Finanzdaten. 2020–2023 sind für die fünf bestehenden Emittenten noch offen.

### v1.4: Jardine Matheson – offizielle Web-Historie
`reports/history/jardine_issuer_web_2021_2025.json` enthält 26 belegte historische Werte 2021–2025 aus Jardines offiziellen IR-Webseiten. Diese sind **nicht** aus einem lokal geprüften PDF extrahiert und bleiben `human_review: pending`. `python plan_history.py` integriert sie als eigenständige Evidenzklasse in die Abdeckungsmatrix. Für den PDF-basierten Import fehlen weiterhin SHA-gepinnter Download und Extraktionsprofil.

## v1.5: 451 gewünschte Unternehmen, fünf Märkte
`python build_universe.py` erzeugt das verlustfreie Unternehmensregister aus `reports/universe/requested_companies.txt`.
`python plan_universe_history.py` erzeugt einen Zehnjahres-Arbeitsplan 2016–2025, ohne fehlende Daten als 0 auszugeben.
Das Register ist **keine** geprüfte Ticker-/Listingdatenbank. Insbesondere historische Delistings, Umbenennungen und A-/H-Aktien müssen vor dem Import gesondert geprüft werden. Die bisherigen geprüften Extraktionsroutinen und der menschliche Prüfvorbehalt bleiben bestehen.
