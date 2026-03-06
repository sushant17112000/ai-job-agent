"""
Configuration constants for the AI Job Search Agent.
"""

# --- Target Search Roles ---
# Domains: Product Management, Strategy Consulting, Digital Transformation, Customer Experience
SEARCH_ROLES = [
    "Product Manager",
    "Strategy Consultant",
    "Management Consultant",
    "Digital Transformation Manager",
    "Customer Experience Manager",
    "Business Analyst",
    "Product Strategy Manager",
    "Digital Strategy Consultant",
]

# --- Cities & Portal-Specific Location Slugs ---
# Order: Singapore, Bengaluru, Mumbai, Hyderabad, Australia
# None means the portal does not support that city via URL filter.
CITIES = {
    "singapore": {
        "linkedin": "Singapore",
        "naukri": None,
        "iimjobs": None,  # post-filter by city name
        "jobstreet": "singapore",
        "ncs": None,       # NCS is India-only
        "timesjobs": None, # TimesJobs is India-only
    },
    "bengaluru": {
        "linkedin": "Bengaluru, India",
        "naukri": "bengaluru",
        "iimjobs": None,  # post-filter by city name
        "jobstreet": None,
        "ncs": "Bengaluru",
        "timesjobs": "Bengaluru",
    },
    "mumbai": {
        "linkedin": "Mumbai, India",
        "naukri": "mumbai",
        "iimjobs": None,  # post-filter by city name
        "jobstreet": None,
        "ncs": "Mumbai",
        "timesjobs": "Mumbai",
    },
    "hyderabad": {
        "linkedin": "Hyderabad, India",
        "naukri": "hyderabad",
        "iimjobs": None,  # post-filter by city name
        "jobstreet": None,
        "ncs": "Hyderabad",
        "timesjobs": "Hyderabad",
    },
    "australia": {
        "linkedin": "Australia",
        "naukri": None,
        "iimjobs": None,
        "jobstreet": None,
        "ncs": None,
        "timesjobs": None,
    },
}

# IIMJobs India city names for post-filtering (lowercase)
IIMJOBS_CITY_NAMES = {
    "singapore": "singapore",
    "bengaluru": "bengaluru",
    "mumbai": "mumbai",
    "hyderabad": "hyderabad",
    "australia": "australia",
}

# --- Matching Settings ---
MIN_MATCH_SCORE = 60
MAX_JOBS_PER_QUERY = 25

# --- LLM: Groq (free tier, no credit card required) ---
# Get your free API key at https://console.groq.com
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
