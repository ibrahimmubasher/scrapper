from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    context = browser.new_context()

    page = context.new_page()

    page.goto(
        "https://creatorapp.zohopublic.com/",
        timeout=120000
    )

    print("\nLOGIN MANUALLY")
    print("After login completes press ENTER\n")

    input()

    # SAVE SESSION
    context.storage_state(path="shams_session.json")

    print("Session saved successfully")

    browser.close()