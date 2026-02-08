"""
Apify API Client for LinkedIn Jobs Scraping

Supports two modes:
1. Actor mode: Run the LinkedIn Jobs Scraper Actor (requires paid subscription)
2. Dataset mode: Fetch from existing dataset (free, uses REST API)
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class JobListing:
    """Structured job listing data."""

    job_id: str
    job_post_link: str
    title: str
    company_name: str
    location: str
    job_type: str = ""  # Full-time, Part-time, Contract, Internship
    seniority_level: str = ""  # Entry level, Mid-Senior, Director, etc.
    posted_at: str = ""
    company_website: str = ""
    salary: str = ""
    description: str = ""
    application_url: str = ""
    required_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "job_post_link": self.job_post_link,
            "title": self.title,
            "company_name": self.company_name,
            "location": self.location,
            "job_type": self.job_type,
            "seniority_level": self.seniority_level,
            "posted_at": self.posted_at,
            "company_website": self.company_website,
            "salary": self.salary,
            "description": self.description,
            "application_url": self.application_url,
            "required_skills": self.required_skills,
        }


class ApifyJobScraper:
    """Client for scraping LinkedIn jobs using Apify.

    Supports two modes:
    - Dataset mode (default): Fetch from existing dataset (no actor run required)
    - Actor mode: Run the actor to scrape new jobs (requires paid subscription)

    Set APIFY_DATASET_ID in .env to use an existing dataset.
    """

    # LinkedIn Jobs Scraper Actor ID
    ACTOR_ID = "bebity/linkedin-jobs-scraper"

    # API base URL
    API_BASE = "https://api.apify.com/v2"

    def __init__(self, api_token: str | None = None, dataset_id: str | None = None):
        """
        Initialize Apify client.

        Args:
            api_token: Apify API token. Defaults to APIFY_API_TOKEN env var.
            dataset_id: Existing dataset ID to fetch from. Defaults to APIFY_DATASET_ID env var.
        """
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN")
        if not self.api_token:
            raise ValueError(
                "Apify API token is required. Set APIFY_API_TOKEN environment variable."
            )

        self.dataset_id = dataset_id or os.getenv("APIFY_DATASET_ID")
        self._client = None  # Lazy load ApifyClient only when needed

    @property
    def client(self):
        """Lazy load ApifyClient for actor mode."""
        if self._client is None:
            from apify_client import ApifyClient

            self._client = ApifyClient(self.api_token)
        return self._client

    def fetch_from_dataset(
        self,
        dataset_id: str | None = None,
        max_jobs: int = 50,
        offset: int = 0,
    ) -> list[JobListing]:
        """
        Fetch job listings from an existing Apify dataset using REST API.

        Args:
            dataset_id: Dataset ID to fetch from. Defaults to self.dataset_id.
            max_jobs: Maximum number of jobs to fetch.
            offset: Number of items to skip (for pagination).

        Returns:
            List of JobListing objects.
        """
        dataset_id = dataset_id or self.dataset_id
        if not dataset_id:
            raise ValueError(
                "No dataset ID provided. Set APIFY_DATASET_ID in .env "
                "or pass dataset_id parameter."
            )

        logger.info(f"Fetching jobs from dataset: {dataset_id}")

        url = f"{self.API_BASE}/datasets/{dataset_id}/items"
        params = {
            "token": self.api_token,
            "limit": max_jobs,
            "offset": offset,
            "format": "json",
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            items = response.json()
            logger.info(f"Fetched {len(items)} job listings from dataset")

            # Parse results into JobListing objects
            jobs = []
            for item in items:
                try:
                    job = self._parse_job_item(item)
                    jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to parse job item: {e}")
                    continue

            return jobs

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch from dataset: {e}")
            raise

    def run_actor_sync(
        self,
        actor_input: dict,
        timeout_secs: int = 300,
    ) -> list[JobListing]:
        """
        Run actor synchronously via REST API and return dataset items.

        Uses /acts/:actorId/run-sync-get-dataset-items endpoint which runs
        the actor and returns the results in a single request.

        Args:
            actor_input: Input configuration for the actor.
            timeout_secs: Maximum time to wait for actor completion.

        Returns:
            List of JobListing objects.
        """
        url = f"{self.API_BASE}/acts/{self.ACTOR_ID.replace('/', '~')}/run-sync-get-dataset-items"
        params = {
            "token": self.api_token,
            "timeout": timeout_secs,
        }
        headers = {
            "Content-Type": "application/json",
        }

        logger.info(f"Running actor synchronously: {self.ACTOR_ID}")
        logger.info(f"Input: {actor_input}")

        try:
            response = requests.post(
                url,
                json=actor_input,
                params=params,
                headers=headers,
                timeout=timeout_secs + 30,  # Extra buffer for network
            )
            response.raise_for_status()

            items = response.json()
            logger.info(f"Actor completed - fetched {len(items)} items")

            # Parse results into JobListing objects
            jobs = []
            for item in items:
                try:
                    job = self._parse_job_item(item)
                    jobs.append(job)
                except Exception as e:
                    logger.warning(f"Failed to parse job item: {e}")
                    continue

            return jobs

        except requests.exceptions.Timeout:
            logger.error("Actor run timed out")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Actor run failed: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text[:500]}")
            raise

    def fetch_jobs(
        self,
        keywords: str,
        location: str = "",
        experience_level: str = "",
        date_posted: str = "week",
        max_jobs: int = 50,
        use_cached_dataset: bool = False,
    ) -> list[JobListing]:
        """
        Fetch job listings - runs actor by default, or uses cached dataset.

        Args:
            keywords: Job search keywords (e.g., "machine learning engineer").
            location: Location filter (e.g., "France", "New York").
            experience_level: Experience level filter ("internship", "entry", "mid", "senior").
            date_posted: Date filter ("day", "week", "month").
            max_jobs: Maximum number of jobs to fetch.
            use_cached_dataset: If True, fetch from cached dataset instead of running actor.

        Returns:
            List of JobListing objects.
        """
        # If cached dataset mode and dataset ID is configured
        if use_cached_dataset and self.dataset_id:
            logger.info(f"Using cached dataset: {self.dataset_id}")
            return self.fetch_from_dataset(max_jobs=max_jobs)

        # Run fresh actor search
        logger.info(
            f"Running fresh search: keywords='{keywords}', location='{location}', max={max_jobs}"
        )

        # Map experience level to LinkedIn format
        experience_map = {
            "internship": "1",
            "entry": "2",
            "associate": "3",
            "mid": "4",
            "senior": "4",
            "director": "5",
            "executive": "6",
        }

        # Map date posted to LinkedIn format
        date_map = {
            "day": "r86400",
            "24h": "r86400",
            "week": "r604800",
            "month": "r2592000",
        }

        # Prepare actor input
        run_input = {
            "searchQueries": [keywords],
            "location": location,
            "maxResults": max_jobs,
            "scrapeJobDetails": True,
            "scrapeCompanyDetails": True,
        }

        # Add experience level filter if specified
        if experience_level and experience_level.lower() in experience_map:
            run_input["experienceLevel"] = [experience_map[experience_level.lower()]]

        # Add date posted filter
        if date_posted and date_posted.lower() in date_map:
            run_input["publishedAt"] = date_map[date_posted.lower()]

        # Use REST API to run actor synchronously
        return self.run_actor_sync(run_input)

    def _parse_job_item(self, item: dict) -> JobListing:
        """
        Parse a raw Apify result into a JobListing object.

        Args:
            item: Raw job data from Apify.

        Returns:
            Parsed JobListing object.
        """
        # Extract job ID from URL or generate one
        job_url = item.get("link", item.get("url", item.get("jobUrl", "")))
        job_id = item.get("id", item.get("jobId", ""))
        if not job_id and job_url:
            # Try to extract ID from URL
            import re

            match = re.search(r"/view/(\d+)", job_url)
            job_id = match.group(1) if match else str(hash(job_url))[:12]

        # Parse posted date
        posted_at = item.get(
            "postedAt", item.get("publishedAt", item.get("postedDate", ""))
        )
        if isinstance(posted_at, datetime):
            posted_at = posted_at.isoformat()

        # Extract skills from description if not provided
        skills = item.get("skills", item.get("requiredSkills", []))
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]

        return JobListing(
            job_id=job_id,
            job_post_link=job_url,
            title=item.get("title", item.get("jobTitle", "Unknown")),
            company_name=item.get("company", item.get("companyName", "Unknown")),
            location=item.get("location", item.get("jobLocation", "")),
            job_type=item.get(
                "employmentType", item.get("jobType", item.get("contractType", ""))
            ),
            seniority_level=item.get("seniorityLevel", item.get("experienceLevel", "")),
            posted_at=posted_at,
            company_website=item.get("companyUrl", item.get("companyWebsite", "")),
            salary=item.get("salary", item.get("salaryRange", "")),
            description=item.get("description", item.get("jobDescription", "")),
            application_url=item.get("applyLink", item.get("applicationUrl", job_url)),
            required_skills=skills if isinstance(skills, list) else [],
        )

    def get_job_details(self, job_url: str) -> JobListing | None:
        """
        Fetch details for a specific job URL.

        Note: This requires running the actor and won't work with free trial expired.

        Args:
            job_url: LinkedIn job posting URL.

        Returns:
            JobListing object or None if fetch fails.
        """
        logger.info(f"Fetching job details for: {job_url}")

        run_input = {
            "startUrls": [{"url": job_url}],
            "scrapeJobDetails": True,
            "scrapeCompanyDetails": True,
        }

        try:
            run = self.client.actor(self.ACTOR_ID).call(run_input=run_input)
            dataset_items = list(
                self.client.dataset(run["defaultDatasetId"]).iterate_items()
            )

            if dataset_items:
                return self._parse_job_item(dataset_items[0])
            return None

        except Exception as e:
            logger.error(f"Failed to fetch job details: {e}")
            return None
