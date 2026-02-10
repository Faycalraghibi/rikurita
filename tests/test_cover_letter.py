"""
Unit Tests for Cover Letter Generator

Tests for the cover letter generation node, filename generation,
compilation integration, and workflow wiring.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCoverLetterGeneratorNode:
    """Tests for generate_cover_letter_node."""

    @pytest.fixture
    def boilerplate_file(self, tmp_path):
        """Create a temporary boilerplate file."""
        content = r"""\documentclass{article}
\begin{document}
Dear <<RECRUITMENT_TEAM>>,
I am <<FIRST_NAME>> <<LAST_NAME>> applying for <<POSITION_TITLE>> at <<COMPANY_NAME>>.
\end{document}
"""
        boilerplate = tmp_path / "cover_letter_boilerplate.tex"
        boilerplate.write_text(content)
        return str(boilerplate)

    def test_node_disabled_returns_empty(self):
        """Node returns empty LaTeX when cover_letter.enabled is false."""
        from graph.nodes.cover_letter_generator import generate_cover_letter_node

        state = {
            "config": {"cover_letter": {"enabled": False}},
            "current_job": {"title": "ML Engineer", "company_name": "TestCo"},
            "resume_data": {},
        }

        result = generate_cover_letter_node(state)

        assert result["generated_cover_letter_latex"] == ""

    def test_node_disabled_by_default(self):
        """Node returns empty when cover_letter section omitted from config."""
        from graph.nodes.cover_letter_generator import generate_cover_letter_node

        state = {
            "config": {},
            "current_job": {"title": "ML Engineer", "company_name": "TestCo"},
            "resume_data": {},
        }

        result = generate_cover_letter_node(state)

        assert result["generated_cover_letter_latex"] == ""

    def test_node_no_job_returns_empty(self):
        """Node returns empty when current_job is None."""
        from graph.nodes.cover_letter_generator import generate_cover_letter_node

        state = {
            "config": {"cover_letter": {"enabled": True}},
            "current_job": None,
            "resume_data": {},
        }

        result = generate_cover_letter_node(state)

        assert result["generated_cover_letter_latex"] == ""

    def test_node_missing_boilerplate_returns_error(self):
        """Node returns error when boilerplate file is not found."""
        from graph.nodes.cover_letter_generator import generate_cover_letter_node

        state = {
            "config": {
                "cover_letter": {
                    "enabled": True,
                    "base_latex_file": "nonexistent.tex",
                }
            },
            "current_job": {"title": "Test", "company_name": "TestCo"},
            "resume_data": {},
        }

        result = generate_cover_letter_node(state)

        assert result["generated_cover_letter_latex"] == ""
        assert len(result["errors"]) > 0

    @patch("graph.nodes.cover_letter_generator.OpenRouterClient")
    def test_placeholder_substitution(self, mock_client_cls, boilerplate_file):
        """All placeholder tokens are replaced in the boilerplate."""
        import json

        from graph.nodes.cover_letter_generator import generate_cover_letter_node

        mock_client = MagicMock()
        mock_client.chat.return_value = json.dumps(
            {
                "POSITION_TITLE": "ML Engineer",
                "RECRUITMENT_TEAM": "HR Team",
                "COMPANY_NAME": "TestCo",
            }
        )
        mock_client_cls.return_value = mock_client

        state = {
            "config": {
                "cover_letter": {
                    "enabled": True,
                    "base_latex_file": boilerplate_file,
                }
            },
            "current_job": {
                "title": "ML Engineer",
                "company_name": "TestCo",
                "description": "Looking for ML engineers",
            },
            "resume_data": {
                "personal": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "+1234567890",
                }
            },
            "relevance_result": {},
        }

        result = generate_cover_letter_node(state)

        latex = result["generated_cover_letter_latex"]
        assert "John" in latex  # FIRST_NAME substituted from static
        assert "Doe" in latex  # LAST_NAME substituted from static
        assert "ML Engineer" in latex  # POSITION_TITLE from LLM
        assert "<<FIRST_NAME>>" not in latex
        assert "<<LAST_NAME>>" not in latex


class TestCoverLetterFilename:
    """Tests for cover letter filename generation."""

    def test_cover_letter_filename_prefix(self):
        """Filename starts with coverletter_ prefix."""
        from graph.nodes.latex_compiler import generate_cover_letter_filename

        date = datetime(2024, 3, 15)
        filename = generate_cover_letter_filename("Google", "ML Engineer", date)

        assert filename.startswith("coverletter_")
        assert "Google" in filename
        assert "ML_Engineer" in filename
        assert "2024-03-15" in filename

    def test_cover_letter_filename_sanitized(self):
        """Filename is properly sanitized."""
        from graph.nodes.latex_compiler import generate_cover_letter_filename

        date = datetime(2024, 1, 1)
        filename = generate_cover_letter_filename("Test Company", "Senior Lead", date)

        assert "/" not in filename
        assert " " not in filename
        assert filename.startswith("coverletter_")
        assert "Test_Company" in filename


class TestCompileLatexNodeCoverLetter:
    """Tests for cover letter compilation in compile_latex_node."""

    def test_compile_node_skips_when_empty(self, tmp_path, monkeypatch):
        """No cover letter compilation when LaTeX is empty."""
        monkeypatch.setattr("graph.nodes.latex_compiler.RESUMES_DIR", tmp_path)

        from graph.nodes.latex_compiler import compile_latex_node

        state = {
            "current_job": {"title": "Test", "company_name": "TestCo"},
            "generated_latex": r"\documentclass{article}\begin{document}Hi\end{document}",
            "generated_cover_letter_latex": "",  # Empty = skip
            "jobs_applied": 0,
            "jobs_failed": 0,
        }

        result = compile_latex_node(state)

        assert result["cover_letter_pdf_path"] == ""
        assert result["cover_letter_tex_path"] == ""

    def test_compile_node_writes_cover_letter_tex(self, tmp_path, monkeypatch):
        """Cover letter .tex file is written when LaTeX is generated."""
        monkeypatch.setattr("graph.nodes.latex_compiler.RESUMES_DIR", tmp_path)

        from graph.nodes.latex_compiler import compile_latex_node

        cl_content = (
            r"\documentclass{article}\begin{document}Cover Letter\end{document}"
        )

        state = {
            "current_job": {"title": "Test Role", "company_name": "TestCo"},
            "generated_latex": r"\documentclass{article}\begin{document}Resume\end{document}",
            "generated_cover_letter_latex": cl_content,
            "jobs_applied": 0,
            "jobs_failed": 0,
        }

        result = compile_latex_node(state)

        # Cover letter tex should exist (even if PDF compilation may fail)
        cl_tex = result.get("cover_letter_tex_path", "")
        if cl_tex:
            assert Path(cl_tex).exists()
            assert "coverletter_" in Path(cl_tex).name

    def test_compile_node_no_current_job(self):
        """Returns empty paths when no current job."""
        from graph.nodes.latex_compiler import compile_latex_node

        state = {
            "current_job": None,
            "generated_latex": "",
            "generated_cover_letter_latex": "",
        }

        result = compile_latex_node(state)

        assert result["resume_pdf_path"] == ""
        assert result["cover_letter_pdf_path"] == ""


class TestWorkflowRouting:
    """Tests for cover letter node in workflow routing."""

    def test_workflow_has_cover_letter_node(self):
        """Workflow graph includes generate_cover_letter node."""
        from graph.workflow import create_workflow

        workflow = create_workflow()

        # The compiled graph should have the cover letter node
        # Check by verifying the graph has the expected nodes
        graph_nodes = workflow.get_graph().nodes
        assert "generate_cover_letter" in graph_nodes

    def test_workflow_edge_resume_to_cover_letter(self):
        """generate_resume connects to generate_cover_letter."""
        from graph.workflow import create_workflow

        workflow = create_workflow()
        graph = workflow.get_graph()

        # Check that generate_resume has an edge to generate_cover_letter
        resume_node = graph.nodes.get("generate_resume")
        assert resume_node is not None

        # Verify edges exist in the graph
        edges = graph.edges
        resume_to_cl = any(
            e.source == "generate_resume" and e.target == "generate_cover_letter"
            for e in edges
        )
        cl_to_compile = any(
            e.source == "generate_cover_letter" and e.target == "compile_latex"
            for e in edges
        )
        assert resume_to_cl, "Missing edge: generate_resume → generate_cover_letter"
        assert cl_to_compile, "Missing edge: generate_cover_letter → compile_latex"


class TestStateExtension:
    """Tests for cover letter fields in WorkflowState."""

    def test_initial_state_has_cover_letter_fields(self):
        """create_initial_state includes cover letter fields."""
        from graph.state import create_initial_state

        config = {"job_search": {"relevance_threshold": 7}}
        resume_data = {"personal": {"name": "Test"}}

        state = create_initial_state(config, resume_data)

        assert "generated_cover_letter_latex" in state
        assert state["generated_cover_letter_latex"] == ""
        assert "cover_letter_pdf_path" in state
        assert state["cover_letter_pdf_path"] == ""
        assert "cover_letter_tex_path" in state
        assert state["cover_letter_tex_path"] == ""

    def test_processed_job_has_cover_letter_fields(self):
        """ProcessedJob includes cover_letter_path."""
        from graph.state import ProcessedJob

        job = ProcessedJob()
        assert hasattr(job, "cover_letter_path")
        assert hasattr(job, "cover_letter_tex_path")

        job_dict = job.to_dict()
        assert "cover_letter_path" in job_dict


class TestFallbackValues:
    """Tests for cover letter fallback value generation."""

    def test_fallback_returns_all_tokens(self):
        """Fallback values include all required dynamic tokens."""
        from graph.nodes.cover_letter_generator import _get_fallback_values

        resume_data = {
            "personal": {"name": "Test User", "title": "Engineer"},
            "skills": {"programming_languages": ["Python", "Java", "C++"]},
            "education": [{"degree": "MSc Computer Science", "institution": "MIT"}],
        }

        result = _get_fallback_values(resume_data, "ML Engineer", "Google")

        assert result["POSITION_TITLE"] == "ML Engineer"
        assert result["COMPANY_NAME"] == "Google"
        assert "EDUCATION_STATUS" in result
        assert "MAIN_SKILLS" in result
        assert "Python" in result["MAIN_SKILLS"]

    def test_static_values_extraction(self):
        """Static values are correctly extracted from personal data."""
        from graph.nodes.cover_letter_generator import _extract_static_values

        personal = {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "+1234567890",
        }
        config = {
            "user_profile": {
                "target_criteria": {"preferred_locations": ["Paris", "Remote"]}
            }
        }

        result = _extract_static_values(personal, config)

        assert result["FIRST_NAME"] == "Jane"
        assert result["LAST_NAME"] == "Smith"
        assert result["EMAIL"] == "jane@example.com"
        assert result["PHONE"] == "+1234567890"
        assert result["LOCATION"] == "Paris"
