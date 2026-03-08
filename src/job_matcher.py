"""
Job Matcher — scores job listings against the candidate CV profile using Groq (Llama 3.3).
"""

import json
import logging
import time
from urllib.parse import urlparse, urlunparse

from config import GROQ_MODEL, MAX_JOBS_PER_ROLE, MAX_REPORT_JOBS, MIN_MATCH_SCORE
from config import SEARCH_ROLES

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Strip query params to deduplicate Naukri/IIMJobs tracking URLs."""
    try:
        parsed = urlparse(url)
        return urlunparse(parsed._replace(query="", fragment=""))
    except Exception:
        return url


def _deduplicate(jobs: list) -> list:
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


def _strip_markdown_fences(raw: str) -> str:
    """Remove ```json ... ``` fences the LLM sometimes adds."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) > 1:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
    return raw.strip()


def _safe_score(raw_score) -> int:
    """Coerce match_score to int, clamped 0-100. Returns 0 on any failure."""
    try:
        if isinstance(raw_score, int):
            return max(0, min(100, raw_score))
        return max(0, min(100, int(float(str(raw_score).strip()))))
    except (ValueError, TypeError):
        logger.warning("Could not coerce match_score to int: %r — defaulting to 0", raw_score)
        return 0


def _score_batch(cv_profile: dict, batch: list, client, batch_num: int) -> list:
    """
    Send a batch of jobs to Groq for scoring.
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

    system_prompt = "Return ONLY valid JSON with no explanation and no markdown code fences."

    user_prompt = f"""You are a career coach scoring job matches for a candidate.

CANDIDATE PROFILE:
- Name: {cv_profile.get('name', '')}
- Target Roles: {', '.join(cv_profile.get('target_roles', []))}
- Skills: {', '.join(cv_profile.get('skills', []))}
- Experience: {cv_profile.get('experience_years', 0)} years
- Education: {cv_profile.get('education', '')}
- Preferred Locations: {', '.join(cv_profile.get('preferred_locations', []))}

HARD RULES (apply before scoring — these override everything else):
- The candidate has {cv_profile.get('experience_years', 0)} years of experience.
- If a job requires more than {cv_profile.get('experience_years', 0) + 2} years of experience, assign score 0.
- Senior/Lead/Head/Director/VP/CTO/CXO roles that typically require 8+ years must score 0.
- Only shortlist roles a candidate with {cv_profile.get('experience_years', 0)} years can realistically apply for.

SCORING RUBRIC (applied only after hard rules pass):
- 80-100: Excellent match (role, skills, location all align)
- 60-79: Good match (most criteria met)
- 40-59: Partial match (some overlap)
- 0-39: Poor match

JOBS TO SCORE:
{jobs_text}

Return a JSON array with one object per job (in the same order):
[
  {{"job_index": 0, "match_score": <integer 0-100>, "match_reason": "<1-2 sentence reason>"}},
  ...
]"""

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            raw = _strip_markdown_fences(response.choices[0].message.content)
            scores = json.loads(raw)
            if not isinstance(scores, list):
                raise ValueError(f"Expected JSON array, got {type(scores)}")
            logger.info("Batch %d: scored %d jobs", batch_num, len(scores))
            return scores

        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Batch %d, attempt %d/%d: bad JSON — %s", batch_num, attempt, max_retries, exc
            )
        except Exception as exc:
            logger.warning(
                "Batch %d, attempt %d/%d: API error — %s", batch_num, attempt, max_retries, exc
            )

        if attempt < max_retries:
            time.sleep(2**attempt)

    logger.error("Batch %d: failed after all retries, skipping.", batch_num)
    return []


def match_all_jobs(cv_profile: dict, all_jobs: list, client) -> list:
    """
    Deduplicate, score, filter, and rank all scraped jobs.
    Returns sorted list of job dicts with 'match_score', 'match_reason', 'rank'.
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
            try:
                idx = int(score_entry.get("job_index", -1))
                if 0 <= idx < len(batch):
                    job = dict(batch[idx])
                    job["match_score"] = _safe_score(score_entry.get("match_score", 0))
                    job["match_reason"] = str(score_entry.get("match_reason", ""))
                    scored_jobs.append(job)
            except Exception as exc:
                logger.debug("Skipping malformed score entry: %s — %s", score_entry, exc)
        if batch_num < len(batches):
            time.sleep(1)

    filtered = [j for j in scored_jobs if j.get("match_score", 0) >= MIN_MATCH_SCORE]
    logger.info(
        "Scoring complete: %d total → %d above threshold (%d)",
        len(scored_jobs), len(filtered), MIN_MATCH_SCORE,
    )

    filtered.sort(key=lambda j: j["match_score"], reverse=True)

    # --- Role diversity: cap each role at MAX_JOBS_PER_ROLE before global top-N ---
    # This prevents one role (e.g. Product Manager) from monopolising the report.
    role_counts: dict[str, int] = {}
    diverse: list[dict] = []
    for job in filtered:
        job_title_lower = job.get("title", "").lower()
        # Match against the configured search roles (case-insensitive substring)
        matched_role = next(
            (r for r in SEARCH_ROLES if r.lower() in job_title_lower),
            job.get("title", "Other"),  # ungrouped titles get their own bucket
        )
        count = role_counts.get(matched_role, 0)
        if count < MAX_JOBS_PER_ROLE:
            diverse.append(job)
            role_counts[matched_role] = count + 1

    # Re-sort after diversity filter (order may have been disrupted by per-role caps)
    diverse.sort(key=lambda j: j["match_score"], reverse=True)
    top = diverse[:MAX_REPORT_JOBS]
    for rank, job in enumerate(top, start=1):
        job["rank"] = rank

    logger.info(
        "Final report: %d jobs across %d roles (capped at %d)",
        len(top), len(role_counts), MAX_REPORT_JOBS,
    )
    return top
