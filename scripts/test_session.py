from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    context = browser.new_context(
        storage_state="naukri_session.json"
    )

    page = context.new_page()

    page.goto("https://www.naukri.com")

    page.wait_for_timeout(5000)

    print("Naukri loaded")

    input("Press Enter to close...")

    browser.close()