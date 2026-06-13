import json

from utils import read_json, write_json


jobs = read_json("outputs/jobs.json", default=[])


def keep_existing_jds(reason):
    existing = read_json("outputs/jds.json", default=[])
    write_json("outputs/jds.json", existing)
    print(f"JD extraction skipped ({reason}); kept {len(existing)} existing JDs")


try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    keep_existing_jds(f"Playwright unavailable: {e}")
    raise SystemExit(0)

results = []

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            storage_state="naukri_session.json"
        )

        page = context.new_page()

        for job in jobs[:3]:
            print(f"Opening: {job['title']}")

            try:
                page.goto(job["url"], timeout=60000)
                page.wait_for_timeout(5000)
                body_text = page.locator("body").inner_text()

                results.append({
                    "title": job["title"],
                    "company": job["company"],
                    "url": job["url"],
                    "jd": body_text[:10000],
                })

            except Exception as e:
                print("Error:", e)

        browser.close()

except Exception as e:
    keep_existing_jds(str(e))
    raise SystemExit(0)

if results:
    write_json("outputs/jds.json", results)
    print("JD extraction completed")
else:
    keep_existing_jds("no JD text extracted")
