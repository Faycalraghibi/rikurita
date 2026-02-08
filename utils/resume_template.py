"""
LaTeX Resume Template Generator

Generates customized resumes using a template-based approach with LLM-driven content selection.
"""

import logging

logger = logging.getLogger(__name__)


def escape_latex(text) -> str:
    """Escape special LaTeX characters."""
    if text is None:
        return ""

    # Handle non-string types
    if not isinstance(text, str):
        text = str(text)

    # Characters that need escaping in LaTeX
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]

    for char, replacement in replacements:
        text = text.replace(char, replacement)

    return text


def _reorder_by_priority(
    items: list, priority_names: list, name_key: str = "name"
) -> list:
    """Reorder items based on priority list. Items in priority list come first."""
    if not priority_names:
        return items

    priority_lower = [p.lower() for p in priority_names]

    # Separate into prioritized and other items
    prioritized = []
    other = []

    for item in items:
        item_name = item.get(name_key, "").lower()

        # Check if item matches any priority name
        matched = False
        for i, pname in enumerate(priority_lower):
            if pname in item_name or item_name in pname:
                prioritized.append((i, item))
                matched = True
                break

        if not matched:
            other.append(item)

    # Sort prioritized by their position in the priority list
    prioritized.sort(key=lambda x: x[0])

    return [item for _, item in prioritized] + other


def _prioritize_skills(skills_list: list, priority_skills: list) -> list:
    """Reorder skills list to put priority skills first."""
    if not priority_skills or not skills_list:
        return skills_list

    priority_lower = [s.lower() for s in priority_skills]

    prioritized = []
    other = []

    for skill in skills_list:
        skill_lower = skill.lower()
        if any(ps in skill_lower or skill_lower in ps for ps in priority_lower):
            prioritized.append(skill)
        else:
            other.append(skill)

    return prioritized + other


def generate_resume_from_template(
    resume_data: dict,
    company_name: str,
    job_title: str,
    customizations: dict | None = None,
) -> str:
    """
    Generate a complete LaTeX resume from template and resume data.

    Args:
        resume_data: Structured resume data from YAML.
        company_name: Target company name.
        job_title: Target job title.
        customizations: LLM-generated customizations with:
            - top_projects: list of project names to prioritize
            - top_skills: list of skills to list first
            - professional_focus: tailored summary sentence

    Returns:
        Complete LaTeX code.
    """
    # Handle different key names for personal info
    personal = resume_data.get("personal", resume_data.get("personal_info", {}))
    education = resume_data.get("education", [])
    experience = resume_data.get("experience", [])
    projects = list(resume_data.get("projects", []))  # Copy to avoid mutating original
    skills = resume_data.get("skills", {})
    certifications = resume_data.get("certifications", [])
    extracurricular = resume_data.get("extracurricular", [])

    # Apply customizations
    professional_focus = None
    if customizations:
        # Reorder projects based on LLM recommendations
        top_projects = customizations.get("top_projects", [])
        if top_projects:
            projects = _reorder_by_priority(projects, top_projects, "name")

        # Get professional focus for header
        professional_focus = customizations.get("professional_focus")

        # Note: top_skills will be used in skills section below

    # Build LaTeX document
    latex = r"""\documentclass[11pt,a4paper]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=0.6in]{geometry}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{titlesec}
\usepackage{xcolor}

\pagestyle{empty}

% Define colors
\definecolor{linkcolor}{RGB}{0,0,139}

% Compact lists
\setlist[itemize]{left=0pt, label={--}, nosep, topsep=2pt, partopsep=0pt}

% Section formatting
\titleformat{\section}{\large\bfseries\uppercase}{}{0em}{}[\titlerule]
\titlespacing{\section}{0pt}{8pt}{4pt}

% Custom commands
\newcommand{\resumeSubheading}[4]{
  \vspace{3pt}
  \noindent\textbf{#1} \hfill #2 \\
  \textit{#3} \hfill \textit{#4}
  \vspace{2pt}
}

\newcommand{\resumeProject}[2]{
  \vspace{3pt}
  \noindent\textbf{#1} \hfill \textit{#2}
  \vspace{2pt}
}

\hypersetup{
    colorlinks=true,
    linkcolor=linkcolor,
    urlcolor=linkcolor,
}

\begin{document}

"""

    # Header
    name = escape_latex(personal.get("name", "Your Name"))
    title = escape_latex(personal.get("title", ""))
    email = personal.get("email", "")
    phone = personal.get("phone", "")
    linkedin = personal.get("linkedin", "")
    github = personal.get("github", "")
    location = escape_latex(personal.get("location", ""))

    latex += r"\begin{center}" + "\n"
    latex += r"{\LARGE \textbf{" + name + r"}}" + "\n\n"

    # Add professional focus or title under name
    if professional_focus:
        latex += r"\vspace{2pt}" + "\n"
        latex += r"{\small\textit{" + escape_latex(professional_focus) + r"}}" + "\n\n"
    elif title:
        latex += r"\vspace{2pt}" + "\n"
        latex += r"{\small\textit{" + title + r"}}" + "\n\n"

    latex += r"\vspace{2pt}" + "\n"

    contact_parts = []
    if email:
        contact_parts.append(
            r"\href{mailto:" + email + r"}{" + escape_latex(email) + r"}"
        )
    if phone:
        contact_parts.append(escape_latex(phone))
    if location:
        contact_parts.append(location)
    if linkedin:
        linkedin_url = (
            linkedin if linkedin.startswith("http") else f"https://{linkedin}"
        )
        linkedin_display = linkedin.replace("https://", "").replace("www.", "")
        contact_parts.append(
            r"\href{" + linkedin_url + r"}{" + escape_latex(linkedin_display) + r"}"
        )
    if github:
        github_url = github if github.startswith("http") else f"https://{github}"
        github_display = github.replace("https://", "").replace("www.", "")
        contact_parts.append(
            r"\href{" + github_url + r"}{" + escape_latex(github_display) + r"}"
        )

    latex += " | ".join(contact_parts) + "\n"
    latex += r"\end{center}" + "\n\n"

    # Education
    if education:
        latex += r"\section{Education}" + "\n"
        for edu in education:
            institution = escape_latex(edu.get("institution", ""))
            degree = escape_latex(edu.get("degree", ""))
            dates = escape_latex(edu.get("dates", ""))
            loc = escape_latex(edu.get("location", ""))

            latex += (
                r"\resumeSubheading{"
                + institution
                + r"}{"
                + dates
                + r"}{"
                + degree
                + r"}{"
                + loc
                + r"}"
                + "\n"
            )

            details = edu.get("details", [])
            if details:
                latex += r"\begin{itemize}" + "\n"
                for detail in details[:3]:
                    latex += r"  \item " + escape_latex(detail) + "\n"
                latex += r"\end{itemize}" + "\n"
        latex += "\n"

    # Certifications
    if certifications:
        latex += r"\section{Certifications}" + "\n"
        latex += r"\begin{itemize}" + "\n"
        for cert in certifications[:5]:
            if isinstance(cert, dict):
                cert_name = escape_latex(cert.get("name", ""))
                cert_issuer = escape_latex(cert.get("issuer", ""))
                latex += r"  \item \textbf{" + cert_name + r"}"
                if cert_issuer:
                    latex += r" -- " + cert_issuer
                latex += "\n"
            else:
                latex += r"  \item " + escape_latex(cert) + "\n"
        latex += r"\end{itemize}" + "\n\n"

    # Experience
    if experience:
        latex += r"\section{Experience}" + "\n"
        for exp in experience:
            company = escape_latex(exp.get("company", ""))
            role = escape_latex(exp.get("role", exp.get("title", "")))
            dates = escape_latex(exp.get("dates", ""))
            loc = escape_latex(exp.get("location", ""))

            latex += (
                r"\resumeSubheading{"
                + company
                + r"}{"
                + dates
                + r"}{"
                + role
                + r"}{"
                + loc
                + r"}"
                + "\n"
            )

            highlights = exp.get("achievements", exp.get("highlights", []))
            if highlights:
                latex += r"\begin{itemize}" + "\n"
                for highlight in highlights[:4]:
                    latex += r"  \item " + escape_latex(highlight) + "\n"
                latex += r"\end{itemize}" + "\n"
        latex += "\n"

    # Projects (reordered based on customizations)
    if projects:
        latex += r"\section{Projects}" + "\n"
        for proj in projects[:4]:
            proj_name = escape_latex(proj.get("name", ""))
            tech = escape_latex(proj.get("technologies", ""))

            latex += r"\resumeProject{" + proj_name + r"}{" + tech + r"}" + "\n"

            achievements = proj.get("achievements", proj.get("description", []))
            if isinstance(achievements, list) and achievements:
                latex += r"\begin{itemize}" + "\n"
                for ach in achievements[:3]:
                    latex += r"  \item " + escape_latex(ach) + "\n"
                latex += r"\end{itemize}" + "\n"
            elif isinstance(achievements, str):
                latex += r"\begin{itemize}" + "\n"
                latex += r"  \item " + escape_latex(achievements) + "\n"
                latex += r"\end{itemize}" + "\n"
        latex += "\n"

    # Skills (with priority ordering)
    if skills:
        latex += r"\section{Skills}" + "\n"
        latex += r"\begin{itemize}[label={}]" + "\n"

        # Get top skills from customizations
        top_skills = customizations.get("top_skills", []) if customizations else []

        prog_langs = skills.get("programming_languages", [])
        if top_skills:
            prog_langs = _prioritize_skills(prog_langs, top_skills)
        if prog_langs:
            langs = ", ".join(escape_latex(lang) for lang in prog_langs)
            latex += r"  \item \textbf{Programming:} " + langs + "\n"

        frameworks = skills.get("frameworks_libraries", skills.get("frameworks", []))
        if top_skills:
            frameworks = _prioritize_skills(frameworks, top_skills)
        if frameworks:
            fw = ", ".join(escape_latex(f) for f in frameworks)
            latex += r"  \item \textbf{Frameworks:} " + fw + "\n"

        other_tech = skills.get("other_technologies", skills.get("tools", []))
        if other_tech:
            tech = ", ".join(escape_latex(t) for t in other_tech)
            latex += r"  \item \textbf{Tools:} " + tech + "\n"

        other_skills = skills.get("other_skills", skills.get("domains", []))
        if other_skills:
            sk = ", ".join(escape_latex(s) for s in other_skills)
            latex += r"  \item \textbf{AI/ML:} " + sk + "\n"

        languages = skills.get("languages", [])
        if languages:
            lang_parts = []
            for lang in languages:
                if isinstance(lang, dict):
                    lname = lang.get("name", "")
                    level = lang.get("level", "")
                    if lname:
                        lang_parts.append(
                            f"{escape_latex(lname)} ({escape_latex(level)})"
                            if level
                            else escape_latex(lname)
                        )
                else:
                    lang_parts.append(escape_latex(lang))
            if lang_parts:
                latex += r"  \item \textbf{Languages:} " + ", ".join(lang_parts) + "\n"

        latex += r"\end{itemize}" + "\n\n"

    # Extracurricular
    if extracurricular:
        latex += r"\section{Extracurricular Activities}" + "\n"
        for activity in extracurricular[:3]:
            role = escape_latex(activity.get("role", ""))
            org = escape_latex(activity.get("organization", ""))
            dates = escape_latex(activity.get("dates", ""))

            latex += (
                r"\resumeProject{" + role + " -- " + org + r"}{" + dates + r"}" + "\n"
            )

            highlights = activity.get("achievements", activity.get("highlights", []))
            if highlights:
                latex += r"\begin{itemize}" + "\n"
                for highlight in highlights[:2]:
                    latex += r"  \item " + escape_latex(highlight) + "\n"
                latex += r"\end{itemize}" + "\n"
        latex += "\n"

    latex += r"\end{document}" + "\n"

    return latex
