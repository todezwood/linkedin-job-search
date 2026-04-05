import os
import json
import time
from datetime import datetime, timezone
from . import BASE_DIR, logger, COMP_FLOOR, COMP_TARGET, COMP_TOP


def _usd_k(amount):
    return f"${amount // 1000}k"


def load_system_prompt():
    if not (COMP_FLOOR and COMP_TARGET and COMP_TOP):
        raise RuntimeError("Set COMP_FLOOR, COMP_TARGET and COMP_TOP in .env to score compensation.")
    with open(os.path.join(BASE_DIR, "config", "system_prompt.txt"), "r", encoding="utf-8") as f:
        sys_txt = f.read()
    sys_txt = (
        sys_txt.replace("{{COMP_FLOOR}}", _usd_k(COMP_FLOOR))
        .replace("{{COMP_TARGET}}", _usd_k(COMP_TARGET))
        .replace("{{COMP_TOP}}", _usd_k(COMP_TOP))
    )
    with open(os.path.join(BASE_DIR, "config", "candidate_profile.md"), "r", encoding="utf-8") as f:
        profile_md = f.read()
    return f"{sys_txt}\n\n=== FULL CANDIDATE PROFILE (REFERENCE ONLY) ===\n{profile_md}"


def load_user_prompt(job):
    with open(os.path.join(BASE_DIR, "config", "user_prompt.txt"), "r", encoding="utf-8") as f:
        template = f.read()

    salary = job.get("salary", "")
    if not salary:
        salary_info = job.get("salaryInfo", [])
        if salary_info:
            salary = " - ".join(salary_info)
    if not salary:
        salary = "Not listed"

    workplace_types = job.get("workplaceTypes", [])
    work_type = workplace_types[0] if workplace_types else "Unknown"

    return (
        template
        .replace("{{ $json.title }}", job.get("title", "Unknown"))
        .replace("{{ $json.companyName }}", job.get("companyName", "Unknown"))
        .replace("{{ $json.location }}", job.get("location", "Unknown"))
        .replace("{{ $json.contractType }}", job.get("employmentType", "Unknown"))
        .replace("{{ $json.experienceLevel }}", job.get("seniorityLevel", "Unknown"))
        .replace("{{ $json.salary }}", salary)
        .replace("{{ $json.description }}", job.get("descriptionText", "Unknown"))
    )


def score_jobs(conn, anthropic_client, model="claude-haiku-4-5-20251001",
               dry_run=False, should_stop=lambda: False):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT job_id, total_response_json FROM jobs "
        "WHERE status = 'scraped' OR (status = 'error' AND retry_count < 3)"
    )
    rows = cursor.fetchall()

    if not rows:
        return

    system_text_content = load_system_prompt()
    system_message = [
        {"type": "text", "text": system_text_content, "cache_control": {"type": "ephemeral"}}
    ]

    for job_id, raw_json in rows:
        if should_stop():
            break

        job_data = json.loads(raw_json) if raw_json else {}
        user_prompt_text = load_user_prompt(job_data)

        if dry_run:
            logger.info(f"[DRY-RUN] Skipped API evaluation for {job_id}")
            continue

        for attempt in range(3):
            if should_stop():
                break
            try:
                response = anthropic_client.messages.create(
                    model=model,
                    max_tokens=600,
                    system=system_message,
                    messages=[{"role": "user", "content": user_prompt_text}],
                )

                response_content = response.content[0].text
                if "```json" in response_content:
                    response_content = response_content.split("```json")[1].split("```")[0].strip()
                elif "```" in response_content:
                    response_content = response_content.split("```")[1].split("```")[0].strip()

                score_data = json.loads(response_content)

                # Never trust the AI's arithmetic — always recalculate the total ourselves
                total_score = (
                    int(score_data.get("compensation_score", 0)) +
                    int(score_data.get("role_alignment_score", 0)) +
                    int(score_data.get("prestige_score", 0)) +
                    int(score_data.get("location_score", 0)) +
                    int(score_data.get("work_arrangement_score", 0))
                )
                score_data["total_score"] = total_score  # overwrite AI's value with correct sum

                logger.info(f"Successfully scored {job_id}: {total_score}")

                now = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    "UPDATE jobs SET status = 'scored', score = ?, model_version = ?, "
                    "evaluation_json = ?, scored_at = ?, error_message = NULL WHERE job_id = ?",
                    (total_score, model, json.dumps(score_data), now, job_id),
                )
                break
            except Exception as e:
                logger.warning(f"Error on {job_id} (Attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep([1, 4, 16][attempt])
                else:
                    cursor.execute(
                        "UPDATE jobs SET status = 'error', retry_count = retry_count + 1, "
                        "error_message = ? WHERE job_id = ?",
                        (str(e), job_id),
                    )
