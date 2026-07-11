"""Turkish Fund Intelligence Terminal — multipage entry point.

Run:  streamlit run app.py

Views are pure viewers over dash_* presentation tables built by
`python -m tefaslab daily`. Only the active page executes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(page_title="Turkish Fund Intelligence Terminal",
                   page_icon="📊", layout="wide")

pages = [
    st.Page("views/market.py", title="Market", icon="🌍", default=True),
    st.Page("views/stocks.py", title="Stocks", icon="📈"),
    st.Page("views/funds.py", title="Fund Explorer", icon="🔎"),
    st.Page("views/compare_funds.py", title="Compare", icon="⚖️"),
    st.Page("views/intelligence.py", title="Intelligence", icon="🧠"),
    st.Page("views/research_lab.py", title="Research Lab", icon="🔬"),
    st.Page("views/data_explorer.py", title="Data Explorer", icon="🗂"),
    st.Page("views/dev.py", title="Developer", icon="🛠"),
]

st.sidebar.title("📊 Fund Intelligence")
nav = st.navigation(pages)
nav.run()
