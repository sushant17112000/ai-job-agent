"""
IIMJobs Scraper — scrapes IIMJobs.com (India-wide, filtered by city post-fetch).
"""

import logging

from playwright.async_api import async_playwright

from config import IIMJOBS_CITY_NAMES, MAX_JOBS_PER_QUERY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.iimjobs.com/j/{query}-jobs.html"

SEL_CARDS = "div.job-container"
SEL_TITLE = "h2.job-title a"
SEL_COMPANY = "span.company-name"
SEL_LOCATION = "span.loc"
SEL_DATE = "span.date"

# Fallback
SEL_CARDS_FB = "div.jobRow"
SEL_TITLE_FB = "h2 a"


class IIMJobsScraper(BaseScraper):
    portal_name = "IIMJobs"

    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        all_jobs = []
        # Collect target city names for post-filtering
        target_city_names = []
        for city_key in cities:
            cn = IIMJOBS_CITY_NAMES.get(city_key)
            if cn:
                target_city_names.append(cn.lower())

        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                try:
                    for title in job_titles:
                        query_slug = title.lower().replace(" ", "-")
                        url = BASE_URL.format(query=query_slug)
                        page_jobs = await self._scrape_page(browser, url)
                        all_jobs.extend(page_jobs)
                finally:
                    await browser.close()
        except Exception as exc:
            logger.error("[IIMJobs] Fatal scraper error: %s", exc)

        # Post-filter by city
        if target_city_names:
            filtered = [
                j for j in all_jobs
                if any(cn in j.get("location", "").lower() for cn in target_city_names)
            ]
            # If no city match at all, include all (might have different location format)
            if not filtered:
                filtered = all_jobs
        else:
            filtered = all_jobs

        filtered = filtered[:MAX_JOBS_PER_QUERY * len(job_titles)]
        logger.info("[IIMJobs] Total jobs scraped: %d (after city filter: %d)", len(all_jobs), len(filtered))
        return filtered

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

                    # Ensure absolute URL
                    if link and not link.startswith("http"):
                        link = "https://www.iimjobs.com" + link

                    company = await self._text(card, SEL_COMPANY)
                    location = await self._text(card, SEL_LOCATION)
                    date_posted = await self._text(card, SEL_DATE)

                    if title and link:
                        jobs.append(
                            self._build_job_dict(
                                title=title,
                                company=company,
                                location=location,
                                url=link,
                                description_snippet="",
                                date_posted=date_posted,
                                portal=self.portal_name,
                            )
                        )
                except Exception as exc:
                    logger.debug("[IIMJobs] Card parse error: %s", exc)

        except Exception as exc:
            logger.warning("[IIMJobs] Page error for %s — %s", url, exc)
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
