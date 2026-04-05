import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SCORE_THRESHOLD = int(os.getenv("SCORE_THRESHOLD", "40"))

# Compensation band (annual total comp, USD). Set in .env so personal numbers never ship.
COMP_FLOOR = int(os.getenv("COMP_FLOOR") or 0)
COMP_TARGET = int(os.getenv("COMP_TARGET") or 0)
COMP_TOP = int(os.getenv("COMP_TOP") or 0)

APIFY_ACTOR_ID = "curious_coder/linkedin-jobs-scraper"
LINKEDIN_SEARCH_BASE_URL = (
    "https://www.linkedin.com/jobs/search-results/"
    "?distance=25.0&f_TPR={time_filter}&geoId=90000084"
    "&keywords=AI%20transformation&origin=JOBS_HOME_KEYWORD_HISTORY"
)

logger = logging.getLogger("pipeline")
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler(
    os.path.join(BASE_DIR, "pipeline.log"), maxBytes=5 * 1024 * 1024, backupCount=3
)
_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(_handler)
logger.addHandler(logging.StreamHandler())
