"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { FundRow } from "@/lib/queries";
import { pct, num, tryBn, signClass } from "@/lib/format";

type SortKey =
  | "skill_score"
  | "suitability_score"
  | "ret_1y"
  | "sharpe"
  | "max_dd"
  | "aum";

const COLS: { key: SortKey; label: string; fmt: (r: FundRow) => string; sign?: boolean }[] = [
  { key: "ret_1y", label: "1Y return", fmt: (r) => pct(r.ret_1y), sign: true },
  { key: "sharpe", label: "Sharpe", fmt: (r) => num(r.sharpe, 2), sign: true },
  { key: "max_dd", label: "Max DD", fmt: (r) => pct(r.max_dd), sign: true },
  { key: "skill_score", label: "Skill", fmt: (r) => num(r.skill_score, 0) },
  { key: "suitability_score", label: "Suitability", fmt: (r) => num(r.suitability_score, 0) },
  { key: "aum", label: "AUM", fmt: (r) => tryBn(r.aum) },
];

export function FundTable({ funds }: { funds: FundRow[] }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("All");
  const [minAum, setMinAum] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("skill_score");
  const [asc, setAsc] = useState(false);

  const categories = useMemo(
    () => ["All", ...Array.from(new Set(funds.map((f) => f.category).filter(Boolean))).sort() as string[]],
    [funds]
  );

  const rows = useMemo(() => {
    let out = funds;
    if (q.trim()) {
      const s = q.toLowerCase();
      out = out.filter(
        (f) =>
          f.code.toLowerCase().includes(s) ||
          (f.title ?? "").toLowerCase().includes(s)
      );
    }
    if (cat !== "All") out = out.filter((f) => f.category === cat);
    if (minAum > 0) out = out.filter((f) => (f.aum ?? 0) >= minAum);
    out = [...out].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      return asc ? av - bv : bv - av;
    });
    return out;
  }, [funds, q, cat, minAum, sortKey, asc]);

  const setSort = (k: SortKey) => {
    if (k === sortKey) setAsc(!asc);
    else {
      setSortKey(k);
      setAsc(false);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search code or name…"
          className="h-9 flex-1 min-w-48 rounded-lg border bg-surface px-3 text-sm outline-none focus:border-accent"
        />
        <select
          value={cat}
          onChange={(e) => setCat(e.target.value)}
          className="h-9 rounded-lg border bg-surface px-2 text-sm outline-none focus:border-accent"
        >
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          value={minAum}
          onChange={(e) => setMinAum(Number(e.target.value))}
          className="h-9 rounded-lg border bg-surface px-2 text-sm outline-none focus:border-accent"
        >
          <option value={0}>Any AUM</option>
          <option value={100e6}>≥ ₺100M</option>
          <option value={500e6}>≥ ₺500M</option>
          <option value={1e9}>≥ ₺1B</option>
        </select>
        <span className="text-sm text-muted">{rows.length} funds</span>
      </div>

      <div className="overflow-x-auto rounded-xl border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-surface text-left">
              <th className="px-3 py-2.5 font-medium">Fund</th>
              {COLS.map((c) => (
                <th
                  key={c.key}
                  onClick={() => setSort(c.key)}
                  className="cursor-pointer select-none whitespace-nowrap px-3 py-2.5 text-right font-medium hover:text-accent"
                >
                  {c.label}
                  {sortKey === c.key && (asc ? " ↑" : " ↓")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 300).map((f) => (
              <tr
                key={f.code}
                className="border-b last:border-0 hover:bg-accent-soft/40"
              >
                <td className="px-3 py-2.5">
                  <Link href={`/funds/${f.code}`} className="block">
                    <span className="font-medium text-accent">{f.code}</span>
                    <span className="ml-2 text-muted">
                      {(f.title ?? "").slice(0, 42)}
                    </span>
                  </Link>
                </td>
                {COLS.map((c) => (
                  <td
                    key={c.key}
                    className={`tnum whitespace-nowrap px-3 py-2.5 text-right ${
                      c.sign ? signClass(f[c.key]) : ""
                    }`}
                  >
                    {c.fmt(f)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 300 && (
        <p className="mt-2 text-xs text-muted">
          Showing top 300 of {rows.length}. Narrow with search or filters.
        </p>
      )}
    </div>
  );
}
