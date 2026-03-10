"""
Generate Assets/entelgia_correlation_map.png

Renders the HTML source file (Assets/entelgia_correlation_map.html) to a
high-resolution PNG using a headless Chromium browser via Playwright.

Run from the repository root:

    python scripts/generate_correlation_map.py

Requires: playwright  (pip install playwright && python -m playwright install chromium)
"""

import asyncio
import os
import sys


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(repo_root, "Assets", "entelgia_correlation_map.html")
    out_path = os.path.join(repo_root, "Assets", "entelgia_correlation_map.png")

    if not os.path.exists(html_path):
        sys.exit(f"Source not found: {html_path}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        sys.exit(
            "playwright is required.  Install with:\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium"
        )

    async def _render() -> None:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                device_scale_factor=2,
            )
            page = await context.new_page()
            await page.goto(f"file://{html_path}", wait_until="networkidle")
            await page.screenshot(path=out_path, full_page=True)
            await browser.close()

    asyncio.run(_render())
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
