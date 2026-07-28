"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { FundRow } from "@/lib/queries";
import { pct, num, tryBn, signClass } from "@/lib/format";
import { Button, Input, Select } from "@/components/ui";

type SortKey =
  | "skill_score"
  | "suitability_score"
  | "ret_1y"
  | "sharpe"
  | "max_dd"
  | "aum";

const COLS: {
  key: SortKey;
  label: string;
  help: string;
  fmt: (row: FundRow) => string;
  sign?: boolean;
}[] = [
  {
    key: "ret_1y",
    label: "1Y return",
    help: "Trailing one-year total return.",
    fmt: (row) => pct(row.ret_1y),
    sign: true,
  },
  {
    key: "sharpe",
    label: "Sharpe",
    help: "Return per unit of volatility; compare primarily within a similar category.",
    fmt: (row) => num(row.sharpe, 2),
    sign: true,
  },
  {
    key: "max_dd",
    label: "Max DD",
    help: "Largest peak-to-trough decline over the measured period; less negative is better.",
    fmt: (row) => pct(row.max_dd),
    sign: true,
  },
  {
    key: "skill_score",
    label: "Research score",
    help: "A fixed-weight heuristic. It is not proof of manager skill; compare within category.",
    fmt: (row) => num(row.skill_score, 0),
  },
  {
    key: "suitability_score",
    label: "Suitability score",
    help: "A fixed-weight comparison aid, not a personalised recommendation.",
    fmt: (row) => num(row.suitability_score, 0),
  },
  {
    key: "aum",
    label: "AUM",
    help: "Assets under management in Turkish lira.",
    fmt: (row) => tryBn(row.aum),
  },
];

const SORT_KEYS = new Set<SortKey>(COLS.map((column) => column.key));
const PAGE_SIZE = 100;

export function FundTable({ funds }: { funds: FundRow[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [visible, setVisible] = useState(PAGE_SIZE);
  const q = searchParams.get("q") ?? "";
  const cat = searchParams.get("cat") ?? "All";
  const minAum = Number(searchParams.get("minAum") ?? 0) || 0;
  const requestedSort = searchParams.get("sort") as SortKey | null;
  const sortKey = requestedSort && SORT_KEYS.has(requestedSort)
    ? requestedSort
    : "skill_score";
  const asc = searchParams.get("dir") === "asc";

  const updateParams = (changes: Record<string, string | number | null>) => {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value == null || value === "" || value === 0 || value === "All") {
        next.delete(key);
      } else {
        next.set(key, String(value));
      }
    }
    setVisible(PAGE_SIZE);
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };

  const categories = useMemo(
    () => [
      "All",
      ...Array.from(new Set(funds.map((fund) => fund.category).filter(Boolean))).sort() as string[],
    ],
    [funds]
  );

  const rows = useMemo(() => {
    let out = funds;
    if (q.trim()) {
      const term = q.toLowerCase();
      out = out.filter(
        (fund) =>
          fund.code.toLowerCase().includes(term) ||
          (fund.title ?? "").toLowerCase().includes(term)
      );
    }
    if (cat !== "All") out = out.filter((fund) => fund.category === cat);
    if (minAum > 0) out = out.filter((fund) => (fund.aum ?? 0) >= minAum);
    return [...out].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      return asc ? av - bv : bv - av;
    });
  }, [funds, q, cat, minAum, sortKey, asc]);

  const setSort = (key: SortKey) => {
    updateParams(
      key === sortKey
        ? { dir: asc ? "desc" : "asc" }
        : { sort: key, dir: "desc" }
    );
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input
          value={q}
          onChange={(event) => updateParams({ q: event.target.value })}
          placeholder="Search code or name…"
          aria-label="Search funds by code or name"
          className="min-w-48 flex-1"
        />
        <Select
          value={cat}
          onChange={(event) => updateParams({ cat: event.target.value })}
          aria-label="Filter by fund category"
          className="px-2"
        >
          {categories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </Select>
        <Select
          value={minAum}
          onChange={(event) => updateParams({ minAum: Number(event.target.value) })}
          aria-label="Filter by minimum assets under management"
          className="px-2"
        >
          <option value={0}>Any AUM</option>
          <option value={100e6}>≥ ₺100M</option>
          <option value={500e6}>≥ ₺500M</option>
          <option value={1e9}>≥ ₺1B</option>
        </Select>
        <span className="text-sm text-muted">{rows.length} funds</span>
      </div>
      <p className="-mt-1 mb-4 text-xs text-muted">
        Scores are fixed-weight research heuristics, not recommendations or
        citable evidence of individual manager skill. Compare funds within the
        same category.
      </p>

      <div className="overflow-x-auto rounded-xl border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-surface text-left">
              <th scope="col" className="sticky left-0 z-10 bg-surface px-3 py-2.5 font-medium">
                Fund
              </th>
              {COLS.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={sortKey === column.key ? (asc ? "ascending" : "descending") : "none"}
                  className="whitespace-nowrap px-3 py-2.5 text-right font-medium"
                >
                  <button
                    type="button"
                    onClick={() => setSort(column.key)}
                    title={column.help}
                    aria-label={`${column.label}. ${column.help} Activate to sort.`}
                    className="cursor-pointer select-none hover:text-accent"
                  >
                    {column.label}
                    {sortKey === column.key && (asc ? " ↑" : " ↓")}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, visible).map((fund) => (
              <tr key={fund.code} className="group border-b last:border-0 hover:bg-accent-soft/40">
                <td className="sticky left-0 bg-surface px-3 py-2.5 group-hover:bg-accent-soft/40">
                  <Link href={`/funds/${fund.code}`} className="block">
                    <span className="font-medium text-accent">{fund.code}</span>
                    <span className="ml-2 text-muted">{(fund.title ?? "").slice(0, 42)}</span>
                  </Link>
                </td>
                {COLS.map((column) => (
                  <td
                    key={column.key}
                    className={`tnum whitespace-nowrap px-3 py-2.5 text-right ${
                      column.sign ? signClass(fund[column.key]) : ""
                    }`}
                  >
                    {column.fmt(fund)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > visible && (
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-muted">
            Showing {visible.toLocaleString()} of {rows.length.toLocaleString()} funds.
          </p>
          <Button variant="secondary" onClick={() => setVisible((count) => count + PAGE_SIZE)}>
            Show 100 more
          </Button>
        </div>
      )}
    </div>
  );
}
