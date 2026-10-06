import os
import json
import time
from playwright.sync_api import sync_playwright

def get_tcx_options(hex_code: str) -> list:
    """
    Given a hex code (e.g., '#1B2A4A' or '1B2A4A'), uses Playwright to 
    query the Pantone Color Finder and returns the pantoneFhCottonTcx color options.
    Returns a list of dicts: [{"code": "19-4029 TCX", "name": "Navy Peony"}, ...]
    """
    # Remove # if present
    hex_code = hex_code.strip().lstrip('#')
    
    tcx_colors = []
    
    # Temporarily remove DYLD variables that poison Chromium's environment on macOS
    old_dyld = os.environ.get("DYLD_LIBRARY_PATH")
    old_fallback = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH")
    if "DYLD_LIBRARY_PATH" in os.environ:
        del os.environ["DYLD_LIBRARY_PATH"]
    if "DYLD_FALLBACK_LIBRARY_PATH" in os.environ:
        del os.environ["DYLD_FALLBACK_LIBRARY_PATH"]

    try:
        with sync_playwright() as p:
            # Try headless first for server/CI, fall back to headful if Cloudflare blocks
            headless_mode = os.environ.get("PANTONE_HEADLESS", "true").lower() in ("true", "1", "yes")
            browser = p.chromium.launch(headless=headless_mode)
            context = browser.new_context()
            page = context.new_page()

            # Intercept POST requests to the API
            def handle_response(response):
                nonlocal tcx_colors
                if "color-finder" in response.url and response.request.method == "POST":
                    try:
                        text = response.text()
                        for line in text.split('\n'):
                            if line.startswith('1:'):
                                data = json.loads(line[2:])
                                pantone_data = data.get("data", {}).get("pantone", {})
                                for book in pantone_data.get("connect", []):
                                    if book.get("bookId") == "pantoneFhCottonTcx":
                                        tcx_colors = book.get("colors", [])
                    except Exception as e:
                        pass

            page.on("response", handle_response)
            
            try:
                page.goto("https://www.pantone.com/color-finder", wait_until="networkidle")
                
                # Fill the hex code in the first text input
                search_input = page.locator('input[type="text"]').first
                search_input.wait_for(state="visible", timeout=10000)
                search_input.fill(hex_code)
                
                # Click the SEARCH button
                try:
                    page.locator('button:has-text("SEARCH")').click(timeout=3000)
                except:
                    page.keyboard.press('Enter')
                
                # Wait for network response to be intercepted
                page.wait_for_timeout(8000)
                
            except Exception as e:
                print(f"[pantone_scraper] Navigation or scraping failed: {e}")
            finally:
                browser.close()

            # If headless mode got no results, retry headful (Cloudflare bypass)
            if not tcx_colors and headless_mode:
                print("[pantone_scraper] Headless got no results, retrying headful...")
                try:
                    browser = p.chromium.launch(headless=False)
                    context = browser.new_context()
                    page = context.new_page()
                    page.on("response", handle_response)
                    page.goto("https://www.pantone.com/color-finder", wait_until="networkidle")
                    search_input = page.locator('input[type="text"]').first
                    search_input.wait_for(state="visible", timeout=10000)
                    search_input.fill(hex_code)
                    try:
                        page.locator('button:has-text("SEARCH")').click(timeout=3000)
                    except:
                        page.keyboard.press('Enter')
                    page.wait_for_timeout(8000)
                    browser.close()
                except Exception as e2:
                    print(f"[pantone_scraper] Headful retry also failed: {e2}")

    finally:
        # Restore environment variables
        if old_dyld is not None:
            os.environ["DYLD_LIBRARY_PATH"] = old_dyld
        if old_fallback is not None:
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = old_fallback

    return tcx_colors

if __name__ == "__main__":
    print(get_tcx_options("#1B2A4A"))
