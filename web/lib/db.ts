import postgres from "postgres";

// Single database layer (the "single point of DB access" principle).
// All queries run server-side only. To later add auth/realtime, swap
// this file for the Supabase JS client — nothing else changes.
const url = process.env.SUPABASE_DB_URL;
if (!url) {
  throw new Error("SUPABASE_DB_URL is not set (see web/.env.local)");
}

const globalForDb = globalThis as unknown as {
  sql?: ReturnType<typeof postgres>;
};

// Use the Supabase TRANSACTION pooler (port 6543 in the URL) — it
// multiplexes many client connections and is built for serverless.
// A small per-process pool (5) lets a page's concurrent Promise.all
// queries each grab a connection instead of deadlocking on one; the
// pooler handles the aggregate count. (max: 1 caused multi-query pages
// to hang; the session pooler on 5432 caps clients at 15 and is the
// wrong mode here.)
export const sql =
  globalForDb.sql ??
  postgres(url, {
    ssl: "require",
    prepare: false, // required for the transaction pooler
    max: 5,
    idle_timeout: 10,
    connect_timeout: 15,
  });

if (process.env.NODE_ENV !== "production") globalForDb.sql = sql;
