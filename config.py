"""
Configuration constants for the AI Job Search Agent.
"""

# --- Cities & Portal-Specific Location Slugs ---
# Order: Singapore, Bengaluru, Australia, New Delhi, Hyderabad
# None means the portal does not support that city via URL filter.
CITIES = {
    "singapore": {
        "linkedin": "Singapore",
        "naukri": None,
        "iimjobs": None,  # post-filter by city name
        "jobstreet": "singapore",
    },
    "bengaluru": {
        "linkedin": "Bengaluru, India",
        "naukri": "bengaluru",
        "iimjobs": None,  # post-filter by city name
        "jobstreet": None,
    },
    "australia": {
        "linkedin": "Australia",
        "naukri": None,
        "iimjobs": None,
        "jobstreet": None,
    },
    "new_delhi": {
        "linkedin": "New Delhi, India",
        "naukri": "new-delhi",
        "iimjobs": None,  # post-filter by city name
        "jobstreet": None,
    },
    "hyderabad": {
        "linkedin": "Hyderabad, India",
        "naukri": "hyderabad",
        "iimjobs": None,  # post-filter by city name
        "jobstreet": None,
    },
}

# IIMJobs India city names for post-filtering (lowercase)
IIMJOBS_CITY_NAMES = {
    "singapore": "singapore",
    "bengaluru": "bengaluru",
    "australia": "australia",
    "new_delhi": "delhi",
    "hyderabad": "hyderabad",
}

# --- Matching Settings ---
MIN_MATCH_SCORE = 60
MAX_JOBS_PER_QUERY = 25

# --- Groq Model (free tier: 14,400 req/day, 500K tokens/day) ---
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Stealth Browser User Agents ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
]

# --- Scraper Timeouts ---
PAGE_TIMEOUT_MS = 30_000   # 30 seconds per page navigation
EXTRA_WAIT_MS = 2_000      # Extra wait after networkidle

# --- Paths ---
CV_PATH = "cv/resume.pdf"
REPORTS_DIR = "reports"
