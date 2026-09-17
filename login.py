import asyncio
import os
import re

from playwright.async_api import async_playwright


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "https://props.cash/"
ENV_PATH = os.path.join(BASE_DIR, ".env")
STORAGE_STATE_PATH = os.path.join(BASE_DIR, "storage_state.json")


def load_env() -> None:
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


async def login() -> None:
    load_env()
    email = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")
    if not email or not password:
        raise RuntimeError("Missing EMAIL or PASSWORD in environment/.env")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=90000)

        login_button = page.get_by_role("button", name=re.compile(r"^Login$", re.IGNORECASE))
        await login_button.first.wait_for(state="visible", timeout=60000)
        await login_button.first.click()

        # Props.Cash still uses Auth0, but the old auth0-lock wrapper is gone.
        email_input = page.locator(
            "input[name='username'], input[name='email'], input[type='email']"
        ).first
        await email_input.wait_for(state="visible", timeout=60000)
        await email_input.fill(email)

        password_input = page.locator("input[name='password'], input[type='password']").first
        try:
            await password_input.wait_for(state="visible", timeout=5000)
        except Exception:
            # Supports Auth0 configurations that show username first, then password.
            continue_button = page.locator("button[name='submit']").first
            if await continue_button.count() == 0:
                continue_button = page.get_by_role(
                    "button", name=re.compile(r"^(Continue|Next)$", re.IGNORECASE)
                ).first
            await continue_button.click()
            await password_input.wait_for(state="visible", timeout=60000)

        await password_input.fill(password)

        submit_button = page.locator("button[name='submit']").first
        if await submit_button.count() == 0:
            submit_button = page.get_by_role(
                "button", name=re.compile(r"^(Log In|Login|Sign In|Continue)$", re.IGNORECASE)
            ).first
        await submit_button.wait_for(state="visible", timeout=60000)
        await submit_button.click()

        # Do not use networkidle here: the app keeps background requests alive.
        await page.wait_for_url(re.compile(r"^https://props\.cash(?:/|$)"), timeout=60000)

        # Wait for Auth0/app state to settle rather than for an obsolete table header.
        authenticated = False
        for _ in range(120):
            auth_storage = await page.evaluate(
                """() => {
                    const keys = [...Object.keys(localStorage), ...Object.keys(sessionStorage)];
                    return keys.some(k => k.toLowerCase().includes('auth0'));
                }"""
            )
            login_visible = False
            try:
                login_visible = await login_button.first.is_visible()
            except Exception:
                pass
            if auth_storage and not login_visible:
                authenticated = True
                break
            await page.wait_for_timeout(250)

        if not authenticated:
            raise RuntimeError("PropsCash login completed but authenticated Auth0 state was not detected")

        await context.storage_state(path=STORAGE_STATE_PATH)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(login())
