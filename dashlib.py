"""Shared helpers for the dashboard views.

Views are pure viewers: they SELECT from dash_* presentation tables
built by `python -m tefaslab daily`. The only live computation allowed
here is per-fund, on-demand work (one fund's NAV, factor model, memo).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tefaslab import compare, db, factors, memo, rolling  # noqa: E402

# categorical palette, fixed slot order (dataviz reference palette)
SERIES = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7"]
BLUE = SERIES[0]


@st.cache_data(ttl=300)
def read_table(name: str, index_col: str | None = None) -> pd.DataFrame:
    conn = db.connect()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {name}", conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    if index_col and index_col in df.columns:
        df = df.set_index(index_col)
    return df


@st.cache_data(ttl=300)
def status() -> dict:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT key, value, updated_at FROM system_status").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    return {k: {"value": json.loads(v), "updated_at": ts}
            for k, v, ts in rows}


def require(df: pd.DataFrame, name: str) -> bool:
    """Guard: show a hint instead of crashing when tables are missing."""
    if df.empty:
        st.warning(f"`{name}` is empty — run `python -m tefaslab daily` "
                   "to build the presentation tables.")
        return False
    return True


def auto_refresh(seconds: int = 60) -> None:
    """Reload the page periodically so live-data pages (Market, Stocks)
    pick up new intraday writes without a manual F5. Streamlit reruns
    a script only on user interaction or reload — never on its own
    when the underlying database changes — so pages showing 'live'
    data need this to actually behave live."""
    st.markdown(f'<meta http-equiv="refresh" content="{seconds}">',
               unsafe_allow_html=True)


def rf_caption() -> None:
    s = status()
    rf = s.get("presentation_rf", {}).get("value", 0.40)
    ts = s.get("pipeline_complete", {}).get("updated_at", "never")
    st.caption(f"Metrics computed at rf={rf:.0%} · last pipeline run: {ts}")
    failed = s.get("pipeline_failed", {}).get("value")
    if failed:
        st.error(f"⚠ Last scheduled pipeline run FAILED: "
                 f"{failed.get('error', 'see logs/')}")
    elif ts != "never":
        from datetime import datetime
        age = (datetime.now()
               - datetime.fromisoformat(ts)).days
        if age >= 3:
            st.warning(f"⚠ Presentation tables are {age} days old — "
                       "run `python -m tefaslab daily`.")


def intraday_fresh(max_age_min: int = 25) -> dict | None:
    """The intraday snapshot if it's recent enough to show, else None."""
    from datetime import datetime
    s = status()
    intra = s.get("intraday", {}).get("value")
    if not intra or "ts" not in intra:
        return None
    try:
        age = (datetime.now()
               - datetime.strptime(intra["ts"], "%Y-%m-%d %H:%M"))
    except ValueError:
        return None
    return intra if age.total_seconds() < max_age_min * 60 else None


# ---- sanctioned live (per-fund, milliseconds) ----

@st.cache_data(ttl=3600)
def load_nav(code: str) -> pd.Series:
    conn = db.connect()
    s = pd.read_sql_query(
        "SELECT date, price FROM prices WHERE code = ? ORDER BY date",
        conn, params=(code,), parse_dates=["date"]).set_index("date")["price"]
    conn.close()
    return s


@st.cache_data(ttl=3600)
def load_factor_model(code: str) -> dict | None:
    conn = db.connect()
    try:
        return factors.fund_factor_model(conn, code)
    except (KeyError, ValueError):
        return None
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def load_rolling(code: str, rf: float) -> pd.DataFrame | None:
    conn = db.connect()
    try:
        return rolling.fund_rolling(conn, code, rf=rf)
    except KeyError:
        return None
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def load_memo(code: str, rf: float) -> str | None:
    table = read_table("dash_metrics", index_col="code")
    conn = db.connect()
    try:
        return memo.generate_memo(conn, code, rf=rf,
                                  table=table if not table.empty else None)
    except KeyError:
        return None
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def load_compare(codes: tuple, rf: float) -> pd.DataFrame:
    table = read_table("dash_metrics", index_col="code")
    conn = db.connect()
    out = compare.compare_funds(conn, list(codes), rf=rf,
                                table=table if not table.empty else None)
    conn.close()
    return out
