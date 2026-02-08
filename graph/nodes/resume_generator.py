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
            logger.warning(f"LLM tailoring failed, using job-type defaults: {e}")
            customizations = _get_job_type_tailoring(job_title)

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
        return _get_job_type_tailoring(job_title)
    except Exception as e:
        logger.warning(f"LLM tailoring failed: {e}")
        return _get_job_type_tailoring(job_title)


def _get_job_type_tailoring(job_title: str) -> dict:
    """
    Generate tailoring based on job type when LLM is unavailable.

    Uses predefined templates for common job types.
    """
    job_lower = job_title.lower()

    # Define different tailoring strategies per job type
    tailoring_templates = {
        "machine learning": {
            "professional_focus": "Machine Learning Engineer with hands-on experience building LLM agents and deep learning systems",
            "top_projects": [
                "Joshu",
                "Juridia's Multilingual Legal Translation",
                "LogoCraftAI",
            ],
            "top_skills": [
                "Python",
                "PyTorch",
                "TensorFlow",
                "Scikit-learn",
                "LangGraph",
            ],
            "tailored_experience": {
                "Oracle": [
                    "Built and stabilized ML agent runtime, improving inference reliability for autonomous reasoning systems",
                    "Refactored machine learning integration layers, optimizing LLM orchestration patterns",
                    "Implemented best practices for ML model coordination and tool-use patterns",
                ],
            },
            "tailored_projects": {
                "Joshu": [
                    "Designed ML-powered agent platform with autonomous reasoning and persistent memory",
                    "Built multi-agent ML workflows with coordination between LLM-based agents",
                ],
            },
            "tailoring_summary": "Emphasized ML, deep learning, and LLM experience",
        },
        "data scien": {
            "professional_focus": "Data Science student with strong foundation in ML, statistics, and production AI systems",
            "top_projects": [
                "Joshu",
                "Juridia's Multilingual Legal Translation",
                "LogoCraftAI",
            ],
            "top_skills": ["Python", "Scikit-learn", "SQL", "PyTorch", "TensorFlow"],
            "tailored_experience": {
                "Oracle": [
                    "Analyzed and diagnosed data pipeline failures in agent systems, improving data flow reliability",
                    "Optimized database integration for ML inference, ensuring consistent data access patterns",
                    "Created data-driven documentation to accelerate team knowledge transfer",
                ],
            },
            "tailored_projects": {
                "Joshu": [
                    "Built data-driven agent platform with semantic memory and context management",
                    "Designed data pipelines for multi-agent coordination and state persistence",
                ],
            },
            "tailoring_summary": "Emphasized data science, analytics, and statistical skills",
        },
        "ai ": {
            "professional_focus": "AI Engineering student specializing in LLM agents, generative AI, and multi-agent systems",
            "top_projects": [
                "Joshu",
                "LogoCraftAI",
                "Juridia's Multilingual Legal Translation",
            ],
            "top_skills": ["LLM Agents", "Python", "LangGraph", "FastAPI", "PyTorch"],
            "tailored_experience": {
                "Oracle": [
                    "Developed autonomous AI agents with advanced reasoning and tool-use capabilities",
                    "Built LLM orchestration layer supporting multiple AI model backends",
                    "Implemented AI best practices for agent coordination and execution patterns",
                ],
            },
            "tailored_projects": {
                "Joshu": [
                    "Created AI agent platform with autonomous reasoning and multi-agent coordination",
                    "Implemented generative AI workflows with persistent semantic memory",
                ],
                "LogoCraftAI": [
                    "Built end-to-end generative AI system from prompt engineering to production deployment",
                ],
            },
            "tailoring_summary": "Emphasized AI, LLM agents, and generative AI experience",
        },
        "research": {
            "professional_focus": "Research-oriented ML engineer with experience in NLP, agent systems, and model fine-tuning",
            "top_projects": [
                "Juridia's Multilingual Legal Translation",
                "Joshu",
                "LogoCraftAI",
            ],
            "top_skills": ["PyTorch", "Hugging Face", "Python", "TensorFlow", "NLP"],
            "tailored_experience": {
                "Oracle": [
                    "Conducted research on agent execution patterns and reasoning reliability",
                    "Investigated and resolved complex failures in autonomous AI systems",
                    "Authored technical research documentation on agent orchestration methods",
                ],
            },
            "tailored_projects": {
                "Juridia's Multilingual Legal Translation": [
                    "Researched and implemented LoRA fine-tuning for domain-specific NLP models",
                    "Evaluated model performance using BLEU metrics and comparative analysis",
                ],
            },
            "tailoring_summary": "Emphasized research, NLP, and academic rigor",
        },
        "analyst": {
            "professional_focus": "Data-driven analyst with engineering background in AI/ML and business analytics",
            "top_projects": [
                "Joshu",
                "LogoCraftAI",
                "Juridia's Multilingual Legal Translation",
            ],
            "top_skills": ["Python", "SQL", "Power BI", "Data Analysis", "Excel"],
            "tailored_experience": {
                "Oracle": [
                    "Analyzed system performance data to diagnose and resolve critical issues",
                    "Created analytical documentation and reports for stakeholder communication",
                    "Collaborated cross-functionally to improve system reliability metrics",
                ],
                "Arrow Electronics": [
                    "Performed systematic API testing and analysis in agile engineering environment",
                ],
            },
            "tailored_projects": {
                "Joshu": [
                    "Analyzed user interaction patterns to optimize agent coordination workflows",
                ],
            },
            "tailoring_summary": "Emphasized analytical skills and data-driven decision making",
        },
    }

    # Default fallback - still provides tailored bullets for general tech/business roles
    default_tailoring = {
        "professional_focus": "Engineering student with hands-on experience in AI/ML, data science, and software development",
        "top_projects": [
            "Joshu",
            "Juridia's Multilingual Legal Translation",
            "LogoCraftAI",
        ],
        "top_skills": ["Python", "Machine Learning", "FastAPI", "PyTorch", "SQL"],
        "tailored_experience": {
            "Oracle": [
                "Delivered production-ready autonomous agent system, resolving critical execution and inference issues",
                "Orchestrated database and API integrations for scalable multi-backend coordination",
                "Established best practices for system architecture and technical documentation",
            ],
            "Arrow Electronics": [
                "Validated enterprise system reliability through comprehensive API testing in agile environment",
            ],
        },
        "tailored_projects": {
            "Joshu": [
                "Built production-grade platform orchestrating AI agents with secure APIs and persistent memory",
                "Implemented end-to-end automation with CI/CD, testing, and cross-platform deployment",
            ],
        },
        "tailoring_summary": "Used default professional profile with tailored bullets",
    }

    # Find matching template
    for keyword, template in tailoring_templates.items():
        if keyword in job_lower:
            logger.info(f"Using '{keyword}' tailoring template for: {job_title}")
            return template

    logger.info(f"Using default tailoring for: {job_title}")
    return default_tailoring
