from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    context = browser.new_context()

    page = context.new_page()

    page.goto("https://www.naukri.com")

    print("Login manually in the browser")

    input("After login, press Enter...")

    context.storage_state(path="naukri_session.json")

    print("Session saved successfully!")

    browser.close()