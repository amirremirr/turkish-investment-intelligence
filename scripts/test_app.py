"""Smoke-test every dashboard view with Streamlit's AppTest."""
import time

from streamlit.testing.v1 import AppTest

targets = ["app.py",
           "views/market.py", "views/stocks.py", "views/funds.py",
           "views/compare_funds.py", "views/intelligence.py",
           "views/research_lab.py", "views/data_explorer.py",
           "views/dev.py"]

failed = 0
for target in targets:
    t0 = time.perf_counter()
    at = AppTest.from_file(target, default_timeout=300)
    at.run()
    elapsed = time.perf_counter() - t0
    if at.exception:
        failed += 1
        print(f"FAIL  {target}")
        for e in at.exception:
            print("   ", e.value)
    else:
        print(f"ok    {target:<28} {elapsed:5.1f}s")

raise SystemExit(1 if failed else 0)
