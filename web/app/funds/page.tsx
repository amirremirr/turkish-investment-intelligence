import { getScreenerFunds } from "@/lib/queries";
import { FundTable } from "@/components/fund-table";

export const revalidate = 1800;

export const metadata = { title: "Fund screener" };

export default async function FundsPage() {
  const funds = await getScreenerFunds();
  return (
    <div>
      <h1 className="text-2xl font-semibold">Fund screener</h1>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        Ranked by two deliberately separate scores. <b>Skill</b> asks “is the
        manager good?” (factor alpha, consistency, downside, factor
        independence). <b>Suitability</b> asks “should a typical investor buy
        it?” (Sharpe, drawdown, stability, liquidity, size). They disagree on
        purpose. Click a column to sort; click a fund for the full profile.
      </p>
      <div className="mt-6">
        <FundTable funds={funds} />
      </div>
    </div>
  );
}
