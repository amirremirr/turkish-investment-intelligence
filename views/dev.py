"""Developer — pipeline status, table sizes, timings."""
import os
import time

import pandas as pd
import streamlit as st

import dashlib as dl
from tefaslab import db

st.title("🛠 Developer")
st.caption("*Pipeline status and performance monitoring.*")

s = dl.status()
if not s:
    st.warning("No system_status yet — run `python -m tefaslab daily`.")
    st.stop()

pipeline_ts = s.get("pipeline_complete", {}).get("updated_at", "never")
counts = s.get("row_counts", {}).get("value", {})
c1, c2, c3 = st.columns(3)
c1.metric("Last pipeline run", pipeline_ts.replace("T", " "))
c2.metric("DB size",
          f"{os.path.getsize(db.DB_PATH) / 1e6:,.0f} MB")
c3.metric("Presentation rf",
          f"{s.get('presentation_rf', {}).get('value', 0.4):.0%}")

st.subheader("Raw table row counts")
if counts:
    st.dataframe(pd.Series(counts, name="rows").to_frame(),
                 use_container_width=True)

st.subheader("Pipeline step timings (last run)")
timings = {k: v["value"].get("seconds")
           for k, v in s.items()
           if isinstance(v.get("value"), dict) and "seconds" in v["value"]}
if timings:
    st.dataframe(pd.Series(timings, name="seconds").to_frame(),
                 use_container_width=True)

st.subheader("Live query benchmark")
if st.button("Run benchmark"):
    conn = db.connect()
    results = {}
    for label, q in [
            ("dash_metrics full read", "SELECT * FROM dash_metrics"),
            ("one fund NAV",
             "SELECT date, price FROM prices WHERE code='AFT'"),
            ("latest prices join",
             "SELECT COUNT(*) FROM prices WHERE "
             "date=(SELECT MAX(date) FROM prices)")]:
        t0 = time.perf_counter()
        pd.read_sql_query(q, conn)
        results[label] = round(time.perf_counter() - t0, 4)
    conn.close()
    st.dataframe(pd.Series(results, name="seconds").to_frame(),
                 use_container_width=True)

st.subheader("system_status (raw)")
st.json({k: v for k, v in s.items()}, expanded=False)
