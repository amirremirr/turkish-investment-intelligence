"use client";

import { useMemo, useState } from "react";
import { num } from "@/lib/format";

type NavPoint = { date: string; price: number };
type Range = "1M" | "3M" | "6M" | "1Y" | "Max";

const RANGES: { label: Range; days?: number }[] = [
  { label: "1M", days: 31 },
  { label: "3M", days: 92 },
  { label: "6M", days: 184 },
  { label: "1Y", days: 366 },
  { label: "Max" },
];

const WIDTH = 720;
const HEIGHT = 280;
const PAD = { top: 18, right: 14, bottom: 36, left: 54 };

function dateLabel(date: string) {
  const value = new Date(`${date}T00:00:00Z`);
  return Number.isNaN(value.getTime())
    ? date
    : new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(value);
}

export function NavChart({ points }: { points: NavPoint[] }) {
  const [range, setRange] = useState<Range>("1Y");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const visible = useMemo(() => {
    const config = RANGES.find((item) => item.label === range);
    if (!config?.days || points.length < 2) return points;
    const last = Date.parse(`${points.at(-1)?.date ?? ""}T00:00:00Z`);
    const cutoff = last - config.days * 86_400_000;
    const filtered = points.filter((point) =>
      Date.parse(`${point.date}T00:00:00Z`) >= cutoff
    );
    return filtered.length >= 2 ? filtered : points;
  }, [points, range]);

  const dimensions = useMemo(() => {
    const min = Math.min(...visible.map((point) => point.price));
    const max = Math.max(...visible.map((point) => point.price));
    const spread = max - min || Math.max(max * 0.02, 1);
    const chartWidth = WIDTH - PAD.left - PAD.right;
    const chartHeight = HEIGHT - PAD.top - PAD.bottom;
    const x = (index: number) => PAD.left + (index / Math.max(visible.length - 1, 1)) * chartWidth;
    const y = (price: number) => PAD.top + chartHeight - ((price - min) / spread) * chartHeight;
    const coords = visible.map((point, index) => ({ x: x(index), y: y(point.price) }));
    const line = coords.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
    const area = `M${coords[0]?.x.toFixed(1)},${(HEIGHT - PAD.bottom).toFixed(1)} ${coords.map((point) => `L${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ")} L${coords.at(-1)?.x.toFixed(1)},${(HEIGHT - PAD.bottom).toFixed(1)} Z`;
    let runningPeak = -Infinity;
    const peaks = visible.map((point, index) => {
      runningPeak = Math.max(runningPeak, point.price);
      return { x: x(index), y: y(runningPeak) };
    });
    const drawdown = coords.length
      ? `${coords.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ")} ${[...peaks].reverse().map((point) => `L${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ")} Z`
      : "";
    return { min, max, x, y, coords, line, area, drawdown };
  }, [visible]);

  if (visible.length < 2) return null;

  const active = visible[Math.min(hoverIndex ?? visible.length - 1, visible.length - 1)];
  const activeCoord = dimensions.coords[Math.min(hoverIndex ?? visible.length - 1, visible.length - 1)];
  const start = visible[0].price;
  const periodReturn = start ? (active.price / start - 1) * 100 : 0;
  const up = visible.at(-1)!.price >= start;
  const digits = dimensions.max < 10 ? 4 : 2;
  const color = up ? "var(--pos)" : "var(--neg)";

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="tnum text-lg font-semibold">{num(active.price, digits)} NAV</div>
          <div className="text-xs text-muted">
            {dateLabel(active.date)} · <span className={periodReturn >= 0 ? "text-pos" : "text-neg"}>{periodReturn >= 0 ? "+" : ""}{num(periodReturn, 1)}%</span> over selected period
          </div>
        </div>
        <div className="flex rounded-lg border p-0.5" aria-label="NAV chart period">
          {RANGES.map((item) => (
            <button
              key={item.label}
              type="button"
              aria-pressed={range === item.label}
              onClick={() => {
                setRange(item.label);
                setHoverIndex(null);
              }}
              className={`rounded-md px-2 py-1 text-xs font-medium ${range === item.label ? "bg-accent text-white" : "text-muted hover:bg-accent-soft hover:text-fg"}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`NAV history chart, ${range} period. ${dateLabel(active.date)}, NAV ${num(active.price, digits)}.`}
        className="h-56 w-full touch-none"
        onPointerMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left - (PAD.left / WIDTH) * rect.width) / (((WIDTH - PAD.left - PAD.right) / WIDTH) * rect.width)));
          setHoverIndex(Math.round(ratio * (visible.length - 1)));
        }}
        onPointerLeave={() => setHoverIndex(null)}
      >
        {[0, 0.5, 1].map((fraction) => {
          const price = dimensions.min + (dimensions.max - dimensions.min) * fraction;
          const y = dimensions.y(price);
          return (
            <g key={fraction}>
              <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y} y2={y} stroke="var(--line)" strokeDasharray="3 4" />
              <text x={PAD.left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="var(--muted)">{num(price, digits)}</text>
            </g>
          );
        })}
        <path d={dimensions.area} fill={color} opacity="0.07" />
        {dimensions.drawdown && <path d={dimensions.drawdown} fill="var(--neg)" opacity="0.08" />}
        <path d={dimensions.line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {hoverIndex != null && activeCoord && (
          <>
            <line x1={activeCoord.x} x2={activeCoord.x} y1={PAD.top} y2={HEIGHT - PAD.bottom} stroke="var(--muted)" strokeDasharray="3 3" />
            <circle cx={activeCoord.x} cy={activeCoord.y} r="4" fill="var(--surface)" stroke={color} strokeWidth="2" />
          </>
        )}
        <text x={PAD.left} y={HEIGHT - 10} fontSize="10" fill="var(--muted)">{dateLabel(visible[0].date)}</text>
        <text x={WIDTH - PAD.right} y={HEIGHT - 10} textAnchor="end" fontSize="10" fill="var(--muted)">{dateLabel(visible.at(-1)!.date)}</text>
      </svg>
      <p className="mt-2 text-xs text-muted">
        NAV is the fund&apos;s published unit price in nominal TRY. The red band marks periods below the prior peak; it is context, not a forecast.
      </p>
    </div>
  );
}
