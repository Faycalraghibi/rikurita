"""
Google Sheets API Client

Wrapper for Google Sheets API to log and track job applications.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

logger = logging.getLogger(__name__)


# Required Google API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column headers for the job tracking sheet
COLUMN_HEADERS = [
    "Timestamp",
    "Job Post Link",
    "Job Title",
    "Job Type",
    "Seniority Level",
    "Posted At",
    "Company Name",
    "Company Website",
    "Salary",
    "Description",
    "Resume Path",
    "Application URL",
    "Relevance Score",
    "Application Status",
    "Notes",
]


class GoogleSheetsClient:
    """Client for logging job applications to Google Sheets."""

    def __init__(
        self,
        credentials_path: str | None = None,
        sheet_id: str | None = None,
    ):
        """
        Initialize Google Sheets client.

        Args:
            credentials_path: Path to Google service account credentials JSON.
                            Defaults to GOOGLE_SHEETS_CREDENTIALS_PATH env var.
            sheet_id: Google Sheet ID to write to.
                     Defaults to GOOGLE_SHEET_ID env var.
        """
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_SHEETS_CREDENTIALS_PATH"
        )
        self.sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID")

        self._client: gspread.Client | None = None
        self._sheet: gspread.Spreadsheet | None = None
        self._worksheet: gspread.Worksheet | None = None

    def _ensure_connected(self) -> None:
        """Ensure connection to Google Sheets is established."""
        if self._client is None:
            if not self.credentials_path:
                raise ValueError(
                    "Google Sheets credentials path is required. "
                    "Set GOOGLE_SHEETS_CREDENTIALS_PATH environment variable."
                )

            if not Path(self.credentials_path).exists():
                raise FileNotFoundError(
                    f"Credentials file not found: {self.credentials_path}"
                )

            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=SCOPES,
            )
            self._client = gspread.authorize(credentials)
            logger.info("Connected to Google Sheets API")

        if self._sheet is None:
            if not self.sheet_id:
                raise ValueError(
                    "Google Sheet ID is required. Set GOOGLE_SHEET_ID environment variable."
                )

            self._sheet = self._client.open_by_key(self.sheet_id)
            logger.info(f"Opened spreadsheet: {self._sheet.title}")

        if self._worksheet is None:
            # Get or create the first worksheet
            self._worksheet = self._sheet.sheet1

            # Ensure headers are set
            self._ensure_headers()

    def _ensure_headers(self) -> None:
        """Ensure column headers are set in the worksheet."""
        try:
            existing_headers = self._worksheet.row_values(1)
            if not existing_headers or existing_headers != COLUMN_HEADERS:
                self._worksheet.update("A1", [COLUMN_HEADERS])
                logger.info("Set column headers in worksheet")
        except Exception as e:
            logger.warning(f"Failed to check/set headers: {e}")
            # Try to set headers anyway
            import contextlib

            with contextlib.suppress(Exception):
                self._worksheet.update("A1", [COLUMN_HEADERS])

    def log_application(
        self,
        job_post_link: str,
        job_title: str,
        job_type: str,
        seniority_level: str,
        posted_at: str,
        company_name: str,
        company_website: str,
        salary: str,
        description: str,
        resume_path: str,
        application_url: str,
        relevance_score: float,
        status: str = "Pending",
        notes: str = "",
    ) -> bool:
        """
        Log a job application to Google Sheets.

        Args:
            job_post_link: LinkedIn job posting URL.
            job_title: Title of the job.
            job_type: Type (Full-time, Part-time, etc.).
            seniority_level: Seniority level of the role.
            posted_at: When the job was posted.
            company_name: Name of the company.
            company_website: Company website URL.
            salary: Salary information.
            description: Job description (may be truncated).
            resume_path: Local path to generated resume.
            application_url: URL to apply for the job.
            relevance_score: LLM-calculated relevance score (0-10).
            status: Application status (Applied/Pending/Skipped).
            notes: Additional notes or match reasoning.

        Returns:
            True if logged successfully, False otherwise.
        """
        try:
            self._ensure_connected()

            # Prepare row data
            timestamp = datetime.now().isoformat()

            # Truncate description if too long (Sheets has cell limits)
            max_desc_length = 5000
            if len(description) > max_desc_length:
                description = description[:max_desc_length] + "..."

            row_data = [
                timestamp,
                job_post_link,
                job_title,
                job_type,
                seniority_level,
                posted_at,
                company_name,
                company_website,
                salary,
                description,
                resume_path,
                application_url,
                str(relevance_score),
                status,
                notes,
            ]

            # Append row to worksheet
            self._worksheet.append_row(row_data, value_input_option="RAW")

            logger.info(f"Logged application: {company_name} - {job_title}")
            return True

        except Exception as e:
            logger.error(f"Failed to log application to Google Sheets: {e}")
            return False

    def batch_log_applications(self, applications: list[dict]) -> int:
        """
        Log multiple applications in batch.

        Args:
            applications: List of application dictionaries with keys matching
                         log_application parameters.

        Returns:
            Number of successfully logged applications.
        """
        try:
            self._ensure_connected()

            rows = []
            timestamp = datetime.now().isoformat()

            for app in applications:
                description = app.get("description", "")
                if len(description) > 5000:
                    description = description[:5000] + "..."

                row = [
                    timestamp,
                    app.get("job_post_link", ""),
                    app.get("job_title", ""),
                    app.get("job_type", ""),
                    app.get("seniority_level", ""),
                    app.get("posted_at", ""),
                    app.get("company_name", ""),
                    app.get("company_website", ""),
                    app.get("salary", ""),
                    description,
                    app.get("resume_path", ""),
                    app.get("application_url", ""),
                    str(app.get("relevance_score", 0)),
                    app.get("status", "Pending"),
                    app.get("notes", ""),
                ]
                rows.append(row)

            if rows:
                self._worksheet.append_rows(rows, value_input_option="RAW")
                logger.info(f"Batch logged {len(rows)} applications")
                return len(rows)

            return 0

        except Exception as e:
            logger.error(f"Failed to batch log applications: {e}")
            return 0

    def update_status(
        self,
        job_post_link: str,
        new_status: str,
        notes: str | None = None,
    ) -> bool:
        """
        Update the status of an existing application.

        Args:
            job_post_link: Job posting URL to find the row.
            new_status: New status to set.
            notes: Optional notes to append.

        Returns:
            True if updated successfully, False otherwise.
        """
        try:
            self._ensure_connected()

            # Find the row with matching job link
            cell = self._worksheet.find(job_post_link)
            if cell is None:
                logger.warning(f"Job not found in sheet: {job_post_link}")
                return False

            row_num = cell.row

            # Update status (column N = 14)
            self._worksheet.update_cell(row_num, 14, new_status)

            # Update notes if provided (column O = 15)
            if notes:
                existing_notes = self._worksheet.cell(row_num, 15).value or ""
                new_notes = (
                    f"{existing_notes}\n[{datetime.now().strftime('%Y-%m-%d')}] {notes}"
                )
                self._worksheet.update_cell(row_num, 15, new_notes.strip())

            logger.info(f"Updated status for row {row_num}: {new_status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update status: {e}")
            return False

    def check_if_applied(self, job_post_link: str) -> bool:
        """
        Check if a job has already been logged.

        Args:
            job_post_link: Job posting URL to check.

        Returns:
            True if already exists in sheet, False otherwise.
        """
        try:
            self._ensure_connected()
            cell = self._worksheet.find(job_post_link)
            return cell is not None
        except Exception as e:
            logger.error(f"Failed to check if applied: {e}")
            return False

    def get_all_applications(self) -> list[dict]:
        """
        Get all logged applications.

        Returns:
            List of application dictionaries.
        """
        try:
            self._ensure_connected()
            records = self._worksheet.get_all_records()
            return records
        except Exception as e:
            logger.error(f"Failed to get applications: {e}")
            return []
