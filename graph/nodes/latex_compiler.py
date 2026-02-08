"""
LaTeX Compiler Node

Compiles LaTeX code to PDF and manages file organization.
"""

import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

from graph.state import WorkflowState

logger = logging.getLogger(__name__)

# Base directory for resume storage
RESUMES_DIR = Path("resumes")


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use in filenames.
    
    Args:
        name: Original string.
        
    Returns:
        Sanitized string safe for filesystem.
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces and dashes with underscores
    sanitized = re.sub(r'[\s\-]+', '_', sanitized)
    # Remove consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    # Limit length
    sanitized = sanitized[:50]
    
    return sanitized or "unknown"


def create_resume_directory(company_name: str, role_title: str) -> Path:
    """
    Create the directory structure for storing resumes.
    
    Args:
        company_name: Name of the company.
        role_title: Title of the role.
        
    Returns:
        Path to the resume directory.
    """
    company_dir = sanitize_filename(company_name)
    role_dir = sanitize_filename(role_title)
    
    resume_path = RESUMES_DIR / company_dir / role_dir
    resume_path.mkdir(parents=True, exist_ok=True)
    
    logger.debug(f"Created resume directory: {resume_path}")
    return resume_path


def generate_resume_filename(company_name: str, role_title: str, date: Optional[datetime] = None) -> str:
    """
    Generate a filename for the resume.
    
    Args:
        company_name: Name of the company.
        role_title: Title of the role.
        date: Date for the filename (defaults to now).
        
    Returns:
        Filename (without extension).
    """
    if date is None:
        date = datetime.now()
    
    company = sanitize_filename(company_name)
    role = sanitize_filename(role_title)
    date_str = date.strftime("%Y-%m-%d")
    
    return f"resume_{company}_{role}_{date_str}"


def compile_latex(
    latex_code: str,
    output_dir: Path,
    filename: str,
) -> Tuple[bool, Optional[Path], Optional[Path], str]:
    """
    Compile LaTeX code to PDF.
    
    Tries local compilers first, then falls back to online API.
    
    Args:
        latex_code: LaTeX source code.
        output_dir: Directory to save output files.
        filename: Base filename (without extension).
        
    Returns:
        Tuple of (success, pdf_path, tex_path, error_message).
    """
    tex_path = output_dir / f"{filename}.tex"
    pdf_path = output_dir / f"{filename}.pdf"
    
    # Write LaTeX source file
    try:
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_code)
        logger.info(f"Saved LaTeX source: {tex_path}")
    except Exception as e:
        return False, None, None, f"Failed to write .tex file: {e}"
    
    # Try local compilation first
    local_success, local_error = _try_local_compilation(latex_code, tex_path, pdf_path, filename)
    if local_success:
        return True, pdf_path, tex_path, ""
    
    # Fall back to online API
    logger.info("Local compiler not available, trying online LaTeX API...")
    online_success, online_error = _try_online_compilation(latex_code, pdf_path)
    if online_success:
        return True, pdf_path, tex_path, ""
    
    # Both failed
    error_msg = f"Local: {local_error}. Online: {online_error}"
    logger.error(f"All compilation methods failed: {error_msg}")
    return False, None, tex_path, error_msg


def _try_local_compilation(
    latex_code: str,
    tex_path: Path,
    pdf_path: Path,
    filename: str,
) -> Tuple[bool, str]:
    """Try compiling with local LaTeX compilers."""
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_tex = Path(temp_dir) / f"{filename}.tex"
        temp_pdf = Path(temp_dir) / f"{filename}.pdf"
        
        # Copy tex file to temp directory
        shutil.copy(tex_path, temp_tex)
        
        # Try latexmk first, then pdflatex
        compilers = [
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-output-directory=" + temp_dir, str(temp_tex)],
            ["pdflatex", "-interaction=nonstopmode", "-output-directory=" + temp_dir, str(temp_tex)],
            ["xelatex", "-interaction=nonstopmode", "-output-directory=" + temp_dir, str(temp_tex)],
        ]
        
        for compiler_cmd in compilers:
            compiler_name = compiler_cmd[0]
            
            if shutil.which(compiler_name) is None:
                continue
            
            logger.info(f"Compiling with {compiler_name}...")
            
            try:
                for _ in range(2):  # Two passes for references
                    result = subprocess.run(
                        compiler_cmd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        cwd=temp_dir,
                    )
                    
                    if temp_pdf.exists():
                        break
                
                if temp_pdf.exists():
                    shutil.copy(temp_pdf, pdf_path)
                    logger.info(f"Compiled PDF: {pdf_path}")
                    return True, ""
                    
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                pass
        
        return False, "No local LaTeX compiler found (pdflatex, xelatex, latexmk)"


def _try_online_compilation(latex_code: str, pdf_path: Path) -> Tuple[bool, str]:
    """
    Compile LaTeX using online API (latex.ytotech.com).
    
    This is a free API that compiles LaTeX to PDF without requiring local installation.
    """
    import requests
    
    # YtoTech LaTeX API (free, no auth required)
    api_url = "https://latex.ytotech.com/builds/sync"
    
    payload = {
        "compiler": "pdflatex",
        "resources": [
            {
                "main": True,
                "content": latex_code,
            }
        ]
    }
    
    try:
        logger.info("Sending LaTeX to online compiler...")
        response = requests.post(
            api_url,
            json=payload,
            timeout=60,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in (200, 201):
            # Check if response is PDF (starts with %PDF)
            if response.content[:4] == b'%PDF':
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"Online compilation successful: {pdf_path}")
                return True, ""
            else:
                # Response might be an error message
                try:
                    error_data = response.json()
                    return False, f"API error: {error_data.get('message', 'Unknown error')}"
                except:
                    return False, "API returned non-PDF response"
        else:
            return False, f"API returned status {response.status_code}: {response.text[:200]}"
            
    except requests.Timeout:
        return False, "Online API timed out"
    except requests.RequestException as e:
        return False, f"Online API request failed: {e}"
    except Exception as e:
        return False, f"Online compilation error: {e}"


def compile_latex_node(state: WorkflowState) -> dict[str, Any]:
    """
    Compile generated LaTeX to PDF and organize files.
    
    Args:
        state: Current workflow state.
        
    Returns:
        Updated state with resume paths.
    """
    current_job = state.get("current_job")
    latex_code = state.get("generated_latex", "")
    
    if not current_job:
        logger.warning("No current job for LaTeX compilation")
        return {
            "resume_pdf_path": "",
            "resume_tex_path": "",
        }
    
    if not latex_code:
        error_msg = "No LaTeX code to compile"
        logger.warning(error_msg)
        return {
            "resume_pdf_path": "",
            "resume_tex_path": "",
            "errors": [error_msg],
            "jobs_failed": state.get("jobs_failed", 0) + 1,
        }
    
    company_name = current_job.get("company_name", "Unknown")
    job_title = current_job.get("title", "Unknown")
    
    logger.info(f"Compiling resume for: {company_name} - {job_title}")
    
    try:
        # Create directory structure
        output_dir = create_resume_directory(company_name, job_title)
        
        # Generate filename
        filename = generate_resume_filename(company_name, job_title)
        
        # Check for existing files and add version if needed
        base_pdf = output_dir / f"{filename}.pdf"
        version = 1
        while base_pdf.exists():
            version += 1
            versioned_filename = f"{filename}_v{version}"
            base_pdf = output_dir / f"{versioned_filename}.pdf"
        
        if version > 1:
            filename = f"{filename}_v{version}"
            logger.info(f"File exists, using version {version}")
        
        # Compile LaTeX
        success, pdf_path, tex_path, error = compile_latex(
            latex_code=latex_code,
            output_dir=output_dir,
            filename=filename,
        )
        
        if success and pdf_path:
            logger.info(f"Resume compiled successfully:")
            logger.info(f"  PDF: {pdf_path}")
            logger.info(f"  TEX: {tex_path}")
            
            return {
                "resume_pdf_path": str(pdf_path),
                "resume_tex_path": str(tex_path),
                "jobs_applied": state.get("jobs_applied", 0) + 1,
            }
        else:
            # Even if PDF failed, we still have the .tex file
            logger.warning(f"PDF compilation failed, .tex file saved: {tex_path}")
            
            return {
                "resume_pdf_path": "",
                "resume_tex_path": str(tex_path) if tex_path else "",
                "errors": [error] if error else [],
                "jobs_failed": state.get("jobs_failed", 0) + 1,
            }
            
    except Exception as e:
        error_msg = f"Failed to compile LaTeX: {e}"
        logger.error(error_msg)
        
        return {
            "resume_pdf_path": "",
            "resume_tex_path": "",
            "errors": [error_msg],
            "jobs_failed": state.get("jobs_failed", 0) + 1,
        }
