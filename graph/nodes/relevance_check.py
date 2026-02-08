"""
Relevance Check Node

Uses LLM to evaluate job fit and filter relevant positions.
"""

import logging
from typing import Any

from graph.state import WorkflowState
from utils.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)


def check_relevance_node(state: WorkflowState) -> dict[str, Any]:
    """
    Check job relevance using LLM.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with relevance result.
    """
    current_job = state.get("current_job")
    config = state.get("config", {})
    relevance_threshold = state.get("relevance_threshold", 7)

    if not current_job:
        logger.warning("No current job to check relevance for")
        return {
            "relevance_result": None,
            "is_relevant": False,
        }

    job_title = current_job.get("title", "Unknown")
    company_name = current_job.get("company_name", "Unknown")
    description = current_job.get("description", "")

    logger.info(f"Checking relevance for: {job_title} at {company_name}")

    if not description:
        logger.info("No description - using title-based keyword matching")

        import re

        # Core technical keywords - some need word boundary matching
        # Format: (keyword, needs_word_boundary)
        core_keyword_patterns = [
            ("machine learning", False),
            ("deep learning", False),
            ("data scien", False),  # matches "data science", "data scientist"
            ("data engineer", False),
            ("artificial intelligence", False),
            ("computer vision", False),
            ("analytics", False),
            ("tensorflow", False),
            ("pytorch", False),
            # Short keywords need word boundary to avoid false matches
            (r"\bml\b", True),  # ML as standalone word
            (r"\bai\b", True),  # AI as standalone word, not "ALIAD", "grain"
            (r"\bnlp\b", True),  # NLP as standalone word
            (r"\bresearch\b", True),  # research as standalone word
        ]

        user_profile = config.get("user_profile", {})
        target_criteria = user_profile.get("target_criteria", {})
        desired_roles = [r.lower() for r in target_criteria.get("desired_roles", [])]

        title_lower = job_title.lower()
        matching_core = []

        for pattern, is_regex in core_keyword_patterns:
            if is_regex:
                if re.search(pattern, title_lower):
                    # Clean up pattern for display
                    clean_name = pattern.replace(r"\b", "").upper()
                    matching_core.append(clean_name)
            else:
                if pattern in title_lower:
                    matching_core.append(pattern)

        matching_roles = [
            role
            for role in desired_roles
            if any(word in title_lower for word in role.split() if len(word) > 3)
        ]

        if matching_core:
            # Title contains core ML/Data keywords - high relevance
            score = 8 if len(matching_core) >= 2 else 7
            matching_points = matching_core + matching_roles
            is_relevant = score >= state.get("relevance_threshold", 7)

            logger.info(
                f"Title match score: {score}/10 (core keywords: {matching_core})"
            )

            return {
                "relevance_result": {
                    "score": score,
                    "reasoning": f"Title contains ML/Data keywords: {', '.join(matching_core)}",
                    "matching_points": matching_points[:5],
                    "missing_requirements": ["Full description not available"],
                },
                "is_relevant": is_relevant,
                "jobs_relevant": state.get("jobs_relevant", 0)
                + (1 if is_relevant else 0),
                "jobs_skipped": state.get("jobs_skipped", 0)
                + (0 if is_relevant else 1),
            }
        elif matching_roles:
            # Role match - give passing score to process the job
            score = 7
            is_relevant = True
            logger.info(f"Role match found: {matching_roles} (score: {score})")

            return {
                "relevance_result": {
                    "score": score,
                    "reasoning": f"Match: {', '.join(matching_roles)}",
                    "matching_points": matching_roles,
                    "missing_requirements": [
                        "Core ML/Data keywords not found in title but role matches"
                    ],
                },
                "is_relevant": True,
                "jobs_relevant": state.get("jobs_relevant", 0) + 1,
            }
        else:
            logger.info(f"Title '{job_title}' doesn't match ML/Data criteria")
            return {
                "relevance_result": {
                    "score": 0,
                    "reasoning": f"Job title '{job_title}' doesn't match ML/Data keywords",
                    "matching_points": [],
                    "missing_requirements": [],
                },
                "is_relevant": False,
                "jobs_skipped": state.get("jobs_skipped", 0) + 1,
            }

    try:
        user_profile = config.get("user_profile", {})
        background = user_profile.get("background", {})
        target_criteria = user_profile.get("target_criteria", {})

        # Get LLM settings (model selection reserved for future use)
        llm_settings = config.get("llm_settings", {})
        _model = llm_settings.get("model", "anthropic/claude-3.5-sonnet")  # noqa: F841

        client = OpenRouterClient()

        relevance_result = client.check_job_relevance(
            job_description=description,
            user_background=background,
            target_criteria=target_criteria,
        )

        score = relevance_result.get(
            "relevance_score", relevance_result.get("score", 0)
        )
        is_relevant = score >= relevance_threshold

        logger.info(f"Relevance Score: {score}/10 (threshold: {relevance_threshold})")
        logger.info(f"Relevant: {'YES' if is_relevant else 'NO'}")

        if is_relevant:
            matching = relevance_result.get("matching_points", [])
            logger.info(f"Matching points: {', '.join(matching[:3])}")
        else:
            reasoning = relevance_result.get("reasoning", "")
            logger.info(f"Reason: {reasoning[:100]}...")

        return {
            "relevance_result": relevance_result,
            "is_relevant": is_relevant,
            "jobs_relevant": state.get("jobs_relevant", 0) + (1 if is_relevant else 0),
            "jobs_skipped": state.get("jobs_skipped", 0) + (0 if is_relevant else 1),
        }

    except Exception as e:
        error_msg = f"Failed to check relevance: {e}"
        logger.error(error_msg)

        return {
            "relevance_result": {
                "score": 0,
                "reasoning": f"Error: {str(e)}",
                "matching_points": [],
                "missing_requirements": [],
            },
            "is_relevant": False,
            "errors": [error_msg],
        }


def should_process_job(state: WorkflowState) -> str:
    """
    Conditional edge function to determine next step after relevance check.

    Args:
        state: Current workflow state.

    Returns:
        "generate_resume" if job is relevant, "next_job" otherwise.
    """
    is_relevant = state.get("is_relevant", False)
    dry_run = state.get("dry_run", False)

    if not is_relevant:
        return "next_job"

    if dry_run:
        logger.info("Dry run mode - skipping resume generation")
        return "log_to_sheets"

    return "generate_resume"
