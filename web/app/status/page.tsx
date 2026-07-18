import { getDataStatus } from "@/lib/queries";
import { Card, SectionTitle } from "@/components/ui";

export const revalidate = 300;

export const metadata = {
  title: "Data status",
  description:
    "What each dataset actually covers, how fresh it is, and where it falls short.",
};

function ageDays(d: string | null): number | null {
  if (!d) return null;
  const t = Date.parse(d.length === 7 ? `${d}-01` : d);
  if (Number.isNaN(t)) return null;
  return Math.floor((Date.now() - t) / 86_400_000);
}

// Monthly datasets (holdings, CPI) are legitimately weeks behind; daily
// ones are not. Judge each against its own publication rhythm rather than
// one global threshold.
function verdict(d: string | null, served: boolean, monthly: boolean) {
  if (!served) return { label: "not served", cls: "text-neg border-neg/40" };
  const age = ageDays(d);
  if (age == null) return { label: "—", cls: "text-muted border-current/30" };
  const stale = monthly ? age > 75 : age > 5;
  return stale
    ? { label: `${age}d old`, cls: "text-neg border-neg/40" }
    : { label: `${age}d old`, cls: "text-pos border-pos/40" };
}

export default async function StatusPage() {
  const { sets, pipelineAt } = await getDataStatus().catch(() => ({
    sets: [],
    pipelineAt: null,
  }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Data status</h1>
        <p className="mt-2 max-w-2xl text-muted">
          Every page on this site renders the same whether the data behind it
          is current, months stale, or barely covered — so here is the actual
          state of each dataset. If something below looks thin or old, treat
          the figures that depend on it with the same suspicion.
        </p>
        {pipelineAt && (
          <p className="mt-2 text-xs text-muted">
            Last pipeline run: {pipelineAt.replace("T", " ").slice(0, 16)} UTC
          </p>
        )}
      </div>

      {sets.length === 0 ? (
        <Card>
          <p className="text-sm text-muted">
            Status could not be read — the serving database is unreachable.
            That itself is a signal: treat everything else on the site as
            unverified right now.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {sets.map((s) => {
            const monthly = /holdings|Macro/i.test(s.name);
            const v = verdict(s.asOf, s.served, monthly);
            return (
              <Card key={s.name}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <SectionTitle hint={s.asOf ? `as of ${s.asOf}` : undefined}>
                    {s.name}
                  </SectionTitle>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs ${v.cls}`}
                  >
                    {v.label}
                  </span>
                </div>
                <div className="tnum text-sm font-medium">{s.coverage}</div>
                <p className="mt-2 text-sm text-muted">{s.note}</p>
              </Card>
            );
          })}
        </div>
      )}

      <Card>
        <SectionTitle>What this does and doesn&apos;t tell you</SectionTitle>
        <p className="text-sm text-muted">
          This page reports coverage and freshness — it does not certify that
          the numbers are <em>correct</em>. Correctness is defended
          separately: unit tests on the parsing and statistics, a twice-daily
          canary that probes each upstream source for schema changes, and a
          daily monitor that fails loudly on stale data or a stalled
          ingest. The limitation worth repeating: this is a personal research
          workstation built on public data, not an audited data product.
        </p>
      </Card>
    </div>
  );
}
