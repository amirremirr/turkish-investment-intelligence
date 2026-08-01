import { NextResponse } from "next/server";
import { getSearchResults } from "@/lib/queries";

export const revalidate = 300;

export async function GET(request: Request) {
  const query = new URL(request.url).searchParams.get("q") ?? "";
  try {
    const results = await getSearchResults(query);
    return NextResponse.json(
      { results },
      { headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600" } }
    );
  } catch {
    // Search is a convenience layer. Do not disclose database details or make
    // an unavailable search endpoint look like a broken product page.
    return NextResponse.json({ results: [] }, { status: 503 });
  }
}
