"""Intelligence — what opportunities and problems exist? (pure viewer)"""
import streamlit as st

import dashlib as dl

st.title("🧠 Intelligence")
st.caption("*What opportunities and problems exist?*")
dl.rf_caption()

s = dl.status()
mood = s.get("risk_appetite", {}).get("value", {})
cf = dl.read_table("dash_cat_flows", index_col="category")

if not cf.empty:
    st.subheader("Today's signals")
    eq = cf.loc["Equity Turkey", "net_flow_bn"] \
        if "Equity Turkey" in cf.index else 0
    mm = cf.loc["Money Market", "net_flow_bn"] \
        if "Money Market" in cf.index else 0
    st.markdown(f"- **Money market flows**: ₺{mm:+.0f}bn / 30d — investors "
                f"are {'defensive' if mm > 0 else 'deploying cash'}")
    st.markdown(f"- **Equity fund flows**: ₺{eq:+.0f}bn / 30d — "
                f"{'accumulation' if eq > 0 else 'distribution'}")
    if mood:
        st.markdown(f"- **Risk appetite**: {mood['reading']} "
                    f"(flow tilt to risk: {mood['flow_tilt_to_risk']:.2f})")

q = dl.read_table("dash_quality", index_col="code")
if dl.require(q, "dash_quality"):
    st.subheader("Fund scores — skill vs suitability")
    st.caption("Manager Skill: is the manager good? Investor Suitability: "
               "should a typical investor buy it? They deliberately "
               "disagree.")
    show = q.sort_values("skill_score", ascending=False).head(15)[
        ["title", "category", "ret_1y", "sharpe", "max_dd",
         "skill_score", "suitability_score"]].copy()
    show["ret_1y"] = (show["ret_1y"] * 100).round(1)
    show["max_dd"] = (show["max_dd"] * 100).round(1)
    show["sharpe"] = show["sharpe"].round(2)
    st.dataframe(show, use_container_width=True)

summary = dl.read_table("dash_closet_summary", index_col="bucket")
if not summary.empty:
    st.subheader("Closet index watch (Equity Turkey)")
    st.dataframe(summary, use_container_width=True)
    st.caption("closet index = R² ≥ 0.85 with beta ≈ 1: index exposure "
               "sold at active fees. Verify before acting — small funds "
               "can show artifact alphas.")
    with st.expander("Full detail table"):
        st.dataframe(dl.read_table("dash_closet_detail", index_col="code"),
                     use_container_width=True)
