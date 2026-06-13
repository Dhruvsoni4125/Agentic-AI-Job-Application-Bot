import json
import os
import urllib.parse

from utils import read_json, write_json

# Read dynamic query or fallback
query_data = read_json("outputs/search_query.json", default={"query": "Generative AI Engineer"})
search_query = query_data.get("query", "Generative AI Engineer")
print(f"Constructing search URLs for query: '{search_query}'")

query_cleaned = "".join(c for c in search_query if c.isalnum() or c.isspace()).strip().lower()
query_hyphenated = query_cleaned.replace(" ", "-")
query_encoded = urllib.parse.quote(search_query.strip().lower())

SEARCH_URLS = [
    f"https://www.naukri.com/{query_hyphenated}-jobs?k={query_encoded}&experience=0",
    f"https://www.naukri.com/{query_hyphenated}-jobs?k={query_encoded}",
]
APPLIED_FILE = "outputs/applied_jobs.json"
JOBS_FILE = "outputs/jobs.json"
DEBUG_HTML_FILE = "outputs/job_search_debug.html"
HEADLESS = os.getenv("JOB_SEARCH_HEADLESS", "false").lower() in {"1", "true", "yes"}

CARD_SELECTORS = [
    "div.srp-jobtuple-wrapper",
    "div.cust-job-tuple",
    "article.jobTuple",
    "div.jobTuple",
    "div[class*='jobTuple']",
    "div[class*='jobtuple']",
    "div[class*='srp-jobtuple']",
]

TITLE_SELECTORS = [
    "a.title",
    "a[class*='title']",
    "a[href*='job-listings']",
]

COMPANY_SELECTORS = [
    "a.comp-name",
    "a[class*='comp']",
    "span[class*='comp']",
]

LOCATION_SELECTORS = [
    "span.locWdth",
    "span[class*='loc']",
]


def keep_existing_jobs(reason):
    existing = read_json(JOBS_FILE, default=[])

    if not existing:
        existing_jds = read_json("outputs/jds.json", default=[])
        existing = [
            {
                "title": jd.get("title", ""),
                "company": jd.get("company", ""),
                "location": "",
                "url": jd.get("url", ""),
            }
            for jd in existing_jds
            if jd.get("url")
        ]

    write_json(JOBS_FILE, existing)
    print(f"Job search skipped ({reason}); kept {len(existing)} existing jobs")


if not os.path.exists(APPLIED_FILE):
    write_json(APPLIED_FILE, [])

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    keep_existing_jobs(f"Playwright unavailable: {e}")
    raise SystemExit(0)

processed_urls = read_json(APPLIED_FILE, default=[])
jobs = []


def first_text(locator, selectors):
    for selector in selectors:
        try:
            item = locator.locator(selector).first
            if item.count() > 0:
                text = item.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue

    return ""


def first_attr(locator, selectors, attr):
    for selector in selectors:
        try:
            item = locator.locator(selector).first
            if item.count() > 0:
                value = item.get_attribute(attr)
                if value:
                    return value
        except Exception:
            continue

    return ""


def collect_jobs_from_cards(page):
    collected = []

    for selector in CARD_SELECTORS:
        cards = page.locator(selector)
        count = min(cards.count(), 20)

        if count == 0:
            continue

        print(f"Found {count} jobs using selector: {selector}")

        for i in range(count):
            card = cards.nth(i)
            title = first_text(card, TITLE_SELECTORS)
            company = first_text(card, COMPANY_SELECTORS)
            location = first_text(card, LOCATION_SELECTORS)
            url = first_attr(card, TITLE_SELECTORS, "href")

            if title and url:
                collected.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                })

        if collected:
            return collected

    return collected


def collect_jobs_from_links(page):
    collected = []
    links = page.locator("a[href*='job-listings']")
    count = min(links.count(), 20)

    if count:
        print(f"Found {count} job links using fallback link scan")

    for i in range(count):
        link = links.nth(i)

        try:
            title = link.inner_text().strip()
            url = link.get_attribute("href")
        except Exception:
            continue

        if title and url:
            collected.append({
                "title": title,
                "company": "",
                "location": "",
                "url": url,
            })

    return collected

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            slow_mo=75,
        )

        context = browser.new_context(
            storage_state="naukri_session.json",
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        for search_url in SEARCH_URLS:
            print(f"Searching: {search_url}")
            page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)

            jobs = collect_jobs_from_cards(page)

            if not jobs:
                jobs = collect_jobs_from_links(page)

            if jobs:
                break

        if not jobs:
            write_json(JOBS_FILE, [])
            with open(DEBUG_HTML_FILE, "w", encoding="utf-8") as f:
                f.write(page.content())
            body_text = page.locator("body").inner_text(timeout=5000)
            if "Access Denied" in body_text:
                print("Naukri returned Access Denied. Keep the visible browser signed in and rerun.")
            print(f"Found 0 jobs. Saved debug page: {DEBUG_HTML_FILE}")

        browser.close()

except Exception as e:
    keep_existing_jobs(str(e))
    raise SystemExit(0)

new_jobs = []

for job in jobs:
    if not job["url"]:
        continue

    if job["url"] in processed_urls:
        print(f"SKIPPED: {job['title']}")
        continue

    new_jobs.append(job)

if new_jobs:
    write_json(JOBS_FILE, new_jobs)
else:
    keep_existing_jobs("no new jobs found")
    raise SystemExit(0)

print(f"\nNew Jobs Found: {len(new_jobs)}")
print("Saved jobs.json")
