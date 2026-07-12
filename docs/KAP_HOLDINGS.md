# KAP Holdings Pipeline

*Scoped and **built** 2026-07-12. Stock-level fund holdings are
publicly accessible with plain requests; the pipeline below runs in
production ([tefaslab/kap.py](../tefaslab/kap.py)).*

## Status: what is DONE

| Piece | State |
|---|---|
| ID scanner (`holdings scan`) | ✅ working; idempotent, retries flaky responses, stops after 400 consecutive empties |
| PDF download + Java-wrapper stripping | ✅ working |
| Table parser (`parse_pdf_holdings`) | ✅ working — position-based row reconstruction; on the test fund: 89/89 holdings, 0 missing values, **weights sum to 98.1%** (rest is cash) |
| `fund_holdings` table + `kap_disclosures` ledger | ✅ in the shared DB |
| Queries: `holdings who ASELS`, `holdings fund IJZ`, `holdings stats` | ✅ CLI |
| Analytics: `crowding` (breadth of ownership), `active` (peer active share), `attrib` (stock-level contribution) | ✅ [ownership.py](../tefaslab/ownership.py) — each reports its own universe size |
| Nightly integration | ✅ pipeline scans forward from the id frontier (≤2,500 ids/night) and parses new reports |

## Upsides (why this is worth it)

1. **Truly stock-level**: ticker, name, ISIN, quantity, unit price,
   purchase date, market value, weight — per holding, per fund, per
   month. Verified against real reports (a eurobond fund and an equity
   fund with 45 TR + 44 foreign positions).
2. **Free and legal**: public disclosures, polite request rates, no
   scraping of protected pages.
3. **Self-validating**: weights sum to ~100% per fund — every parsed
   report carries its own consistency check.
4. **Foreign holdings included**: US/EU ISINs come through, so foreign
   equity funds' books (Nasdaq names etc.) are visible too — not just
   BIST positions.
5. Unlocks the roadmap items that need holdings: crowding, active
   share, holdings-based closet-index detection, true stock-selection
   attribution, the stock↔fund explorer.

## Downsides & limitations (accepted, documented)

1. **History is forward-only.** IDs can't be enumerated per fund;
   holdings history accumulates from the first scan (Apr-2026 reports
   are the earliest captured). There is no practical deep backfill.
2. **The export endpoint is flaky**: under load it intermittently
   returns empty bodies for ids that exist. Mitigation: per-id retry +
   idempotent rescans (empty ids are rechecked on the next pass; found
   ids are never re-fetched). A range converges over 2–3 passes.
3. **Scanning is brute-force**: most ids belong to other disclosure
   types (companies, notices), so ~90%+ of requests are discarded.
   ~1–2.5k ids/night ≈ 30–45 min of polite crawling in the pipeline.
4. **Not all funds file usefully**: money-market/serbest funds may file
   stub reports; coverage is naturally best for securities-holding
   funds (which is where holdings matter).
5. **Parser assumes the SPK template.** It is position-based (x/y
   word coordinates), so a template redesign would break it loudly
   (zero rows parsed → status `error`, visible in `holdings stats`).
6. **Fund-code resolution** relies on the code appearing in the PDF
   header or the title matching TEFAS registry; unresolved reports are
   marked `error` rather than guessed.
7. Weight column semantics: three weight variants exist in the table
   (FPD/group/FTD); we store the fund-total-value weight. Values are
   nominal TRY at report date.
8. **Active share is peer-relative, not index-relative** — official
   BIST constituent weights aren't in the database, so `holdings
   active` measures differentiation from the covered peer aggregate.
9. **Attribution covers priced holdings only**: TR tickers have local
   prices; foreign holdings (US/EU) land in the residual until foreign
   price series are added. The output states explained-vs-actual
   explicitly.

## What was established

1. **Where holdings live.** Every fund files a monthly **"Portföy
   Dağılım Raporu"** disclosure on KAP. The disclosure body is a stub;
   the data is a PDF attachment containing section
   *III — FON PORTFÖY DEĞERİ TABLOSU*: the full security-by-security
   portfolio — ticker, name, **ISIN**, quantity, unit price, purchase
   date, market value, and weight. Verified on a bond fund (eurobond
   positions) and an equity fund (89 ISINs: 45 TR stocks + 33 US +
   others), both April 2026 reports.
2. **Which endpoints are open.** KAP's *query/list* APIs are
   bot-blocked (HTTP 666), but its *content* endpoints accept plain
   requests:
   - `GET /tr/Bildirim/{id}` — disclosure page, server-rendered
     (metadata + attachment objIds)
   - `GET /tr/api/notification/export/excel/{id}` — 9 KB export
     (cheap fingerprinting: fund name, report type)
   - `GET /tr/api/file/download/{objId}` — the attachment. Quirk: the
     file arrives wrapped in a Java-serialization header; the real PDF
     starts at the `%PDF` byte offset (~27 bytes in).
3. **How to enumerate.** Disclosure IDs are globally sequential. Fund
   houses file monthly reports in bulk (e.g. İş Portföy's funds occupy
   a contiguous ID block). A daily scanner walks new IDs via the cheap
   excel export, keeps `Portföy Dağılım` hits, and resolves their PDFs.
   ~1–2k new IDs/day across all of KAP ≈ 30 min of polite crawling.

## Pipeline spec (v1)

```
daily:  scan new ids ──▶ filter "Portföy Dağılım Raporu"
                     ──▶ Bildirim page ─▶ fund + objId
                     ──▶ download PDF (strip wrapper)
                     ──▶ parse III. FON PORTFÖY DEĞERİ TABLOSU
                     ──▶ fund_holdings(code, period, isin, ticker,
                                        quantity, value, weight)
```

- **Parser approach**: rows are ISIN-anchored; pypdf text extraction
  scrambles column alignment, so v1 should use layout-aware extraction
  (pdfplumber) with the SPK-standard template. Fund houses share the
  template — differences are cosmetic.
- **ISIN → ticker matching**: TR ISINs map to our `stocks` registry;
  foreign ISINs (US/IE/…) kept as-is.
- **History**: enumeration only works forward (plus whatever recent
  ID ranges are scanned retroactively). Holdings history accumulates
  from the start date — a reason to start the scanner early.

## What this unlocks (in order)

1. `fund_holdings` table → **which funds own which stocks**
2. Crowding: how many funds hold ASELS; concentration risk
3. **Active share** vs BIST100/30 for every equity fund → upgrades the
   closet-index study from R²-based to holdings-based
4. **True attribution**: stock selection vs sector allocation vs
   market — replaces "unexplained return" with named stocks
5. Stock ↔ fund relationship explorer in the dashboard

## Verification artifacts

- `scripts/kap_scan.py` — ID-range scanner (fingerprints report types)
- `scripts/kap_pdf_test.py` — PDF download + wrapper stripping (bond fund)
- `scripts/kap_equity_test2.py` — equity fund verification (89 ISINs)
- Sample PDFs in `data/kap_scan/` (gitignored)
