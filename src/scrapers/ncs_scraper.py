"""
NCS Scraper — India's National Career Service Portal (ncs.gov.in).

Government of India's official job portal — aggregates private sector,
PSU, and government vacancies. Supports keyword + location search.
"""

import asyncio
import logging
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from config import MAX_JOBS_PER_QUERY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# NCS search URL — keyword-based, location post-filtered
SEARCH_URL = (
    "https://www.ncs.gov.in/jobseeker/Pages/JobSearch.aspx"
    "?keyword={query}&location={location}"
)

# Primary selectors (React-rendered portal)
SEL_CARDS   = "div.job-card, div.jobCard, li.job-listing, div[class*='jobCard'], div[class*='job-card']"
SEL_TITLE   = "h2, h3, .job-title, .position-name, [class*='job-title'], [class*='jobTitle']"
SEL_COMPANY = ".company-name, .employer-name, .org-name, [class*='company'], [class*='employer']"
SEL_LOCATION= ".location, .job-location, [class*='location']"
SEL_LINK    = "a[href*='job'], a[href*='Job'], a[href*='vacancy']"

# Fallback — generic table / list rows used in older portal version
SEL_CARDS_FB= "table.jobList tr[class*='job'], ul.job-list li, .search-result-item"
SEL_TITLE_FB= "td.jobTitle a, .resultTitle a, a.jobLink"


class NCSScraper(BaseScraper):
    portal_name = "NCS"

    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        jobs = []
        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                try:
                    for title in job_titles:
                        for city_key, slugs in cities.items():
                            location = slugs.get("ncs")
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
            logger.error("[NCS] Fatal scraper error: %s", exc)

        logger.info("[NCS] Total jobs scraped: %d", len(jobs))
        return jobs

    async def _scrape_page(self, browser, url: str, city: str) -> list[dict]:
        context = await self._create_stealth_context(browser)
        page = await context.new_page()
        jobs = []

        try:
            ok = await self._navigate_safely(page, url)
            if not ok:
                return []

            # NCS is a React SPA — wait for network to settle then allow JS render
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            await asyncio.sleep(2)

            # Try primary dynamic card selector
            cards = await page.query_selector_all(SEL_CARDS)

            # Fallback to older portal layout
            if not cards:
                cards = await page.query_selector_all(SEL_CARDS_FB)

            if not cards:
                logger.warning("[NCS] No job cards found for city=%s url=%s", city, url)
                return []

            for card in cards:
                try:
                    title = await self._text(card, SEL_TITLE) or await self._text(card, SEL_TITLE_FB)
                    company = await self._text(card, SEL_COMPANY)
                    location = await self._text(card, SEL_LOCATION) or city

                    # Skip cards that clearly aren't jobs (header rows, ads)
                    if not title or len(title) < 3:
                        continue

                    link_el = await card.query_selector(SEL_LINK)
                    link = ""
                    if link_el:
                        href = await link_el.get_attribute("href") or ""
                        link = href if href.startswith("http") else f"https://www.ncs.gov.in{href}"

                    jobs.append(
                        self._build_job_dict(
                            title=title,
                            company=company or "Government / PSU",
                            location=location,
                            url=link,  # empty string if no job link found — avoids dedup collapse on search URL
                            description_snippet="",
                            date_posted="",
                            portal=self.portal_name,
                        )
                    )
                except Exception as exc:
                    logger.debug("[NCS] Card parse error: %s", exc)

        except Exception as exc:
            logger.warning("[NCS] Page error city=%s — %s", city, exc)
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
