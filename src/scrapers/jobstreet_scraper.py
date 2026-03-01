"""
Jobstreet Scraper — scrapes JobStreet Singapore (Singapore only).
"""

import logging

from playwright.async_api import async_playwright

from config import MAX_JOBS_PER_QUERY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.jobstreet.com.sg/jobs/{query}-jobs"
PORTAL_BASE = "https://www.jobstreet.com.sg"

SEL_CARDS = "article[data-automation='normalJob']"
SEL_TITLE = "a[data-automation='jobTitle']"
SEL_COMPANY = "a[data-automation='jobCompany']"
SEL_LOCATION = "a[data-automation='jobLocation']"

# Fallback
SEL_CARDS_FB = "article[data-testid='job-card']"
SEL_TITLE_FB = "h1 a, h2 a, h3 a"


class JobstreetScraper(BaseScraper):
    portal_name = "Jobstreet"

    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        # Jobstreet SG only covers Singapore
        singapore_slug = None
        for city_key, slugs in cities.items():
            sg = slugs.get("jobstreet")
            if sg:
                singapore_slug = sg
                break

        if not singapore_slug:
            logger.info("[Jobstreet] No Singapore city configured — skipping.")
            return []

        jobs = []
        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                try:
                    for title in job_titles:
                        query_slug = title.lower().replace(" ", "-")
                        url = BASE_URL.format(query=query_slug)
                        page_jobs = await self._scrape_page(browser, url)
                        jobs.extend(page_jobs[:MAX_JOBS_PER_QUERY])
                finally:
                    await browser.close()
        except Exception as exc:
            logger.error("[Jobstreet] Fatal scraper error: %s", exc)

        logger.info("[Jobstreet] Total jobs scraped: %d", len(jobs))
        return jobs

    async def _scrape_page(self, browser, url: str) -> list[dict]:
        context = await self._create_stealth_context(browser)
        page = await context.new_page()
        jobs = []

        try:
            ok = await self._navigate_safely(page, url)
            if not ok:
                return []

            await page.wait_for_load_state("networkidle", timeout=20_000)

            cards = await page.query_selector_all(SEL_CARDS)
            if not cards:
                cards = await page.query_selector_all(SEL_CARDS_FB)

            for card in cards:
                try:
                    title_el = await card.query_selector(SEL_TITLE) or await card.query_selector(SEL_TITLE_FB)
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    link = await title_el.get_attribute("href") if title_el else ""

                    # Relative URLs — prepend base
                    if link and not link.startswith("http"):
                        link = PORTAL_BASE + link

                    company_el = await card.query_selector(SEL_COMPANY)
                    company = (await company_el.inner_text()).strip() if company_el else ""

                    location_el = await card.query_selector(SEL_LOCATION)
                    location = (await location_el.inner_text()).strip() if location_el else "Singapore"

                    if title and link:
                        jobs.append(
                            self._build_job_dict(
                                title=title,
                                company=company,
                                location=location,
                                url=link,
                                description_snippet="",
                                date_posted="",
                                portal=self.portal_name,
                            )
                        )
                except Exception as exc:
                    logger.debug("[Jobstreet] Card parse error: %s", exc)

        except Exception as exc:
            logger.warning("[Jobstreet] Page error for %s — %s", url, exc)
        finally:
            await page.close()
            await context.close()

        return jobs
