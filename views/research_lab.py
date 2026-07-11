"""Research Lab — interactive studies. The one page where waiting is OK:
nothing runs until you press Run."""
import streamlit as st

import dashlib as dl
from tefaslab import db, research

st.title("🔬 Research Lab")
st.caption("*Run your own studies. Computation happens on demand.*")

study = st.selectbox("Study", [
    "Flow predictability — do fund flows predict BIST returns?",
    "Performance chasing — do investors buy after returns happen?",
    "Closet indexing — are active funds actually active?",
])

if study.startswith("Flow"):
    c1, c2 = st.columns(2)
    category = c1.selectbox("Flow category", [
        "Equity Turkey", "Foreign Equity", "Precious Metals",
        "Money Market", "Hedge (Serbest)"])
    regime = c2.selectbox("Volatility regime", ["full sample", "high_vol",
                                                "low_vol"])
    if st.button("Run regression", type="primary"):
        with st.spinner("Running…"):
            conn = db.connect()
            out = research.flow_predictability(
                conn, category,
                regime=None if regime == "full sample" else regime)
            conn.close()
        st.dataframe(out.round(3), use_container_width=True)
        st.caption("beta = % BIST move per 1% AUM flow. Overlapping "
                   "horizons inflate t-stats; treat |t| > 3 as "
                   "interesting, not |t| > 2.")

elif study.startswith("Performance"):
    category = st.selectbox("Category", [
        "Equity Turkey", "Foreign Equity", "Precious Metals"])
    if st.button("Run regression", type="primary"):
        with st.spinner("Running…"):
            conn = db.connect()
            out = research.performance_chasing(conn, category)
            conn.close()
        st.dataframe(out.round(3), use_container_width=True)
        st.caption("beta = weekly flow (%AUM) per 100% trailing return. "
                   "A positive, significant beta at longer lookbacks = "
                   "medium-term return chasing.")

else:
    min_aum = st.number_input("Min AUM (₺mn)", 0, 100000, 500, 100)
    if st.button("Run analysis", type="primary"):
        with st.spinner("Running…"):
            conn = db.connect()
            summary, detail = research.closet_index(conn,
                                                    min_aum=min_aum * 1e6)
            conn.close()
        st.dataframe(summary, use_container_width=True)
        st.subheader("Most index-like")
        st.dataframe(detail.head(15).round(3), use_container_width=True)
        st.subheader("Most active")
        st.dataframe(detail.tail(15).round(3), use_container_width=True)
