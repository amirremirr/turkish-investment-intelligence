import Link from "next/link";
import { notFound } from "next/navigation";
import { getStock, getStockOwners } from "@/lib/queries";
import { Card, Stat, SectionTitle } from "@/components/ui";
import { num, tryBn, intFmt } from "@/lib/format";

export const revalidate = 3600;
export const dynamicParams = true;

// On-demand ISR like the fund pages — don't prerender every ticker at
// build time and exhaust the Supabase pooler.
export function generateStaticParams() {
  return [];
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  return { title: ticker.toUpperCase() };
}

export default async function StockPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const [stock, owners] = await Promise.all([
    getStock(ticker),
    getStockOwners(ticker),
  ]);
  // A ticker with no stock row AND no disclosed owner isn't in our universe.
  if (!stock && owners.length === 0) notFound();

  const t = ticker.toUpperCase();
  const totalValue = owners.reduce((s, o) => s + (o.value ?? 0), 0);
  const maxWeight = Math.max(0, ...owners.map((o) => o.weight_pct ?? 0));

  return (
    <div className="space-y-8">
      <div>
        <Link href="/stocks" className="text-sm text-muted hover:text-fg">
          ← All stocks
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">
          <span className="text-accent">{t}</span>
          {stock?.name ? (
            <>
              {" "}
              <span className="text-muted">·</span> {stock.name}
            </>
          ) : null}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {[stock?.sector, stock?.industry, stock?.city]
            .filter(Boolean)
            .join(" · ") || "BIST equity"}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Card>
          <Stat label="Funds holding" value={intFmt(owners.length)} />
        </Card>
        <Card>
          <Stat
            label="Disclosed value"
            value={totalValue > 0 ? tryBn(totalValue) : "—"}
          />
        </Card>
        <Card>
          <Stat
            label="Largest weight"
            value={maxWeight > 0 ? `${num(maxWeight, 1)}%` : "—"}
          />
        </Card>
      </div>

      <Card>
        <SectionTitle
          hint={
            owners.length ? `${owners.length} funds · latest disclosure` : undefined
          }
        >
          Funds holding {t}
        </SectionTitle>
        {owners.length === 0 ? (
          <p className="text-sm text-muted">
            No fund has disclosed a position in {t} yet. Holdings are parsed from
            KAP monthly portfolio reports and accumulate forward-only.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted">
                  <th className="py-2 font-medium">Fund</th>
                  <th className="py-2 font-medium">Category</th>
                  <th className="py-2 text-right font-medium">Weight</th>
                  <th className="py-2 text-right font-medium">Value</th>
                </tr>
              </thead>
              <tbody>
                {owners.map((o) => (
                  <tr
                    key={o.code}
                    className="border-b last:border-0 hover:bg-accent-soft/40"
                  >
                    <td className="py-2">
                      <Link
                        href={`/funds/${o.code}`}
                        className="font-medium text-accent hover:underline"
                      >
                        {o.code}
                      </Link>
                      <span className="ml-2 text-muted">
                        {(o.title ?? "").slice(0, 34)}
                      </span>
                    </td>
                    <td className="py-2 text-muted">{o.category ?? "—"}</td>
                    <td className="tnum py-2 text-right">
                      {o.weight_pct != null ? `${num(o.weight_pct, 1)}%` : "—"}
                    </td>
                    <td className="tnum py-2 text-right">
                      {o.value ? tryBn(o.value) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-3 text-xs text-muted">
          A position appears only after the fund files its monthly KAP
          portfolio report. Which funds hold the stock is complete; the{" "}
          <em>weight</em> shows only where that fund&apos;s PDF template parsed
          cleanly (many still read “—”), and is the stock&apos;s share of the
          fund&apos;s portfolio, not adjusted for fund size.
        </p>
      </Card>
    </div>
  );
}
