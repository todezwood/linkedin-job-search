import json
from datetime import datetime, timezone
from apify_client import ApifyClient
from . import logger, APIFY_API_TOKEN, APIFY_ACTOR_ID, LINKEDIN_SEARCH_BASE_URL


def extract_jobs(conn, dry_run=False):
    if dry_run:
        logger.info("[DRY-RUN] Skipping Apify extraction.")
        return

    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM pipeline_metadata WHERE key = 'last_successful_run'"
    )
    row = cursor.fetchone()

    now = datetime.now(timezone.utc)
    use_past_week = False

    if row:
        last_run = datetime.fromisoformat(row[0])
        hours_since_last = (now - last_run).total_seconds() / 3600
        if hours_since_last > 28:
            logger.warning(
                f"Last pipeline run was {hours_since_last:.1f} hours ago. "
                "Falling back to 1-Week Apify fetch to prevent data loss."
            )
            use_past_week = True
        else:
            logger.info("Last pipeline run was recent. Using 24-Hour Apify fetch.")
    else:
        logger.info("No previous run detected. Running 1-Week Apify fetch to seed database.")
        use_past_week = True

    # r86400 = Past 24 hours, r604800 = Past week
    time_filter = "r604800" if use_past_week else "r86400"
    time_filter_label = "Past Week" if use_past_week else "Past 24 Hours"

    client = ApifyClient(APIFY_API_TOKEN)
    search_url = LINKEDIN_SEARCH_BASE_URL.format(time_filter=time_filter)

    run_input = {
        "count": 50,  # minimum 10 for this actor
        "scrapeCompany": True,
        "splitByLocation": False,
        "splitCountry": "US",
        "urls": [search_url],
    }

    logger.info(f"Starting Apify Actor {APIFY_ACTOR_ID} with filter {time_filter_label}...")
    run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input, timeout_secs=600)

    if run and run.get("defaultDatasetId"):
        dataset_items = client.dataset(run["defaultDatasetId"]).iterate_items()

        jobs_inserted = 0
        jobs_ignored = 0

        for job in dataset_items:
            job_id = str(job.get("id", job.get("jobId", "")))
            if not job_id:
                continue

            try:
                cursor.execute(
                    "INSERT INTO jobs (job_id, status, total_response_json) VALUES (?, ?, ?)",
                    (job_id, "scraped", json.dumps(job)),
                )
                jobs_inserted += 1
            except Exception:
                jobs_ignored += 1

        logger.info(
            f"Apify scrape complete. New: {jobs_inserted}. Duplicates ignored: {jobs_ignored}."
        )
    else:
        logger.error("Apify run failed or returned no dataset.")
