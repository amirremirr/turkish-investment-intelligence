import Link from "next/link";
import { notFound } from "next/navigation";
import { getFund, getFundNav, getFundHoldings } from "@/lib/queries";
import { Card, Stat, Delta, SectionTitle, Bar } from "@/components/ui";
import { Sparkline } from "@/components/sparkline";
import { pct, pctPoints, num, tryBn, intFmt, signClass } from "@/lib/format";

export const revalidate = 3600;
export const dynamicParams = true;

// Render fund pages on first request and cache them (ISR), rather than
// prerendering hundreds at build time — the Supabase pooler caps
// concurrent connections, and a build that opens one per fund exhausts
// it (locally and on Vercel). On-demand + revalidate is both robust and
// still fast after the first hit.
export function generateStaticParams() {
  return [];
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  return { title: code.toUpperCase() };
}

const FACTORS: { key: keyof FactorRow; label: string }[] = [
  { key: "beta_bist100", label: "BIST100" },
  { key: "beta_nasdaq_try", label: "Nasdaq (TRY)" },
  { key: "beta_gold_try", label: "Gold (TRY)" },
  { key: "beta_usdtry", label: "USD/TRY" },
];
type FactorRow = {
  beta_bist100: number | null;
  beta_nasdaq_try: number | null;
  beta_gold_try: number | null;
  beta_usdtry: number | null;
};

export default async function FundPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const fund = await getFund(code);
  if (!fund) notFound();

  const [nav, holdings] = await Promise.all([
    getFundNav(code),
    getFundHoldings(code),
  ]);

  // downsample NAV to ~200 points for a compact SVG
  const step = Math.max(1, Math.floor(nav.length / 200));
  const navPoints = nav.filter((_, i) => i % step === 0).map((d) => d.price);

  const maxBeta = Math.max(
    0.5,
    ...FACTORS.map((f) => Math.abs((fund[f.key] as number | null) ?? 0))
  );

  return (
    <div className="space-y-8">
      <div>
        <Link href="/funds" className="text-sm text-muted hover:text-fg">
          ← All funds
        </Link>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">
              <span className="text-accent">{fund.code}</span>{" "}
              <span className="text-muted">·</span> {fund.category}
            </h1>
            <p className="mt-1 max-w-2xl text-muted">{fund.title}</p>
          </div>
          <div className="flex gap-4">
            {fund.skill_score != null && (
              <div className="text-right">
                <div className="text-xs uppercase text-muted">Skill</div>
                <div className="tnum text-2xl font-semibold text-accent">
                  {num(fund.skill_score, 0)}
                </div>
              </div>
            )}
            {fund.suitability_score != null && (
              <div className="text-right">
                <div className="text-xs uppercase text-muted">Suitability</div>
                <div className="tnum text-2xl font-semibold">
                  {num(fund.suitability_score, 0)}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        <Card>
          <Stat
            label="1Y return"
            value={pct(fund.ret_1y)}
            subClass={signClass(fund.ret_1y)}
          />
        </Card>
        <Card>
          <Stat
            label="vs BIST100"
            value={
              <span className={signClass(fund.excess_1y)}>
                {pctPoints(fund.excess_1y)}
              </span>
            }
          />
        </Card>
        <Card>
          <Stat label="Sharpe" value={num(fund.sharpe, 2)} />
        </Card>
        <Card>
          <Stat label="Volatility" value={pct(fund.ann_vol, 0)} />
        </Card>
        <Card>
          <Stat
            label="Max drawdown"
            value={<span className="text-neg">{pct(fund.max_dd)}</span>}
          />
        </Card>
        <Card>
          <Stat label="AUM" value={tryBn(fund.aum)} />
        </Card>
      </div>

      {navPoints.length > 2 && (
        <Card>
          <SectionTitle
            hint={`${nav[0]?.date} → ${nav[nav.length - 1]?.date} · ${intFmt(fund.investors)} investors`}
          >
            NAV history
          </SectionTitle>
          <Sparkline points={navPoints} height={180} />
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle hint={`R² ${num(fund.r_squared, 2)}`}>
            Factor exposure
          </SectionTitle>
          <div className="space-y-3">
            {FACTORS.map((f) => {
              const beta = (fund[f.key] as number | null) ?? 0;
              return (
                <div key={f.key} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3">
                  <span className="text-sm text-muted">{f.label}</span>
                  <Bar value={beta} max={maxBeta} signed />
                  <span className="tnum text-right text-sm">
                    {num(beta, 2)}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-4 border-t pt-3 text-sm text-muted">
            Annualized alpha{" "}
            <span className={`tnum ${signClass(fund.alpha_annual)}`}>
              {pct(fund.alpha_annual, 0)}
            </span>{" "}
            (t = {num(fund.alpha_t, 1)}). Alpha t is used for scoring — a noisy
            alpha on a short history is penalized. Betas lag the market
            (+1d domestic, +2d global); see the methodology.
          </p>
        </Card>

        <Card>
          <SectionTitle
            hint={holdings.length ? `${holdings.length} positions` : undefined}
          >
            Top holdings
          </SectionTitle>
          {holdings.length === 0 ? (
            <p className="text-sm text-muted">
              No stock-level holdings captured yet. Holdings are parsed from KAP
              monthly portfolio reports and accumulate over time.
            </p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {holdings.slice(0, 12).map((h, i) => (
                  <tr key={i} className="border-b last:border-0">
                    <td className="py-1.5 font-medium">
                      {h.ticker ? (
                        <Link
                          href={`/stocks/${h.ticker}`}
                          className="text-accent hover:underline"
                        >
                          {h.ticker}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-1.5 text-muted">
                      {(h.name ?? "").slice(0, 28)}
                    </td>
                    <td className="tnum py-1.5 text-right">
                      {h.weight_pct != null ? `${num(h.weight_pct, 1)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
