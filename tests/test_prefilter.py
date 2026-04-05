"""Unit tests for the pre-filter module (salary parsing and title filtering)."""
import json
import sqlite3
import unittest
from unittest import mock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.prefilter import get_max_annual_salary, prefilter_jobs, INTERN_PATTERN


class TestInternPattern(unittest.TestCase):
    def test_matches_intern(self):
        self.assertTrue(INTERN_PATTERN.search("Software Engineering Intern"))
        self.assertTrue(INTERN_PATTERN.search("Intern - Data Science"))
        self.assertTrue(INTERN_PATTERN.search("Summer 2026 Intern- Tableau"))

    def test_does_not_match_internal(self):
        self.assertIsNone(INTERN_PATTERN.search("Internal Tools Engineer"))
        self.assertIsNone(INTERN_PATTERN.search("International Sales Manager"))


class TestGetMaxAnnualSalary(unittest.TestCase):
    def test_salary_insights_yearly(self):
        job = {
            "salaryInsights": {
                "compensationBreakdown": [
                    {"maxSalary": "240000.0", "payPeriod": "YEARLY", "minSalary": "180000.0"}
                ]
            }
        }
        self.assertEqual(get_max_annual_salary(job), 240000.0)

    def test_salary_insights_hourly(self):
        job = {
            "salaryInsights": {
                "compensationBreakdown": [
                    {"maxSalary": "100.0", "payPeriod": "HOURLY", "minSalary": "80.0"}
                ]
            }
        }
        self.assertEqual(get_max_annual_salary(job), 100.0 * 2080)

    def test_salary_insights_yearly_but_looks_hourly(self):
        """LinkedIn sometimes labels hourly rates as YEARLY (e.g. 72.0 YEARLY)."""
        job = {
            "salaryInsights": {
                "compensationBreakdown": [
                    {"maxSalary": "72.0", "payPeriod": "YEARLY", "minSalary": "70.0"}
                ]
            }
        }
        self.assertEqual(get_max_annual_salary(job), 72.0 * 2080)

    def test_salary_info_array(self):
        job = {"salaryInfo": ["$80,000.00", "$120,000.00"]}
        self.assertEqual(get_max_annual_salary(job), 120000.0)

    def test_salary_string(self):
        job = {"salary": "$80,000.00/yr - $120,000.00/yr"}
        self.assertEqual(get_max_annual_salary(job), 120000.0)

    def test_zero_salary_returns_none(self):
        """LinkedIn returns $0.00 when salary is unknown — should not count as data."""
        job = {"salaryInfo": ["$0.00", "$0.00"]}
        self.assertIsNone(get_max_annual_salary(job))

    def test_no_salary_data(self):
        job = {"title": "Some Role", "companyName": "Acme"}
        self.assertIsNone(get_max_annual_salary(job))

    def test_empty_salary_string(self):
        job = {"salary": ""}
        self.assertIsNone(get_max_annual_salary(job))


class TestPrefilterJobs(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT DEFAULT 'scraped',
                error_message TEXT,
                total_response_json TEXT
            )
        """)

    def _insert_job(self, job_id, title, salary_info=None):
        job_data = {"title": title}
        if salary_info:
            job_data["salaryInfo"] = salary_info
        self.conn.execute(
            "INSERT INTO jobs (job_id, status, total_response_json) VALUES (?, 'scraped', ?)",
            (job_id, json.dumps(job_data)),
        )

    def test_filters_intern(self):
        self._insert_job("1", "Data Science Intern")
        prefilter_jobs(self.conn)
        status = self.conn.execute("SELECT status FROM jobs WHERE job_id = '1'").fetchone()[0]
        self.assertEqual(status, "filtered")

    @mock.patch("pipeline.prefilter.COMP_FLOOR", 150_000)
    def test_filters_low_salary(self):
        self._insert_job("2", "Program Manager", salary_info=["$80,000.00", "$120,000.00"])
        prefilter_jobs(self.conn)
        status = self.conn.execute("SELECT status FROM jobs WHERE job_id = '2'").fetchone()[0]
        self.assertEqual(status, "filtered")

    @mock.patch("pipeline.prefilter.COMP_FLOOR", 150_000)
    def test_passes_high_salary(self):
        self._insert_job("3", "AI Lead", salary_info=["$180,000.00", "$240,000.00"])
        prefilter_jobs(self.conn)
        status = self.conn.execute("SELECT status FROM jobs WHERE job_id = '3'").fetchone()[0]
        self.assertEqual(status, "scraped")

    @mock.patch("pipeline.prefilter.COMP_FLOOR", 0)
    def test_no_floor_keeps_low_salary(self):
        self._insert_job("5", "Program Manager", salary_info=["$80,000.00", "$120,000.00"])
        prefilter_jobs(self.conn)
        status = self.conn.execute("SELECT status FROM jobs WHERE job_id = '5'").fetchone()[0]
        self.assertEqual(status, "scraped")

    def test_passes_no_salary(self):
        self._insert_job("4", "AI Director")
        prefilter_jobs(self.conn)
        status = self.conn.execute("SELECT status FROM jobs WHERE job_id = '4'").fetchone()[0]
        self.assertEqual(status, "scraped")


if __name__ == "__main__":
    unittest.main()
