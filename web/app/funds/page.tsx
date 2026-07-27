import { FundTable } from "@/components/fund-table";
import { PageHeader } from "@/components/ui";
import { getScreenerFunds } from "@/lib/queries";
import { Suspense } from "react";

export const revalidate = 1800;

export const metadata = { title: "Fund screener" };

export default async function FundsPage() {
  const funds = await getScreenerFunds();
  return (
    <div>
      <PageHeader
        title="Fund screener"
        description={
          <>
            Ranked by two deliberately separate scores. <b>Skill</b> asks “is the
            manager good?” (factor alpha, consistency, downside, factor
            independence). <b>Suitability</b> asks “should a typical investor buy
            it?” (Sharpe, drawdown, stability, liquidity, size). They disagree on
            purpose. Click a column to sort; click a fund for the full profile.
          </>
        }
      />
      <div className="mt-6">
        <Suspense
          fallback={<div className="h-80 animate-pulse rounded-xl border bg-surface" aria-label="Loading fund screener" />}
        >
          <FundTable funds={funds} />
        </Suspense>
      </div>
    </div>
  );
}
