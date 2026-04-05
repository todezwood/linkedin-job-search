# LinkedIn AI Job Search Pipeline

An automated pipeline that scrapes LinkedIn for AI-focused job postings, scores them against a custom rubric using Claude, and exports high-quality matches to Google Sheets daily.

## How It Works

```
LinkedIn (Apify Scraper)
        ↓
   SQLite (dedup)
        ↓
  Pre-Filter (no API cost)
  • Skip intern roles
  • Skip salary below your floor
        ↓
  Claude Haiku (scoring)
  • Compensation
  • Role Alignment
  • Company Prestige
  • Location
  • Work Arrangement
        ↓
  Google Sheets (score ≥ 40)
```

Each job is scored out of **102 points** across five categories. Only jobs that meet the minimum score threshold are exported to the sheet. The pipeline runs automatically every day at 10 AM via macOS launchd.

## Scoring Rubric

| Category | Max Points |
|---|---|
| Compensation (total comp) | 30 |
| Role Alignment / AI Focus | 25 |
| Company Prestige | 30 |
| Location | 15 |
| Work Arrangement (bonus) | 2 |
| **Total** | **102** |

Full rubric: [`config/scoring_framework.md`](config/scoring_framework.md)

## Project Structure

```
├── pipeline/
│   ├── __init__.py       # Config, logger, shared constants
│   ├── __main__.py       # Orchestrator — run with: python -m pipeline
│   ├── scraper.py        # Apify LinkedIn scraper integration
│   ├── prefilter.py      # Pre-API filtering (intern titles, salary floor)
│   ├── scorer.py         # Claude Haiku evaluation
│   └── exporter.py       # Google Sheets export
├── config/
│   ├── candidate_profile.md   # Target role definition
│   ├── scoring_framework.md   # Scoring rubric reference
│   ├── system_prompt.txt      # AI system prompt
│   └── user_prompt.txt        # AI user prompt template
├── scripts/
│   ├── run.sh            # launchd daily schedule wrapper
│   └── reset.py          # Reset DB and sheet for a fresh run
└── tests/
    └── test_prefilter.py # Unit tests for salary parsing and filtering
```

## Setup

**1. Clone and install dependencies**
```bash
git clone <repo-url>
cd linkedin-job-search
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Configure environment variables**
```bash
cp .env.example .env
# Fill in your keys and your comp band in .env
```

**3. Add Google Sheets credentials**

Place your Google service account JSON file at the project root as `credentials.json`.
[How to create a service account →](https://docs.gspread.org/en/latest/oauth2.html#service-account)

**4. Run**
```bash
python -m pipeline           # Live run
python -m pipeline --dry-run # Test without API calls
```

**5. Run tests**
```bash
python -m unittest tests.test_prefilter -v
```

## Required API Keys

| Key | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| `APIFY_API_TOKEN` | [apify.com](https://console.apify.com/account/integrations) |
| `SPREADSHEET_ID` | The ID from your Google Sheet URL |

## Design Decisions

**Pre-filtering saves API costs** — Intern roles and jobs with salary clearly below `COMP_FLOOR` are filtered out before hitting the Anthropic API. Since many jobs don't list salary, unknown salary passes through (FAANG rarely posts comp publicly).

**Python calculates the total score** — The AI scores each category independently. The total is always summed in Python, never trusted from the model output, eliminating arithmetic errors.

**SQLite as the dedup layer** — Job IDs are the primary key. Duplicate prevention is handled by a database constraint (`IntegrityError`) rather than application logic — atomic and race-condition-proof.

**24h vs 7-day scrape window** — If the pipeline ran recently it fetches the past 24 hours (cheap). If more than 28 hours have passed since the last successful run, it falls back to a 7-day window to avoid gaps.
