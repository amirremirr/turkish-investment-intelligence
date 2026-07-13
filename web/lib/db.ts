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

export const sql =
  globalForDb.sql ??
  postgres(url, {
    ssl: "require",
    prepare: false, // safe with Supabase's connection pooler
    max: 3,
    idle_timeout: 20,
    connect_timeout: 15,
  });

if (process.env.NODE_ENV !== "production") globalForDb.sql = sql;
