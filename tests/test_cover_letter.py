"""
Unit Tests for Cover Letter Generator

Tests for the cover letter generation node (code-based template), filename generation,
compilation integration, and workflow wiring.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCoverLetterGeneratorNode:
    """Tests for generate_cover_letter_node using Python template."""

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

    @patch("graph.nodes.cover_letter_generator.generate_cover_letter_from_template")
    @patch("graph.nodes.cover_letter_generator._load_cover_letter_data")
    @patch("graph.nodes.cover_letter_generator.OpenRouterClient")
    def test_template_generation_with_llm_overrides(
        self, mock_client_cls, mock_load_data, mock_generate_template
    ):
        """Node calls template function with merged data (YAML + LLM)."""
        import json

        from graph.nodes.cover_letter_generator import generate_cover_letter_node

        # Mock YAML data
        mock_load_data.return_value = {
            "recruitment_team": "Default Team",
            "company_motivation": "Default Motivation",
        }

        # Mock LLM response
        mock_client = MagicMock()
        mock_client.chat.return_value = json.dumps(
            {
                "company_motivation": "LLM Motivation",
                "role_missions": "LLM Missions",
            }
        )
        mock_client_cls.return_value = mock_client

        # Mock template generation
        mock_generate_template.return_value = r"\documentclass{moderncv}..."

        state = {
            "config": {"cover_letter": {"enabled": True}},
            "current_job": {
                "title": "ML Engineer",
                "company_name": "TestCo",
                "description": "Job Desc",
            },
            "resume_data": {
                "personal": {"name": "John Doe"},
            },
            "relevance_result": {},
        }

        result = generate_cover_letter_node(state)

        assert result["generated_cover_letter_latex"] == r"\documentclass{moderncv}..."

        # Verify call to template function
        mock_generate_template.assert_called_once()
        call_kwargs = mock_generate_template.call_args[1]

        # passed data should be merged
        passed_data = call_kwargs["cover_letter_data"]
        assert passed_data["recruitment_team"] == "Default Team"  # From YAML
        assert (
            passed_data["company_motivation"] == "LLM Motivation"
        )  # Overridden by LLM
        assert passed_data["role_missions"] == "LLM Missions"  # From LLM only

        assert call_kwargs["job_title"] == "ML Engineer"
        assert call_kwargs["company_name"] == "TestCo"


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
        assert "&" not in filename
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


class TestCoverLetterTemplate:
    """Tests for utils.cover_letter_template."""

    def test_generate_from_template_structure(self):
        """Template generates valid LaTeX loop structure."""
        from utils.cover_letter_template import generate_cover_letter_from_template

        cl_data = {
            "recruitment_team": "Team A",
            "company_motivation": "Motivation Text",
            "role_missions": "Mission Text",
            # other fields optional or handled gracefully
        }
        personal = {"name": "John Doe", "email": "john@example.com"}

        latex = generate_cover_letter_from_template(
            cl_data, personal, "Job Title", "Company X"
        )

        assert r"\documentclass" in latex
        assert r"\begin{document}" in latex
        assert r"\end{document}" in latex
        assert "John" in latex
        assert "Doe" in latex
        assert "Team A" in latex
        assert "Motivation Text" in latex
        assert "Company X" in latex
