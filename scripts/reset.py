"""Reset the pipeline: clear scores in SQLite and wipe Google Sheet."""
import os
import sqlite3
import gspread
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

# Reset SQLite
conn = sqlite3.connect(os.path.join(BASE_DIR, "jobs_state.db"))
cursor = conn.cursor()
cursor.execute("UPDATE jobs SET status = 'scraped', evaluation_json = NULL")
conn.commit()
print(f"Reset {cursor.rowcount} jobs back to 'scraped' state.")
conn.close()

# Clear Google Sheet
try:
    gc = gspread.service_account(filename=os.path.join(BASE_DIR, "credentials.json"))
    sh = gc.open_by_key(os.getenv("SPREADSHEET_ID"))
    worksheet = sh.sheet1
    worksheet.clear()

    headers = [
        "Title", "Company", "Salary", "Location", "Office Type", "Total Score", "URL",
        "AI Rating", "AI Summary", "Role Alignment", "Comp Alignment",
        "Prestige Alignment", "Work Arrangement", "Job ID",
    ]
    worksheet.update([headers], "A1")
    print("Cleared Google Sheet and wrote headers at A1.")
except Exception as e:
    print(f"Failed to clear sheet: {e}")
