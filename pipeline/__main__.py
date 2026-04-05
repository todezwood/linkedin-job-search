import os
import signal
import fcntl
import sqlite3
import argparse
from datetime import datetime, timezone
from anthropic import Anthropic

from . import BASE_DIR, logger, ANTHROPIC_API_KEY
from .scraper import extract_jobs
from .prefilter import prefilter_jobs
from .scorer import score_jobs
from .exporter import export_to_sheets

shutdown_requested = False


def handle_signal(signum, frame):
    global shutdown_requested
    logger.info("Graceful shutdown requested. Will exit after current API call completes...")
    shutdown_requested = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def init_db():
    db_path = os.path.join(BASE_DIR, "jobs_state.db")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'scraped',
            retry_count INTEGER DEFAULT 0,
            score INTEGER,
            model_version TEXT,
            error_message TEXT,
            total_response_json TEXT,
            evaluation_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scored_at TIMESTAMP,
            exported_at TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn


def run_backup():
    logger.info("Performing database backup...")
    try:
        src = sqlite3.connect(os.path.join(BASE_DIR, "jobs_state.db"))
        dst = sqlite3.connect(os.path.join(BASE_DIR, "jobs_state.db.bak"))
        src.backup(dst)
        dst.close()
        src.close()
    except Exception as e:
        logger.error(f"Failed to backup database: {e}")


def main():
    parser = argparse.ArgumentParser(description="AI Job Search Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Run without calling APIs")
    args = parser.parse_args()

    lock_file_path = os.path.join(BASE_DIR, "pipeline.lock")
    try:
        lock_file = open(lock_file_path, "w")
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error("Pipeline already running. Exiting.")
        return

    logger.info("Starting AI Job Search Pipeline...")
    conn = init_db()
    anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if not args.dry_run else None

    # Step 1: Scrape
    try:
        extract_jobs(conn, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Apify extraction failed: {e}. Proceeding to score existing queue.")

    # Step 2: Pre-filter
    prefilter_jobs(conn)

    # Step 3: Score
    score_jobs(conn, anthropic_client, dry_run=args.dry_run,
               should_stop=lambda: shutdown_requested)

    # Step 4: Export
    export_to_sheets(conn, dry_run=args.dry_run)

    # Mark successful run
    if not args.dry_run:
        now_str = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_metadata (key, value, updated_at) "
            "VALUES ('last_successful_run', ?, ?)",
            (now_str, now_str),
        )

    run_backup()
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    logger.info("Pipeline completed successfully.")


if __name__ == "__main__":
    main()
