"""Market Overview — what is happening in Turkey today? (pure viewer)"""
import streamlit as st

import dashlib as dl

st.title("🌍 Market Overview")
st.caption("*What is happening in Turkey today?*")
dl.rf_caption()

s = dl.status()
snap = s.get("market_snapshot", {}).get("value", {})
br = s.get("breadth", {}).get("value", {})
mood = s.get("risk_appetite", {}).get("value", {})
counts = s.get("row_counts", {}).get("value", {})

if snap:
    cols = st.columns(len(snap))
    for col, (label, v) in zip(cols, snap.items()):
        col.metric(label, f"{v['level']:,.1f}",
                   f"{v['chg_1d'] * 100:+.2f}% (1d)")
    st.caption(f"as of {list(snap.values())[0]['date']}; NAV-based fund "
               "data lags one day")

if br:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Advancers / Decliners",
              f"{br['advancers']} / {br['decliners']}",
              f"ratio {br['adv_dec_ratio']}")
    c2.metric("% above 50d MA", f"{br['pct_above_50d_ma']}%")
    c3.metric("Equity turnover", f"₺{br['turnover_bn_try']}B")
    c4.metric("Breadth date", br["date"])

st.divider()

metrics_tbl = dl.read_table("dash_metrics", index_col="code")
cf = dl.read_table("dash_cat_flows", index_col="category")
if dl.require(metrics_tbl, "dash_metrics") and dl.require(cf, "dash_cat_flows"):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total fund AUM", f"₺{metrics_tbl['aum'].sum() / 1e12:.2f}T")
    c2.metric("30d net fund flow",
              f"₺{cf['net_flow_try'].sum() / 1e9:+.0f}B")
    if mood:
        c3.metric("Investor risk appetite", mood["reading"].split(" ")[0])
        c4.metric("Risk-asset AUM share",
                  f"{mood['risk_asset_aum_share_now']:.0f}%",
                  f"{mood['risk_asset_aum_share_now'] - mood['risk_asset_aum_share_year_ago']:+.1f}pp vs yr ago")

    st.subheader("Net flows by category — last 30 days (₺bn)")
    st.bar_chart(cf["net_flow_bn"], color=dl.BLUE, horizontal=True)

rot = dl.read_table("dash_rotation", index_col="date")
if not rot.empty:
    st.subheader("Where the money sits — AUM share by category (%)")
    top_cats = rot.iloc[-1].nlargest(5).index.tolist()
    st.line_chart(rot[top_cats], color=dl.SERIES[:len(top_cats)])
    st.caption("Month-end AUM share, top 5 categories. Rising share with "
               "negative flows = price effect, not new money.")
