"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/funds", label: "Funds" },
  { href: "/stocks", label: "Stocks" },
  { href: "/market", label: "Market" },
  { href: "/signals", label: "Signal Lab" },
  { href: "/research", label: "Research" },
  { href: "/status", label: "Data status" },
];

export function Nav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const active = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  const navLink = (link: (typeof LINKS)[number], mobile = false) => (
    <Link
      key={link.href}
      href={link.href}
      onClick={() => setOpen(false)}
      className={`rounded-md px-3 py-1.5 transition-colors ${
        mobile ? "block text-base" : ""
      } ${
        active(link.href)
          ? "bg-accent-soft text-accent"
          : "text-muted hover:text-fg"
      }`}
    >
      {link.label}
    </Link>
  );

  return (
    <header className="sticky top-0 z-20 border-b bg-surface/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-5">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span aria-hidden>▦</span>
          <span className="hidden sm:inline">Turkish Fund Intelligence</span>
          <span className="sm:hidden">TFI</span>
        </Link>
        <nav aria-label="Primary navigation" className="hidden items-center gap-1 text-sm md:flex">
          {LINKS.map((link) => navLink(link))}
        </nav>
        <a
          href="https://github.com/amirremirr/turkish-investment-intelligence"
          target="_blank"
          rel="noreferrer"
          className="ml-auto hidden text-sm text-muted hover:text-fg md:inline"
        >
          GitHub ↗
        </a>
        <Button
          variant="ghost"
          className="ml-auto w-9 px-0 md:hidden"
          aria-expanded={open}
          aria-controls="mobile-navigation"
          aria-label={open ? "Close navigation" : "Open navigation"}
          onClick={() => setOpen((value) => !value)}
        >
          <span aria-hidden>{open ? "×" : "☰"}</span>
        </Button>
      </div>
      {open && (
        <div id="mobile-navigation" className="border-t bg-surface px-5 py-3 md:hidden">
          <nav aria-label="Mobile navigation" className="mx-auto grid max-w-6xl gap-1">
            {LINKS.map((link) => navLink(link, true))}
            <a
              href="https://github.com/amirremirr/turkish-investment-intelligence"
              target="_blank"
              rel="noreferrer"
              className="mt-2 rounded-md px-3 py-2 text-sm text-muted hover:bg-accent-soft hover:text-fg"
            >
              GitHub ↗
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}
