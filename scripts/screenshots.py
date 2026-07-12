"""Capture dashboard screenshots for the README/docs site."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("market", "http://localhost:8501/"),
    ("stocks", "http://localhost:8501/stocks"),
    ("intelligence", "http://localhost:8501/intelligence"),
    ("fund_explorer", "http://localhost:8501/funds"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    for name, url in PAGES:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(9000)  # let charts render
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
        print("captured", name)
    browser.close()
