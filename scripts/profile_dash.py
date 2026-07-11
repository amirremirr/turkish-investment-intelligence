"""Time the heavy calls behind the dashboard."""
import time

from tefaslab import db, factors, memo, metrics, quality, smartmoney

conn = db.connect()


def clock(label, fn):
    t0 = time.perf_counter()
    fn()
    print(f"{time.perf_counter() - t0:6.2f}s  {label}")


clock("metrics.load_prices", lambda: metrics.load_prices(conn))
clock("metrics.compute_metrics", lambda: metrics.compute_metrics(conn, rf=0.4))
clock("factors.all_factor_betas", lambda: factors.all_factor_betas(conn))
clock("factors.fund_factor_model(AFT)",
      lambda: factors.fund_factor_model(conn, "AFT"))
clock("smartmoney.category_flows", lambda: smartmoney.category_flows(conn))
clock("quality.combined_scores", lambda: quality.combined_scores(conn, rf=0.4))
clock("memo.generate_memo(AFT)", lambda: memo.generate_memo(conn, "AFT", 0.4))
conn.close()
