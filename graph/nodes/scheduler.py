"""
Scheduler Node

Entry point node that loads configuration and prepares the workflow.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from graph.state import WorkflowState

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file.

    Returns:
        Configuration dictionary.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded configuration from {config_path}")
    return config


def load_resume_data(resume_data_path: str = "templates/resume_data.yaml") -> dict:
    """
    Load resume data from YAML file.

    Args:
        resume_data_path: Path to resume data file.

    Returns:
        Resume data dictionary.
    """
    path = Path(resume_data_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume data file not found: {resume_data_path}")

    with open(path, encoding="utf-8") as f:
        resume_data = yaml.safe_load(f)

    logger.info(f"Loaded resume data from {resume_data_path}")
    return resume_data


def scheduler_node(state: WorkflowState) -> dict[str, Any]:
    """
    Scheduler node - entry point for the workflow.

    Loads configuration if not already loaded and validates settings.

    Args:
        state: Current workflow state.

    Returns:
        Updated state values.
    """
    logger.info("=" * 60)
    logger.info("RIKURITA JOB APPLICATION WORKFLOW")
    logger.info("=" * 60)

    config = state.get("config", {})
    resume_data = state.get("resume_data", {})

    if not config:
        config = load_config()

    if not resume_data:
        resume_data = load_resume_data()

    job_search = config.get("job_search", {})
    keywords = job_search.get("keywords", "")
    location = job_search.get("location", "")
    max_jobs = job_search.get("max_jobs_per_run", 50)
    relevance_threshold = job_search.get("relevance_threshold", 7)

    logger.info("Job Search Settings:")
    logger.info(f"  Keywords: {keywords}")
    logger.info(f"  Location: {location}")
    logger.info(f"  Max Jobs: {max_jobs}")
    logger.info(f"  Relevance Threshold: {relevance_threshold}")
    logger.info(f"  Dry Run: {state.get('dry_run', False)}")

    if not keywords:
        error_msg = "No job search keywords configured in config.yaml"
        logger.error(error_msg)
        return {
            "config": config,
            "resume_data": resume_data,
            "errors": [error_msg],
            "should_continue": False,
            "workflow_complete": True,
        }

    user_profile = config.get("user_profile", {})
    if not user_profile:
        logger.warning(
            "No user profile configured - relevance checking may be less accurate"
        )

    return {
        "config": config,
        "resume_data": resume_data,
        "relevance_threshold": relevance_threshold,
        "should_continue": True,
    }
