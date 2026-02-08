"""
Resume Generator Node

Generates customized LaTeX resumes for relevant jobs.
Uses template-based approach with LLM-driven content selection.
"""

import logging
import json
from typing import Any, Optional

from graph.state import WorkflowState
from utils.resume_template import generate_resume_from_template
from utils.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)


def generate_resume_node(state: WorkflowState) -> dict[str, Any]:
    """
    Generate a customized LaTeX resume for the current job.
    
    Uses LLM to select and reorder content based on job requirements,
    then template-based generation for reliable LaTeX output.
    
    Args:
        state: Current workflow state.
        
    Returns:
        Updated state with generated LaTeX code.
    """
    current_job = state.get("current_job")
    resume_data = state.get("resume_data", {})
    config = state.get("config", {})
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
            customizations = _get_job_tailoring(
                client, resume_data, job_title, company_name, description, matching_points
            )
            if customizations:
                logger.info(f"LLM tailoring: prioritizing {customizations.get('top_projects', [])}")
        except Exception as e:
            logger.warning(f"LLM tailoring failed, using default order: {e}")
        
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


def _get_job_tailoring(
    client: OpenRouterClient,
    resume_data: dict,
    job_title: str,
    company_name: str,
    description: str,
    matching_points: list,
) -> Optional[dict]:
    """
    Use LLM to determine how to tailor the resume for this specific job.
    
    Returns:
        Dictionary with tailoring instructions:
        - top_projects: list of project names to prioritize (in order)
        - top_skills: list of skills to list first
        - experience_order: list of company names in display order
        - professional_summary: optional 1-2 sentence tailored summary
    """
    # Build context about the candidate
    projects = resume_data.get("projects", [])
    project_names = [p.get("name", "") for p in projects]
    
    experience = resume_data.get("experience", [])
    exp_companies = [e.get("company", "") for e in experience]
    
    skills = resume_data.get("skills", {})
    all_skills = (
        skills.get("programming_languages", []) +
        skills.get("frameworks_libraries", skills.get("frameworks", [])) +
        skills.get("other_skills", skills.get("domains", []))
    )
    
    # Create prompt for the LLM
    system_prompt = """You are a career coach helping tailor a resume for a specific job.
Given the job and candidate information, decide:
1. Which projects are most relevant (order them by relevance)
2. Which skills to highlight first
3. A brief 1-sentence professional focus for this role

Return ONLY valid JSON with this exact structure:
{
    "top_projects": ["project1", "project2"],
    "top_skills": ["skill1", "skill2", "skill3", "skill4", "skill5"],
    "professional_focus": "Brief sentence about candidate's fit for this role"
}

Return ONLY the JSON, no other text."""

    # Build job context
    job_context = f"Job: {job_title} at {company_name}"
    if description:
        job_context += f"\n\nJob Description:\n{description[:800]}"
    if matching_points:
        job_context += f"\n\nMatching points: {', '.join(matching_points[:5])}"
    
    prompt = f"""{job_context}

Candidate's projects: {', '.join(project_names)}
Candidate's skills: {', '.join(all_skills[:15])}
Experience companies: {', '.join(exp_companies)}

Which projects and skills are most relevant for this {job_title} role?"""

    try:
        response = client.chat(prompt, system_prompt, max_tokens=400, temperature=0.3)
        
        # Clean up response (handle markdown code blocks)
        response = response.strip()
        if response.startswith("```"):
            parts = response.split("```")
            if len(parts) >= 2:
                response = parts[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()
        
        result = json.loads(response)
        logger.info(f"Tailoring for {job_title}: focus on {result.get('top_projects', [])[:2]}")
        return result
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        # Fall back to keyword-based tailoring
        return _keyword_based_tailoring(job_title, resume_data)
    except Exception as e:
        logger.warning(f"LLM tailoring request failed: {e}")
        return _keyword_based_tailoring(job_title, resume_data)


def _keyword_based_tailoring(job_title: str, resume_data: dict) -> dict:
    """
    Generate tailoring based on keyword matching when LLM fails.
    
    Analyzes the job title and matches against project/skill keywords.
    """
    job_lower = job_title.lower()
    
    # Define keyword mappings for different job types
    keyword_project_map = {
        # ML/AI roles prioritize Joshu and Juridia
        "machine learning": ["Joshu", "Juridia"],
        "ml ": ["Joshu", "Juridia"],
        "deep learning": ["Juridia", "Joshu"],
        "ai ": ["Joshu", "LogoCraftAI"],
        "artificial intelligence": ["Joshu", "LogoCraftAI"],
        "nlp": ["Juridia", "Joshu"],
        "recommender": ["Joshu", "Juridia"],
        "data scien": ["Joshu", "Juridia", "LogoCraftAI"],
        "data engineer": ["Joshu", "Juridia"],
        "research": ["Joshu", "Juridia"],
    }
    
    keyword_skill_map = {
        "machine learning": ["Python", "PyTorch", "TensorFlow", "Scikit-learn"],
        "ml ": ["Python", "PyTorch", "TensorFlow", "Scikit-learn"],
        "deep learning": ["PyTorch", "TensorFlow", "Python"],
        "ai ": ["LLM Agents", "Python", "LangGraph", "FastAPI"],
        "nlp": ["Hugging Face", "PyTorch", "Python"],
        "data scien": ["Python", "Scikit-learn", "SQL", "PyTorch"],
        "recommender": ["PyTorch", "Python", "Scikit-learn"],
    }
    
    # Match keywords
    top_projects = []
    top_skills = []
    
    for keyword, projects in keyword_project_map.items():
        if keyword in job_lower:
            top_projects.extend(projects)
            break
    
    for keyword, skills in keyword_skill_map.items():
        if keyword in job_lower:
            top_skills.extend(skills)
            break
    
    # Remove duplicates while preserving order
    top_projects = list(dict.fromkeys(top_projects))
    top_skills = list(dict.fromkeys(top_skills))
    
    # Generate professional focus based on job title
    focus_map = {
        "machine learning": "Aspiring ML engineer with hands-on experience in LLM agents and deep learning",
        "data scien": "Data Science engineering student with AI/ML project experience",
        "ai ": "AI engineering student specializing in LLM agents and generative AI",
        "research": "Research-oriented engineer with experience in AI systems and NLP",
        "recommender": "ML engineer with experience in production recommendation systems",
    }
    
    professional_focus = None
    for keyword, focus in focus_map.items():
        if keyword in job_lower:
            professional_focus = focus
            break
    
    if not professional_focus:
        professional_focus = "Data Science & AI Engineering student with hands-on project experience"
    
    result = {
        "top_projects": top_projects[:3] if top_projects else [],
        "top_skills": top_skills[:5] if top_skills else [],
        "professional_focus": professional_focus,
    }
    
    logger.info(f"Keyword-based tailoring for '{job_title}': {result.get('top_projects', [])}")
    return result
