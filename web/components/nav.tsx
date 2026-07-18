"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/funds", label: "Funds" },
  { href: "/stocks", label: "Stocks" },
  { href: "/market", label: "Market" },
  { href: "/research", label: "Research" },
  { href: "/status", label: "Data status" },
];

export function Nav() {
  const path = usePathname();
  const active = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  return (
    <header className="sticky top-0 z-20 border-b bg-surface/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-5">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span aria-hidden>📊</span>
          <span className="hidden sm:inline">Turkish Fund Intelligence</span>
          <span className="sm:hidden">TFI</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-md px-3 py-1.5 transition-colors ${
                active(l.href)
                  ? "bg-accent-soft text-accent"
                  : "text-muted hover:text-fg"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <a
          href="https://github.com/amirremirr/turkish-investment-intelligence"
          target="_blank"
          rel="noreferrer"
          className="ml-auto hidden text-sm text-muted hover:text-fg sm:inline"
        >
          GitHub ↗
        </a>
      </div>
    </header>
  );
}
