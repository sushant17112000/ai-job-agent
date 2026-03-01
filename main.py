"""
AI Job Search Agent — Orchestrator.
"""

import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from groq import Groq

from config import CITIES, CV_PATH, REPORTS_DIR
from src.cv_parser import CVParseError, extract_text_from_pdf, parse_cv_with_groq
from src.excel_generator import generate_excel
from src.github_uploader import commit_excel_via_git
from src.job_matcher import match_all_jobs
from src.scrapers.iimjobs_scraper import IIMJobsScraper
from src.scrapers.jobstreet_scraper import JobstreetScraper
from src.scrapers.linkedin_scraper import LinkedInScraper
from src.scrapers.naukri_scraper import NaukriScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def safe_scrape(scraper, job_titles: list, cities: dict) -> list:
    """Run a scraper and return [] on any unhandled exception."""
    try:
        return await scraper.scrape(job_titles, cities)
    except Exception as exc:
        logger.error("[%s] Unhandled exception in scraper: %s", scraper.portal_name, exc)
        return []


async def main() -> None:
    # 1. Validate prerequisites
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY environment variable is not set.")
        sys.exit(1)

    if not Path(CV_PATH).exists():
        logger.error("CV not found at '%s'. Place your resume PDF there.", CV_PATH)
        sys.exit(1)

    try:
        client = Groq(api_key=api_key)
    except Exception as exc:
        logger.error("Failed to initialize Groq client: %s", exc)
        sys.exit(1)

    # 2. Parse CV
    logger.info("=== Step 1: Parsing CV ===")
    try:
        cv_text    = extract_text_from_pdf(CV_PATH)
        cv_profile = parse_cv_with_groq(cv_text, client)
        logger.info("Candidate: %s | Roles: %s", cv_profile.get("name"), cv_profile.get("target_roles"))
    except (CVParseError, FileNotFoundError) as exc:
        logger.error("CV parsing failed: %s", exc)
        sys.exit(1)

    job_titles = cv_profile.get("target_roles", [])
    if not job_titles or not isinstance(job_titles, list):
        logger.warning("No target roles found in CV — defaulting to 'Software Engineer'.")
        job_titles = ["Software Engineer"]

    # 3. Run all 4 scrapers concurrently
    logger.info("=== Step 2: Scraping job portals ===")
    scrapers = [LinkedInScraper(), NaukriScraper(), IIMJobsScraper(), JobstreetScraper()]

    results = await asyncio.gather(*[safe_scrape(s, job_titles, CITIES) for s in scrapers])

    all_jobs = []
    for scraper, portal_jobs in zip(scrapers, results):
        logger.info("[%s] Returned %d jobs", scraper.portal_name, len(portal_jobs))
        all_jobs.extend(portal_jobs)

    logger.info("Total raw jobs collected: %d", len(all_jobs))

    if not all_jobs:
        logger.warning("No jobs scraped from any portal today. Exiting cleanly.")
        sys.exit(0)

    # 4. Score with Groq
    logger.info("=== Step 3: Scoring jobs with Groq ===")
    scored_jobs = match_all_jobs(cv_profile, all_jobs, client)
    logger.info("Matched jobs after scoring: %d", len(scored_jobs))

    if not scored_jobs:
        logger.warning("No jobs met the minimum match score. Exiting cleanly.")
        sys.exit(0)

    # 5. Generate Excel
    logger.info("=== Step 4: Generating Excel report ===")
    report_path = generate_excel(
        scored_jobs=scored_jobs,
        cv_profile=cv_profile,
        report_date=date.today(),
        output_dir=REPORTS_DIR,
    )
    logger.info("Report saved: %s", report_path)

    # 6. Commit (GitHub Actions only)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        logger.info("=== Step 5: Committing report ===")
        commit_excel_via_git(
            file_path=report_path,
            commit_message=f"Daily job report: {date.today().isoformat()}",
        )

    logger.info("=== Done! ===")


if __name__ == "__main__":
    asyncio.run(main())
