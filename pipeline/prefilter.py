import re
import json
from . import logger, COMP_FLOOR

INTERN_PATTERN = re.compile(r"\bintern\b", re.IGNORECASE)


def get_max_annual_salary(job_data):
    """Extract the highest annual salary from structured Apify data.
    Returns the max salary as a float, or None if salary data is unavailable."""

    # Priority 1: salaryInsights (most reliable structured data)
    insights = job_data.get("salaryInsights", {})
    breakdown = insights.get("compensationBreakdown", [])
    if breakdown:
        max_vals = []
        for comp in breakdown:
            try:
                max_sal = float(comp.get("maxSalary", 0))
                pay_period = comp.get("payPeriod", "YEARLY").upper()
                if pay_period == "YEARLY" and max_sal < 1000:
                    max_sal *= 2080  # likely hourly mislabeled as yearly
                elif pay_period == "HOURLY":
                    max_sal *= 2080
                elif pay_period == "MONTHLY":
                    max_sal *= 12
                elif pay_period == "WEEKLY":
                    max_sal *= 52
                max_vals.append(max_sal)
            except (ValueError, TypeError):
                continue
        if max_vals and max(max_vals) > 0:
            return max(max_vals)

    # Priority 2: salaryInfo array (e.g. ["$80,000.00", "$120,000.00"])
    salary_info = job_data.get("salaryInfo", [])
    if salary_info:
        parsed = []
        for s in salary_info:
            cleaned = re.sub(r"[^\d.]", "", str(s))
            try:
                val = float(cleaned)
                if val < 1000:
                    val *= 2080
                parsed.append(val)
            except ValueError:
                continue
        if parsed and max(parsed) > 0:
            return max(parsed)

    # Priority 3: salary string (e.g. "$80,000.00/yr - $120,000.00/yr")
    salary_str = job_data.get("salary", "")
    if salary_str:
        amounts = re.findall(r"[\d,]+\.?\d*", salary_str)
        parsed = []
        for a in amounts:
            try:
                val = float(a.replace(",", ""))
                if val < 1000:
                    val *= 2080
                parsed.append(val)
            except ValueError:
                continue
        if parsed and max(parsed) > 0:
            return max(parsed)

    return None


def prefilter_jobs(conn):
    """Filter out jobs that clearly don't qualify before sending to the API.
    Marks disqualified jobs as 'filtered' with a reason."""
    cursor = conn.cursor()
    cursor.execute("SELECT job_id, total_response_json FROM jobs WHERE status = 'scraped'")
    rows = cursor.fetchall()

    if not rows:
        return

    filtered_count = 0
    for job_id, raw_json in rows:
        job_data = json.loads(raw_json) if raw_json else {}
        title = job_data.get("title", "")

        # Filter 1: Intern roles
        if INTERN_PATTERN.search(title):
            cursor.execute(
                "UPDATE jobs SET status = 'filtered', error_message = ? WHERE job_id = ?",
                (f"Pre-filter: intern title '{title}'", job_id),
            )
            logger.info(f"Filtered {job_id}: intern title '{title}'")
            filtered_count += 1
            continue

        # Filter 2: Salary high end below the comp floor (off when COMP_FLOOR is unset)
        max_salary = get_max_annual_salary(job_data)
        if COMP_FLOOR and max_salary is not None and max_salary < COMP_FLOOR:
            cursor.execute(
                "UPDATE jobs SET status = 'filtered', error_message = ? WHERE job_id = ?",
                (f"Pre-filter: max salary ${max_salary:,.0f} below comp floor", job_id),
            )
            logger.info(f"Filtered {job_id}: max salary ${max_salary:,.0f} below comp floor")
            filtered_count += 1
            continue

    if filtered_count:
        logger.info(
            f"Pre-filter complete. {filtered_count} jobs filtered, "
            f"{len(rows) - filtered_count} sent to scoring."
        )
