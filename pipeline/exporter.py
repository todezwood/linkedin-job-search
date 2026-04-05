import os
import json
from datetime import datetime, timezone
import gspread
from . import BASE_DIR, logger, SPREADSHEET_ID, SCORE_THRESHOLD


def export_to_sheets(conn, dry_run=False):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT job_id, score, total_response_json, evaluation_json "
        "FROM jobs WHERE status = 'scored' AND score >= ?",
        (SCORE_THRESHOLD,),
    )
    exportable = cursor.fetchall()

    if not exportable:
        logger.info("No new high-scoring jobs to export.")
        return

    if dry_run:
        logger.info(f"[DRY-RUN] Skipped Google Sheets export of {len(exportable)} jobs.")
        return

    logger.info(f"Authenticating with Google Sheets to export {len(exportable)} jobs...")
    try:
        gc = gspread.service_account(
            filename=os.path.join(BASE_DIR, "credentials.json")
        )
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.sheet1

        col_values = worksheet.col_values(14)
        blacklist = set(col_values[-500:]) if col_values else set()

        rows_to_insert = []
        ids_to_mark = []

        for job_id, score, response_json, eval_json in exportable:
            if str(job_id) in blacklist:
                ids_to_mark.append(job_id)
                continue

            job_data = json.loads(response_json) if response_json else {}
            eval_data = json.loads(eval_json) if eval_json else {}

            raw_title = job_data.get("title", "")
            raw_company = job_data.get("companyName", "")
            raw_location = job_data.get("location", "")
            raw_salary = job_data.get("salary", "")
            if not raw_salary:
                salary_info = job_data.get("salaryInfo", [])
                if salary_info:
                    raw_salary = " - ".join(salary_info)
            workplace_types = job_data.get("workplaceTypes", [])
            raw_work_type = workplace_types[0] if workplace_types else ""
            url = job_data.get("link", "")

            rating = eval_data.get("rating", "")
            summary = eval_data.get("summary", "")

            salary = raw_salary if raw_salary else eval_data.get("normalized_salary", "")
            location = raw_location if raw_location else eval_data.get("normalized_location", "")

            ai_work_type = eval_data.get("normalized_work_type", "")
            work_type = raw_work_type
            if not raw_work_type or (
                "remote" not in raw_work_type.lower()
                and "hybrid" not in raw_work_type.lower()
                and ai_work_type != "Unspecified"
            ):
                work_type = ai_work_type

            rows_to_insert.append([
                raw_title, raw_company, salary, location, work_type, score, url,
                rating, summary,
                f"{eval_data.get('role_alignment_score', 0)} - {eval_data.get('role_alignment_reason', '')}",
                f"{eval_data.get('compensation_score', 0)} - {eval_data.get('compensation_reason', '')}",
                f"{eval_data.get('prestige_score', 0)} - {eval_data.get('prestige_reason', '')}",
                f"{eval_data.get('work_arrangement_score', 0)} - {eval_data.get('work_arrangement_reason', '')}",
                str(job_id),
            ])
            ids_to_mark.append(job_id)

        if rows_to_insert:
            worksheet.append_rows(rows_to_insert)
            logger.info(f"Successfully appended {len(rows_to_insert)} rows to Google Sheets.")

        now = datetime.now(timezone.utc).isoformat()
        for jid in ids_to_mark:
            cursor.execute(
                "UPDATE jobs SET status = 'exported', exported_at = ? WHERE job_id = ?",
                (now, jid),
            )

    except Exception as e:
        logger.error(f"Failed to export to Google Sheets: {e}")
