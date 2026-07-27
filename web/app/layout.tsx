import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";


export const metadata: Metadata = {
  title: {
    default: "Turkish Fund Intelligence",
    template: "%s · Turkish Fund Intelligence",
  },
  description:
    "Professional analytics for the Turkish fund and equity market — " +
    "factor models, flows, holdings, and research. Not investment advice.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="flex min-h-full flex-col">
        <Nav />
        <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8">
          {children}
        </main>
        <footer className="border-t">
          <div className="mx-auto max-w-6xl px-5 py-8 text-xs text-muted">
            Built on public data (TEFAS, KAP, TCMB EVDS, Yahoo). Figures are
            nominal TRY. Not investment advice — for research and education.
          </div>
        </footer>
      </body>
    </html>
  );
}
