"""
Apify Scraper Node

Fetches job listings from LinkedIn via Apify API.
"""

import logging
from typing import Any

from graph.state import WorkflowState
from utils.apify_client import ApifyJobScraper

logger = logging.getLogger(__name__)


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
    
    try:
        scraper = ApifyJobScraper()
        jobs = scraper.fetch_jobs(
            keywords=keywords,
            location=location,
            experience_level=experience_level,
            date_posted=date_posted,
            max_jobs=max_jobs,
        )
        
        # Convert JobListing objects to dicts
        job_dicts = [job.to_dict() for job in jobs]
        
        logger.info(f"Fetched {len(job_dicts)} jobs from LinkedIn")
        
        if not job_dicts:
            logger.warning("No jobs found matching search criteria")
            return {
                "all_jobs": [],
                "total_jobs": 0,
                "should_continue": False,
                "workflow_complete": True,
            }
        
        # Log sample job titles
        logger.info("Sample job titles:")
        for job in job_dicts[:5]:
            logger.info(f"  - {job.get('title', 'Unknown')} at {job.get('company_name', 'Unknown')}")
        
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
