import Link from "next/link";
import {
  getCategoryFlows,
  getSectors,
  getCrowding,
  getHoldingsCoverage,
  getStatus,
  type StatusMap,
} from "@/lib/queries";
import { Card, SectionTitle, Bar, Stat } from "@/components/ui";
import { num, signClass } from "@/lib/format";
import { freshIntraday, type LiveMover } from "@/lib/live";

export const revalidate = 300;
export const metadata = { title: "Market" };

function MoverList({ title, rows }: { title: string; rows: LiveMover[] }) {
  return (
    <Card>
      <div className="mb-2 font-semibold">{title}</div>
      <table className="w-full text-sm">
        <tbody>
          {rows.slice(0, 8).map((m) => (
            <tr key={m.ticker} className="border-b last:border-0">
              <td className="py-1.5 font-medium">{m.ticker}</td>
              <td className="py-1.5 text-muted">{m.title.slice(0, 26)}</td>
              <td className="tnum py-1.5 text-right">{num(m.price, 2)}</td>
              <td
                className={`tnum py-1.5 text-right ${signClass(m.chg_pct)}`}
              >
                {m.chg_pct >= 0 ? "+" : ""}
                {num(m.chg_pct, 1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

type RiskAppetite = {
  reading?: string;
  flow_tilt_to_risk?: number;
  risk_asset_aum_share_now?: number;
};

export default async function MarketPage() {
  // Guard each query: the small Supabase instance can time a query out
  // under the build's concurrent load; a degraded section is far better
  // than a failed build, and it self-heals on the next revalidation.
  const [flows, sectors, crowding, coverage, status] = await Promise.all([
    getCategoryFlows().catch(() => []),
    getSectors().catch(() => []),
    getCrowding(20).catch(() => []),
    getHoldingsCoverage().catch(() => 0),
    getStatus().catch((): StatusMap => ({})),
  ]);
  const mood = (status.risk_appetite ?? {}) as RiskAppetite;
  const live = freshIntraday(status.intraday);

  const maxFlow = Math.max(...flows.map((f) => Math.abs(f.net_flow_bn)), 1);
  const maxSect = Math.max(...sectors.map((s) => Math.abs(s.ret_1m)), 0.01);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Market</h1>
        <p className="mt-1 text-sm text-muted">
          Where investor money is moving, what sectors are doing, and which
          stocks funds crowd into.
        </p>
      </div>

      {live?.movers && (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-neg" />
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
              Live movers
            </h2>
            <span className="text-xs text-muted">
              {live.ts} UTC · delayed ~15 min
            </span>
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <MoverList title="Gainers" rows={live.movers.gainers} />
            <MoverList title="Losers" rows={live.movers.losers} />
          </div>
        </div>
      )}

      {mood.reading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card>
            <Stat label="Investor risk appetite" value={mood.reading.split(" ")[0]} />
          </Card>
          <Card>
            <Stat
              label="Flow tilt to risk"
              value={num(mood.flow_tilt_to_risk, 2)}
              sub="0 = fully defensive · 1 = fully risk-on"
            />
          </Card>
          <Card>
            <Stat
              label="Risk-asset AUM share"
              value={`${num(mood.risk_asset_aum_share_now, 0)}%`}
            />
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle hint="last 30 days, ₺bn">
            Net flows by category
          </SectionTitle>
          <div className="space-y-2.5">
            {flows.map((f) => (
              <div
                key={f.category}
                className="grid grid-cols-[9rem_1fr_3.5rem] items-center gap-3"
              >
                <span className="truncate text-sm">{f.category}</span>
                <Bar value={f.net_flow_bn} max={maxFlow} signed />
                <span
                  className={`tnum text-right text-sm ${signClass(f.net_flow_bn)}`}
                >
                  {f.net_flow_bn >= 0 ? "+" : ""}
                  {num(f.net_flow_bn, 0)}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <SectionTitle hint="median stock, 1 month">
            Sector performance
          </SectionTitle>
          <div className="space-y-2.5">
            {sectors.map((s) => (
              <div
                key={s.sector}
                className="grid grid-cols-[9rem_1fr_3.5rem] items-center gap-3"
              >
                <span className="truncate text-sm">
                  {s.sector}
                  <span className="ml-1 text-xs text-muted">({s.stocks})</span>
                </span>
                <Bar value={s.ret_1m} max={maxSect} signed />
                <span
                  className={`tnum text-right text-sm ${signClass(s.ret_1m)}`}
                >
                  {num(s.ret_1m * 100, 1)}%
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <SectionTitle
          hint={`${coverage} funds covered so far · grows nightly`}
        >
          Most-held stocks
        </SectionTitle>
        {crowding.length === 0 ? (
          <p className="text-sm text-muted">
            Holdings coverage is still accumulating (parsed monthly from KAP).
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted">
                  <th className="py-2 font-medium">Stock</th>
                  <th className="py-2 font-medium">Name</th>
                  <th className="py-2 text-right font-medium">Funds holding</th>
                  <th className="py-2 text-right font-medium">Avg weight</th>
                </tr>
              </thead>
              <tbody>
                {crowding.map((c) => (
                  <tr
                    key={c.ticker}
                    className="border-b last:border-0 hover:bg-accent-soft/40"
                  >
                    <td className="py-2 font-medium">
                      <Link
                        href={`/stocks/${c.ticker}`}
                        className="text-accent hover:underline"
                      >
                        {c.ticker}
                      </Link>
                    </td>
                    <td className="py-2 text-muted">
                      {(c.name ?? "").slice(0, 40)}
                    </td>
                    <td className="tnum py-2 text-right">{c.n_funds}</td>
                    <td className="tnum py-2 text-right">
                      {num(c.avg_weight, 1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
