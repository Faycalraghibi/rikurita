"""
Resume Generator Node

Generates customized LaTeX resumes for relevant jobs.
Uses LLM to tailor content (bullet points, emphasis) based on job requirements.
"""

import json
import logging
import time
from typing import Any

from graph.state import WorkflowState
from utils.openrouter_client import OpenRouterClient
from utils.resume_template import generate_resume_from_template

logger = logging.getLogger(__name__)

# Delay between LLM calls to avoid rate limiting (seconds)
LLM_CALL_DELAY = 3.0


def generate_resume_node(state: WorkflowState) -> dict[str, Any]:
    """
    Generate a customized LaTeX resume for the current job.

    Uses LLM to tailor content based on job requirements,
    then template-based generation for reliable LaTeX output.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with generated LaTeX code.
    """
    current_job = state.get("current_job")
    resume_data = state.get("resume_data", {})
    _config = state.get("config", {})  # noqa: F841 - reserved for future use
    relevance_result = state.get("relevance_result", {})

    if not current_job:
        logger.warning("No current job to generate resume for")
        return {"generated_latex": ""}

    job_title = current_job.get("title", "Unknown")
    company_name = current_job.get("company_name", "Unknown")
    description = current_job.get("description", "")

    logger.info(f"Generating tailored resume for: {job_title} at {company_name}")

    if not resume_data:
        error_msg = "No resume data available"
        logger.error(error_msg)
        return {
            "generated_latex": "",
            "errors": [error_msg],
        }

    try:
        # Get matching points from relevance check
        matching_points = relevance_result.get("matching_points", [])

        # Get LLM-based customizations for this specific job
        customizations = None
        try:
            client = OpenRouterClient()
            customizations = _get_full_tailoring(
                client,
                resume_data,
                job_title,
                company_name,
                description,
                matching_points,
            )
            if customizations:
                logger.info(
                    f"LLM tailoring: {customizations.get('tailoring_summary', 'N/A')}"
                )
        except Exception as e:
            logger.warning(f"LLM tailoring failed: {e}")
            logger.info("Using fallback: original resume content (no LLM tailoring)")
            customizations = None

        # Generate resume using template with customizations
        latex_code = generate_resume_from_template(
            resume_data=resume_data,
            company_name=company_name,
            job_title=job_title,
            customizations=customizations,
        )

        if not latex_code:
            error_msg = "Template returned empty LaTeX code"
            logger.error(error_msg)
            return {
                "generated_latex": "",
                "errors": [error_msg],
            }

        # Basic validation
        if "\\documentclass" not in latex_code or "\\end{document}" not in latex_code:
            logger.warning("Generated LaTeX may be incomplete")

        logger.info(f"Generated tailored LaTeX resume ({len(latex_code)} characters)")

        return {
            "generated_latex": latex_code,
        }

    except Exception as e:
        error_msg = f"Failed to generate resume: {e}"
        logger.error(error_msg)

        return {
            "generated_latex": "",
            "errors": [error_msg],
        }


def _get_full_tailoring(
    client: OpenRouterClient,
    resume_data: dict,
    job_title: str,
    company_name: str,
    description: str,
    matching_points: list,
) -> dict | None:
    """
    Use LLM to generate fully tailored resume content.

    This rewrites bullet points, selects relevant achievements,
    and creates a targeted professional summary.

    Returns:
        Dictionary with:
        - professional_focus: tailored headline for this role
        - tailored_experience: dict of company -> list of rewritten bullets
        - tailored_projects: dict of project -> list of rewritten bullets
        - top_skills: list of skills to highlight first
        - top_projects: list of project names in priority order
    """
    # Build resume context
    projects = resume_data.get("projects", [])
    experience = resume_data.get("experience", [])
    skills = resume_data.get("skills", {})

    all_skills = (
        skills.get("programming_languages", [])
        + skills.get("frameworks_libraries", skills.get("frameworks", []))
        + skills.get("other_skills", skills.get("domains", []))
    )

    # Build detailed prompt
    system_prompt = """You are an expert resume tailoring assistant.
Your job is to REWRITE resume bullet points to emphasize skills and achievements
that are most relevant to the specific job the candidate is applying for.

You must:
1. Rewrite experience bullet points to emphasize relevant keywords and skills
2. Rewrite project descriptions to highlight relevant technologies
3. Create a compelling 1-line professional summary for this specific role
4. Select which skills to list first

Return ONLY valid JSON with this structure:
{
    "professional_focus": "One compelling sentence about candidate's fit",
    "tailored_experience": {
        "Company Name": [
            "Rewritten bullet 1 emphasizing relevant skills",
            "Rewritten bullet 2 with job-specific keywords"
        ]
    },
    "tailored_projects": {
        "Project Name": [
            "Rewritten achievement emphasizing relevant tech"
        ]
    },
    "top_skills": ["skill1", "skill2", "skill3"],
    "top_projects": ["Project1", "Project2"],
    "tailoring_summary": "Brief note on what was emphasized"
}

Return ONLY JSON, no other text."""

    # Build job context
    job_context = f"TARGET JOB: {job_title} at {company_name}"
    if description:
        job_context += f"\n\nJob Description:\n{description[:1000]}"
    else:
        job_context += "\n\n(No job description available - tailor based on job title)"
    if matching_points:
        job_context += f"\n\nMatching keywords: {', '.join(matching_points[:5])}"

    # Build resume context
    exp_text = ""
    for exp in experience:
        company = exp.get("company", "")
        role = exp.get("role", exp.get("title", ""))
        bullets = exp.get("achievements", exp.get("highlights", []))
        exp_text += f"\n{role} at {company}:\n"
        for b in bullets:
            exp_text += f"  - {b}\n"

    proj_text = ""
    for proj in projects:
        name = proj.get("name", "")
        tech = proj.get("technologies", "")
        bullets = proj.get("achievements", proj.get("description", []))
        proj_text += f"\n{name} ({tech}):\n"
        if isinstance(bullets, list):
            for b in bullets:
                proj_text += f"  - {b}\n"
        else:
            proj_text += f"  - {bullets}\n"

    prompt = f"""{job_context}

CANDIDATE'S CURRENT RESUME:

EXPERIENCE:
{exp_text}

PROJECTS:
{proj_text}

SKILLS: {", ".join(all_skills[:15])}

Rewrite the bullet points to better match this {job_title} position.
Emphasize relevant technologies, skills, and achievements.
Keep the core facts accurate but adjust the language and emphasis."""

    try:
        response = client.chat(prompt, system_prompt, max_tokens=1200, temperature=0.4)

        # Add delay after LLM call to avoid rate limiting
        time.sleep(LLM_CALL_DELAY)

        # Clean up response
        response = response.strip()
        if response.startswith("```"):
            parts = response.split("```")
            if len(parts) >= 2:
                response = parts[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

        result = json.loads(response)
        logger.info(f"Full tailoring generated for: {job_title}")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM tailoring response: {e}")
        return _get_fallback_customization(resume_data)
    except Exception as e:
        logger.warning(f"LLM tailoring failed: {e}")
        return _get_fallback_customization(resume_data)


def _get_fallback_customization(resume_data: dict) -> dict:
    """
    Generate minimal customizations when LLM is unavailable.

    This does NOT modify any content - it simply passes through
    the original resume data. The template will use the original
    experience bullets, project descriptions, etc.

    This is intentionally minimal to keep the tool general-purpose.
    All actual tailoring should come from the LLM.

    Args:
        resume_data: The user's resume data from YAML.

    Returns:
        Dictionary with empty tailoring (use original content).
    """
    # Get user's professional title from resume_data if available
    personal = resume_data.get("personal", resume_data.get("personal_info", {}))
    professional_focus = personal.get("title", None)

    # Build minimal result - all tailoring fields empty
    # The template will use original content from resume_data
    result = {
        "professional_focus": professional_focus,  # From user's data or None
        "top_projects": [],  # Empty = keep original order
        "top_skills": [],  # Empty = keep original order
        "tailored_experience": {},  # Empty = use original bullets
        "tailored_projects": {},  # Empty = use original bullets
        "tailoring_summary": "Using original resume (LLM unavailable)",
    }

    logger.info("Using fallback: original resume content (no LLM tailoring)")
    return result
