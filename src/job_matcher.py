"""
Job Matcher — scores job listings against the candidate CV profile using Gemini.
"""

import json
import logging
import time
from urllib.parse import urlparse, urlunparse

from google import genai
from google.genai import types

from config import GEMINI_MODEL, MIN_MATCH_SCORE

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Strip query params to deduplicate Naukri/IIMJobs tracking URLs."""
    try:
        parsed = urlparse(url)
        return urlunparse(parsed._replace(query="", fragment=""))
    except Exception:
        return url


def _deduplicate(jobs: list[dict]) -> list[dict]:
    """Remove duplicate jobs by normalized URL."""
    seen = set()
    unique = []
    for job in jobs:
        key = _normalize_url(job.get("url", ""))
        if key and key not in seen:
            seen.add(key)
            unique.append(job)
    logger.info("Deduplication: %d → %d jobs", len(jobs), len(unique))
    return unique


def _score_batch(cv_profile: dict, batch: list[dict], client: genai.Client, batch_num: int) -> list[dict]:
    """
    Send a batch of jobs to Gemini for scoring.

    Returns list of dicts: [{job_index, match_score, match_reason}, ...]
    """
    jobs_text = ""
    for i, job in enumerate(batch):
        jobs_text += (
            f"\nJob {i}:\n"
            f"  Title: {job.get('title', '')}\n"
            f"  Company: {job.get('company', '')}\n"
            f"  Location: {job.get('location', '')}\n"
            f"  Description: {job.get('description_snippet', '')}\n"
        )

    system_prompt = "Return ONLY valid JSON, no explanation, no markdown code fences."

    user_prompt = f"""You are a career coach scoring job matches for a candidate.

CANDIDATE PROFILE:
- Name: {cv_profile.get('name', '')}
- Target Roles: {', '.join(cv_profile.get('target_roles', []))}
- Skills: {', '.join(cv_profile.get('skills', []))}
- Experience: {cv_profile.get('experience_years', 0)} years
- Education: {cv_profile.get('education', '')}
- Preferred Locations: {', '.join(cv_profile.get('preferred_locations', []))}

SCORING RUBRIC:
- 80-100: Excellent match (role, skills, location all align)
- 60-79: Good match (most criteria met)
- 40-59: Partial match (some overlap)
- 0-39: Poor match

JOBS TO SCORE:
{jobs_text}

Return a JSON array with one object per job (in the same order):
[
  {{"job_index": 0, "match_score": <0-100>, "match_reason": "<1-2 sentence reason>"}},
  ...
]"""

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.1,
                    max_output_tokens=2048,
                ),
            )
            raw = response.text.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            scores = json.loads(raw)
            logger.info("Batch %d: scored %d jobs", batch_num, len(scores))
            return scores

        except json.JSONDecodeError as exc:
            logger.warning(
                "Batch %d, attempt %d/%d: invalid JSON — %s", batch_num, attempt, max_retries, exc
            )
        except Exception as exc:
            logger.warning(
                "Batch %d, attempt %d/%d: API error — %s", batch_num, attempt, max_retries, exc
            )

        if attempt < max_retries:
            time.sleep(2**attempt)

    logger.error("Batch %d: failed after all retries, skipping.", batch_num)
    return []


def match_all_jobs(cv_profile: dict, all_jobs: list[dict], client: genai.Client) -> list[dict]:
    """
    Deduplicate, score, filter, and rank all scraped jobs.

    Returns:
        Sorted list of job dicts augmented with 'match_score', 'match_reason', 'rank'.
    """
    if not all_jobs:
        logger.info("No jobs to score.")
        return []

    unique_jobs = _deduplicate(all_jobs)

    batch_size = 10
    batches = [unique_jobs[i : i + batch_size] for i in range(0, len(unique_jobs), batch_size)]

    scored_jobs = []
    for batch_num, batch in enumerate(batches, start=1):
        scores = _score_batch(cv_profile, batch, client, batch_num)
        for score_entry in scores:
            idx = score_entry.get("job_index", -1)
            if 0 <= idx < len(batch):
                job = dict(batch[idx])
                job["match_score"] = score_entry.get("match_score", 0)
                job["match_reason"] = score_entry.get("match_reason", "")
                scored_jobs.append(job)
        if batch_num < len(batches):
            time.sleep(2)

    filtered = [j for j in scored_jobs if j.get("match_score", 0) >= MIN_MATCH_SCORE]
    logger.info(
        "Scoring complete: %d total → %d above threshold (%d)",
        len(scored_jobs),
        len(filtered),
        MIN_MATCH_SCORE,
    )

    filtered.sort(key=lambda j: j["match_score"], reverse=True)
    for rank, job in enumerate(filtered, start=1):
        job["rank"] = rank

    return filtered
