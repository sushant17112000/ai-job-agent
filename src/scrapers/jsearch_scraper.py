"""
JSearch Scraper — JSearch API via RapidAPI.

Aggregates jobs from Naukri, IIMJobs, LinkedIn, Indeed, Glassdoor & more.
Free tier: 200 requests/month. Basic: $10/month for 1,000 req/month.
Sign up: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
Required env var: JSEARCH_API_KEY
"""

import asyncio
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from config import MAX_JOBS_PER_QUERY
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_ENDPOINT = "https://jsearch.p.rapidapi.com/search"
_HOST     = "jsearch.p.rapidapi.com"

# Map city keys to search-friendly labels
_INDIA_CITY_LABELS = {
    "bengaluru": "Bangalore India",
    "mumbai":    "Mumbai India",
    "hyderabad": "Hyderabad India",
}


class JSearchScraper(BaseScraper):
    portal_name = "JSearch"

    def __init__(self) -> None:
        self._api_key = os.environ.get("JSEARCH_API_KEY", "")

    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        if not self._api_key:
            logger.warning("[JSearch] JSEARCH_API_KEY not set — skipping.")
            return []

        jobs: list[dict] = []
        for title in job_titles:
            for city_key in cities:
                city_label = _INDIA_CITY_LABELS.get(city_key)
                if not city_label:
                    continue
                page_jobs = await self._fetch_jobs(title, city_label)
                jobs.extend(page_jobs[:MAX_JOBS_PER_QUERY])

        logger.info("[JSearch] Total jobs fetched: %d", len(jobs))
        return jobs

    async def _fetch_jobs(self, title: str, city_label: str) -> list[dict]:
        query  = f"{title} in {city_label}"
        params = urllib.parse.urlencode({
            "query":       query,
            "page":        "1",
            "num_pages":   "1",
            "date_posted": "today",
        })
        url = f"{_ENDPOINT}?{params}"

        try:
            data = await asyncio.to_thread(self._get_json, url, self._api_key)
        except Exception as exc:
            logger.warning("[JSearch] API error for '%s' in %s — %s", title, city_label, exc)
            return []

        jobs = []
        for item in data.get("data", []):
            job_title   = (item.get("job_title") or "").strip()
            company     = (item.get("employer_name") or "").strip()
            city        = (item.get("job_city") or item.get("job_country") or city_label).strip()
            url_link    = (item.get("job_apply_link") or item.get("job_google_link") or "").strip()
            description = (item.get("job_description") or "").strip()[:500]
            posted      = (item.get("job_posted_at_datetime_utc") or "").strip()

            if job_title:
                jobs.append(
                    self._build_job_dict(
                        title=job_title,
                        company=company,
                        location=city,
                        url=url_link,
                        description_snippet=description,
                        date_posted=posted,
                        portal=self.portal_name,
                    )
                )
        return jobs

    @staticmethod
    def _get_json(url: str, api_key: str) -> dict:
        """Synchronous JSON fetch (run inside asyncio.to_thread)."""
        req = urllib.request.Request(
            url,
            headers={
                "X-RapidAPI-Key":  api_key,
                "X-RapidAPI-Host": _HOST,
                "Accept":          "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
