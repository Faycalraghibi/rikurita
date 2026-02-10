"""
Cover Letter Generator Node

Generates customized LaTeX cover letters for relevant jobs.
Uses LLM to fill a parameterized LaTeX boilerplate based on job requirements.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from graph.state import WorkflowState
from utils.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)

# Delay between LLM calls to avoid rate limiting (seconds)
LLM_CALL_DELAY = 3.0

# All placeholder tokens in the boilerplate
BOILERPLATE_TOKENS = [
    "FIRST_NAME",
    "LAST_NAME",
    "POSITION_TITLE",
    "LOCATION",
    "PHONE",
    "EMAIL",
    "RECRUITMENT_TEAM",
    "COMPANY_NAME",
    "EDUCATION_STATUS",
    "SPECIALIZATION",
    "START_DATE",
    "COMPANY_MOTIVATION",
    "COMPANY_IMPACT",
    "MAIN_SKILLS",
    "RELEVANT_PROJECTS",
    "TECH_CHALLENGES",
    "ROLE_MISSIONS",
    "LEARNING_OBJECTIVES",
]


def generate_cover_letter_node(state: WorkflowState) -> dict[str, Any]:
    """
    Generate a customized LaTeX cover letter for the current job.

    Reads the boilerplate template, uses LLM to generate values for each
    placeholder token, and substitutes them into the template.

    Short-circuits if cover_letter.enabled is False in config.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with generated cover letter LaTeX code.
    """
    config = state.get("config", {})
    cover_letter_config = config.get("cover_letter", {})

    # Feature flag: skip if disabled
    if not cover_letter_config.get("enabled", False):
        logger.debug("Cover letter generation disabled in config")
        return {"generated_cover_letter_latex": ""}

    current_job = state.get("current_job")
    resume_data = state.get("resume_data", {})
    relevance_result = state.get("relevance_result") or {}

    if not current_job:
        logger.warning("No current job to generate cover letter for")
        return {"generated_cover_letter_latex": ""}

    job_title = current_job.get("title", "Unknown")
    company_name = current_job.get("company_name", "Unknown")
    description = current_job.get("description", "")

    logger.info(f"Generating cover letter for: {job_title} at {company_name}")

    # Load boilerplate template
    boilerplate_path = cover_letter_config.get(
        "base_latex_file", "templates/cover_letter_boilerplate.tex"
    )
    try:
        boilerplate = Path(boilerplate_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        error_msg = f"Cover letter boilerplate not found: {boilerplate_path}"
        logger.error(error_msg)
        return {
            "generated_cover_letter_latex": "",
            "errors": [error_msg],
        }

    # Pre-fill static tokens from resume_data / config
    personal = resume_data.get("personal", {})
    static_values = _extract_static_values(personal, config)

    # Get LLM-generated values for dynamic tokens
    dynamic_values = _get_llm_cover_letter_values(
        resume_data=resume_data,
        job_title=job_title,
        company_name=company_name,
        description=description,
        relevance_result=relevance_result,
    )

    # Merge: static values take precedence for personal info tokens,
    # LLM values fill the rest
    all_values = {**dynamic_values, **static_values}

    # Perform substitution
    filled_latex = boilerplate
    for token in BOILERPLATE_TOKENS:
        placeholder = f"<<{token}>>"
        value = all_values.get(token, "")
        if value:
            filled_latex = filled_latex.replace(placeholder, value)
        else:
            logger.warning(f"No value for cover letter token: {token}")

    # Check for remaining unsubstituted placeholders
    remaining = re.findall(r"<<\w+>>", filled_latex)
    if remaining:
        logger.warning(f"Unsubstituted cover letter tokens: {remaining}")

    # Validate basic LaTeX structure
    if "\\documentclass" not in filled_latex or "\\end{document}" not in filled_latex:
        logger.warning("Generated cover letter LaTeX may be incomplete")

    logger.info(f"Generated cover letter LaTeX ({len(filled_latex)} characters)")

    return {
        "generated_cover_letter_latex": filled_latex,
    }


def _extract_static_values(personal: dict, config: dict) -> dict[str, str]:
    """
    Extract static token values from resume data and config.

    These are personal details that don't need LLM generation.

    Args:
        personal: Personal info from resume_data.yaml.
        config: Full config dictionary.

    Returns:
        Dictionary mapping token names to values.
    """
    # Parse full name into first/last
    full_name = personal.get("name", "")
    name_parts = full_name.strip().split(" ", 1) if full_name else []
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Get location from config user_profile
    user_profile = config.get("user_profile", {})
    locations = user_profile.get("target_criteria", {}).get("preferred_locations", [])
    location = locations[0] if locations else ""

    return {
        "FIRST_NAME": first_name,
        "LAST_NAME": last_name,
        "PHONE": personal.get("phone", ""),
        "EMAIL": personal.get("email", ""),
        "LOCATION": location,
    }


def _get_llm_cover_letter_values(
    resume_data: dict,
    job_title: str,
    company_name: str,
    description: str,
    relevance_result: dict,
) -> dict[str, str]:
    """
    Use LLM to generate values for dynamic cover letter placeholders.

    Args:
        resume_data: The user's resume data.
        job_title: Target job title.
        company_name: Target company name.
        description: Job description text.
        relevance_result: Relevance check result dict.

    Returns:
        Dictionary mapping token names to LLM-generated values.
    """
    # Build context from resume data
    personal = resume_data.get("personal", {})
    experience = resume_data.get("experience", [])
    projects = resume_data.get("projects", [])
    skills = resume_data.get("skills", {})
    education = resume_data.get("education", [])

    all_skills = (
        skills.get("programming_languages", [])
        + skills.get("frameworks_libraries", skills.get("frameworks", []))
        + skills.get("other_skills", skills.get("domains", []))
    )

    matching_points = relevance_result.get("matching_points", [])

    # Build experience summary
    exp_summary = ""
    for exp in experience[:3]:
        company = exp.get("company", "")
        role = exp.get("role", exp.get("title", ""))
        bullets = exp.get("achievements", exp.get("highlights", []))
        exp_summary += f"\n{role} at {company}:\n"
        for b in bullets[:2]:
            exp_summary += f"  - {b}\n"

    # Build projects summary
    proj_summary = ""
    for proj in projects[:3]:
        name = proj.get("name", "")
        tech = proj.get("technologies", "")
        proj_summary += f"  - {name} ({tech})\n"

    # Build education summary
    edu_summary = ""
    for edu in education[:2]:
        degree = edu.get("degree", "")
        institution = edu.get("institution", "")
        edu_summary += f"  - {degree} at {institution}\n"

    system_prompt = """You are an expert cover letter writer.
Your job is to generate specific values for placeholders in a cover letter template.

The cover letter template has these dynamic placeholders you must fill:
- POSITION_TITLE: The exact job title being applied for
- RECRUITMENT_TEAM: How to address the recipient (e.g., "Recruitment Team" or "HR Department")
- COMPANY_NAME: The company name
- EDUCATION_STATUS: Current education status (e.g., "a final-year Master's student in Computer Science")
- SPECIALIZATION: Field of specialization
- START_DATE: Desired start date (e.g., "March 2025" or "as soon as possible")
- COMPANY_MOTIVATION: Why this company appeals (2-3 compelling reasons based on job description)
- COMPANY_IMPACT: What contributing to this company represents (specific projects/missions)
- MAIN_SKILLS: Top relevant technical skills (comma-separated, 4-6 skills)
- RELEVANT_PROJECTS: Brief mention of 1-2 most relevant projects
- TECH_CHALLENGES: Technical challenges encountered in those projects
- ROLE_MISSIONS: Key missions of the role that align with the candidate's interests
- LEARNING_OBJECTIVES: What the candidate wants to learn/strengthen

Return ONLY valid JSON with token names as keys and their values as strings.
Values should be plain text (no LaTeX commands). Keep each value concise (1-2 sentences max).
Return ONLY JSON, no other text."""

    prompt = f"""TARGET JOB: {job_title} at {company_name}

Job Description:
{description[:1500] if description else "(No description available)"}

{"Matching keywords: " + ", ".join(matching_points[:5]) if matching_points else ""}

CANDIDATE BACKGROUND:
Name: {personal.get("name", "")}
Title: {personal.get("title", "")}

Education:
{edu_summary}

Experience:
{exp_summary}

Projects:
{proj_summary}

Skills: {", ".join(all_skills[:15])}

Generate the cover letter placeholder values tailored to this specific job."""

    try:
        client = OpenRouterClient()
        response = client.chat(prompt, system_prompt, max_tokens=800, temperature=0.4)

        # Add delay after LLM call to avoid rate limiting
        time.sleep(LLM_CALL_DELAY)

        # Parse JSON response
        response = response.strip()
        if response.startswith("```"):
            parts = response.split("```")
            if len(parts) >= 2:
                response = parts[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

        result = json.loads(response)
        logger.info(f"LLM generated cover letter values for: {job_title}")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM cover letter response: {e}")
        return _get_fallback_values(resume_data, job_title, company_name)
    except Exception as e:
        logger.warning(f"LLM cover letter generation failed: {e}")
        return _get_fallback_values(resume_data, job_title, company_name)


def _get_fallback_values(
    resume_data: dict,
    job_title: str,
    company_name: str,
) -> dict[str, str]:
    """
    Generate minimal fallback values when LLM is unavailable.

    Args:
        resume_data: The user's resume data.
        job_title: Target job title.
        company_name: Target company name.

    Returns:
        Dictionary with basic placeholder values.
    """
    personal = resume_data.get("personal", {})
    skills = resume_data.get("skills", {})
    education = resume_data.get("education", [])

    all_skills = (
        skills.get("programming_languages", [])[:3]
        + skills.get("frameworks_libraries", skills.get("frameworks", []))[:2]
    )

    edu_status = ""
    if education:
        degree = education[0].get("degree", "")
        institution = education[0].get("institution", "")
        edu_status = f"a student in {degree} at {institution}" if degree else ""

    logger.info("Using fallback cover letter values (LLM unavailable)")

    return {
        "POSITION_TITLE": job_title,
        "RECRUITMENT_TEAM": "Recruitment Team",
        "COMPANY_NAME": company_name,
        "EDUCATION_STATUS": edu_status or "a student",
        "SPECIALIZATION": personal.get("title", "my field"),
        "START_DATE": "as soon as possible",
        "COMPANY_MOTIVATION": f"its innovative work and the opportunity to contribute to {company_name}'s mission",
        "COMPANY_IMPACT": f"the projects at {company_name}",
        "MAIN_SKILLS": ", ".join(all_skills) if all_skills else "my technical skills",
        "RELEVANT_PROJECTS": "my academic and personal projects",
        "TECH_CHALLENGES": "real-world engineering challenges",
        "ROLE_MISSIONS": f"the core responsibilities of the {job_title} role",
        "LEARNING_OBJECTIVES": "applied engineering and industry best practices",
    }
