"""
Application Logger Node

Logs job applications to local CSV file for tracking.
Optionally logs to Google Sheets if configured.
"""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from graph.state import ApplicationStatus, WorkflowState

logger = logging.getLogger(__name__)

# Local tracking file
TRACKING_FILE = Path("track/applications.csv")

# CSV column headers (same as Google Sheets)
CSV_HEADERS = [
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


def _ensure_csv_exists() -> None:
    """Create CSV file with headers if it doesn't exist."""
    if not TRACKING_FILE.exists():
        with open(TRACKING_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        logger.info(f"Created tracking file: {TRACKING_FILE}")


def _log_to_csv(row_data: list) -> bool:
    """
    Append a row to the local CSV tracking file.

    Args:
        row_data: List of values matching CSV_HEADERS order.

    Returns:
        True if successful, False otherwise.
    """
    try:
        _ensure_csv_exists()
        with open(TRACKING_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row_data)
        return True
    except Exception as e:
        logger.error(f"Failed to write to CSV: {e}")
        return False


def _check_if_logged_locally(job_post_link: str) -> bool:
    """
    Check if a job has already been logged in the local CSV.

    Args:
        job_post_link: Job posting URL to check.

    Returns:
        True if already exists, False otherwise.
    """
    if not TRACKING_FILE.exists():
        return False

    try:
        with open(TRACKING_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Job Post Link") == job_post_link:
                    return True
        return False
    except Exception as e:
        logger.error(f"Failed to check CSV: {e}")
        return False


def _try_log_to_sheets(
    job_data: dict,
    relevance_result: dict,
    resume_pdf_path: str,
    status: str,
    notes: str,
) -> bool:
    """
    Try to log to Google Sheets if configured.

    Returns True if logged successfully, False otherwise (including if not configured).
    """
    # Check if Google Sheets is configured
    if not os.getenv("GOOGLE_SHEET_ID") or not os.getenv(
        "GOOGLE_SHEETS_CREDENTIALS_PATH"
    ):
        return False

    try:
        from utils.sheets_client import GoogleSheetsClient

        sheets_client = GoogleSheetsClient()

        success = sheets_client.log_application(
            job_post_link=job_data.get("job_post_link", ""),
            job_title=job_data.get("title", ""),
            job_type=job_data.get("job_type", ""),
            seniority_level=job_data.get("seniority_level", ""),
            posted_at=job_data.get("posted_at", ""),
            company_name=job_data.get("company_name", ""),
            company_website=job_data.get("company_website", ""),
            salary=job_data.get("salary", ""),
            description=job_data.get("description", ""),
            resume_path=resume_pdf_path,
            application_url=job_data.get("application_url", ""),
            relevance_score=relevance_result.get(
                "relevance_score", relevance_result.get("score", 0)
            ),
            status=status,
            notes=notes[:500],
        )

        if success:
            logger.info("Also logged to Google Sheets")
        return success

    except Exception as e:
        logger.debug(f"Google Sheets logging skipped: {e}")
        return False


def log_to_sheets_node(state: WorkflowState) -> dict[str, Any]:
    """
    Log the current job application to local CSV (and optionally Google Sheets).

    Args:
        state: Current workflow state.

    Returns:
        Updated state with logged status.
    """
    current_job = state.get("current_job")
    relevance_result = state.get("relevance_result", {})
    resume_pdf_path = state.get("resume_pdf_path", "")
    dry_run = state.get("dry_run", False)

    if not current_job:
        logger.warning("No current job to log")
        return {}

    company_name = current_job.get("company_name", "Unknown")
    job_title = current_job.get("title", "Unknown")

    is_relevant = state.get("is_relevant", False)
    if not is_relevant:
        status = ApplicationStatus.SKIPPED.value
    elif resume_pdf_path:
        status = ApplicationStatus.APPLIED.value
    elif dry_run:
        status = ApplicationStatus.PENDING.value
    else:
        status = ApplicationStatus.FAILED.value

    # Prepare notes from relevance reasoning
    notes = relevance_result.get("reasoning", "")
    matching_points = relevance_result.get("matching_points", [])
    if matching_points:
        notes = f"Match: {', '.join(matching_points[:3])}. {notes}"

    job_link = current_job.get("job_post_link", "")

    if job_link and _check_if_logged_locally(job_link):
        logger.info(f"Job already logged, skipping: {job_link}")
        return {
            "jobs_processed": state.get("jobs_processed", 0) + 1,
        }

    logger.info(f"Logging application: {company_name} - {job_title} ({status})")

    timestamp = datetime.now().isoformat()
    description = current_job.get("description", "")
    if len(description) > 500:
        description = description[:500] + "..."

    row_data = [
        timestamp,
        job_link,
        job_title,
        current_job.get("job_type", ""),
        current_job.get("seniority_level", ""),
        current_job.get("posted_at", ""),
        company_name,
        current_job.get("company_website", ""),
        current_job.get("salary", ""),
        description,
        resume_pdf_path,
        current_job.get("application_url", ""),
        str(relevance_result.get("relevance_score", relevance_result.get("score", 0))),
        status,
        notes[:200],
    ]

    csv_success = _log_to_csv(row_data)

    if csv_success:
        logger.info(f"Logged to {TRACKING_FILE}")
    else:
        logger.warning("Failed to log to local CSV")

    _try_log_to_sheets(current_job, relevance_result, resume_pdf_path, status, notes)

    processed_job = {
        **current_job,
        "relevance_score": relevance_result.get(
            "relevance_score", relevance_result.get("score", 0)
        ),
        "resume_path": resume_pdf_path,
        "status": status,
    }

    return {
        "processed_jobs": [processed_job],
        "jobs_processed": state.get("jobs_processed", 0) + 1,
    }


def log_skipped_job_node(state: WorkflowState) -> dict[str, Any]:
    """
    Log a skipped (non-relevant) job to the processed list.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with processed job.
    """
    current_job = state.get("current_job")
    relevance_result = state.get("relevance_result", {})

    if not current_job:
        return {}

    company_name = current_job.get("company_name", "Unknown")
    job_title = current_job.get("title", "Unknown")
    job_link = current_job.get("job_post_link", "")

    # Also log skipped jobs to CSV for tracking
    timestamp = datetime.now().isoformat()
    score = relevance_result.get("relevance_score", relevance_result.get("score", 0))
    notes = f"Skipped: {relevance_result.get('reasoning', 'Below threshold')[:150]}"

    row_data = [
        timestamp,
        job_link,
        job_title,
        current_job.get("job_type", ""),
        current_job.get("seniority_level", ""),
        current_job.get("posted_at", ""),
        company_name,
        current_job.get("company_website", ""),
        current_job.get("salary", ""),
        "",  # No description for skipped
        "",  # No resume path
        current_job.get("application_url", ""),
        str(score),
        ApplicationStatus.SKIPPED.value,
        notes,
    ]

    _log_to_csv(row_data)

    processed_job = {
        **current_job,
        "relevance_score": score,
        "resume_path": "",
        "status": ApplicationStatus.SKIPPED.value,
    }

    return {
        "processed_jobs": [processed_job],
        "jobs_processed": state.get("jobs_processed", 0) + 1,
    }
