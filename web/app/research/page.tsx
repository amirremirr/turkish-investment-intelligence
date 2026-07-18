import { Card } from "@/components/ui";

export const metadata = { title: "Research" };

const REPO =
  "https://github.com/amirremirr/turkish-investment-intelligence/blob/main/docs/research";

const NOTES = [
  {
    n: 1,
    file: "01-contrarian-flows.md",
    title: "Retail fund flows are mildly contrarian",
    finding:
      "Equity-fund inflows predict lower future BIST100 returns (Newey–West t=−2.5 at 21 days) — but the effect exists only in low-volatility regimes and only for domestic equity flows. A complacency phenomenon, confirmed out-of-sample.",
  },
  {
    n: 2,
    file: "02-performance-chasing.md",
    title: "Investors chase quarterly winners",
    finding:
      "Weekly flows don't respond to last week's returns, but respond strongly to trailing 63-day returns (t=4.3). Turkish investors chase what has worked for months — medium-term, not short-term, momentum chasing.",
  },
  {
    n: 3,
    file: "03-closet-indexing.md",
    title: "~1 in 5 large “active” equity funds is a closet indexer",
    finding:
      "Of 236 large “active” equity funds, 52 run R²≥0.85 with beta≈1 and no positive alpha — including major bank funds at R²>0.95. Alpha is measured excess-of-cash with NAV resets clipped, so the deposit rate isn’t mistaken for skill. Index exposure sold at active fees.",
  },
  {
    n: 4,
    file: "04-nav-timing-lag.md",
    title: "The TEFAS NAV timing lag",
    finding:
      "TEFAS NAVs are computed from the prior close (+2 days for globally-priced assets). Correcting it moved a BIST30 index fund's measured beta from 0.12 to 0.995 and erased what looked like 31pp of “alpha.” Any same-day analysis of TEFAS data is structurally wrong.",
  },
  {
    n: 5,
    file: "05-defensive-investor.md",
    title: "The defensive Turkish investor",
    finding:
      "Synthesis: with real rates at +9pp, parking cash is rational — and equity's rising AUM share is pure price effect, not conviction (flows are negative). The quarterly-chasing pattern predicts where flows go next.",
  },
];

export default function ResearchPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Research</h1>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        Reproducible studies on the Turkish fund market. Each is computed from
        the platform's own database with documented methodology — Newey–West
        standard errors, out-of-sample validation, and stated limitations. Full
        write-ups on GitHub.
      </p>
      <p className="mt-3 max-w-2xl rounded-lg border border-dashed p-3 text-xs text-muted">
        <b>Scope honestly stated:</b> the sample is ~2.5 years inside one
        macro regime; flow effects clear significance tests but explain
        &lt;1% of return variance and are not tradable after costs; the
        closet-index study measures index-like <i>exposure</i>, not
        net-of-fee value (fee data isn't public via TEFAS). These are
        internal research memos with open methods — not validated
        academic results, and not investment advice.
      </p>

      <div className="mt-6 space-y-4">
        {NOTES.map((note) => (
          <a
            key={note.n}
            href={`${REPO}/${note.file}`}
            target="_blank"
            rel="noreferrer"
          >
            <Card className="transition-colors hover:border-accent">
              <div className="flex items-baseline gap-3">
                <span className="tnum text-sm text-muted">
                  {String(note.n).padStart(2, "0")}
                </span>
                <h2 className="font-semibold">{note.title}</h2>
                <span className="ml-auto text-sm text-accent">Read ↗</span>
              </div>
              <p className="mt-2 pl-8 text-sm text-muted">{note.finding}</p>
            </Card>
          </a>
        ))}
      </div>

      <p className="mt-8 text-xs text-muted">
        Methodology, the institutional audit, and the data dictionary are in the{" "}
        <a
          className="text-accent"
          href="https://github.com/amirremirr/turkish-investment-intelligence/tree/main/docs"
          target="_blank"
          rel="noreferrer"
        >
          docs directory
        </a>
        .
      </p>
    </div>
  );
}
