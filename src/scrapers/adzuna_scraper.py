"""
Adzuna Scraper — Adzuna Job Search API (India).

Free tier: 200 requests/day.
Sign up: https://developer.adzuna.com
Required env vars: ADZUNA_APP_ID, ADZUNA_APP_KEY
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

# India country code for Adzuna
_BASE = "https://api.adzuna.com/v1/api/jobs/in/search/1"

# Only search Indian cities (Adzuna India endpoint)
_INDIA_CITIES = {"bengaluru", "mumbai", "hyderabad"}


class AdzunaScraper(BaseScraper):
    portal_name = "Adzuna"

    def __init__(self) -> None:
        self._app_id  = os.environ.get("ADZUNA_APP_ID", "")
        self._app_key = os.environ.get("ADZUNA_APP_KEY", "")

    async def scrape(self, job_titles: list[str], cities: dict) -> list[dict]:
        if not self._app_id or not self._app_key:
            logger.warning("[Adzuna] ADZUNA_APP_ID / ADZUNA_APP_KEY not set — skipping.")
            return []

        jobs: list[dict] = []
        for title in job_titles:
            for city_key in cities:
                if city_key not in _INDIA_CITIES:
                    continue
                city_label = city_key.capitalize()
                page_jobs = await self._fetch_jobs(title, city_label)
                jobs.extend(page_jobs[:MAX_JOBS_PER_QUERY])

        logger.info("[Adzuna] Total jobs fetched: %d", len(jobs))
        return jobs

    async def _fetch_jobs(self, title: str, city: str) -> list[dict]:
        params = urllib.parse.urlencode({
            "app_id":          self._app_id,
            "app_key":         self._app_key,
            "what":            title,
            "where":           city,
            "results_per_page": MAX_JOBS_PER_QUERY,
            "max_days_old":    7,
            "content-type":    "application/json",
        })
        url = f"{_BASE}?{params}"

        try:
            data = await asyncio.to_thread(self._get_json, url)
        except Exception as exc:
            logger.warning("[Adzuna] API error for '%s' in %s — %s", title, city, exc)
            return []

        jobs = []
        for item in data.get("results", []):
            job_title   = (item.get("title") or "").strip()
            company     = (item.get("company") or {}).get("display_name", "").strip()
            location    = (item.get("location") or {}).get("display_name", city).strip()
            url_link    = (item.get("redirect_url") or "").strip()
            description = (item.get("description") or "").strip()[:500]
            created     = (item.get("created") or "").strip()

            if job_title:
                jobs.append(
                    self._build_job_dict(
                        title=job_title,
                        company=company,
                        location=location,
                        url=url_link,
                        description_snippet=description,
                        date_posted=created,
                        portal=self.portal_name,
                    )
                )
        return jobs

    @staticmethod
    def _get_json(url: str) -> dict:
        """Synchronous JSON fetch (run inside asyncio.to_thread)."""
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "AI-Job-Agent/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
