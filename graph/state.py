"""
Workflow State Schema

Defines the state structure for the LangGraph workflow.
"""

import operator
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, TypedDict


class ApplicationStatus(Enum):
    """Status of a job application."""

    PENDING = "Pending"
    APPLIED = "Applied"
    SKIPPED = "Skipped"
    FAILED = "Failed"


@dataclass
class JobData:
    """Structured job data extracted from Apify."""

    job_id: str = ""
    job_post_link: str = ""
    title: str = ""
    company_name: str = ""
    location: str = ""
    job_type: str = ""
    seniority_level: str = ""
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

    @classmethod
    def from_dict(cls, data: dict) -> "JobData":
        """Create from dictionary."""
        return cls(
            job_id=data.get("job_id", ""),
            job_post_link=data.get("job_post_link", ""),
            title=data.get("title", ""),
            company_name=data.get("company_name", ""),
            location=data.get("location", ""),
            job_type=data.get("job_type", ""),
            seniority_level=data.get("seniority_level", ""),
            posted_at=data.get("posted_at", ""),
            company_website=data.get("company_website", ""),
            salary=data.get("salary", ""),
            description=data.get("description", ""),
            application_url=data.get("application_url", ""),
            required_skills=data.get("required_skills", []),
        )


@dataclass
class RelevanceResult:
    """Result of LLM relevance check."""

    score: float = 0.0
    reasoning: str = ""
    matching_points: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)

    def is_relevant(self, threshold: float = 7.0) -> bool:
        """Check if job meets relevance threshold."""
        return self.score >= threshold

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "reasoning": self.reasoning,
            "matching_points": self.matching_points,
            "missing_requirements": self.missing_requirements,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RelevanceResult":
        """Create from dictionary."""
        return cls(
            score=data.get("relevance_score", data.get("score", 0.0)),
            reasoning=data.get("reasoning", ""),
            matching_points=data.get("matching_points", []),
            missing_requirements=data.get("missing_requirements", []),
        )


@dataclass
class ProcessedJob:
    """A job that has been processed through the workflow."""

    job: JobData = field(default_factory=JobData)
    relevance: RelevanceResult | None = None
    resume_path: str = ""
    resume_tex_path: str = ""
    cover_letter_path: str = ""
    cover_letter_tex_path: str = ""
    status: ApplicationStatus = ApplicationStatus.PENDING
    error: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            **self.job.to_dict(),
            "relevance_score": self.relevance.score if self.relevance else 0,
            "relevance_reasoning": self.relevance.reasoning if self.relevance else "",
            "matching_points": self.relevance.matching_points if self.relevance else [],
            "resume_path": self.resume_path,
            "cover_letter_path": self.cover_letter_path,
            "status": self.status.value,
            "error": self.error,
        }


class WorkflowState(TypedDict):
    """
    State schema for the LangGraph workflow.

    This TypedDict defines all data that flows through the workflow nodes.
    """

    # Configuration
    config: dict  # Loaded from config.yaml
    resume_data: dict  # Loaded from resume_data.yaml
    relevance_threshold: float  # Minimum score to proceed (default: 7)
    dry_run: bool  # If True, don't actually create resumes

    # Job processing
    all_jobs: list[dict]  # All fetched jobs from Apify
    current_job_index: int  # Index of current job being processed
    current_job: dict | None  # Current job data

    # Relevance checking
    relevance_result: dict | None  # Result of relevance check
    is_relevant: bool  # Whether current job passed relevance check

    # Resume generation
    generated_latex: str  # Generated LaTeX code
    resume_pdf_path: str  # Path to compiled PDF
    resume_tex_path: str  # Path to .tex source

    # Cover letter generation
    generated_cover_letter_latex: str  # Generated cover letter LaTeX code
    cover_letter_pdf_path: str  # Path to compiled cover letter PDF
    cover_letter_tex_path: str  # Path to cover letter .tex source

    # Processed jobs accumulator
    processed_jobs: Annotated[list[dict], operator.add]  # All processed jobs

    # Statistics
    total_jobs: int
    jobs_processed: int
    jobs_relevant: int
    jobs_applied: int
    jobs_skipped: int
    jobs_failed: int

    # Error tracking
    errors: Annotated[list[str], operator.add]  # Accumulated errors

    # Control flow
    should_continue: bool  # Whether to continue processing more jobs
    workflow_complete: bool  # Whether workflow has finished


def create_initial_state(
    config: dict,
    resume_data: dict,
    dry_run: bool = False,
) -> WorkflowState:
    """
    Create initial workflow state.

    Args:
        config: Configuration from config.yaml.
        resume_data: Resume data from resume_data.yaml.
        dry_run: If True, don't create actual resumes.

    Returns:
        Initial WorkflowState.
    """
    relevance_threshold = config.get("job_search", {}).get("relevance_threshold", 7)

    return WorkflowState(
        config=config,
        resume_data=resume_data,
        relevance_threshold=relevance_threshold,
        dry_run=dry_run,
        all_jobs=[],
        current_job_index=0,
        current_job=None,
        relevance_result=None,
        is_relevant=False,
        generated_latex="",
        resume_pdf_path="",
        resume_tex_path="",
        generated_cover_letter_latex="",
        cover_letter_pdf_path="",
        cover_letter_tex_path="",
        processed_jobs=[],
        total_jobs=0,
        jobs_processed=0,
        jobs_relevant=0,
        jobs_applied=0,
        jobs_skipped=0,
        jobs_failed=0,
        errors=[],
        should_continue=True,
        workflow_complete=False,
    )
