"""Fund Explorer — is this fund good? (viewer + per-fund on-demand)"""
import pandas as pd
import streamlit as st

import dashlib as dl

st.title("🔎 Fund Explorer")
st.caption("*Is this fund good?*")
dl.rf_caption()

table = dl.read_table("dash_metrics", index_col="code")
if not dl.require(table, "dash_metrics"):
    st.stop()

rf = dl.status().get("presentation_rf", {}).get("value", 0.40)

options = [f"{c} — {t[:60]}" for c, t in table["title"].dropna().items()]
default_ix = next((i for i, o in enumerate(options)
                   if o.startswith("AFT ")), 0)
pick = st.selectbox("Fund", options, index=default_ix)
code = pick.split(" — ")[0]
m = table.loc[code]

st.subheader(m["title"])
st.caption(f"{m['category']} · {int(m['investors']):,} investors"
           if pd.notna(m["investors"]) else str(m["category"]))
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("1y return", f"{m['ret_1y'] * 100:.1f}%"
          if pd.notna(m["ret_1y"]) else "—")
c2.metric("vs BIST100 (1y)", f"{m['excess_1y'] * 100:+.1f}pp"
          if pd.notna(m["excess_1y"]) else "—")
c3.metric("Sharpe", f"{m['sharpe']:.2f}")
c4.metric("Max drawdown", f"{m['max_dd'] * 100:.1f}%")
c5.metric("AUM", f"₺{m['aum'] / 1e9:.2f}B" if pd.notna(m["aum"]) else "—")

st.subheader("NAV")
st.line_chart(dl.load_nav(code), color=dl.BLUE)

f = dl.load_factor_model(code)
if f:
    st.subheader("What drives this fund? (1y factor attribution)")
    attr = pd.DataFrame(f["factors"]).T
    attr.loc["unexplained"] = [None, None, f["unexplained_return"]]
    st.dataframe(attr, use_container_width=True)
    st.caption(f"R² = {f['r_squared']:.2f}. 'Unexplained' mixes manager "
               "skill with missing factors — it is not pure alpha.")
else:
    st.info("Not enough overlapping history for the factor model.")

roll = dl.load_rolling(code, rf)
if roll is not None:
    st.subheader("Rolling 63-day Sharpe")
    st.line_chart(roll["roll_sharpe"], color=dl.BLUE)

with st.expander("📄 Investment memo (auto-generated)"):
    text = dl.load_memo(code, rf)
    st.markdown(text) if text else st.info("Not enough data for a memo.")
