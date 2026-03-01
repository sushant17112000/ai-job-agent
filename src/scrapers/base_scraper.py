"""
Base Scraper — abstract Playwright-based scraper with stealth and safety helpers.
"""

import logging
import random
from abc import ABC, abstractmethod

from config import PAGE_TIMEOUT_MS, USER_AGENTS

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all job portal scrapers."""

    portal_name: str = "unknown"

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        """
        Scrape jobs for the given titles across relevant cities.

        Args:
            job_titles: list of job title strings to search.
            cities: the CITIES config dict mapping city keys to portal slugs.

        Returns:
            List of standardized job dicts.
        """

    # ------------------------------------------------------------------
    # Browser helpers
    # ------------------------------------------------------------------

    async def _launch_browser(self, playwright):
        """Launch Chromium with GitHub Actions-compatible flags."""
        return await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )

    async def _create_stealth_context(self, browser):
        """Create a browser context with randomized fingerprint."""
        ua = random.choice(USER_AGENTS)
        viewport = {
            "width": random.randint(1280, 1920),
            "height": random.randint(800, 1080),
        }
        context = await browser.new_context(
            user_agent=ua,
            viewport=viewport,
            locale="en-US",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
        )
        # Mask webdriver flag
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return context

    async def _navigate_safely(self, page, url: str) -> bool:
        """
        Navigate to URL with a timeout guard.

        Returns:
            True on success, False on timeout or other error.
        """
        try:
            await page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            return True
        except Exception as exc:
            logger.warning("[%s] Navigation failed for %s — %s", self.portal_name, url, exc)
            return False

    # ------------------------------------------------------------------
    # Standardized job dict builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_job_dict(
        title: str,
        company: str,
        location: str,
        url: str,
        description_snippet: str,
        date_posted: str,
        portal: str,
    ) -> dict:
        """Return a standardized job dictionary."""
        return {
            "title": (title or "").strip(),
            "company": (company or "").strip(),
            "location": (location or "").strip(),
            "url": (url or "").strip(),
            "description_snippet": (description_snippet or "").strip()[:500],
            "date_posted": (date_posted or "").strip(),
            "portal": portal,
        }
