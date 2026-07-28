import { signClass } from "@/lib/format";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  SelectHTMLAttributes,
} from "react";

const controlBase =
  "h-9 rounded-lg border bg-surface px-3 text-sm shadow-[var(--shadow-sm)] outline-none transition-colors placeholder:text-muted hover:border-fg/25 focus:border-accent";

export function Button({
  className = "",
  variant = "primary",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
}) {
  const styles = {
    primary: "bg-accent text-white hover:opacity-90",
    secondary: "bg-surface text-fg hover:bg-accent-soft",
    ghost: "border-transparent bg-transparent text-muted shadow-none hover:bg-accent-soft hover:text-fg",
  };
  return (
    <button
      type={type}
      className={`inline-flex h-9 items-center justify-center rounded-lg border px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${controlBase} ${className}`} {...props} />;
}

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${controlBase} ${className}`} {...props} />;
}

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "accent" | "positive" | "warning";
  className?: string;
}) {
  const styles = {
    neutral: "bg-surface text-muted",
    accent: "bg-accent-soft text-accent",
    positive: "bg-[color-mix(in_srgb,var(--pos)_12%,transparent)] text-pos",
    warning: "bg-warning-soft text-warning",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${styles[tone]} ${className}`}>
      {children}
    </span>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

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
