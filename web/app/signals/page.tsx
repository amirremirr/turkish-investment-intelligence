import Link from "next/link";
import { Badge, Card, PageHeader, SectionTitle, Stat } from "@/components/ui";
import { num } from "@/lib/format";
import {
  getSignalLabStatus,
  getStatus,
  type SignalLabStatus,
  type StatusMap,
} from "@/lib/queries";
import { freshIntraday } from "@/lib/live";

export const revalidate = 300;
export const metadata = {
  title: "Signal Lab",
  description:
    "Transparent status and evidence for the platform's exploratory momentum research.",
};

const REPO =
  "https://github.com/amirremirr/turkish-investment-intelligence/blob/main/docs";

const COHORT_LABELS: Record<string, string> = {
  "exhaustion-v1": "Crowded exhaustion (risk context)",
  "moderate-4-7-normal-turnover-v1": "Moderate 4-7% / ordinary turnover",
  "moderate-7-9-normal-turnover-v1": "Moderate 7-9% / ordinary turnover",
};

function dateRange(first: string | null, last: string | null) {
  if (!first || !last) return "No qualifying observations yet";
  return first === last ? first : `${first} to ${last}`;
}

function CaptureStatus({ data }: { data: SignalLabStatus | null }) {
  if (!data) {
    return (
      <Card>
        <p className="text-sm text-muted">
          The prospective signal ledger is not available from the serving
          database yet. This does not mean that a positive or negative result
          exists; it means the page cannot verify collection coverage right now.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <Stat label="Recorded observations" value={num(data.observations, 0)} sub="one defined event per stock, date and version" />
        </Card>
        <Card>
          <Stat label="Event days" value={num(data.eventDays, 0)} sub={dateRange(data.firstSignalDate, data.lastSignalDate)} />
        </Card>
        <Card>
          <Stat label="5-minute bars captured" value={num(data.intradayBars, 0)} sub="raw prospective path records" />
        </Card>
        <Card>
          <Stat label="Events with bars" value={num(data.signalsWithBars, 0)} sub={data.lastBarAt ? `latest: ${data.lastBarAt}` : "no bars captured yet"} />
        </Card>
      </div>
      <Card>
        <SectionTitle hint="each cohort is fixed before its future outcomes are read">Collection by cohort</SectionTitle>
        {data.cohorts.length === 0 ? (
          <p className="text-sm text-muted">No cohort observations are stored yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b text-left text-muted">
                <th className="py-2 font-medium">Cohort</th><th className="py-2 text-right font-medium">Events</th>
                <th className="py-2 text-right font-medium">Days</th><th className="py-2 text-right font-medium">With bars</th>
                <th className="py-2 text-right font-medium">5-minute bars</th>
              </tr></thead>
              <tbody>{data.cohorts.map((cohort) => (
                <tr key={cohort.signalVersion} className="border-b last:border-0">
                  <td className="py-2">{COHORT_LABELS[cohort.signalVersion] ?? cohort.signalVersion}</td>
                  <td className="tnum py-2 text-right">{num(cohort.observations, 0)}</td>
                  <td className="tnum py-2 text-right">{num(cohort.eventDays, 0)}</td>
                  <td className="tnum py-2 text-right">{num(cohort.signalsWithBars, 0)}</td>
                  <td className="tnum py-2 text-right">{num(cohort.intradayBars, 0)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

export default async function SignalLabPage() {
  const [status, signalData] = await Promise.all([
    getStatus().catch((): StatusMap => ({})),
    getSignalLabStatus().catch((): SignalLabStatus | null => null),
  ]);
  const live = freshIntraday(status.intraday);
  const watch = live?.exhaustion_watch;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Signal Lab"
        description="A transparent record of the momentum research process: what was tested, what failed, what data is collecting now, and what would be required before any future claim could be shown prominently."
        actions={<Badge tone="warning">Exploratory research only</Badge>}
      />

      <Card className="border-warning/40 bg-warning-soft/30">
        <h2 className="font-semibold">There is no buy, sell or short signal here</h2>
        <p className="mt-2 max-w-4xl text-sm text-muted">
          Historical daily-price tests did not establish a repeatable,
          executable positive edge. The current watch is designed to flag
          possible momentum exhaustion so a user does not confuse a crowded
          move with a confirmed opportunity. It is not an instruction to trade.
        </p>
      </Card>

      <section>
        <SectionTitle hint="updated from the serving database">
          Prospective data collection
        </SectionTitle>
        <p className="mb-3 max-w-3xl text-sm text-muted">
          For each defined exhaustion event, the system stores a dated signal
          record and any available adjusted 5-minute price bars. This lets us
          test the opening path later without rewriting history after seeing an
          outcome.
        </p>
        <CaptureStatus data={signalData} />
      </section>

      <section>
        <SectionTitle hint="only shown while the delayed feed is fresh">
          Current momentum-exhaustion watch
        </SectionTitle>
        {!live ? (
          <Card>
            <p className="text-sm text-muted">
              The intraday feed is currently stale, closed or unavailable. The
              research ledger above is separate from this temporary display.
            </p>
          </Card>
        ) : !watch?.candidates?.length ? (
          <Card>
            <p className="text-sm text-muted">
              {watch?.state ?? "No qualifying events"}. This is a normal
              outcome: the watch appears only after a crowded prior-day move
              and a next-session opening gap of at least 1%.
            </p>
          </Card>
        ) : (
          <Card>
            <p className="mb-3 text-sm text-muted">
              These are research observations, not recommendations. A red
              label means &quot;do not chase without further evidence,&quot; not
              &quot;sell&quot; or &quot;short.&quot;
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted">
                    <th className="py-2 font-medium">Stock</th>
                    <th className="py-2 text-right font-medium">Open gap</th>
                    <th className="py-2 text-right font-medium">Prior day</th>
                    <th className="py-2 text-right font-medium">Turnover shock</th>
                  </tr>
                </thead>
                <tbody>
                  {watch.candidates.map((row) => (
                    <tr key={row.ticker} className="border-b last:border-0">
                      <td className="py-2">
                        <Link className="font-medium text-accent hover:underline" href={`/stocks/${row.ticker}`}>
                          {row.ticker}
                        </Link>
                        <span className="ml-2 text-muted">{row.title}</span>
                      </td>
                      <td className="tnum py-2 text-right text-neg">+{num(row.opening_gap_pct, 1)}%</td>
                      <td className="tnum py-2 text-right">+{num(row.previous_day_return_pct, 1)}%</td>
                      <td className="tnum py-2 text-right">{num(row.turnover_shock, 1)}x</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {watch.source_note && <p className="mt-3 text-xs text-muted">{watch.source_note}</p>}
          </Card>
        )}
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <Card>
          <Badge tone="warning">Tested and rejected for use</Badge>
          <h2 className="mt-3 font-semibold">Daily attention continuation</h2>
          <p className="mt-2 text-sm text-muted">
            Buying liquid daily winners with unusual turnover at the next open
            and holding to the close produced a small negative average result
            (about -0.09% gross). Larger opening gaps were worse.
          </p>
        </Card>
        <Card>
          <Badge tone="warning">Not validated</Badge>
          <h2 className="mt-3 font-semibold">Moderate, quieter momentum</h2>
          <p className="mt-2 text-sm text-muted">
            A follow-up test of moderate moves without abnormal turnover was
            not robust. One favourable average was driven by a few outsized
            days and weakened in the later sample.
          </p>
        </Card>
        <Card>
          <Badge tone="accent">Current question</Badge>
          <h2 className="mt-3 font-semibold">The opening path</h2>
          <p className="mt-2 text-sm text-muted">
            Does an event that survives the opening auction hold for 5, 15, 30
            or 60 minutes before later reversal? Only the prospective 5-minute
            data can answer this.
          </p>
        </Card>
      </section>

      <section>
        <SectionTitle>How the next result will be judged</SectionTitle>
        <Card>
          <ol className="list-decimal space-y-2 pl-5 text-sm text-muted">
            <li>Use only dated observations captured before their outcome.</li>
            <li>Compare open-to-5, 15, 30 and 60 minutes, plus the close.</li>
            <li>Report median and poor outcomes, not only the average.</li>
            <li>Separate gap size, liquidity, turnover, prior run-up and market direction.</li>
            <li>Require observations across future months and realistic execution checks before promotion.</li>
          </ol>
        </Card>
      </section>

      <section>
        <SectionTitle>Evidence and full methodology</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <a className="rounded-xl border bg-surface p-4 text-sm font-medium text-accent hover:bg-accent-soft" href={`${REPO}/research/attention-momentum.md`} target="_blank" rel="noreferrer">Daily attention study</a>
          <a className="rounded-xl border bg-surface p-4 text-sm font-medium text-accent hover:bg-accent-soft" href={`${REPO}/research/moderate-momentum.md`} target="_blank" rel="noreferrer">Moderate momentum study</a>
          <a className="rounded-xl border bg-surface p-4 text-sm font-medium text-accent hover:bg-accent-soft" href={`${REPO}/research/intraday-momentum-path.md`} target="_blank" rel="noreferrer">Prospective intraday plan</a>
          <a className="rounded-xl border bg-surface p-4 text-sm font-medium text-accent hover:bg-accent-soft" href={`${REPO}/SIGNAL_LAB.md`} target="_blank" rel="noreferrer">Signal governance</a>
        </div>
      </section>
    </div>
  );
}
