"""Stocks — what is moving in the market? (pure viewer)"""
import streamlit as st

import dashlib as dl

st.title("📈 Stocks")
st.caption("*What is moving in the stock market?*")

sect = dl.read_table("dash_sectors", index_col="sector")
if dl.require(sect, "dash_sectors"):
    st.subheader("Sector performance (median stock, 1 day)")
    st.bar_chart((sect["ret_1d"] * 100).round(2), color=dl.BLUE,
                 horizontal=True)
    with st.expander("Sector table (1d / 1w / 1m)"):
        fmt = sect.copy()
        for c in ("ret_1d", "ret_1w", "ret_1m"):
            fmt[c] = (fmt[c] * 100).round(1)
        st.dataframe(fmt, use_container_width=True)

live = dl.intraday_fresh()
if live and live.get("movers"):
    import pandas as pd
    st.subheader(f"🔴 Live movers — {live['ts']} (delayed ~15 min)")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Gainers**")
        st.dataframe(pd.DataFrame(live["movers"]["gainers"]),
                     use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**Losers**")
        st.dataframe(pd.DataFrame(live["movers"]["losers"]),
                     use_container_width=True, hide_index=True)
    with st.expander("Live turnover leaders / unusual volume"):
        c1, c2 = st.columns(2)
        c1.dataframe(pd.DataFrame(live["movers"]["turnover"]),
                     use_container_width=True, hide_index=True)
        c2.dataframe(pd.DataFrame(live["movers"]["unusual_volume"]),
                     use_container_width=True, hide_index=True)
    st.divider()

movers = dl.read_table("dash_movers")
if dl.require(movers, "dash_movers"):
    def board(name):
        df = movers[movers["board"] == name].set_index("ticker")
        out = df[["title", "close", "ret_1d", "ret_1w",
                  "turnover_mn", "vol_vs_20d"]].copy()
        out["ret_1d"] = (out["ret_1d"] * 100).round(1)
        out["ret_1w"] = (out["ret_1w"] * 100).round(1)
        out["turnover_mn"] = out["turnover_mn"].round(0)
        out["vol_vs_20d"] = out["vol_vs_20d"].round(1)
        return out

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top gainers (1d)")
        st.dataframe(board("gainers"), use_container_width=True)
    with c2:
        st.subheader("Top losers (1d)")
        st.dataframe(board("losers"), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Highest turnover")
        st.dataframe(board("turnover"), use_container_width=True)
    with c2:
        st.subheader("Unusual volume (>2x 20d avg)")
        st.dataframe(board("unusual_volume"), use_container_width=True)
    st.caption("Liquidity filter: daily turnover ≥ ₺10mn. Volume ratio "
               "compares today with the 20-day average.")
