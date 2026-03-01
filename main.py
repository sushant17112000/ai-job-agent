"""
AI Job Search Agent — Orchestrator.

Runs all scrapers concurrently, scores jobs with Gemini, and generates an Excel report.
"""

import asyncio
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Load .env for local runs (no-op in GitHub Actions)
load_dotenv()

import google.generativeai as genai

from config import CV_PATH, CITIES, GEMINI_MODEL, REPORTS_DIR
from src.cv_parser import CVParseError, extract_text_from_pdf, parse_cv_with_gemini
from src.excel_generator import generate_excel
from src.github_uploader import commit_excel_via_git
from src.job_matcher import match_all_jobs
from src.scrapers.iimjobs_scraper import IIMJobsScraper
from src.scrapers.jobstreet_scraper import JobstreetScraper
from src.scrapers.linkedin_scraper import LinkedInScraper
from src.scrapers.naukri_scraper import NaukriScraper

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safe scraper wrapper
# ---------------------------------------------------------------------------
async def safe_scrape(scraper, job_titles: list[str], cities: dict) -> list[dict]:
    """Run a scraper and return [] on any unhandled exception."""
    try:
        return await scraper.scrape(job_titles, cities)
    except Exception as exc:
        logger.error("[%s] Unhandled exception in scraper: %s", scraper.portal_name, exc)
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    # 1. Validate prerequisites
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY environment variable is not set.")
        sys.exit(1)

    if not Path(CV_PATH).exists():
        logger.error("CV not found at '%s'. Please place your resume PDF there.", CV_PATH)
        sys.exit(1)

    # Configure Gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    # 2. Parse CV
    logger.info("=== Step 1: Parsing CV ===")
    try:
        cv_text = extract_text_from_pdf(CV_PATH)
        cv_profile = parse_cv_with_gemini(cv_text, model)
        logger.info("Candidate: %s | Roles: %s", cv_profile.get("name"), cv_profile.get("target_roles"))
    except (CVParseError, FileNotFoundError) as exc:
        logger.error("CV parsing failed: %s", exc)
        sys.exit(1)

    job_titles: list[str] = cv_profile.get("target_roles", [])
    if not job_titles:
        logger.warning("No target roles extracted from CV — using generic 'Software Engineer'.")
        job_titles = ["Software Engineer"]

    # 3. Run all 4 scrapers concurrently
    logger.info("=== Step 2: Scraping job portals ===")
    scrapers = [
        LinkedInScraper(),
        NaukriScraper(),
        IIMJobsScraper(),
        JobstreetScraper(),
    ]

    results = await asyncio.gather(
        *[safe_scrape(s, job_titles, CITIES) for s in scrapers]
    )

    all_jobs: list[dict] = []
    for scraper, portal_jobs in zip(scrapers, results):
        logger.info("[%s] Returned %d jobs", scraper.portal_name, len(portal_jobs))
        all_jobs.extend(portal_jobs)

    logger.info("Total raw jobs collected: %d", len(all_jobs))

    if not all_jobs:
        logger.warning("No jobs scraped from any portal. Exiting cleanly.")
        sys.exit(0)

    # 4. Score and filter jobs with Gemini
    logger.info("=== Step 3: Scoring jobs with Gemini ===")
    scored_jobs = match_all_jobs(cv_profile, all_jobs, model)
    logger.info("Matched jobs after scoring: %d", len(scored_jobs))

    if not scored_jobs:
        logger.warning("No jobs met the minimum match score. Exiting cleanly.")
        sys.exit(0)

    # 5. Generate Excel report
    logger.info("=== Step 4: Generating Excel report ===")
    report_path = generate_excel(
        scored_jobs=scored_jobs,
        cv_profile=cv_profile,
        report_date=date.today(),
        output_dir=REPORTS_DIR,
    )
    logger.info("Report saved: %s", report_path)

    # 6. Commit via git (GitHub Actions only)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        logger.info("=== Step 5: Committing report to GitHub ===")
        commit_excel_via_git(
            file_path=report_path,
            commit_message=f"Daily job report: {date.today().isoformat()}",
        )

    logger.info("=== Done! ===")


if __name__ == "__main__":
    asyncio.run(main())
