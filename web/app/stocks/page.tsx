import Link from "next/link";
import {
  getCoveredStocks,
  getHoldingsCoverage,
  getWeightCoverage,
  getCoveredFunds,
} from "@/lib/queries";
import { Card, SectionTitle } from "@/components/ui";
import { num, intFmt } from "@/lib/format";

export const revalidate = 3600;

export const metadata = {
  title: "Stocks",
  description:
    "BIST equities ranked by how many funds hold them, from public KAP disclosures.",
};

export default async function StocksPage() {
  const [stocks, coverage, wcov, funds] = await Promise.all([
    getCoveredStocks().catch(() => []),
    getHoldingsCoverage().catch(() => 0),
    getWeightCoverage().catch(() => ({ withWeights: 0, total: 0 })),
    getCoveredFunds().catch(() => []),
  ]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Stocks held by Turkish funds</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Every BIST equity disclosed in the latest KAP portfolio reports,
          ranked by how many funds hold it. Follow a stock to see which funds
          own it — then follow a fund back to its full book. Coverage grows
          forward-only as monthly disclosures accumulate.
        </p>
        {wcov.total > 0 && wcov.withWeights < wcov.total && (
          <p className="mt-2 text-xs text-muted">
            Which funds hold a stock is complete; position <em>weights</em>{" "}
            currently parse cleanly for {wcov.withWeights} of {wcov.total}{" "}
            funds&apos; KAP PDF templates, so many weights below show “—” until
            the parser covers more layouts.
          </p>
        )}
      </div>

      {funds.length > 0 && (
        <Card>
          <SectionTitle hint={`${funds.length} of the ~2,400 fund universe`}>
            Funds with a disclosed book
          </SectionTitle>
          <p className="mb-3 text-sm text-muted">
            KAP holdings are forward-only and still accumulating, so most
            fund pages have no book yet. These are the ones that do — start
            here rather than clicking through the screener.
          </p>
          <div className="max-h-80 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b text-left text-xs text-muted">
                  <th className="py-1 font-medium">Fund</th>
                  <th className="py-1 font-medium">Category</th>
                  <th className="py-1 text-right font-medium">Positions</th>
                  <th className="py-1 text-right font-medium">Weighted</th>
                </tr>
              </thead>
              <tbody>
                {funds.map((f) => (
                  <tr
                    key={f.code}
                    className="border-b last:border-0 hover:bg-accent-soft/40"
                  >
                    <td className="py-1.5">
                      <Link
                        href={`/funds/${f.code}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {f.code}
                      </Link>
                      <span className="ml-2 text-muted">
                        {(f.title ?? "").slice(0, 34)}
                      </span>
                    </td>
                    <td className="py-1.5 text-muted">{f.category ?? "—"}</td>
                    <td className="tnum py-1.5 text-right">{f.positions}</td>
                    <td className="tnum py-1.5 text-right text-muted">
                      {f.weighted}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card>
        <SectionTitle
          hint={`${intFmt(stocks.length)} stocks · ${coverage} funds covered so far`}
        >
          Most widely held
        </SectionTitle>
        {stocks.length === 0 ? (
          <p className="text-sm text-muted">
            Holdings coverage is still accumulating (parsed monthly from KAP
            disclosures).
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted">
                  <th className="py-2 font-medium">Ticker</th>
                  <th className="py-2 font-medium">Company</th>
                  <th className="py-2 font-medium">Sector</th>
                  <th className="py-2 text-right font-medium">Funds holding</th>
                  <th className="py-2 text-right font-medium">Avg weight</th>
                </tr>
              </thead>
              <tbody>
                {stocks.map((s) => (
                  <tr
                    key={s.ticker}
                    className="border-b last:border-0 hover:bg-accent-soft/40"
                  >
                    <td className="py-2 font-medium">
                      <Link
                        href={`/stocks/${s.ticker}`}
                        className="text-accent hover:underline"
                      >
                        {s.ticker}
                      </Link>
                    </td>
                    <td className="py-2 text-muted">
                      {(s.name ?? "").slice(0, 40)}
                    </td>
                    <td className="py-2 text-muted">{s.sector ?? "—"}</td>
                    <td className="tnum py-2 text-right">{s.n_funds}</td>
                    <td className="tnum py-2 text-right">
                      {num(s.avg_weight, 1)}%
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
