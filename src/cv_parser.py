"""
CV Parser — extracts text from PDF and uses Groq (Llama) to produce a structured profile.
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


def parse_cv_with_groq(text: str, client) -> dict:
    """
    Send CV text to Groq (Llama) and return a structured profile dict.

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

    system_prompt = "Return ONLY valid JSON, no explanation, no markdown code fences."

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

    max_retries = 2
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
            raw = response.choices[0].message.content.strip()

            # Strip accidental markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            profile = json.loads(raw)
            logger.info("CV parsed successfully: %s", profile.get("name", "unknown"))
            return profile

        except json.JSONDecodeError as exc:
            logger.warning(
                "Attempt %d/%d: Groq returned invalid JSON — %s", attempt, max_retries, exc
            )
            if attempt < max_retries:
                time.sleep(2**attempt)
        except Exception as exc:
            logger.warning("Attempt %d/%d: Groq API error — %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(2**attempt)

    raise CVParseError("Failed to parse CV after all retries.")
