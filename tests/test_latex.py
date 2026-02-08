"""
Unit Tests for LaTeX Compiler

Tests file naming, directory creation, and LaTeX compilation logic.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.nodes.latex_compiler import (
    sanitize_filename,
    create_resume_directory,
    generate_resume_filename,
    compile_latex,
    RESUMES_DIR,
)


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""
    
    def test_basic_name(self):
        """Test basic name without special characters."""
        assert sanitize_filename("Google") == "Google"
    
    def test_spaces_replaced(self):
        """Test spaces are replaced with underscores."""
        assert sanitize_filename("Machine Learning Engineer") == "Machine_Learning_Engineer"
    
    def test_special_characters_removed(self):
        """Test special characters are removed."""
        assert sanitize_filename('Test<>:"/\\|?*') == "Test"
    
    def test_dashes_replaced(self):
        """Test dashes are replaced with underscores."""
        assert sanitize_filename("Mid-Senior Level") == "Mid_Senior_Level"
    
    def test_consecutive_underscores(self):
        """Test consecutive underscores are reduced."""
        assert sanitize_filename("Test   Multiple    Spaces") == "Test_Multiple_Spaces"
    
    def test_leading_trailing_underscores(self):
        """Test leading/trailing underscores are removed."""
        assert sanitize_filename("  Test  ") == "Test"
    
    def test_length_limit(self):
        """Test filename is limited to 50 characters."""
        long_name = "A" * 100
        result = sanitize_filename(long_name)
        assert len(result) <= 50
    
    def test_empty_string(self):
        """Test empty string returns 'unknown'."""
        assert sanitize_filename("") == "unknown"
        assert sanitize_filename("***") == "unknown"
    
    def test_unicode_characters(self):
        """Test unicode characters are preserved."""
        assert sanitize_filename("Société Générale") == "Société_Générale"
    
    def test_real_company_names(self):
        """Test with real company name examples."""
        assert sanitize_filename("McKinsey & Company") == "McKinsey_Company"
        assert sanitize_filename("L'Oréal") == "LOréal"


class TestGenerateResumeFilename:
    """Tests for generate_resume_filename function."""
    
    def test_basic_filename(self):
        """Test basic filename generation."""
        date = datetime(2024, 1, 15)
        filename = generate_resume_filename("Google", "ML Engineer", date)
        assert filename == "resume_Google_ML_Engineer_2024-01-15"
    
    def test_sanitization_applied(self):
        """Test that company and role are sanitized."""
        date = datetime(2024, 2, 20)
        filename = generate_resume_filename("McKinsey & Co", "Senior Consultant", date)
        assert "/" not in filename
        assert "&" not in filename
        assert " " not in filename
    
    def test_uses_current_date_by_default(self):
        """Test that current date is used when not provided."""
        filename = generate_resume_filename("TestCo", "TestRole")
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in filename


class TestCreateResumeDirectory:
    """Tests for create_resume_directory function."""
    
    def test_creates_directory_structure(self, tmp_path, monkeypatch):
        """Test directory structure is created correctly."""
        # Patch RESUMES_DIR to use temp path
        monkeypatch.setattr("graph.nodes.latex_compiler.RESUMES_DIR", tmp_path)
        
        result = create_resume_directory("Google", "ML Engineer")
        
        assert result.exists()
        assert result.is_dir()
        assert "Google" in str(result)
        assert "ML_Engineer" in str(result)
    
    def test_handles_special_characters(self, tmp_path, monkeypatch):
        """Test special characters in names are handled."""
        monkeypatch.setattr("graph.nodes.latex_compiler.RESUMES_DIR", tmp_path)
        
        result = create_resume_directory("McKinsey & Co", "Senior/Lead Consultant")
        
        assert result.exists()
        assert "/" not in result.name
        assert "&" not in str(result.relative_to(tmp_path))


class TestCompileLatex:
    """Tests for compile_latex function."""
    
    @pytest.fixture
    def valid_latex(self):
        """Return valid minimal LaTeX code."""
        return r"""
\documentclass{article}
\begin{document}
Hello, World!
\end{document}
"""
    
    @pytest.fixture
    def invalid_latex(self):
        """Return invalid LaTeX code."""
        return r"""
\documentclass{article}
\begin{document}
Missing end document tag
"""
    
    def test_writes_tex_file(self, tmp_path, valid_latex):
        """Test that .tex file is always written."""
        success, pdf_path, tex_path, error = compile_latex(
            valid_latex, tmp_path, "test_resume"
        )
        
        assert tex_path is not None
        assert tex_path.exists()
        assert tex_path.suffix == ".tex"
        
        # Verify content
        content = tex_path.read_text()
        assert "Hello, World!" in content
    
    @patch("shutil.which")
    def test_handles_missing_compiler(self, mock_which, tmp_path, valid_latex):
        """Test graceful handling when no LaTeX compiler is available."""
        mock_which.return_value = None
        
        success, pdf_path, tex_path, error = compile_latex(
            valid_latex, tmp_path, "test_resume"
        )
        
        # Should still write .tex file even if compilation fails
        assert tex_path is not None
        assert tex_path.exists()
        assert success is False  # No compiler available


class TestIntegration:
    """Integration tests for the latex_compiler module."""
    
    def test_full_workflow_dry_run(self, tmp_path, monkeypatch):
        """Test full workflow without actual compilation."""
        monkeypatch.setattr("graph.nodes.latex_compiler.RESUMES_DIR", tmp_path)
        
        # Simulate workflow
        from graph.nodes.latex_compiler import (
            create_resume_directory,
            generate_resume_filename,
        )
        
        company = "Test Company"
        role = "Test Role"
        
        output_dir = create_resume_directory(company, role)
        filename = generate_resume_filename(company, role)
        
        assert output_dir.exists()
        assert "Test_Company" in str(output_dir)
        assert "Test_Role" in str(output_dir)
        assert "resume_Test_Company_Test_Role_" in filename
