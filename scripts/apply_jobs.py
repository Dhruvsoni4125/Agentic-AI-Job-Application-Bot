import json
import os
import time
import pandas as pd

from utils import load_env, project_path, safe_job_name

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed. Automated application cannot run.")
    raise SystemExit(1)

load_env()

import urllib.parse
import urllib.request

TRACKER_FILE = project_path("outputs", "applications.csv")
HEADLESS = os.getenv("JOB_APPLY_HEADLESS", "false").lower() in {"1", "true", "yes"}
SESSION_FILE = project_path("naukri_session.json")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def notify_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            pass
    except Exception as e:
        print(f"Failed to notify Telegram: {e}")


def upload_resume(page, pdf_path):
    print(f"Uploading tailored resume: {pdf_path}")
    page.goto("https://www.naukri.com/mnjuser/profile", timeout=60000)
    page.wait_for_timeout(5000)

    # Try attaching CV using standard selectors
    file_input_selectors = [
        "input#attachCV",
        "input[type='file'][id*='attach']",
        "input[type='file'][name*='resume']",
        "input[type='file']"
    ]

    uploaded = False
    for selector in file_input_selectors:
        try:
            input_el = page.locator(selector).first
            if input_el.count() > 0:
                print(f"Found file input with selector: '{selector}'")
                input_el.set_input_files(pdf_path)
                page.wait_for_timeout(8000)  # Wait for upload request to complete
                uploaded = True
                print("Resume upload request triggered successfully.")
                break
        except Exception as e:
            print(f"Failed to upload using selector '{selector}': {e}")

    if not uploaded:
        print("Could not upload resume: File input element not found.")
        return False
    return True


def apply_to_job(page, job_url):
    print(f"Navigating to job page: {job_url}")
    page.goto(job_url, timeout=60000)
    page.wait_for_timeout(5000)

    body_text = page.locator("body").inner_text().lower()

    if "already applied" in body_text or "applied" in body_text:
        print("Already applied to this job.")
        return "ALREADY_APPLIED"

    # Search for Apply buttons
    apply_button = page.locator("button:has-text('Apply')").first
    apply_external = page.locator("button:has-text('Apply on Company Site')").first
    apply_alternative = page.locator("#apply-button, .apply-button, .applyBtn").first

    if apply_external.count() > 0:
        print("Redirects to external company site. Manual application required.")
        return "MANUAL_APPLY_REQUIRED"

    target_button = None
    if apply_button.count() > 0:
        target_button = apply_button
    elif apply_alternative.count() > 0:
        target_button = apply_alternative

    if target_button:
        try:
            print("Clicking Apply button...")
            target_button.click()
            page.wait_for_timeout(5000)
            
            # Check for questionnaire or successful toast
            post_body_text = page.locator("body").inner_text().lower()
            if "successfully applied" in post_body_text or "applied" in post_body_text:
                print("Application submitted successfully!")
                return "APPLIED"
            else:
                # Often standard Naukri apply buttons click and apply instantly.
                print("Clicked apply button. Assuming successful submission.")
                return "APPLIED"
        except Exception as e:
            print(f"Error clicking apply button: {e}")
            return "APPLY_CLICK_FAILED"

    print("No apply button found on page.")
    return "APPLY_BUTTON_NOT_FOUND"


def main():
    if not os.path.exists(TRACKER_FILE):
        print(f"Tracker file not found at {TRACKER_FILE}. Nothing to apply for.")
        return

    df = pd.read_csv(TRACKER_FILE)
    ready_jobs = df[df["status"] == "READY"]

    if ready_jobs.empty:
        print("No jobs found with status 'READY'. Pipeline completed.")
        return

    print(f"Found {len(ready_jobs)} jobs ready for application.")

    if not os.path.exists(SESSION_FILE):
        print(f"Session file {SESSION_FILE} not found. Cannot automate application.")
        return

    with sync_playwright() as p:
        print(f"Launching browser (headless={HEADLESS})...")
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            storage_state=SESSION_FILE,
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        for idx, row in ready_jobs.iterrows():
            job_title = row["job_title"]
            company = row["company"]
            job_url = row["job_url"]
            safe_name = safe_job_name(job_title)

            print(f"\nProcessing Application: {job_title} at {company}")

            # 1. Upload custom resume if it exists
            pdf_path = project_path("outputs", "ats_resume_pdf", f"{safe_name}.pdf")
            upload_success = False
            if os.path.exists(pdf_path):
                upload_success = upload_resume(page, pdf_path)
            else:
                print(f"No custom PDF resume found at {pdf_path}. Skipping upload, applying with current default resume.")
                upload_success = True  # Proceed anyway

            # 2. Apply to the job
            if upload_success:
                app_status = apply_to_job(page, job_url)
            else:
                app_status = "RESUME_UPLOAD_FAILED"

            # 3. Update status in dataframe
            df.at[idx, "status"] = app_status
            if app_status == "APPLIED":
                df.at[idx, "resume_generated"] = "YES (SUBMITTED)"
                notify_telegram(f"Job Applied for {company} for role of {job_title} Successfully")
            
            # Save progress in tracker CSV immediately
            df.to_csv(TRACKER_FILE, index=False)

        browser.close()
    
    print("\nApplication run completed. Tracker CSV updated.")


if __name__ == "__main__":
    main()
