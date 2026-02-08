"""
Apify Scraper Node

Fetches job listings from LinkedIn via Apify API.
"""

import csv
import logging
from pathlib import Path
from typing import Any

from graph.state import WorkflowState
from utils.apify_client import ApifyJobScraper

logger = logging.getLogger(__name__)

# Path to applications tracking file
TRACKING_FILE = Path("track/applications.csv")


def _load_existing_job_urls() -> set[str]:
    """
    Load existing job URLs from applications.csv.

    Returns:
        Set of job post links that have already been processed.
    """
    existing_urls: set[str] = set()

    if not TRACKING_FILE.exists():
        logger.info("No existing applications.csv - all jobs are new")
        return existing_urls

    try:
        with open(TRACKING_FILE, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                job_link = row.get("Job Post Link", "")
                if job_link:
                    existing_urls.add(job_link)
        logger.info(f"Loaded {len(existing_urls)} existing job URLs for deduplication")
    except Exception as e:
        logger.warning(f"Failed to load existing applications: {e}")

    return existing_urls


def fetch_jobs_node(state: WorkflowState) -> dict[str, Any]:
    """
    Fetch jobs from Apify LinkedIn scraper.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with fetched jobs.
    """
    logger.info("-" * 40)
    logger.info("FETCHING JOBS FROM LINKEDIN")
    logger.info("-" * 40)

    config = state.get("config", {})
    job_search = config.get("job_search", {})

    keywords = job_search.get("keywords", "")
    location = job_search.get("location", "")
    experience_level = job_search.get("experience_level", "")
    date_posted = job_search.get("date_posted", "week")
    max_jobs = job_search.get("max_jobs_per_run", 50)

    if not keywords:
        error_msg = "No job search keywords configured"
        logger.error(error_msg)
        return {
            "errors": [error_msg],
            "should_continue": False,
            "workflow_complete": True,
        }

    existing_urls = _load_existing_job_urls()

    use_cached_dataset = job_search.get("use_cached_dataset", False)
    if use_cached_dataset:
        logger.info(
            "Mode: Using cached dataset (set use_cached_dataset: false to run fresh search)"
        )
    else:
        logger.info(
            "Mode: Running fresh actor search (requires paid Apify subscription)"
        )

    try:
        scraper = ApifyJobScraper()
        jobs = scraper.fetch_jobs(
            keywords=keywords,
            location=location,
            experience_level=experience_level,
            date_posted=date_posted,
            max_jobs=max_jobs,
            use_cached_dataset=use_cached_dataset,
        )

        job_dicts = [job.to_dict() for job in jobs]

        original_count = len(job_dicts)
        job_dicts = [
            job
            for job in job_dicts
            if job.get("job_post_link", "") not in existing_urls
        ]
        skipped_count = original_count - len(job_dicts)

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} already-processed jobs")

        logger.info(f"Found {len(job_dicts)} new jobs to process")

        if not job_dicts:
            logger.warning("No new jobs found matching search criteria")
            return {
                "all_jobs": [],
                "total_jobs": 0,
                "should_continue": False,
                "workflow_complete": True,
            }

        logger.info("Sample job titles:")
        for job in job_dicts[:5]:
            logger.info(
                f"  - {job.get('title', 'Unknown')} at {job.get('company_name', 'Unknown')}"
            )

        return {
            "all_jobs": job_dicts,
            "total_jobs": len(job_dicts),
            "current_job_index": 0,
            "should_continue": True,
        }

    except Exception as e:
        error_msg = f"Failed to fetch jobs from Apify: {e}"
        logger.error(error_msg)
        return {
            "errors": [error_msg],
            "should_continue": False,
            "workflow_complete": True,
        }


def get_next_job_node(state: WorkflowState) -> dict[str, Any]:
    """
    Get the next job to process from the list.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with current job set.
    """
    all_jobs = state.get("all_jobs", [])
    current_index = state.get("current_job_index", 0)

    if current_index >= len(all_jobs):
        logger.info("All jobs have been processed")
        return {
            "current_job": None,
            "should_continue": False,
            "workflow_complete": True,
        }

    current_job = all_jobs[current_index]

    logger.info(f"\nProcessing job {current_index + 1}/{len(all_jobs)}:")
    logger.info(f"  Title: {current_job.get('title', 'Unknown')}")
    logger.info(f"  Company: {current_job.get('company_name', 'Unknown')}")
    logger.info(f"  Location: {current_job.get('location', 'Unknown')}")

    return {
        "current_job": current_job,
        "current_job_index": current_index + 1,  # Increment for next iteration
        "should_continue": True,
    }
