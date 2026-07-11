"""Fund classification (Priority 3).

Turkish fund titles follow regulatory naming (SPK), so keyword rules on
the title classify most funds; the rest fall back to their latest
portfolio allocation. Writes funds.category.
"""

from __future__ import annotations

import re
import sqlite3

import pandas as pd

# Order matters: first match wins. Titles are official uppercase Turkish.
# Patterns are regexes: ALTIN needs a word boundary so that ALTINCI
# ("sixth") doesn't classify as gold.
TITLE_RULES = [
    ("PARA PİYASASI", "Money Market"),
    ("YABANCI HİSSE", "Foreign Equity"),
    (r"YABANCI.*(TEKNOLOJİ|BYF)", "Foreign Equity"),
    (r"(TEKNOLOJİ|BYF).*YABANCI", "Foreign Equity"),
    (r"AMERİKA|NASDAQ|S&P", "Foreign Equity"),
    ("TEKNOLOJİ", "Equity Turkey"),
    ("HİSSE SENEDİ", "Equity Turkey"),
    (r"\bALTIN\b", "Precious Metals"),
    ("GÜMÜŞ", "Precious Metals"),
    ("KIYMETLİ MADEN", "Precious Metals"),
    ("BORÇLANMA ARAÇLARI", "Debt"),
    ("EUROBOND", "Debt"),
    ("DIŞ BORÇLANMA", "Debt"),
    ("KİRA SERTİFİKA", "Participation"),
    ("KATILIM", "Participation"),
    ("FON SEPETİ", "Fund of Funds"),
    ("KARMA", "Mixed"),
    ("DEĞİŞKEN", "Variable"),
    ("SERBEST", "Hedge (Serbest)"),
]

# Allocation fallback: (asset codes to sum, threshold %, category)
ALLOC_RULES = [
    (("yhs",), 50, "Foreign Equity"),
    (("hs",), 50, "Equity Turkey"),
    (("km", "kmbyf", "kmkba"), 50, "Precious Metals"),
    (("dt", "ost", "osks", "kibd", "yba"), 50, "Debt"),
    (("kks", "kkstl", "kksd", "kba", "kh", "khtl"), 50, "Participation"),
    (("tr", "vmtl", "vm", "tpp", "bpp"), 60, "Money Market"),
]


def classify_title(title: str | None) -> str | None:
    if not title:
        return None
    for pattern, category in TITLE_RULES:
        if re.search(pattern, title):
            return category
    return None


def classify_allocation(weights: dict[str, float]) -> str:
    for assets, threshold, category in ALLOC_RULES:
        if sum(weights.get(a, 0) for a in assets) >= threshold:
            return category
    return "Other"


def classify_all(conn: sqlite3.Connection) -> pd.Series:
    """Classify every fund and persist to funds.category.
    Returns category counts."""
    funds = pd.read_sql_query("SELECT code, title FROM funds", conn)

    latest_alloc = pd.read_sql_query(
        """
        SELECT a.code, a.asset, a.pct FROM allocations a
        JOIN (SELECT code, MAX(date) AS d FROM allocations GROUP BY code) m
          ON m.code = a.code AND m.d = a.date
        """,
        conn,
    )
    alloc_map: dict[str, dict[str, float]] = {
        code: dict(zip(g["asset"], g["pct"]))
        for code, g in latest_alloc.groupby("code")
    }

    rows = []
    for _, r in funds.iterrows():
        cat = classify_title(r["title"])
        if cat is None:
            cat = classify_allocation(alloc_map.get(r["code"], {}))
        rows.append((cat, r["code"]))

    conn.executemany("UPDATE funds SET category = ? WHERE code = ?", rows)
    conn.commit()
    return pd.Series([c for c, _ in rows]).value_counts()
