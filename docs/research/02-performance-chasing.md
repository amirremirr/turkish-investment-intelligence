# Research Note 2 — Investors chase quarterly winners, not weekly ones

**Question.** Do Turkish fund investors allocate *after* returns have
already happened — and at what memory horizon?

**Data.** Weekly aggregate net flows into Equity Turkey funds
(% of category AUM), regressed on trailing category returns at
5/21/63-day lookbacks (equal-weight fund NAV returns), Jan 2024 – Jul
2026, ~130 weekly observations.

**Method.** `Flow_t = α + β·Return_{t−lookback:t−1} + ε`.

## Results

(Newey–West standard errors; restructuring-guarded flows)

| Trailing-return lookback | β | naive t | **NW t** | R² |
|---|---|---|---|---|
| 5 days | 0.011 | 1.3 | 1.9 | 0.012 |
| 21 days | 0.008 | 2.1 | 2.4 | 0.034 |
| 63 days | **0.006** | 3.3 | **4.3** | **0.083** |

Flows do not respond to last week's returns. They respond to the
trailing *quarter*: **Turkish mutual fund investors exhibit medium-term
return chasing rather than short-term momentum chasing.** A fund
category that has worked for ~3 months attracts measurable new money;
a good week attracts nothing.

## Corroborating evidence

The AUM-rotation data tells the same story from the other side: between
December 2025 and July 2026, Equity Turkey's share of total fund AUM
rose from 5.4% to 9.0% while cumulative *flows* into the category were
negative — the share gain was pure price effect. Investors had not yet
chased the rally; by the flow-chasing estimate above, sustained
quarterly performance is what eventually moves them.

## Interpretation & limitations

The 63-day horizon matches how retail investors actually experience
performance: through monthly/quarterly summaries, not daily prices.
Combined with Note 1 (contrarian flows), the picture is coherent:
money arrives after a quarter of gains, which is, on average, late.

Weekly aggregation limits n to ~130; the result clears t=3 but rests on
a single regime. Fund-level panel regressions (flow_i,t on return_i)
are the natural extension.

*Reproduce:* `python -m tefaslab research chasing`
