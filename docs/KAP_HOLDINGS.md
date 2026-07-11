# KAP Holdings Pipeline — Scoping Result & Spec

*Scoping sprint 2026-07-12. Verdict: **feasible with plain requests,
no browser needed.** Stock-level fund holdings are publicly accessible;
the pipeline below is verified end-to-end on live data.*

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
