"""Institutional-readiness audit: run programmatic checks against the
database and models, print findings for docs/AUDIT.md."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tefaslab import benchmarks as bm
from tefaslab import db, factors, metrics, quality

conn = db.connect()
print("=" * 70)
print("SECTION 1 — DATA LAYER")
print("=" * 70)

# 1.1 fund types present
types = pd.read_sql_query(
    "SELECT fund_type, COUNT(*) n FROM funds GROUP BY fund_type", conn)
print("\nfund types in DB:\n", types.to_string(index=False))

# 1.2 time-series integrity
neg = conn.execute("SELECT COUNT(*) FROM prices WHERE price < 0").fetchone()[0]
zero_aum = conn.execute(
    "SELECT COUNT(*) FROM prices WHERE aum = 0").fetchone()[0]
print(f"\nnegative NAV rows: {neg}; zero-AUM rows: {zero_aum}")

# extreme investor count jumps (>10x day over day)
inv = pd.read_sql_query(
    "SELECT code, date, investors FROM prices WHERE investors > 0 "
    "ORDER BY code, date", conn)
inv["prev"] = inv.groupby("code")["investors"].shift()
jumps = inv[(inv["prev"] > 100) & ((inv["investors"] / inv["prev"] > 10)
                                   | (inv["investors"] / inv["prev"] < 0.1))]
print(f"investor-count 10x jumps: {len(jumps)} "
      f"({jumps['code'].nunique()} funds)")

# 1.3 survivorship
last_date = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
dead = conn.execute(
    "SELECT COUNT(*) FROM (SELECT code, MAX(date) d FROM prices "
    "GROUP BY code) WHERE d < date(?, '-30 days')", (last_date,)).fetchone()[0]
total = conn.execute("SELECT COUNT(DISTINCT code) FROM prices").fetchone()[0]
universe = pd.read_sql_query(
    "SELECT substr(date,1,7) m, COUNT(DISTINCT code) n FROM prices "
    "GROUP BY m", conn)
print(f"\ndead funds retained in DB (no price for 30+ days): {dead}/{total}")
print(f"universe growth: {universe['n'].iloc[0]} funds "
      f"({universe['m'].iloc[0]}) -> {universe['n'].iloc[-1]} "
      f"({universe['m'].iloc[-1]})")

print("\n" + "=" * 70)
print("SECTION 2 — FLOW AUDIT: top 15 largest absolute daily flows")
print("=" * 70)
fl = pd.read_sql_query(
    "SELECT p.code, f.title, p.date, p.price, p.shares, p.aum FROM prices p "
    "JOIN funds f ON f.code=p.code WHERE p.shares IS NOT NULL "
    "ORDER BY p.code, p.date", conn)
fl["flow"] = fl.groupby("code")["shares"].diff() * fl["price"]
fl["nav_ret"] = fl.groupby("code")["price"].pct_change()
top = fl.reindex(fl["flow"].abs().sort_values(ascending=False).index).head(15)
top["flow_bn"] = (top["flow"] / 1e9).round(1)
top["nav_ret_pct"] = (top["nav_ret"] * 100).round(1)
top["suspect"] = top["nav_ret"].abs() > 0.10
print(top[["code", "date", "flow_bn", "nav_ret_pct",
           "suspect"]].to_string(index=False))
print(f"\nflows co-occurring with >10% NAV moves (restructuring suspects): "
      f"{int(top['suspect'].sum())}/15")

print("\n" + "=" * 70)
print("SECTION 3 — FACTOR MODEL")
print("=" * 70)
fx = pd.DataFrame({label: bm.load_series(conn, series).pct_change()
                   for label, (series, _lag) in factors.FACTORS.items()})
corr = fx.corr().round(2)
print("\nfactor return correlation matrix (daily, unlagged):")
print(corr.to_string())

# beta stability: YEF year by year
nav = pd.read_sql_query(
    "SELECT date, price FROM prices WHERE code='YEF' ORDER BY date",
    conn, parse_dates=["date"]).set_index("date")["price"]
bist = bm.load_series(conn, "bist100").pct_change().shift(1)
r = nav.pct_change()
print("\nYEF beta vs BIST100(+1) by year:")
for year in (2024, 2025, 2026):
    d = pd.concat([r, bist], axis=1, keys=["f", "b"]).dropna()
    d = d[d.index.year == year]
    if len(d) > 60:
        print(f"  {year}: beta {d['f'].cov(d['b']) / d['b'].var():.3f} "
              f"(n={len(d)})")

# alpha significance across universe
betas = factors.all_factor_betas(conn)
if "alpha_t" in betas.columns:
    sig = (betas["alpha_t"].abs() > 2).sum()
    print(f"\nfunds with |alpha t| > 2: {sig}/{len(betas)} "
          f"({sig / len(betas) * 100:.0f}%)")
else:
    print("\nalpha t-stats NOT COMPUTED — finding: rankings use raw alpha")

print("\n" + "=" * 70)
print("SECTION 4 — SCORE SENSITIVITY")
print("=" * 70)
comp = quality._components(conn, 0.40, 100e6, 500, 126)
base = quality.skill_scores(conn, components=comp)["skill_score"]
perturbed_weights = [
    {"alpha": 0.40, "consistency": 0.20, "downside": 0.20,
     "independence": 0.20},
    {"alpha": 0.30, "consistency": 0.30, "downside": 0.20,
     "independence": 0.20},
    {"alpha": 0.35, "consistency": 0.25, "downside": 0.30,
     "independence": 0.10},
]
orig = dict(quality.SKILL_WEIGHTS)
for w in perturbed_weights:
    quality.SKILL_WEIGHTS.update(w)
    alt = quality.skill_scores(conn, components=comp)["skill_score"]
    rho = base.rank().corr(alt.rank(), method="spearman")
    top20 = len(set(base.nlargest(20).index) & set(alt.nlargest(20).index))
    print(f"weights {list(w.values())}: rank corr {rho:.3f}, "
          f"top-20 overlap {top20}/20")
quality.SKILL_WEIGHTS.update(orig)

print("\n" + "=" * 70)
print("SECTION 5 — SECURITY / REPO HYGIENE")
print("=" * 70)
tracked = subprocess.run(["git", "ls-files"], capture_output=True,
                         text=True).stdout.splitlines()
bad = [f for f in tracked if f.endswith((".db", ".env", ".log"))
       or f.startswith(("data/", "logs/"))]
print(f"tracked files: {len(tracked)}; sensitive/artifact files tracked: "
      f"{bad or 'none'}")
secrets = subprocess.run(
    ["git", "grep", "-l", "-iE", "api_key|password|secret|token"],
    capture_output=True, text=True).stdout.splitlines()
secrets = [s for s in secrets if "audit" not in s]
print(f"files containing secret-like keywords: {secrets or 'none'}")

conn.close()
print("\naudit complete")
