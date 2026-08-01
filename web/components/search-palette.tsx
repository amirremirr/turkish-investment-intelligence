"use client";

import { useCallback, useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui";

type SearchResult = {
  kind: "fund" | "stock";
  code: string;
  title: string | null;
  detail: string | null;
  href: string;
};

export function SearchPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const listId = useId();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);

  const close = useCallback(() => {
    onOpenChange(false);
    setQuery("");
    setResults([]);
    setActive(0);
  }, [onOpenChange]);

  const select = (result: SearchResult) => {
    router.push(result.href);
    close();
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpenChange(true);
      }
      if (event.key === "Escape" && open) close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [close, onOpenChange, open]);

  useEffect(() => {
    const term = query.trim();
    if (!open || term.length < 2 || term.length > 80) {
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(term)}`, {
          signal: controller.signal,
        });
        const body = (await response.json()) as { results?: SearchResult[] };
        if (!controller.signal.aborted) {
          setResults(Array.isArray(body.results) ? body.results : []);
          setActive(0);
        }
      } catch {
        if (!controller.signal.aborted) setResults([]);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 150);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [open, query]);

  if (!open) return null;

  const message = query.trim().length < 2
    ? "Type at least two characters to search funds and BIST stocks."
    : query.trim().length > 80
      ? "Searches can contain up to 80 characters."
      : loading
        ? "Searching…"
        : results.length === 0
          ? "No matching fund or stock was found."
          : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-fg/20 px-4 pt-[12vh] backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="search-palette-title"
        className="w-full max-w-xl overflow-hidden rounded-xl border bg-surface shadow-xl"
      >
        <div className="border-b p-3">
          <div className="flex items-center gap-3">
            <span aria-hidden className="text-muted">⌕</span>
            <Input
              autoFocus
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setResults([]);
                setActive(0);
              }}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown" && results.length) {
                  event.preventDefault();
                  setActive((index) => (index + 1) % results.length);
                } else if (event.key === "ArrowUp" && results.length) {
                  event.preventDefault();
                  setActive((index) => (index - 1 + results.length) % results.length);
                } else if (event.key === "Enter" && results[active]) {
                  event.preventDefault();
                  select(results[active]);
                } else if (event.key === "Escape") {
                  event.preventDefault();
                  close();
                }
              }}
              aria-label="Search funds and stocks"
              aria-controls={listId}
              aria-activedescendant={results[active] ? `${listId}-${active}` : undefined}
              placeholder="Search funds or BIST stocks…"
              className="h-10 flex-1 border-0 bg-transparent px-0 shadow-none focus:border-0"
            />
            <kbd className="rounded border px-1.5 py-0.5 text-xs text-muted">Esc</kbd>
          </div>
        </div>
        <h2 id="search-palette-title" className="sr-only">Search funds and stocks</h2>
        <div id={listId} role="listbox" className="max-h-96 overflow-y-auto p-2">
          {message ? (
            <p className="px-3 py-6 text-center text-sm text-muted">{message}</p>
          ) : (
            results.map((result, index) => (
              <button
                key={`${result.kind}-${result.code}`}
                id={`${listId}-${index}`}
                type="button"
                role="option"
                aria-selected={index === active}
                onMouseEnter={() => setActive(index)}
                onClick={() => select(result)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left ${
                  index === active ? "bg-accent-soft" : "hover:bg-accent-soft/60"
                }`}
              >
                <span className="w-12 text-xs font-medium uppercase tracking-wide text-muted">
                  {result.kind}
                </span>
                <span className="w-14 font-medium text-accent">{result.code}</span>
                <span className="min-w-0 flex-1 truncate text-sm">{result.title ?? "Unnamed"}</span>
                {result.detail && <span className="max-w-28 truncate text-xs text-muted">{result.detail}</span>}
              </button>
            ))
          )}
        </div>
        <div className="flex gap-3 border-t px-4 py-2 text-xs text-muted">
          <span>↑↓ to select</span><span>Enter to open</span><span>Esc to close</span>
        </div>
      </div>
    </div>
  );
}
