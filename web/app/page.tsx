import Link from "next/link";
import { getStatus, getMarketAggregate, type StatusMap } from "@/lib/queries";
import { Card, Stat, Delta } from "@/components/ui";
import { pct, tryBn, num, intFmt } from "@/lib/format";
import { freshIntraday } from "@/lib/live";

export const revalidate = 300;

type Snap = Record<string, { level: number; chg_1d: number; date?: string }>;
type Macro = {
  inflation_yoy?: number;
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
    t: "Investors chase quarterly winners",
    d: "Flows respond to trailing 63-day returns (t=4.3), not weekly moves — medium-term performance chasing.",
  },
  {
    t: "31 closet index funds identified",
    d: "Of 192 large “active” equity funds, 31 run R²≥0.85 at β≈1 with ≈0 alpha — index exposure at active fees.",
  },
  {
    t: "The TEFAS NAV timing lag",
    d: "NAVs lag the market (+1d domestic, +2d global). Correcting it moved an index fund's measured beta from 0.12 to 0.995.",
  },
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
        <div className="grid gap-4 sm:grid-cols-2">
          {FINDINGS.map((f) => (
            <Link key={f.t} href="/research">
              <Card className="h-full transition-colors hover:border-accent">
                <div className="font-semibold">{f.t}</div>
                <p className="mt-1.5 text-sm text-muted">{f.d}</p>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
