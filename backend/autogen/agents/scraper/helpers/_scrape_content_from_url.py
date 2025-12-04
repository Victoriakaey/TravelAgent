import re
import os
import json
import asyncio
import hashlib
import logging
import requests
import trafilatura
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from trafilatura.metadata import extract_metadata

logger = logging.getLogger(__name__)

# ========== Basic Utilities ==========

def fetch_static_html(url: str, timeout: int = 10) -> str:
    """Fetch raw HTML with requests (static)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SmartScraper/1.0)"}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.info(f"[fetch_static_html] Error fetching {url}: {str(e)}")
        return ""


async def fetch_dynamic_html(
    url: str,
    timeout: int = 30_000,
    wait_selector: str = "body",
    screenshot_path: str | None = None,
    debug: bool = False,
) -> str:
    """Fetch rendered HTML with Playwright (dynamic)."""

    safe_name = hashlib.md5(url.encode()).hexdigest()
    base_dir = screenshot_path or "autogen/log"
    filename = os.path.join(base_dir, safe_name)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/112.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            logger.info(f"[fetch_dynamic_html] Navigating to: {url}")

            # Try networkidle first
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout)
            except Exception as e:
                logger.warning(f"[fetch_dynamic_html] networkidle failed: {e}, retrying with domcontentloaded")
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            # Wait for selector
            try:
                await page.wait_for_selector(wait_selector, timeout=timeout)
                logger.info(f"[fetch_dynamic_html] Selector '{wait_selector}' matched.")
            except Exception as e:
                logger.warning(f"[fetch_dynamic_html] wait_for_selector failed: {e}")

            # Extra time for lazy JS
            await page.wait_for_timeout(3000)

            # Screenshot + debug HTML
            if debug:
                os.makedirs(filename, exist_ok=True)
                screenshot_file = os.path.join(filename, "screenshot.png")
                await page.screenshot(path=screenshot_file, full_page=True)
                logger.info(f"[fetch_dynamic_html] Screenshot saved: {screenshot_file}")

            # Get HTML
            html = await page.content()

            # iframe fallback
            if len(html) < 1000:
                for frame in page.frames:
                    try:
                        frame_html = await frame.content()
                        if len(frame_html) > len(html):
                            logger.info(f"[fetch_dynamic_html] Using iframe content from {frame.url}")
                            html = frame_html
                            break
                    except Exception:
                        pass

            logger.info(f"[fetch_dynamic_html] Got HTML length={len(html)}")
            logger.debug(html[:500])

            # Save debug HTML
            if debug:
                debug_file = os.path.join(filename, "debug.html")
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info(f"[fetch_dynamic_html] Raw HTML saved: {debug_file}")

            await browser.close()
            return html

    except Exception as e:
        logger.info(f"[fetch_dynamic_html] Error fetching {url}: {str(e)}")
        return ""


def extract_page_metadata(html: str) -> dict:
    """Extract metadata with Trafilatura."""
    try:
        doc = extract_metadata(html)
        if not doc:
            return {}
        return {
            "title": getattr(doc, "title", None),
            "author": getattr(doc, "author", None),
            "date": getattr(doc, "date", None),
            "description": getattr(doc, "description", None),
            "language": getattr(doc, "language", None),
            "sitename": getattr(doc, "sitename", None),
            "url": getattr(doc, "url", None),
        }
    except Exception as e:
        logger.info(f"[extract_page_metadata] Failed: {str(e)}")
        return {}


def extract_clean_content(html: str, min_length: int = 200) -> str:
    """Extract main text with Trafilatura."""
    config = trafilatura.settings.use_config()
    config.set("DEFAULT", "EXTRACTION_TIMEOUT", "0.2")
    config.set("DEFAULT", "EXTRACTION_MIN_LENGTH", str(min_length))
    try:
        return trafilatura.extract(html, config=config) or ""
    except Exception as e:
        logger.info(f"[extract_clean_content] Error: {str(e)}")
        return ""


def split_into_chunks(text: str, min_length: int = 200) -> list[str]:
    """Split text into chunks."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) < min_length:
            current += " " + p
        else:
            if current:
                chunks.append(current.strip())
            current = p
    if current:
        chunks.append(current.strip())
    return chunks


# ========== General Pipeline ==========

async def scrape_and_filter(
    url: str,
    min_html_length: int = 2000,
    wait_selector: str = "main, article, div.content, div#content, div.post, section",
    debug: bool = True,
    log_path: str = "autogen/log",
) -> dict:
    """Full scrape pipeline with debug option."""
    result = {"metadata": {}, "raw_html": "", "clean_content": "", "chunks": []}

    screenshot_path = log_path + "/dynamic_page_scraping/"

    logger.info(f"\n====== Scraping URL: {url} ======")

    # Step 1: static fetch
    html = fetch_static_html(url)
    if len(html) < min_html_length:
        logger.info("[Pipeline] Static fetch too short, trying dynamic...")
        html = await fetch_dynamic_html(url, wait_selector=wait_selector, debug=debug, screenshot_path=screenshot_path)

    result["raw_html"] = html or ""

    # Step 2: metadata
    result["metadata"] = extract_page_metadata(html) or {}

    # Step 3: clean content
    # clean_text = extract_clean_content(html)
    # result["clean_content"] = clean_text or ""

    clean_text = extract_clean_content(html)
    if not clean_text and len(html) > 5000:  # fallback for long pages
        logger.warning("[Pipeline] Trafilatura extraction failed, falling back to BeautifulSoup")
        soup = BeautifulSoup(html, "lxml")
        # Remove script/style/noscript
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        text = soup.get_text("\n")
        # Clean up extra blank lines
        clean_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

    result["clean_content"] = clean_text or ""

    # Step 4: chunking
    result["chunks"] = split_into_chunks(clean_text) if clean_text else []

    if not result["chunks"]:
        logger.warning(f"[Pipeline] No content extracted from {url}")

    logger.info(f"[Pipeline] Chunked into {len(result['chunks'])} segments.")
    return result
