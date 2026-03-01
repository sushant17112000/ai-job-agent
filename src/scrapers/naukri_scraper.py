"""
Naukri Scraper — scrapes Naukri.com job listings for Indian cities.
"""

import asyncio
import logging

from playwright.async_api import async_playwright

from config import MAX_JOBS_PER_QUERY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.naukri.com/{query}-jobs-in-{city}"

SEL_CARDS = "article.jobTuple"
SEL_TITLE = "a.title"
SEL_COMPANY = "a.subTitle"
SEL_LOCATION = "li.location span"
SEL_DATE = "span.date"

# Fallback
SEL_CARDS_FB = "div.jobTupleHeader"
SEL_TITLE_FB = "a[title]"


class NaukriScraper(BaseScraper):
    portal_name = "Naukri"

    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        jobs = []
        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                try:
                    for title in job_titles:
                        for city_key, slugs in cities.items():
                            city_slug = slugs.get("naukri")
                            if not city_slug:
                                continue
                            query_slug = title.lower().replace(" ", "-")
                            url = BASE_URL.format(query=query_slug, city=city_slug)
                            page_jobs = await self._scrape_page(browser, url)
                            jobs.extend(page_jobs[:MAX_JOBS_PER_QUERY])
                finally:
                    await browser.close()
        except Exception as exc:
            logger.error("[Naukri] Fatal scraper error: %s", exc)

        logger.info("[Naukri] Total jobs scraped: %d", len(jobs))
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
            await asyncio.sleep(2)

            # Dismiss login modal if present
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except Exception:
                pass

            # Try primary selectors
            cards = await page.query_selector_all(SEL_CARDS)
            if not cards:
                cards = await page.query_selector_all(SEL_CARDS_FB)

            for card in cards:
                try:
                    title = await self._text(card, SEL_TITLE) or await self._text(card, SEL_TITLE_FB)
                    company = await self._text(card, SEL_COMPANY)
                    location = await self._text(card, SEL_LOCATION)
                    date_posted = await self._text(card, SEL_DATE)

                    link_el = await card.query_selector(SEL_TITLE) or await card.query_selector(SEL_TITLE_FB)
                    link = await link_el.get_attribute("href") if link_el else ""

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
                    logger.debug("[Naukri] Card parse error: %s", exc)

        except Exception as exc:
            logger.warning("[Naukri] Page error for %s — %s", url, exc)
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
