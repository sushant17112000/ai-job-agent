"""
TimesJobs Scraper — timesjobs.com (Times Internet, widely used in India).

Supports keyword + location search with last-24-hours filter.
"""

import asyncio
import logging
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from config import MAX_JOBS_PER_QUERY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# last 1 day filter: sequence=1 (posted today)
SEARCH_URL = (
    "https://www.timesjobs.com/candidate/job-search.html"
    "?searchType=personalizedSearch&from=submit"
    "&txtKeywords={query}&txtLocation={location}&sequence=1&startPage=1"
)

SEL_CARDS   = "li.clearfix.job-bx.wht-shd-bx"
SEL_TITLE   = "h2 a"
SEL_COMPANY = "h3.joblist-comp-name"
SEL_LOCATION= "ul.top-jd-dtl li"          # first <li> is location
SEL_DATE    = "span.sim-posted"

# Fallback
SEL_CARDS_FB= "div.job-bx, li[class*='job']"
SEL_TITLE_FB= "a[title]"


class TimesJobsScraper(BaseScraper):
    portal_name = "TimesJobs"

    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        jobs = []
        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                try:
                    for title in job_titles:
                        for city_key, slugs in cities.items():
                            location = slugs.get("timesjobs")
                            if not location:
                                continue
                            url = SEARCH_URL.format(
                                query=quote_plus(title),
                                location=quote_plus(location),
                            )
                            page_jobs = await self._scrape_page(browser, url, city_key)
                            jobs.extend(page_jobs[:MAX_JOBS_PER_QUERY])
                finally:
                    await browser.close()
        except Exception as exc:
            logger.error("[TimesJobs] Fatal scraper error: %s", exc)

        logger.info("[TimesJobs] Total jobs scraped: %d", len(jobs))
        return jobs

    async def _scrape_page(self, browser, url: str, city: str) -> list[dict]:
        context = await self._create_stealth_context(browser)
        page = await context.new_page()
        jobs = []

        try:
            ok = await self._navigate_safely(page, url)
            if not ok:
                return []

            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            await asyncio.sleep(1.5)

            cards = await page.query_selector_all(SEL_CARDS)
            if not cards:
                cards = await page.query_selector_all(SEL_CARDS_FB)

            if not cards:
                logger.warning("[TimesJobs] No job cards found for city=%s", city)
                return []

            for card in cards:
                try:
                    title_el = await card.query_selector(SEL_TITLE)
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    if not title:
                        title = await self._text(card, SEL_TITLE_FB)
                    if not title:
                        continue

                    link = ""
                    if title_el:
                        link = await title_el.get_attribute("href") or ""

                    company = await self._text(card, SEL_COMPANY)
                    date_posted = await self._text(card, SEL_DATE)

                    # Location: first list item in top-jd-dtl
                    loc_items = await card.query_selector_all(SEL_LOCATION)
                    location = (await loc_items[0].inner_text()).strip() if loc_items else city

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
                    logger.debug("[TimesJobs] Card parse error: %s", exc)

        except Exception as exc:
            logger.warning("[TimesJobs] Page error city=%s — %s", city, exc)
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
