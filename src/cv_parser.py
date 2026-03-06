"""
CV Parser — extracts text from PDF and uses Groq (Llama 3.3) to produce a structured profile.
"""

import json
import logging
import time
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


class CVParseError(Exception):
    """Raised when the CV cannot be parsed after all retries."""


def extract_text_from_pdf(path: str) -> str:
    """Extract all text from a PDF file by concatenating every page."""
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"CV not found at: {path}")

    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    full_text = "\n\n".join(pages_text)
    if not full_text.strip():
        raise CVParseError("PDF appears to contain no extractable text (scanned image?)")

    logger.info("Extracted %d characters from %d pages", len(full_text), len(pages_text))
    return full_text


def _strip_markdown_fences(raw: str) -> str:
    """Remove ```json ... ``` fences that the LLM sometimes wraps output in."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) > 1:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
    return raw.strip()


def parse_cv_with_groq(text: str, client) -> dict:
    """
    Send CV text to Groq and return a structured profile dict.

    Returns:
        {
            "name": str,
            "target_roles": [str, ...],
            "skills": [str, ...],
            "experience_years": int,
            "education": str,
            "preferred_locations": [str, ...]
        }

    Raises:
        CVParseError: if Groq returns invalid JSON after 2 retries.
    """
    from config import GROQ_MODEL

    system_prompt = "Return ONLY valid JSON with no explanation and no markdown code fences."

    user_prompt = f"""Extract a structured professional profile from the following CV text.

Return a JSON object with exactly these keys:
- "name": full name of the candidate (string)
- "target_roles": list of job titles the candidate is targeting or has held (max 8, strings)
- "skills": list of technical and soft skills (max 20, strings)
- "experience_years": total years of professional experience (integer)
- "education": highest qualification and institution (string)
- "preferred_locations": list of cities or countries preferred for work (strings)

CV TEXT:
{text}"""

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
                max_tokens=1024,
            )
            raw = _strip_markdown_fences(response.choices[0].message.content)
            profile = json.loads(raw)

            # Ensure required keys exist with sensible defaults
            profile.setdefault("name", "Unknown")
            profile.setdefault("target_roles", [])
            profile.setdefault("skills", [])
            profile.setdefault("experience_years", 0)
            profile.setdefault("education", "")
            profile.setdefault("preferred_locations", [])

            # Ensure target_roles is a list
            if not isinstance(profile["target_roles"], list):
                profile["target_roles"] = [str(profile["target_roles"])]

            logger.info("CV parsed successfully: %s", profile.get("name", "unknown"))
            return profile

        except json.JSONDecodeError as exc:
            logger.warning(
                "Attempt %d/%d: Groq returned invalid JSON — %s\nRaw response: %r",
                attempt, max_retries, exc, raw if "raw" in dir() else "N/A",
            )
            if attempt < max_retries:
                time.sleep(2**attempt)
        except Exception as exc:
            logger.warning(
                "Attempt %d/%d: Groq API error — %s: %s",
                attempt, max_retries, type(exc).__name__, exc,
            )
            if attempt < max_retries:
                time.sleep(2**attempt)

    raise CVParseError("Failed to parse CV after all retries.")
