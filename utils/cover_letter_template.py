"""
LaTeX Cover Letter Template Generator

Generates customized cover letters using a template-based approach with data from cover_letter_data.yaml
and LLM-generated overrides.
"""

import logging

from utils.resume_template import escape_latex

logger = logging.getLogger(__name__)


def generate_cover_letter_from_template(
    cover_letter_data: dict,
    personal_info: dict,
    job_title: str,
    company_name: str,
) -> str:
    """
    Generate a complete LaTeX cover letter from template and data.

    Args:
        cover_letter_data: Data for the cover letter content (context, motivation, etc.)
        personal_info: Personal info (name, email, phone, location)
        job_title: Target job title
        company_name: Target company name

    Returns:
        Complete LaTeX code.
    """

    # Helper to safely get and escape data
    def get_safe(data, key, default=""):
        return escape_latex(data.get(key, default))

    # Personal Info
    first_name = get_safe(personal_info, "first_name")
    last_name = get_safe(personal_info, "last_name")
    if not first_name and not last_name:
        # Fallback to full name split if available
        full_name = personal_info.get("name", "").split(" ")
        if len(full_name) >= 1:
            first_name = escape_latex(full_name[0])
        if len(full_name) >= 2:
            last_name = escape_latex(" ".join(full_name[1:]))

    phone = get_safe(personal_info, "phone")
    email = get_safe(personal_info, "email")
    location = get_safe(personal_info, "location")

    # Job Specifics
    # job_title and company_name are passed directly, escape them
    job_title_latex = escape_latex(job_title)
    company_name_latex = escape_latex(company_name)

    # Cover Letter Content
    recruitment_team = get_safe(
        cover_letter_data, "recruitment_team", "Recruitment Team"
    )

    # Paragraph 1: Context
    education_status = get_safe(cover_letter_data, "education_status")
    specialization = get_safe(cover_letter_data, "specialization")
    start_date = get_safe(cover_letter_data, "start_date")

    # Paragraph 2-5
    company_motivation = get_safe(cover_letter_data, "company_motivation")
    company_impact = get_safe(cover_letter_data, "company_impact")

    # Skills handling: can be list or string
    main_skills_raw = cover_letter_data.get("main_skills", [])
    if isinstance(main_skills_raw, list):
        main_skills = ", ".join(escape_latex(s) for s in main_skills_raw)
    else:
        main_skills = escape_latex(str(main_skills_raw))

    relevant_projects = get_safe(cover_letter_data, "relevant_projects")
    tech_challenges = get_safe(cover_letter_data, "tech_challenges")
    role_missions = get_safe(cover_letter_data, "role_missions")
    learning_objectives = get_safe(cover_letter_data, "learning_objectives")

    latex = (
        r"""\documentclass[11pt,a4paper,sans]{moderncv}

% ===== STYLE =====
\moderncvstyle{banking}
\moderncvcolor{blue}
\usepackage[scale=0.85]{geometry}
\usepackage[utf8]{inputenc}

% ===== CANDIDATE INFO =====
\firstname{"""
        + first_name
        + r"""}
\familyname{"""
        + last_name
        + r"""}
\title{Application -- """
        + job_title_latex
        + r"""}
\address{"""
        + location
        + r"""}{}
\mobile{"""
        + phone
        + r"""}
\email{"""
        + email
        + r"""}

\begin{document}

% ===== RECIPIENT INFO =====
\recipient{"""
        + recruitment_team
        + r"""}{"""
        + company_name_latex
        + r"""}
\date{\today}
\opening{Dear Sir or Madam,}
\makelettertitle

% ===== PARAGRAPH 1 : CONTEXT =====
I am currently """
        + education_status
        + r""", specializing in """
        + specialization
        + r""", and I would like to apply for the position of \textit{"""
        + job_title_latex
        + r"""} at """
        + company_name_latex
        + r""", starting from """
        + start_date
        + r""".

% ===== PARAGRAPH 2 : COMPANY MOTIVATION =====
"""
        + company_name_latex
        + r""" particularly appeals to me due to """
        + company_motivation
        + r""". Contributing to """
        + company_impact
        + r""" represents for me a stimulating technological and human challenge.

% ===== PARAGRAPH 3 : TECHNICAL FIT =====
Throughout my academic training and projects, I have developed strong skills in """
        + main_skills
        + r""". In particular, I have worked on """
        + relevant_projects
        + r""", which allowed me to gain hands-on experience with """
        + tech_challenges
        + r""".

% ===== PARAGRAPH 4 : ROLE ALIGNMENT =====
Curious and self-driven, I thrive in environments where technical rigor meets initiative. Missions related to """
        + role_missions
        + r""" align perfectly with the type of responsibilities in which I am eager to invest and grow.

% ===== PARAGRAPH 5 : CLOSING =====
Motivated and detail-oriented, I would be delighted to contribute to the work carried out by your teams while further strengthening my expertise in """
        + learning_objectives
        + r""".

I remain at your disposal for any interview that would allow me to further explain my motivation and interest in this position.

\closing{Yours sincerely,}
\makeletterclosing

\end{document}
"""
    )

    return latex
