"""Market Overview — what is happening in Turkey today? (pure viewer)"""
import streamlit as st

import dashlib as dl

st.title("🌍 Market Overview")
st.caption("*What is happening in Turkey today?*")
dl.rf_caption()
dl.auto_refresh(60)

s = dl.status()
snap = s.get("market_snapshot", {}).get("value", {})
br = s.get("breadth", {}).get("value", {})
mood = s.get("risk_appetite", {}).get("value", {})
counts = s.get("row_counts", {}).get("value", {})

live = dl.intraday_fresh()
if live and live.get("snapshot"):
    cols = st.columns(len(live["snapshot"]) + 1)
    for col, (label, v) in zip(cols, live["snapshot"].items()):
        col.metric(f"🔴 {label}", f"{v['level']:,.1f}",
                   f"{v['chg_1d'] * 100:+.2f}%")
    lb = live.get("breadth", {})
    cols[-1].metric("Adv / Dec (live)",
                    f"{lb.get('advancers', '–')} / "
                    f"{lb.get('decliners', '–')}")
    st.caption(f"LIVE as of {live['ts']} (quotes delayed ~15 min; "
               "refreshed every 15 min during BIST hours)")
elif snap:
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

macro = s.get("macro_regime", {}).get("value", {})
if macro:
    st.divider()
    st.subheader("Macro regime")
    c1, c2, c3, c4 = st.columns(4)
    if "inflation_yoy" in macro:
        c1.metric("Inflation (yoy)", f"{macro['inflation_yoy']}%",
                  macro.get("inflation_trend", ""),
                  delta_color="inverse")
    if "policy_rate" in macro:
        c2.metric("Policy rate (CBRT funding)",
                  f"{macro['policy_rate']}%")
    if "real_rate" in macro:
        c3.metric("Real rate", f"{macro['real_rate']:+.1f}pp",
                  macro.get("rates", ""))
    if "usdtry_3m_pct" in macro:
        c4.metric("USDTRY 3m", f"{macro['usdtry_3m_pct']:+.1f}%",
                  macro.get("fx", ""), delta_color="inverse")
    st.caption(f"CPI as of {macro.get('inflation_asof', '?')} "
               "(publication lag). Regime thresholds documented in "
               "METHODOLOGY.")

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
