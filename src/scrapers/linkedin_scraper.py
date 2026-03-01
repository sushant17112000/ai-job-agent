"""
LinkedIn Scraper — scrapes public LinkedIn job search results (last 24 hours).

Note: LinkedIn aggressively blocks data-center IPs. On GitHub Actions this will
fail ~30-40 % of the time. The pipeline continues with results from other portals.
"""

import logging
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from config import MAX_JOBS_PER_QUERY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://www.linkedin.com/jobs/search/"
    "?keywords={query}&location={location}&f_TPR=r86400&position=1&pageNum=0"
)

# Primary selectors
SEL_LIST = "ul.jobs-search__results-list li"
SEL_TITLE = "h3.base-search-card__title"
SEL_COMPANY = "h4.base-search-card__subtitle"
SEL_LOCATION = "span.job-search-card__location"
SEL_DATE = "time.job-search-card__listdate"
SEL_LINK = "a.base-card__full-link"

# Fallback selectors (LinkedIn sometimes changes class names)
SEL_LIST_FB = "ul.jobs-search-results__list li"
SEL_TITLE_FB = "h3"
SEL_COMPANY_FB = "h4"


class LinkedInScraper(BaseScraper):
    portal_name = "LinkedIn"

    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        jobs = []
        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                try:
                    for title in job_titles:
                        for city_key, slugs in cities.items():
                            location = slugs.get("linkedin")
                            if not location:
                                continue
                            url = BASE_URL.format(
                                query=quote_plus(title), location=quote_plus(location)
                            )
                            page_jobs = await self._scrape_page(browser, url, location)
                            jobs.extend(page_jobs[:MAX_JOBS_PER_QUERY])
                finally:
                    await browser.close()
        except Exception as exc:
            logger.error("[LinkedIn] Fatal scraper error: %s", exc)

        logger.info("[LinkedIn] Total jobs scraped: %d", len(jobs))
        return jobs

    async def _scrape_page(self, browser, url: str, location: str) -> list[dict]:
        context = await self._create_stealth_context(browser)
        page = await context.new_page()
        jobs = []

        try:
            ok = await self._navigate_safely(page, url)
            if not ok:
                return []

            # Try primary list selector
            try:
                await page.wait_for_selector(SEL_LIST, timeout=10_000)
                cards = await page.query_selector_all(SEL_LIST)
            except Exception:
                # Fallback selector
                try:
                    cards = await page.query_selector_all(SEL_LIST_FB)
                except Exception:
                    cards = []

            if len(cards) < 3:
                logger.warning("[LinkedIn] Blocked or no results for location=%s (got %d cards)", location, len(cards))
                return []

            for card in cards:
                try:
                    title = await self._text(card, SEL_TITLE) or await self._text(card, SEL_TITLE_FB)
                    company = await self._text(card, SEL_COMPANY) or await self._text(card, SEL_COMPANY_FB)
                    loc = await self._text(card, SEL_LOCATION) or location
                    date_posted = await self._attr(card, SEL_DATE, "datetime") or ""
                    link_el = await card.query_selector(SEL_LINK)
                    link = await link_el.get_attribute("href") if link_el else ""

                    if title and link:
                        jobs.append(
                            self._build_job_dict(
                                title=title,
                                company=company,
                                location=loc,
                                url=link,
                                description_snippet="",
                                date_posted=date_posted,
                                portal=self.portal_name,
                            )
                        )
                except Exception as exc:
                    logger.debug("[LinkedIn] Card parse error: %s", exc)

        except Exception as exc:
            logger.warning("[LinkedIn] Page error: %s", exc)
        finally:
            await page.close()
            await context.close()

        return jobs

    @staticmethod
    async def _text(element, selector: str) -> str:
        try:
            el = await element.query_selector(selector)
            return (await el.inner_text()).strip() if el else ""
        except Exception:
            return ""

    @staticmethod
    async def _attr(element, selector: str, attr: str) -> str:
        try:
            el = await element.query_selector(selector)
            return (await el.get_attribute(attr) or "").strip() if el else ""
        except Exception:
            return ""
