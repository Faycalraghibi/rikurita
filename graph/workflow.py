"""
LangGraph Workflow Definition

Defines the complete job application automation workflow.
"""

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from graph.nodes.apify_scraper import fetch_jobs_node, get_next_job_node
from graph.nodes.latex_compiler import compile_latex_node
from graph.nodes.relevance_check import check_relevance_node
from graph.nodes.resume_generator import generate_resume_node
from graph.nodes.scheduler import scheduler_node
from graph.nodes.sheets_logger import log_skipped_job_node, log_to_sheets_node
from graph.state import WorkflowState, create_initial_state

logger = logging.getLogger(__name__)


def should_continue_processing(state: WorkflowState) -> Literal["get_next_job", "end"]:
    """
    Determine whether to continue processing more jobs.

    Args:
        state: Current workflow state.

    Returns:
        "get_next_job" to continue, "end" to finish.
    """
    should_continue = state.get("should_continue", True)
    workflow_complete = state.get("workflow_complete", False)
    current_index = state.get("current_job_index", 0)
    total_jobs = state.get("total_jobs", 0)

    if workflow_complete or not should_continue:
        return "end"

    if current_index >= total_jobs:
        return "end"

    return "get_next_job"


def route_after_relevance(
    state: WorkflowState,
) -> Literal["generate_resume", "log_skipped", "next_job"]:
    """
    Route after relevance check based on score and dry run mode.

    Args:
        state: Current workflow state.

    Returns:
        Next node to execute.
    """
    is_relevant = state.get("is_relevant", False)
    dry_run = state.get("dry_run", False)

    if not is_relevant:
        return "log_skipped"

    if dry_run:
        # In dry run, log relevant jobs but don't generate resumes
        logger.info("Dry run mode - skipping resume generation for relevant job")
        return "log_skipped"

    return "generate_resume"


def print_summary_node(state: WorkflowState) -> dict:
    """
    Print a summary of the workflow execution.

    Args:
        state: Current workflow state.

    Returns:
        Final state updates.
    """
    logger.info("\n" + "=" * 60)
    logger.info("WORKFLOW COMPLETE - SUMMARY")
    logger.info("=" * 60)

    total_jobs = state.get("total_jobs", 0)
    jobs_processed = state.get("jobs_processed", 0)
    jobs_relevant = state.get("jobs_relevant", 0)
    jobs_applied = state.get("jobs_applied", 0)
    jobs_skipped = state.get("jobs_skipped", 0)
    jobs_failed = state.get("jobs_failed", 0)

    logger.info(f"Total jobs fetched:     {total_jobs}")
    logger.info(f"Jobs processed:         {jobs_processed}")
    logger.info(
        f"Jobs relevant (>={state.get('relevance_threshold', 7)}):   {jobs_relevant}"
    )
    logger.info(f"Resumes generated:      {jobs_applied}")
    logger.info(f"Jobs skipped:           {jobs_skipped}")
    logger.info(f"Jobs failed:            {jobs_failed}")

    errors = state.get("errors", [])
    if errors:
        logger.warning(f"\nErrors encountered ({len(errors)}):")
        for error in errors[:5]:  # Show first 5 errors
            logger.warning(f"  - {error[:100]}")
        if len(errors) > 5:
            logger.warning(f"  ... and {len(errors) - 5} more errors")

    processed_jobs = state.get("processed_jobs", [])
    applied_jobs = [j for j in processed_jobs if j.get("status") == "Applied"]
    if applied_jobs:
        logger.info("\nGenerated resumes:")
        for job in applied_jobs:
            logger.info(f"  - {job.get('company_name')}: {job.get('resume_path')}")

    logger.info("=" * 60)

    return {
        "workflow_complete": True,
    }


def create_workflow() -> StateGraph:
    """
    Create the job application automation workflow.

    Returns:
        Compiled StateGraph workflow.
    """
    workflow = StateGraph(WorkflowState)

    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("fetch_jobs", fetch_jobs_node)
    workflow.add_node("get_next_job", get_next_job_node)
    workflow.add_node("check_relevance", check_relevance_node)
    workflow.add_node("generate_resume", generate_resume_node)
    workflow.add_node("compile_latex", compile_latex_node)
    workflow.add_node("log_to_sheets", log_to_sheets_node)
    workflow.add_node("log_skipped", log_skipped_job_node)
    workflow.add_node("print_summary", print_summary_node)

    workflow.set_entry_point("scheduler")

    workflow.add_edge("scheduler", "fetch_jobs")
    workflow.add_edge("fetch_jobs", "get_next_job")

    workflow.add_edge("get_next_job", "check_relevance")

    workflow.add_conditional_edges(
        "check_relevance",
        route_after_relevance,
        {
            "generate_resume": "generate_resume",
            "log_skipped": "log_skipped",
        },
    )

    workflow.add_edge("generate_resume", "compile_latex")

    workflow.add_edge("compile_latex", "log_to_sheets")

    workflow.add_conditional_edges(
        "log_to_sheets",
        should_continue_processing,
        {
            "get_next_job": "get_next_job",
            "end": "print_summary",
        },
    )

    workflow.add_conditional_edges(
        "log_skipped",
        should_continue_processing,
        {
            "get_next_job": "get_next_job",
            "end": "print_summary",
        },
    )

    workflow.add_edge("print_summary", END)

    return workflow.compile()


def run_workflow(
    config: dict = None,
    resume_data: dict = None,
    dry_run: bool = False,
) -> dict:
    """
    Run the job application workflow.

    Args:
        config: Optional configuration dict (loaded from file if not provided).
        resume_data: Optional resume data dict (loaded from file if not provided).
        dry_run: If True, don't create actual resumes.

    Returns:
        Final workflow state.
    """
    from graph.nodes.scheduler import load_config
    from graph.nodes.scheduler import load_resume_data as load_resume

    if config is None:
        config = load_config()
    if resume_data is None:
        resume_data = load_resume()

    initial_state = create_initial_state(
        config=config,
        resume_data=resume_data,
        dry_run=dry_run,
    )

    workflow = create_workflow()

    logger.info("Starting workflow execution...")

    final_state = workflow.invoke(initial_state)

    return final_state
