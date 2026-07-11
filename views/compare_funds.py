"""Compare — which one should I choose? (on-demand after selection)"""
import pandas as pd
import streamlit as st

import dashlib as dl

st.title("⚖️ Compare")
st.caption("*Which one should I choose?*")
dl.rf_caption()

table = dl.read_table("dash_metrics", index_col="code")
if not dl.require(table, "dash_metrics"):
    st.stop()
rf = dl.status().get("presentation_rf", {}).get("value", 0.40)

codes = st.multiselect(
    "Funds to compare (2–5)", sorted(table.index.tolist()),
    default=[c for c in ("MAC", "AFT", "YEF") if c in table.index])
if 2 <= len(codes) <= 5:
    navs = pd.DataFrame({c: dl.load_nav(c) for c in codes}).dropna()
    rebased = navs / navs.iloc[0] * 100
    st.subheader("Growth of 100 (common period)")
    st.line_chart(rebased, color=dl.SERIES[:len(codes)])

    cmp_table = dl.load_compare(tuple(sorted(codes)), rf)
    st.dataframe(cmp_table.astype(str), use_container_width=True, height=800)
else:
    st.info("Pick between 2 and 5 funds.")
