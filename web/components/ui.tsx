import { signClass } from "@/lib/format";

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border bg-surface p-5 ${className}`}
    >
      {children}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  subClass,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  subClass?: string;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className="tnum mt-1 text-2xl font-semibold">{value}</div>
      {sub != null && (
        <div className={`tnum mt-0.5 text-sm ${subClass ?? "text-muted"}`}>
          {sub}
        </div>
      )}
    </div>
  );
}

// A signed value rendered with +/- coloring and an arrow.
export function Delta({
  value,
  text,
}: {
  value: number | null | undefined;
  text: string;
}) {
  const cls = signClass(value);
  const arrow = value == null ? "" : value > 0 ? "▲ " : value < 0 ? "▼ " : "";
  return (
    <span className={`tnum ${cls}`}>
      {arrow}
      {text}
    </span>
  );
}

export function SectionTitle({
  children,
  hint,
}: {
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="mb-3 flex items-baseline justify-between">
      <h2 className="text-lg font-semibold">{children}</h2>
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </div>
  );
}

// Horizontal proportion bar for a signed or unsigned value.
export function Bar({
  value,
  max,
  signed = false,
}: {
  value: number;
  max: number;
  signed?: boolean;
}) {
  const frac = max === 0 ? 0 : Math.min(Math.abs(value) / max, 1);
  const color = !signed
    ? "var(--accent)"
    : value >= 0
      ? "var(--pos)"
      : "var(--neg)";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--line)]">
      <div
        className="h-full rounded-full"
        style={{ width: `${frac * 100}%`, background: color }}
      />
    </div>
  );
}
