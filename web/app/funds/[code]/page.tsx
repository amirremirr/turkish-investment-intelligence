import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getFund,
  getFundNav,
  getFundHoldings,
  getSimilarFunds,
  getFundAttribution,
} from "@/lib/queries";
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

  const [nav, holdings, similar, attrib] = await Promise.all([
    getFundNav(code),
    getFundHoldings(code),
    getSimilarFunds(code).catch(() => []),
    getFundAttribution(code).catch(() => []),
  ]);

  // downsample NAV to ~200 points for a compact SVG
  const step = Math.max(1, Math.floor(nav.length / 200));
  const navPoints = nav.filter((_, i) => i % step === 0).map((d) => d.price);

  const maxBeta = Math.max(
    0.5,
    ...FACTORS.map((f) => Math.abs((fund[f.key] as number | null) ?? 0))
  );

  // portfolio shape from the disclosed book (weights present for the
  // funds whose KAP template parsed; concentration + how much of the
  // book sits in consensus names vs unique picks)
  const weighted = holdings.filter((h) => h.weight_pct != null);
  const hasWeights = weighted.length > 0;
  const top10 = weighted
    .slice(0, 10)
    .reduce((s, h) => s + (h.weight_pct ?? 0), 0);
  const consensusWeight = weighted
    .filter((h) => (h.n_funds ?? 0) >= 3)
    .reduce((s, h) => s + (h.weight_pct ?? 0), 0);

  // Stock-selection attribution. Only locally-priced holdings carry a
  // return, so report the share of book actually covered — otherwise the
  // contributions read as explaining more than they do.
  const attribPriced = attrib.filter((a) => a.contribution_pp != null);
  const attribWeight = attribPriced.reduce((s, a) => s + (a.weight_pct ?? 0), 0);
  const attribTotal = attribPriced.reduce(
    (s, a) => s + (a.contribution_pp ?? 0), 0);
  const bookWeight = weighted.reduce((s, h) => s + (h.weight_pct ?? 0), 0);
  const movers = [...attribPriced.slice(0, 5), ...attribPriced.slice(-3)]
    .filter((a, i, arr) => arr.findIndex((x) => x.ticker === a.ticker) === i);
  // these come out of SQL already in percent / percentage points, so they
  // must NOT go through pctPoints() (which scales a fraction by 100)
  const pp = (x: number | null | undefined, d = 2) =>
    x == null ? "—" : `${x >= 0 ? "+" : ""}${num(x, d)}pp`;

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
            Portfolio
          </SectionTitle>
          {holdings.length === 0 ? (
            <p className="text-sm text-muted">
              No stock-level holdings captured yet. Holdings are parsed from KAP
              monthly portfolio reports and accumulate over time.
            </p>
          ) : (
            <>
              {hasWeights && (
                <div className="mb-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  <span className="text-muted">
                    Top 10:{" "}
                    <span className="tnum font-medium text-fg">
                      {num(top10, 0)}%
                    </span>
                  </span>
                  <span className="text-muted">
                    In consensus names (≥3 funds):{" "}
                    <span className="tnum font-medium text-fg">
                      {num(consensusWeight, 0)}%
                    </span>
                  </span>
                </div>
              )}
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted">
                    <th className="py-1 font-medium">Stock</th>
                    <th className="py-1 font-medium">Name</th>
                    <th className="py-1 text-right font-medium">Held by</th>
                    <th className="py-1 text-right font-medium">Weight</th>
                  </tr>
                </thead>
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
                        {(h.name ?? "").slice(0, 24)}
                      </td>
                      <td className="tnum py-1.5 text-right text-muted">
                        {h.n_funds && h.n_funds > 1
                          ? `${h.n_funds} funds`
                          : h.n_funds === 1
                            ? "only here"
                            : "—"}
                      </td>
                      <td className="tnum py-1.5 text-right">
                        {h.weight_pct != null
                          ? `${num(h.weight_pct, 1)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </Card>

        {similar.length > 0 && (
          <Card>
            <SectionTitle hint="by holdings overlap">
              Most similar funds
            </SectionTitle>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted">
                  <th className="py-1 font-medium">Fund</th>
                  <th className="py-1 text-right font-medium">Shared</th>
                  <th className="py-1 text-right font-medium">Overlap</th>
                </tr>
              </thead>
              <tbody>
                {similar.map((s) => (
                  <tr key={s.code} className="border-b last:border-0">
                    <td className="py-1.5">
                      <Link
                        href={`/funds/${s.code}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {s.code}
                      </Link>
                      <span className="ml-2 text-muted">
                        {(s.title ?? "").slice(0, 30)}
                      </span>
                    </td>
                    <td className="tnum py-1.5 text-right text-muted">
                      {s.shared}
                    </td>
                    <td className="tnum py-1.5 text-right font-medium">
                      {num(s.overlap, 0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-muted">
              Overlap = share of portfolio held in the same stocks at the same
              weight (Σ min weight). A high figure means near-identical books —
              holdings-based herding, independent of the return-based
              closet-index signal.
            </p>
          </Card>
        )}

        {attribPriced.length >= 3 && (
          <Card>
            <SectionTitle
              hint={`${num(attribWeight, 0)}% of book priced`}
            >
              What drove the month after
            </SectionTitle>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted">
                  <th className="py-1 font-medium">Stock</th>
                  <th className="py-1 text-right font-medium">Weight</th>
                  <th className="py-1 text-right font-medium">Stock</th>
                  <th className="py-1 text-right font-medium">Contribution</th>
                </tr>
              </thead>
              <tbody>
                {movers.map((a) => (
                  <tr key={a.ticker} className="border-b last:border-0">
                    <td className="py-1.5 font-medium">
                      {a.ticker ? (
                        <Link
                          href={`/stocks/${a.ticker}`}
                          className="text-accent hover:underline"
                        >
                          {a.ticker}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="tnum py-1.5 text-right text-muted">
                      {num(a.weight_pct, 1)}%
                    </td>
                    <td
                      className={`tnum py-1.5 text-right ${signClass(a.stock_ret_pct)}`}
                    >
                      {num(a.stock_ret_pct, 1)}%
                    </td>
                    <td
                      className={`tnum py-1.5 text-right font-medium ${signClass(a.contribution_pp)}`}
                    >
                      {pp(a.contribution_pp, 2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-muted">
              Each holding&apos;s weight × its return in the month after the
              report — {pp(attribTotal, 1)} in total from the{" "}
              {num(attribWeight, 0)}% of the book that has local prices (of{" "}
              {num(bookWeight, 0)}% disclosed). Foreign equities and bonds
              have no local price and sit in the residual, so this explains
              stock selection, not the whole return.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
