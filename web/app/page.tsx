import Link from "next/link";
import { getStatus, getMarketAggregate, type StatusMap } from "@/lib/queries";
import { Card, Stat, Delta } from "@/components/ui";
import { pct, tryBn, num, intFmt } from "@/lib/format";
import { freshIntraday } from "@/lib/live";

export const revalidate = 300;

type Snap = Record<string, { level: number; chg_1d: number; date?: string }>;
type Macro = {
  inflation_yoy?: number;
  inflation_asof?: string;
  policy_rate?: number;
  real_rate?: number;
  rates?: string;
  usdtry_3m_pct?: number;
};

const FINDINGS = [
  {
    t: "Retail fund flows are mildly contrarian",
    d: "Equity-fund inflows predict lower BIST returns (Newey–West t=−2.5), but only in calm markets and only for domestic equity.",
  },
  {
    t: "Performance chasing does not survive fund-level testing",
    d: "Flows respond to trailing 63-day returns (t=4.3), not weekly moves — medium-term performance chasing.",
  },
  {
    t: "~1 in 5 “active” equity funds is a closet indexer",
    d: "Of 236 large active equity funds, 52 run R²≥0.85 at β≈1 with no positive alpha — index exposure sold at active fees.",
  },
  {
    t: "The TEFAS NAV timing lag",
    d: "NAVs lag the market (+1d domestic, +2d global). Correcting it moved an index fund's measured beta from 0.12 to 0.995.",
  },
];

const RESEARCH_NOTE_URLS = [
  "https://github.com/amirremirr/turkish-investment-intelligence/blob/main/docs/research/01-contrarian-flows.md",
  "https://github.com/amirremirr/turkish-investment-intelligence/blob/main/docs/research/02-performance-chasing.md",
  "https://github.com/amirremirr/turkish-investment-intelligence/blob/main/docs/research/03-closet-indexing.md",
  "https://github.com/amirremirr/turkish-investment-intelligence/blob/main/docs/research/04-nav-timing-lag.md",
];

export default async function Home() {
  const [status, agg] = await Promise.all([
    getStatus().catch((): StatusMap => ({})),
    getMarketAggregate().catch(() => ({ total_aum: 0, n_funds: 0 })),
  ]);
  const live = freshIntraday(status.intraday);
  const snap = (live?.snapshot ?? status.market_snapshot ?? {}) as Snap;
  const macro = (status.macro_regime ?? {}) as Macro;
  const breadth = live?.breadth;

  return (
    <div className="space-y-12">
      <section className="pt-4">
        <div className="inline-flex items-center gap-2 rounded-full border bg-surface px-3 py-1 text-xs text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-pos" />
          {intFmt(agg.n_funds)} funds · {tryBn(agg.total_aum)} tracked ·
          refreshed nightly
        </div>
        <h1 className="mt-5 max-w-3xl text-4xl font-semibold leading-tight sm:text-5xl">
          Professional <span className="text-accent">questions</span> for the
          Turkish fund market.
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted">
          Most tools stop at “top returns.” This open research project asks
          what professionals ask: what risk earned that return, where investor
          money is actually moving, and whether a manager is skilled or just
          exposed — with every method documented and every limitation stated.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/funds"
            className="rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white"
          >
            Explore the fund screener →
          </Link>
          <Link
            href="/research"
            className="rounded-lg border px-4 py-2.5 text-sm font-medium hover:border-accent"
          >
            Read the research
          </Link>
        </div>
      </section>

      <section aria-labelledby="start-here">
        <h2 id="start-here" className="text-sm font-semibold uppercase tracking-wide text-muted">
          Start here
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Link href="/funds" className="rounded-xl border bg-surface p-4 transition-colors hover:border-accent">
            <div className="text-xs font-medium text-accent">01 · Compare</div>
            <div className="mt-1 font-semibold">Screen funds</div>
            <p className="mt-1 text-sm text-muted">Filter and compare funds within the same category.</p>
          </Link>
          <Link href="/stocks" className="rounded-xl border bg-surface p-4 transition-colors hover:border-accent">
            <div className="text-xs font-medium text-accent">02 · Inspect</div>
            <div className="mt-1 font-semibold">Open disclosed holdings</div>
            <p className="mt-1 text-sm text-muted">See the funds and BIST stocks with a parsed KAP portfolio book.</p>
          </Link>
          <Link href="/status" className="rounded-xl border bg-surface p-4 transition-colors hover:border-accent">
            <div className="text-xs font-medium text-accent">03 · Verify</div>
            <div className="mt-1 font-semibold">Check the data status</div>
            <p className="mt-1 text-sm text-muted">Confirm coverage and freshness before relying on any result.</p>
          </Link>
        </div>
      </section>

      {Object.keys(snap).length > 0 && (
        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
              {live ? (
                <span className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-neg" />
                  Live market
                </span>
              ) : (
                "Market snapshot"
              )}
            </h2>
            <span className="text-xs text-muted">
              {live
                ? `${live.ts} UTC · quotes delayed ~15 min`
                : `as of ${Object.values(snap)[0]?.date ?? "latest"}`}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Object.entries(snap).map(([label, v]) => (
              <Card key={label}>
                <Stat
                  label={label}
                  value={num(v.level, 1)}
                  sub={<Delta value={v.chg_1d} text={pct(v.chg_1d, 2)} />}
                />
              </Card>
            ))}
            {breadth && (
              <Card>
                <Stat
                  label="Advancers / Decliners"
                  value={`${breadth.advancers ?? "–"} / ${breadth.decliners ?? "–"}`}
                  sub={`₺${breadth.turnover_bn_try ?? "–"}B turnover`}
                />
              </Card>
            )}
          </div>
          {macro.inflation_yoy != null && (
            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Card>
                <Stat
                  label="Inflation (yoy)"
                  value={`${num(macro.inflation_yoy, 1)}%`}
                  /* CPI publishes monthly in arrears, and a retired EVDS
                     series can freeze while still returning 200s — label
                     the vintage so a stale figure can't read as current. */
                  sub={
                    macro.inflation_asof
                      ? `CPI as of ${macro.inflation_asof.slice(0, 7)}`
                      : undefined
                  }
                />
              </Card>
              <Card>
                <Stat
                  label="Policy rate"
                  value={`${num(macro.policy_rate, 1)}%`}
                />
              </Card>
              <Card>
                <Stat
                  label="Real rate"
                  value={`${(macro.real_rate ?? 0) >= 0 ? "+" : ""}${num(macro.real_rate, 1)}pp`}
                  sub={macro.rates}
                />
              </Card>
              <Card>
                <Stat
                  label="USD/TRY 3m"
                  value={`${(macro.usdtry_3m_pct ?? 0) >= 0 ? "+" : ""}${num(macro.usdtry_3m_pct, 1)}%`}
                />
              </Card>
            </div>
          )}
        </section>
      )}

      <section>
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted">
          Research findings
        </h2>
        <p className="mb-4 text-xs text-muted">
          In-sample evidence from Jan 2024 → present — a single
          high-inflation, restrictive-rate regime. Effects are
          statistically supported but economically modest (R² &lt; 1% for
          flow signals); read the notes for methods and limits before
          treating any of this as durable.
        </p>
        <p className="-mt-2 mb-4 rounded-lg border border-accent bg-accent-soft p-3 text-xs text-fg">
          <b>Interpretation gate:</b> no individual fund alpha survives
          multiple-testing control, and the aggregate performance-chasing
          result falls from t=4.3 to t=1.2 in a fund-level fixed-effects test.
          These findings are research context, not signals to trade or proof
          of manager skill.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {FINDINGS.map((f, index) => (
            <a
              key={f.t}
              href={RESEARCH_NOTE_URLS[index]}
              target="_blank"
              rel="noreferrer"
              aria-label={`Read the full research note: ${f.t}`}
            >
              <Card className="h-full transition-colors hover:border-accent">
                <div className="font-semibold">{f.t}</div>
                <p className="mt-1.5 text-sm text-muted">{f.d}</p>
                <span className="mt-3 inline-block text-xs font-medium text-accent">
                  Read the note â†—
                </span>
              </Card>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
