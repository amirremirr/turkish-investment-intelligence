"""Command-line interface.

Examples:
  python -m tefaslab ingest --start 2024-01-01 --end 2026-07-10
  python -m tefaslab update
  python -m tefaslab top --by sharpe --n 20 --rf 0.40
  python -m tefaslab fund AFT --rf 0.40
"""

from __future__ import annotations

import argparse
import json
from datetime import date

import pandas as pd

import sys

from . import (benchmarks, classify, compare, db, factors, flows, health,
               ingest, memo, metrics, pipeline, quality, report, research,
               rolling, smartmoney, stocks)


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def cmd_ingest(args) -> None:
    totals = ingest.ingest_range(
        args.start, args.end, fund_type=args.type, fund_code=args.fund or "",
        with_allocations=not args.no_allocations)
    print(f"Done: {totals}")


def cmd_update(args) -> None:
    totals = ingest.update(fund_type=args.type,
                           with_allocations=not args.no_allocations)
    print(f"Done: {totals}")


def cmd_top(args) -> None:
    conn = db.connect()
    table = metrics.compute_metrics(conn, fund_type=args.type, rf=args.rf,
                                    min_obs=args.min_obs)
    conn.close()
    if args.category:
        table = table[table["category"].str.contains(args.category,
                                                     case=False, na=False)]
    if args.min_aum:
        table = table[table["aum"] >= args.min_aum * 1e6]
    if args.min_investors:
        table = table[table["investors"] >= args.min_investors]
    table = table.sort_values(args.by, ascending=False).head(args.n)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 40)
    fmt = table.copy()
    for col in ("ret_1m", "ret_3m", "ret_6m", "ret_1y", "excess_1y", "max_dd"):
        fmt[col] = (fmt[col] * 100).round(1)
    for col in ("ann_vol", "sharpe", "sortino", "beta"):
        fmt[col] = fmt[col].round(2)
    fmt["aum"] = (fmt["aum"] / 1e9).round(2).rename("aum_bn")
    print(fmt.to_string())
    if args.csv:
        table.to_csv(args.csv)
        print(f"\nSaved full table to {args.csv}")


def cmd_fund(args) -> None:
    conn = db.connect()
    report = metrics.fund_report(conn, args.code, rf=args.rf)
    conn.close()
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_benchmarks(args) -> None:
    counts = benchmarks.fetch_benchmarks(start=args.start)
    print(f"Done: {counts}")


def cmd_classify(args) -> None:
    conn = db.connect()
    counts = classify.classify_all(conn)
    conn.close()
    print(counts.to_string())


def cmd_flows(args) -> None:
    conn = db.connect()
    market = flows.market_flows(conn, days=args.days, fund_type=args.type)
    top = flows.top_fund_flows(conn, days=args.days, n=args.n,
                               fund_type=args.type)
    conn.close()
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 40)
    print(f"== market net flow, last {min(args.days, 10)} days (mn TRY) ==")
    print((market.tail(10) / 1e6).round(0).to_string())
    total = market["net_flow_try"].sum()
    print(f"\n{args.days}-day total: {total / 1e9:,.2f} bn TRY")
    print(f"\n== top fund flows over {args.days} days (mn TRY) ==")
    fmt = top.copy()
    fmt["net_flow_try"] = (fmt["net_flow_try"] / 1e6).round(0)
    print(fmt.rename(columns={"net_flow_try": "net_flow_mn"}).to_string())


def cmd_factors(args) -> None:
    conn = db.connect()
    if args.code:
        result = factors.fund_factor_model(conn, args.code, days=args.days)
        conn.close()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    table = factors.all_factor_betas(conn, days=args.days)
    conn.close()
    if args.category:
        table = table[table["category"].str.contains(args.category,
                                                     case=False, na=False)]
    table = table.sort_values("alpha_annual", ascending=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 40)
    print(table.head(args.n).round(3).to_string())
    if args.csv:
        table.to_csv(args.csv)
        print(f"\nSaved full table to {args.csv}")


def cmd_rolling(args) -> None:
    conn = db.connect()
    df = rolling.fund_rolling(conn, args.code, rf=args.rf,
                              window=args.window)
    conn.close()
    view = rolling.monthly_view(df)
    fmt = view.copy()
    fmt["roll_return"] = (fmt["roll_return"] * 100).round(1)
    fmt["drawdown"] = (fmt["drawdown"] * 100).round(1)
    for c in ("roll_vol", "roll_sharpe", "roll_beta"):
        if c in fmt:
            fmt[c] = fmt[c].round(2)
    print(f"{args.code.upper()} — {args.window}d rolling, month-end snapshots")
    print(fmt.to_string())
    if args.csv:
        df.to_csv(args.csv)
        print(f"\nSaved daily series to {args.csv}")


def cmd_compare(args) -> None:
    conn = db.connect()
    table = compare.compare_funds(conn, args.codes, rf=args.rf)
    conn.close()
    pd.set_option("display.width", 250)
    print(table.to_string())


def cmd_smartmoney(args) -> None:
    conn = db.connect()
    cf = smartmoney.category_flows(conn, days=args.days)
    rot = smartmoney.category_rotation(conn, months=args.months)
    mood = smartmoney.risk_appetite(conn, days=args.days)
    conn.close()
    pd.set_option("display.width", 250)
    print(f"== net flows by category, last {args.days} days ==")
    print(cf[["net_flow_bn"]].to_string())
    print(f"\n== AUM share by category, month-end (%) ==")
    print(rot.to_string())
    print("\n== investor risk appetite ==")
    for k, v in mood.items():
        print(f"  {k}: {v}")


def cmd_quality(args) -> None:
    conn = db.connect()
    fn = {"skill": quality.skill_scores,
          "suitability": quality.suitability_scores,
          "combined": quality.combined_scores}[args.view]
    kwargs = {} if args.view == "combined" \
        else {"within_category": args.within_category}
    table = fn(conn, rf=args.rf, min_aum=args.min_aum * 1e6,
               min_investors=args.min_investors, **kwargs)
    conn.close()
    if args.category:
        table = table[table["category"].str.contains(args.category,
                                                     case=False, na=False)]
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 40)
    fmt = table.head(args.n).copy()
    for c in ("ret_1y", "max_dd", "retention_90d"):
        if c in fmt:
            fmt[c] = (fmt[c] * 100).round(1)
    for c in ("sharpe", "alpha_annual", "consistency", "r_squared"):
        if c in fmt:
            fmt[c] = fmt[c].round(2)
    fmt["aum"] = (fmt["aum"] / 1e9).round(2)
    print(fmt.to_string())
    if args.csv:
        table.to_csv(args.csv)
        print(f"\nSaved full table to {args.csv}")


def cmd_report(args) -> None:
    from pathlib import Path
    from datetime import date
    conn = db.connect()
    text = report.build_report(conn)
    conn.close()
    out_dir = Path(args.save)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{date.today():%Y-%m}.md"
    path.write_text(text, encoding="utf-8")
    print(text[:1500])
    print(f"\n... saved full report to {path}")


def cmd_daily(args) -> None:
    code = pipeline.run(skip_raw=args.skip_raw, rf=args.rf)
    sys.exit(code)


def cmd_stocks(args) -> None:
    conn = db.connect()
    if args.sectors:
        n = stocks.enrich_sectors(conn)
        conn.close()
        print(f"Sector data fetched for {n} tickers")
        return
    n = stocks.update_registry(conn)
    print(f"Ticker registry: {n} listings from KAP")
    if args.registry_only:
        conn.close()
        return
    if args.update:
        total = stocks.update_prices(conn)
    else:
        total = stocks.ingest_prices(conn, start=str(args.start),
                                     tickers=args.tickers)
    conn.close()
    print(f"Done: {total:,} price rows")


def cmd_memo(args) -> None:
    conn = db.connect()
    text = memo.generate_memo(conn, args.code, rf=args.rf)
    conn.close()
    print(text)
    if args.save:
        with open(args.save, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"\nSaved to {args.save}")


def cmd_research(args) -> None:
    conn = db.connect()
    pd.set_option("display.width", 220)
    if args.study == "flows":
        print(f"Do {args.category} fund flows predict future BIST100 "
              "returns?\n(beta = % BIST move per 1% AUM flow; caveat: "
              "overlapping horizons inflate t-stats)\n")
        print(research.flow_predictability(conn, args.category,
                                           regime=args.regime)
              .round(3).to_string())
        if args.regime:
            print(f"\n(regime: {args.regime} — trailing 21d BIST vol "
                  "vs median split)")
    elif args.study == "flows-by-category":
        print("Flow -> future BIST return (21d horizon) by category:\n")
        print(research.flow_predictability_by_category(conn)
              .round(3).to_string())
    elif args.study == "flows-oos":
        print(f"Out-of-sample validation ({args.category}, 21d horizon, "
              "split 2026-01-01):\n")
        print(research.flow_predictability_oos(conn, args.category)
              .round(3).to_string())
    elif args.study == "diagnostics":
        print("Factor-model sanity by category "
              "(mean betas should match mandates):\n")
        print(factors.category_diagnostics(conn).to_string())
    elif args.study == "chasing":
        print(f"Do investors chase past {args.category} returns?\n"
              "(beta = weekly flow %AUM per 100% trailing return)\n")
        print(research.performance_chasing(conn, args.category)
              .round(3).to_string())
    elif args.study == "closet":
        summary, detail = research.closet_index(conn,
                                                min_aum=args.min_aum * 1e6)
        print("Are 'active' Turkish equity funds actually active?\n")
        print(summary.to_string())
        print("\n== most index-like (closet index candidates) ==")
        pd.set_option("display.max_colwidth", 45)
        print(detail.head(10).round(3).to_string())
        print("\n== most active ==")
        print(detail.tail(10).round(3).to_string())
    conn.close()


def cmd_health(args) -> None:
    conn = db.connect()
    code = health.report(conn)
    conn.close()
    sys.exit(code)


def cmd_stats(args) -> None:
    conn = db.connect()
    n_funds = conn.execute("SELECT COUNT(*) FROM funds").fetchone()[0]
    n_prices = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    n_alloc = conn.execute("SELECT COUNT(*) FROM allocations").fetchone()[0]
    dates = conn.execute("SELECT MIN(date), MAX(date) FROM prices").fetchone()
    conn.close()
    print(f"funds:       {n_funds:>12,}")
    print(f"price rows:  {n_prices:>12,}")
    print(f"alloc rows:  {n_alloc:>12,}")
    print(f"date range:  {dates[0]} .. {dates[1]}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="tefaslab",
                                     description="TEFAS fund data pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="download a historical date range")
    p.add_argument("--start", type=_parse_date, required=True)
    p.add_argument("--end", type=_parse_date, default=date.today())
    p.add_argument("--type", choices=["YAT", "EMK", "BYF", "GYF", "GSYF"],
                   default="YAT")
    p.add_argument("--fund", help="single fund code (default: all funds)")
    p.add_argument("--no-allocations", action="store_true")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("update", help="fetch since last stored date")
    p.add_argument("--type", choices=["YAT", "EMK", "BYF", "GYF", "GSYF"],
                   default="YAT")
    p.add_argument("--no-allocations", action="store_true")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("top", help="rank funds by a metric")
    p.add_argument("--by", default="sharpe",
                   choices=["sharpe", "sortino", "ret_1m", "ret_3m",
                            "ret_6m", "ret_1y", "ann_vol", "max_dd", "aum"])
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--type", choices=["YAT", "EMK"], default=None)
    p.add_argument("--rf", type=float, default=0.0,
                   help="annual risk-free rate, e.g. 0.40 for 40%%")
    p.add_argument("--min-obs", type=int, default=20)
    p.add_argument("--category", help="filter by category substring")
    p.add_argument("--min-aum", type=float, default=0,
                   help="minimum AUM in millions TRY")
    p.add_argument("--min-investors", type=int, default=0)
    p.add_argument("--csv", help="also save full table to this CSV path")
    p.set_defaults(func=cmd_top)

    p = sub.add_parser("benchmarks",
                       help="fetch BIST/FX/gold benchmark series")
    p.add_argument("--start", default="2024-01-01")
    p.set_defaults(func=cmd_benchmarks)

    p = sub.add_parser("classify", help="assign a category to every fund")
    p.set_defaults(func=cmd_classify)

    p = sub.add_parser("flows", help="estimated net fund flows (TRY)")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--type", choices=["YAT", "EMK", "BYF", "GYF", "GSYF"],
                   default=None)
    p.set_defaults(func=cmd_flows)

    p = sub.add_parser("factors",
                       help="factor betas (BIST/gold/FX) and attribution")
    p.add_argument("code", nargs="?",
                   help="fund code for detailed attribution; omit for "
                        "all-fund beta table")
    p.add_argument("--days", type=int, default=252)
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--category", help="filter beta table by category")
    p.add_argument("--csv")
    p.set_defaults(func=cmd_factors)

    p = sub.add_parser("rolling", help="rolling metrics for one fund")
    p.add_argument("code")
    p.add_argument("--window", type=int, default=63)
    p.add_argument("--rf", type=float, default=0.0)
    p.add_argument("--csv", help="save full daily series")
    p.set_defaults(func=cmd_rolling)

    p = sub.add_parser("compare", help="side-by-side fund comparison")
    p.add_argument("codes", nargs="+", help="2-5 fund codes")
    p.add_argument("--rf", type=float, default=0.0)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("smartmoney",
                       help="category flows, rotation, risk appetite")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--months", type=int, default=12)
    p.set_defaults(func=cmd_smartmoney)

    p = sub.add_parser("quality",
                       help="Manager Skill / Investor Suitability scores")
    p.add_argument("--view", choices=["combined", "skill", "suitability"],
                   default="combined")
    p.add_argument("--within-category", action="store_true",
                   help="percentile-rank within each category instead of "
                        "across the whole universe")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--rf", type=float, default=0.0)
    p.add_argument("--category")
    p.add_argument("--min-aum", type=float, default=100,
                   help="minimum AUM in millions TRY (default 100)")
    p.add_argument("--min-investors", type=int, default=500)
    p.add_argument("--csv")
    p.set_defaults(func=cmd_quality)

    p = sub.add_parser("report",
                       help="generate the Monthly Intelligence Report")
    p.add_argument("--save", default="reports")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("daily",
                       help="full ETL: update raw data + rebuild dash tables")
    p.add_argument("--skip-raw", action="store_true",
                   help="only rebuild analytics tables (no network)")
    p.add_argument("--rf", type=float, default=pipeline.PRESENTATION_RF)
    p.set_defaults(func=cmd_daily)

    p = sub.add_parser("stocks", help="BIST stock tickers + daily OHLCV")
    p.add_argument("--start", type=_parse_date, default=date(2024, 1, 1))
    p.add_argument("--update", action="store_true",
                   help="incremental from last stored date")
    p.add_argument("--registry-only", action="store_true",
                   help="only refresh the ticker list from KAP")
    p.add_argument("--sectors", action="store_true",
                   help="fetch sector/industry per ticker (slow, one-time)")
    p.add_argument("--tickers", nargs="+",
                   help="specific tickers (default: all)")
    p.set_defaults(func=cmd_stocks)

    p = sub.add_parser("memo", help="generate an investment memo")
    p.add_argument("code")
    p.add_argument("--rf", type=float, default=0.0)
    p.add_argument("--save", help="also write markdown to this path")
    p.set_defaults(func=cmd_memo)

    p = sub.add_parser("research", help="run a research study")
    p.add_argument("study", choices=["flows", "flows-by-category",
                                     "flows-oos", "chasing", "closet",
                                     "diagnostics"])
    p.add_argument("--category", default="Equity Turkey")
    p.add_argument("--regime", choices=["high_vol", "low_vol"],
                   help="volatility-regime subsample (flows study)")
    p.add_argument("--min-aum", type=float, default=100,
                   help="minimum AUM in millions TRY (closet study)")
    p.set_defaults(func=cmd_research)

    p = sub.add_parser("health", help="data quality checks")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("fund", help="detailed report for one fund")
    p.add_argument("code")
    p.add_argument("--rf", type=float, default=0.0)
    p.set_defaults(func=cmd_fund)

    p = sub.add_parser("stats", help="database summary")
    p.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
