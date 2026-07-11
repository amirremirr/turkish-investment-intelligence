"""Test the production parser on the saved IJZ PDF."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tefaslab.kap import parse_pdf_holdings  # noqa: E402

pdf = open("data/kap_scan/IJZ_portfolio.pdf", "rb").read()
code, rows = parse_pdf_holdings(pdf)
print("fund code:", code, "| holdings:", len(rows))
tr = [r for r in rows if r["isin"].startswith("TR")]
print("TR holdings:", len(tr))
w = sum(r["weight_pct"] or 0 for r in rows)
print(f"sum of weights: {w:.1f}%")
missing_w = sum(1 for r in rows if r["weight_pct"] is None)
missing_v = sum(1 for r in rows if r["value"] is None)
print(f"rows missing weight: {missing_w}, missing value: {missing_v}")
print("\ntop 10 by weight:")
for r in sorted(rows, key=lambda r: -(r["weight_pct"] or 0))[:10]:
    print(f"  {str(r['ticker']):<8} {r['isin']}  w={r['weight_pct']}  "
          f"val={r['value']}  {str(r['name'])[:32]}")
