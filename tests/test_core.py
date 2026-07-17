"""Unit tests for the platform's core logic.

Focus: the places where a silent regression would corrupt results —
the NAV-lag beta convention, the flow restructuring guard, the
classifier's Turkish-morphology rules, the OLS/Newey-West estimator,
EVDS date parsing, and the KAP PDF parser (against a real fixture).
Run: pytest -q
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tefaslab import classify, db, evds, flows, metrics, research  # noqa: E402
from tefaslab.kap import parse_pdf_holdings  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------- OLS

def test_ols_recovers_known_beta():
    rng = np.random.default_rng(7)
    x = rng.normal(0, 1, 400)
    y = 2.0 * x + rng.normal(0, 0.5, 400)
    res = research._ols(y, x, nw_lags=5)
    assert abs(res["beta"] - 2.0) < 0.1
    assert res["t_stat"] > 10
    assert np.isfinite(res["nw_t"]) and res["nw_t"] > 5
    assert res["r2"] > 0.8


def test_ols_too_few_observations():
    res = research._ols(np.ones(10), np.ones(10))
    assert np.isnan(res["beta"])


# --------------------------------------------------------- classifier

@pytest.mark.parametrize("title,expected", [
    ("X PORTFÖY ALTIN FONU", "Precious Metals"),
    ("X PORTFÖY ALTINCI SERBEST FON", "Hedge (Serbest)"),  # sixth != gold
    ("X PORTFÖY YABANCI HİSSE SENEDİ FONU", "Foreign Equity"),
    ("X AMERİKA TEKNOLOJİ YABANCI BYF FON SEPETİ FONU", "Foreign Equity"),
    ("X PORTFÖY TEKNOLOJİ KATILIM FONU", "Equity Turkey"),
    ("X PORTFÖY PARA PİYASASI (TL) FONU", "Money Market"),
    ("X PORTFÖY HİSSE SENEDİ FONU (HİSSE SENEDİ YOĞUN FON)",
     "Equity Turkey"),
])
def test_title_classifier(title, expected):
    assert classify.classify_title(title) == expected


def test_allocation_fallback():
    assert classify.classify_allocation({"yhs": 80.0}) == "Foreign Equity"
    assert classify.classify_allocation({"tr": 40.0, "vmtl": 30.0}) \
        == "Money Market"
    assert classify.classify_allocation({}) == "Other"


# --------------------------------------------------------- EVDS dates

def test_evds_date_parsing():
    assert evds._parse_date("02-01-2024") == "2024-01-02"
    assert evds._parse_date("2026-1") == "2026-01-01"
    assert evds._parse_date("2026-12") == "2026-12-01"


# ------------------------------------------------- flows + beta (DB)

@pytest.fixture()
def tmp_conn(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    yield conn
    conn.close()


def test_flow_restructuring_guard(tmp_conn):
    tmp_conn.execute("INSERT INTO funds VALUES ('AAA', 'TEST FON', "
                     "'YAT', 'Equity Turkey')")
    rows, price, shares = [], 10.0, 1000.0
    start = date(2025, 1, 1)
    for i in range(10):
        d = (start + timedelta(days=i)).isoformat()
        if i == 5:
            price *= 100          # restructuring day
        shares += 10
        rows.append(("AAA", d, price, shares, 100, price * shares))
    tmp_conn.executemany(
        "INSERT INTO prices VALUES (?,?,?,?,?,?)", rows)
    tmp_conn.commit()
    df = flows.load_flow_frame(tmp_conn)
    # the restructuring day must be excluded...
    assert str(start + timedelta(days=5)) not in \
        df["date"].dt.strftime("%Y-%m-%d").values
    # ...and a normal day's flow equals delta-shares x price
    normal = df[df["date"] == str(start + timedelta(days=2))]
    assert normal["flow"].iloc[0] == pytest.approx(10 * 10.0)


def test_beta_uses_lagged_benchmark(tmp_conn):
    """A fund whose return equals *yesterday's* index return must show
    beta ~1 — this is the TEFAS NAV-lag convention."""
    rng = np.random.default_rng(1)
    bench_ret = rng.normal(0, 0.01, 300)
    bench = 1000 * np.cumprod(1 + bench_ret)
    fund = 10 * np.cumprod(1 + np.concatenate([[0], bench_ret[:-1]]))
    tmp_conn.execute("INSERT INTO funds VALUES ('AAA', 'LAGGED INDEX "
                     "FON', 'YAT', 'Equity Turkey')")
    start = date(2025, 1, 1)
    prows, brows = [], []
    for i in range(300):
        d = (start + timedelta(days=i)).isoformat()
        prows.append(("AAA", d, float(fund[i]), 1e6, 1000, 1e7))
        brows.append(("bist100", d, float(bench[i])))
    tmp_conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?)", prows)
    tmp_conn.executemany("INSERT INTO benchmarks VALUES (?,?,?)", brows)
    tmp_conn.commit()
    out = metrics.compute_metrics(tmp_conn, min_obs=50)
    assert out.loc["AAA", "beta"] == pytest.approx(1.0, abs=0.05)


# -------------------------------------------- TEFAS contract check

def test_tefas_contract_accepts_valid_shape():
    from tefaslab import client
    good = {"resultList": [{"fonKodu": "AAA", "tarih": "2026-01-01",
                            "fiyat": 1.0, "tedPaySayisi": 1,
                            "kisiSayisi": 1, "portfoyBuyukluk": 1.0}],
            "toplamSayi": 1}
    client._check_contract(good, "test", client._HISTORY_KEYS)  # no raise


def test_tefas_contract_catches_missing_wrapper():
    from tefaslab import client
    with pytest.raises(client.TefasError, match="no 'resultList'"):
        client._check_contract({"data": []}, "test", client._HISTORY_KEYS)


def test_tefas_contract_catches_renamed_field():
    from tefaslab import client
    # 'fiyat' renamed to 'price' -> must fail loudly, not ingest nulls
    bad = {"resultList": [{"fonKodu": "AAA", "tarih": "2026-01-01",
                           "price": 1.0, "tedPaySayisi": 1,
                           "kisiSayisi": 1, "portfoyBuyukluk": 1.0}]}
    with pytest.raises(client.TefasError, match="missing expected fields"):
        client._check_contract(bad, "test", client._HISTORY_KEYS)


def test_tefas_contract_ignores_empty_result():
    from tefaslab import client
    client._check_contract({"resultList": []}, "test", client._HISTORY_KEYS)


# ------------------------------------------------------ publisher

def test_publisher_roundtrip(tmp_path, tmp_conn):
    """Publish from a small SQLite source to a sqlite:/// target —
    exercises the exact SQLAlchemy path used for Supabase Postgres."""
    from tefaslab import publish as pub
    tmp_conn.execute("INSERT INTO funds VALUES ('AAA','T','YAT','Equity "
                     "Turkey')")
    tmp_conn.executemany(
        "INSERT INTO prices VALUES (?,?,?,?,?,?)",
        [("AAA", f"2025-01-{d:02d}", 10.0, 1, 1, 10) for d in (1, 2, 3)])
    tmp_conn.commit()
    src_path = tmp_path / "test.db"          # tmp_conn's file
    target = f"sqlite:///{tmp_path / 'serving.db'}"
    stats = pub.publish(url=target, db_path=src_path)
    assert stats["funds"] == 1
    assert stats["prices"] == 3
    # second run must be incremental: zero new price rows
    stats2 = pub.publish(url=target, db_path=src_path)
    assert stats2["prices"] == 0
    # append a new day -> only it is shipped
    tmp_conn.execute("INSERT INTO prices VALUES "
                     "('AAA','2025-01-04',11,1,1,11)")
    tmp_conn.commit()
    stats3 = pub.publish(url=target, db_path=src_path)
    assert stats3["prices"] == 1


def test_publish_preserves_cloud_only_status(tmp_path, tmp_conn):
    """A row that only exists in the serving copy (e.g. 'intraday',
    written directly by the cloud cron) must survive a publish that
    full-replaces everything else."""
    from tefaslab import publish as pub
    from sqlalchemy import create_engine, text
    # source has a STALE local intraday (a leftover) — it must be ignored
    tmp_conn.execute("CREATE TABLE system_status "
                     "(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    tmp_conn.executemany(
        "INSERT INTO system_status VALUES (?,?,?)",
        [("pipeline_complete", "true", "2026-07-17T20:00:00"),
         ("intraday", '{"ts":"STALE-LOCAL"}', "2026-07-13T00:00:00")])
    tmp_conn.commit()
    eng = create_engine(f"sqlite:///{tmp_path / 'serving.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE system_status "
                       "(key TEXT, value TEXT, updated_at TEXT)"))
        c.execute(text("INSERT INTO system_status "
                       "VALUES ('intraday', '{\"ts\":\"FRESH-CLOUD\"}', 't')"))
        c.execute(text("INSERT INTO system_status "
                       "VALUES ('pipeline_complete', 'false', 'old')"))
    pub._publish_status(tmp_conn, eng)
    with eng.connect() as c:
        intra = c.execute(text("SELECT value FROM system_status "
                               "WHERE key='intraday'")).scalar()
        pcval = c.execute(text("SELECT value FROM system_status "
                               "WHERE key='pipeline_complete'")).scalar()
    eng.dispose()
    assert "FRESH-CLOUD" in intra   # cloud intraday untouched, not clobbered
    assert pcval == "true"          # local-owned key refreshed, not stale


# ------------------------------------------------------- KAP parser

def test_kap_parser_on_fixture():
    pdf = (FIXTURES / "IJZ_2026-04.pdf").read_bytes()
    code, rows = parse_pdf_holdings(pdf)
    assert code == "IJZ"
    assert len(rows) == 89
    tr = [r for r in rows if r["isin"].startswith("TR")]
    assert len(tr) == 45
    total_weight = sum(r["weight_pct"] or 0 for r in rows)
    assert 90 < total_weight < 102          # rest is cash
    assert all(r["value"] is not None for r in rows)
    top = max(rows, key=lambda r: r["weight_pct"] or 0)
    assert top["ticker"] == "AVGO"          # Broadcom, 5.98% in fixture
