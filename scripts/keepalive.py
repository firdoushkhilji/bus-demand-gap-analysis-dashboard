"""Opens the hosted dashboard in a real browser so Streamlit Community Cloud counts it as a visit.
If the app has gone to sleep, clicks the wake-up button. The app address comes from the APP_URL repository variable."""
import os, sys, time
from playwright.sync_api import sync_playwright

url = os.environ.get("APP_URL", "").strip()
if not url:
    sys.exit("Set the APP_URL repository variable to the dashboard address.")
with sync_playwright() as p:
    page = p.chromium.launch().new_page()
    page.goto(url, timeout=90_000)
    time.sleep(10)
    for frame in [page] + page.frames:
        btn = frame.get_by_role("button", name="Yes, get this app back up")
        if btn.count():
            btn.first.click(); print("App was asleep: woke it."); time.sleep(45); break
    else:
        print("App already awake.")
    time.sleep(20)                       # stay connected briefly so the session counts
    print("Done:", page.title())
