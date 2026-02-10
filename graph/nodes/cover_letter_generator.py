"""
Cover Letter Generator Node

Generates customized LaTeX cover letters for relevant jobs.
Uses cover_letter_data.yaml as a base and LLM to tailor specific sections.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import yaml

from graph.state import WorkflowState
from utils.cover_letter_template import generate_cover_letter_from_template
from utils.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)

# Delay between LLM calls to avoid rate limiting (seconds)
LLM_CALL_DELAY = 3.0


def generate_cover_letter_node(state: WorkflowState) -> dict[str, Any]:
    """
    Generate a customized LaTeX cover letter for the current job.

    Uses cover_letter_data.yaml defaults + LLM overrides + Python template.

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

    # Load base data from YAML
    base_data = _load_cover_letter_data()

    # Get LLM-generated overrides for dynamic fields
    llm_overrides = _get_llm_cover_letter_values(
        resume_data=resume_data,
        job_title=job_title,
        company_name=company_name,
        description=description,
        relevance_result=relevance_result,
        base_data=base_data,
    )

    # Merge: base keys + LLM overrides
    # Note: personal info is passed separately from resume_data
    merged_data = {**base_data, **llm_overrides}

    # Generate LaTeX code using Python template
    try:
        latex_code = generate_cover_letter_from_template(
            cover_letter_data=merged_data,
            personal_info=resume_data.get("personal", {}),
            job_title=job_title,
            company_name=company_name,
        )
    except Exception as e:
        logger.error(f"Failed to generate cover letter from template: {e}")
        return {
            "generated_cover_letter_latex": "",
            "errors": [f"Template error: {e}"],
        }

    logger.info(f"Generated cover letter LaTeX ({len(latex_code)} characters)")

    return {
        "generated_cover_letter_latex": latex_code,
    }


def _load_cover_letter_data() -> dict:
    """Load default cover letter data from YAML."""
    cl_data_path = Path("templates/cover_letter_data.yaml")
    if cl_data_path.exists():
        try:
            with open(cl_data_path, encoding="utf-8") as f:
                full_data = yaml.safe_load(f) or {}
                return full_data.get("cover_letter", {})
        except Exception as e:
            logger.warning(f"Failed to load cover_letter_data.yaml: {e}")
    else:
        logger.warning("cover_letter_data.yaml not found, using empty defaults")
    return {}


def _get_llm_cover_letter_values(
    resume_data: dict,
    job_title: str,
    company_name: str,
    description: str,
    relevance_result: dict,
    base_data: dict,
) -> dict[str, str]:
    """
    Use LLM to tailor specific sections of the cover letter.

    Args:
        resume_data: User resume data.
        job_title: Target job title.
        company_name: Target company name.
        description: Job description.
        relevance_result: Formatting relevance info.
        base_data: Default values from YAML (used as fallback logic context).

    Returns:
        Dictionary of overridden keys matching cover_letter_data structure.
    """
    # Build context from resume data
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

    # We want the LLM to override these semantic fields if it can do better

    system_prompt = """You are an expert cover letter writer.
Your goal is to tailor specific sections of a cover letter for a job application.

Return a JSON object with the following keys (if you have enough info to improve them, otherwise omit):
- company_motivation: Why this specific company appeals to the candidate (2-3 reasons based on job description).
- company_impact: What contributing to this company means (mention specific products/values).
- role_missions: Key responsibilities of the role that align with candidate's profile.
- tech_challenges: Technical challenges relevant to the role that the candidate has faced.
- learning_objectives: What the candidate hopes to learn or strengthen in this role.
- relevant_projects: Specific relevant projects from candidate's background to mention.

Keep the tone professional, enthusiastic, and concise.
Do NOT invent facts. Use the provided candidate background.
Return ONLY valid JSON."""

    prompt = f"""TARGET JOB: {job_title} at {company_name}

Job Description:
{description[:1500] if description else "(No description available)"}

{"Matching keywords: " + ", ".join(matching_points[:5]) if matching_points else ""}

CANDIDATE BACKGROUND:
Education:
{edu_summary}

Experience:
{exp_summary}

Projects:
{proj_summary}

Skills: {", ".join(all_skills[:15])}

Current Defaults (only override if you can specificly tailor to this job):
- company_motivation: {base_data.get("company_motivation", "")}
- company_impact: {base_data.get("company_impact", "")}
- role_missions: {base_data.get("role_missions", "")}

Generate tailored content overrides in JSON format."""

    try:
        client = OpenRouterClient()
        response = client.chat(prompt, system_prompt, max_tokens=800, temperature=0.4)

        # Add delay after LLM call
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
        logger.info(f"LLM generated cover letter overrides for: {job_title}")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        return {}
    except Exception as e:
        logger.warning(f"LLM cover letter generation failed: {e}")
        return {}
