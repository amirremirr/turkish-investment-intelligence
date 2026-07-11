"""Data Explorer — browse, filter, download, or query with SQL."""
import pandas as pd
import streamlit as st

import dashlib as dl
from tefaslab import db, flows

st.title("🗂 Data Explorer")
st.caption("*Raw and derived data — filter, browse, download, or query "
           "with SQL. Draw your own conclusions.*")


@st.cache_data(ttl=1800)
def load_dataset(name: str, category: str, code_filter: str,
                 start: str, end: str) -> pd.DataFrame:
    conn = db.connect()
    params: list = []
    if name == "prices (daily NAV/AUM/investors)":
        q = ("SELECT p.code, f.title, f.category, p.date, p.price, "
             "p.shares, p.investors, p.aum FROM prices p "
             "JOIN funds f ON f.code = p.code WHERE p.date BETWEEN ? AND ?")
        params = [start, end]
    elif name == "allocations (daily asset weights)":
        q = ("SELECT a.code, f.title, f.category, a.date, a.asset, a.pct "
             "FROM allocations a JOIN funds f ON f.code = a.code "
             "WHERE a.date BETWEEN ? AND ?")
        params = [start, end]
    elif name == "benchmarks (BIST/FX/gold/Nasdaq/sectors)":
        q = ("SELECT series, date, value FROM benchmarks "
             "WHERE date BETWEEN ? AND ?")
        params = [start, end]
    elif name == "stock prices (BIST OHLCV)":
        q = ("SELECT sp.ticker AS code, s.title, s.sector, sp.date, "
             "sp.open, sp.high, sp.low, sp.close, sp.volume "
             "FROM stock_prices sp LEFT JOIN stocks s ON s.ticker=sp.ticker "
             "WHERE sp.date BETWEEN ? AND ?")
        params = [start, end]
    elif name == "stocks (BIST company registry)":
        q = "SELECT ticker AS code, title, sector, industry, city FROM stocks"
    elif name == "metrics (precomputed per fund)":
        q = "SELECT * FROM dash_metrics"
    elif name == "funds (registry + category)":
        q = "SELECT code, title, fund_type, category FROM funds"
    else:  # daily fund flows
        out = flows.load_flow_frame(conn)
        out = out[(out["date"] >= start) & (out["date"] <= end)]
        conn.close()
        return out
    df = pd.read_sql_query(q, conn, params=params or None)
    conn.close()
    if category != "All" and "category" in df.columns:
        df = df[df["category"] == category]
    if code_filter and "code" in df.columns:
        codes = [c.strip().upper() for c in code_filter.split(",")]
        df = df[df["code"].isin(codes)]
    return df


datasets = ["prices (daily NAV/AUM/investors)",
            "allocations (daily asset weights)",
            "flows (daily net flow per fund)",
            "metrics (precomputed per fund)",
            "benchmarks (BIST/FX/gold/Nasdaq/sectors)",
            "stock prices (BIST OHLCV)",
            "stocks (BIST company registry)",
            "funds (registry + category)"]

meta = dl.read_table("dash_metrics", index_col="code")
c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
ds = c1.selectbox("Dataset", datasets)
cats = ["All"] + (sorted(meta["category"].dropna().unique().tolist())
                  if not meta.empty else [])
cat = c2.selectbox("Category", cats)
code_filter = c3.text_input("Fund codes (comma-sep)", "")
dcol1, dcol2 = c4.columns(2)
start = dcol1.text_input("From", "2026-01-01")
end = dcol2.text_input("To", "2026-12-31")

df = load_dataset(ds, cat, code_filter, start, end)
st.write(f"{len(df):,} rows")
st.dataframe(df.head(2000), use_container_width=True, height=450)
st.download_button("⬇ Download full result as CSV",
                   df.to_csv(index=False).encode("utf-8"),
                   file_name="tefas_export.csv", mime="text/csv")
st.caption("Table view shows the first 2,000 rows; the download contains "
           "everything.")

with st.expander("🧪 SQL query (read-only)"):
    st.caption("Tables: funds, prices, allocations, benchmarks, stocks, "
               "stock_prices, dash_* (precomputed). SELECT only.")
    sql = st.text_area(
        "Query",
        "SELECT f.category, COUNT(*) funds, SUM(p.aum)/1e9 aum_bn\n"
        "FROM funds f\n"
        "JOIN prices p ON p.code = f.code\n"
        "WHERE p.date = (SELECT MAX(date) FROM prices)\n"
        "GROUP BY f.category ORDER BY aum_bn DESC",
        height=160)
    if st.button("Run query"):
        if sql.strip().lower().startswith("select"):
            try:
                conn = db.connect()
                res = pd.read_sql_query(sql, conn)
                conn.close()
                st.dataframe(res, use_container_width=True)
                st.download_button("⬇ Download query result",
                                   res.to_csv(index=False).encode("utf-8"),
                                   file_name="query_result.csv",
                                   mime="text/csv")
            except Exception as err:
                st.error(str(err))
        else:
            st.error("SELECT statements only.")
