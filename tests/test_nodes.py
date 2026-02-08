"""
Unit Tests for Workflow Nodes

Tests for individual LangGraph workflow nodes.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSchedulerNode:
    """Tests for scheduler node."""
    
    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock config file."""
        config_content = """
user_profile:
  name: "Test User"
  background:
    summary: "Test summary"
    skills: ["Python", "ML"]
job_search:
  keywords: "ML engineer"
  location: "Paris"
  relevance_threshold: 7
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        return str(config_file)
    
    @pytest.fixture
    def mock_resume_data(self, tmp_path):
        """Create a mock resume data file."""
        resume_content = """
personal:
  name: "Test User"
  email: "test@example.com"
experience:
  - company: "TestCo"
    role: "Developer"
"""
        resume_file = tmp_path / "resume_data.yaml"
        resume_file.write_text(resume_content)
        return str(resume_file)
    
    def test_load_config(self, mock_config):
        """Test config loading."""
        from graph.nodes.scheduler import load_config
        
        config = load_config(mock_config)
        
        assert config["user_profile"]["name"] == "Test User"
        assert config["job_search"]["keywords"] == "ML engineer"
    
    def test_load_config_not_found(self):
        """Test config loading with missing file."""
        from graph.nodes.scheduler import load_config
        
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")
    
    def test_scheduler_node(self, mock_config, mock_resume_data):
        """Test scheduler node execution."""
        from graph.nodes.scheduler import scheduler_node, load_config, load_resume_data
        
        config = load_config(mock_config)
        resume = load_resume_data(mock_resume_data)
        
        state = {
            "config": config,
            "resume_data": resume,
            "dry_run": False,
        }
        
        result = scheduler_node(state)
        
        assert result["should_continue"] is True
        assert result["relevance_threshold"] == 7


class TestRelevanceCheckNode:
    """Tests for relevance check node."""
    
    @pytest.fixture
    def mock_state(self):
        """Create mock workflow state."""
        return {
            "current_job": {
                "title": "ML Engineer",
                "company_name": "TechCorp",
                "description": "Looking for ML Engineer with Python skills...",
            },
            "config": {
                "user_profile": {
                    "background": {
                        "summary": "ML Engineer",
                        "skills": ["Python", "TensorFlow"],
                    },
                    "target_criteria": {
                        "desired_roles": ["ML Engineer"],
                    },
                },
                "llm_settings": {
                    "model": "anthropic/claude-3.5-sonnet",
                },
            },
            "relevance_threshold": 7,
            "jobs_relevant": 0,
            "jobs_skipped": 0,
        }
    
    def test_should_process_job_relevant(self):
        """Test routing for relevant job."""
        from graph.nodes.relevance_check import should_process_job
        
        state = {"is_relevant": True, "dry_run": False}
        result = should_process_job(state)
        
        assert result == "generate_resume"
    
    def test_should_process_job_not_relevant(self):
        """Test routing for non-relevant job."""
        from graph.nodes.relevance_check import should_process_job
        
        state = {"is_relevant": False, "dry_run": False}
        result = should_process_job(state)
        
        assert result == "next_job"
    
    def test_should_process_job_dry_run(self):
        """Test routing in dry run mode."""
        from graph.nodes.relevance_check import should_process_job
        
        state = {"is_relevant": True, "dry_run": True}
        result = should_process_job(state)
        
        assert result == "log_to_sheets"
    
    def test_no_description_skips(self):
        """Test that jobs without description are skipped."""
        from graph.nodes.relevance_check import check_relevance_node
        
        state = {
            "current_job": {
                "title": "Test Job",
                "company_name": "TestCo",
                "description": "",  # Empty description
            },
            "jobs_skipped": 0,
        }
        
        result = check_relevance_node(state)
        
        assert result["is_relevant"] is False
        assert result["jobs_skipped"] == 1


class TestApifyScraperNode:
    """Tests for Apify scraper node."""
    
    def test_get_next_job_node(self):
        """Test getting next job from list."""
        from graph.nodes.apify_scraper import get_next_job_node
        
        jobs = [
            {"title": "Job 1", "company_name": "Co1"},
            {"title": "Job 2", "company_name": "Co2"},
        ]
        
        state = {
            "all_jobs": jobs,
            "current_job_index": 0,
        }
        
        result = get_next_job_node(state)
        
        assert result["current_job"]["title"] == "Job 1"
        assert result["current_job_index"] == 1
        assert result["should_continue"] is True
    
    def test_get_next_job_node_end(self):
        """Test behavior when all jobs processed."""
        from graph.nodes.apify_scraper import get_next_job_node
        
        state = {
            "all_jobs": [{"title": "Job 1"}],
            "current_job_index": 1,  # Already past the list
        }
        
        result = get_next_job_node(state)
        
        assert result["current_job"] is None
        assert result["should_continue"] is False
        assert result["workflow_complete"] is True


class TestWorkflow:
    """Tests for workflow routing functions."""
    
    def test_should_continue_processing_yes(self):
        """Test continue processing when jobs remain."""
        from graph.workflow import should_continue_processing
        
        state = {
            "should_continue": True,
            "workflow_complete": False,
            "current_job_index": 5,
            "total_jobs": 10,
        }
        
        result = should_continue_processing(state)
        assert result == "get_next_job"
    
    def test_should_continue_processing_no(self):
        """Test stop processing when complete."""
        from graph.workflow import should_continue_processing
        
        state = {
            "should_continue": True,
            "workflow_complete": False,
            "current_job_index": 10,
            "total_jobs": 10,
        }
        
        result = should_continue_processing(state)
        assert result == "end"
    
    def test_route_after_relevance_not_relevant(self):
        """Test routing for non-relevant job."""
        from graph.workflow import route_after_relevance
        
        state = {"is_relevant": False, "dry_run": False}
        result = route_after_relevance(state)
        
        assert result == "log_skipped"
    
    def test_route_after_relevance_relevant(self):
        """Test routing for relevant job."""
        from graph.workflow import route_after_relevance
        
        state = {"is_relevant": True, "dry_run": False}
        result = route_after_relevance(state)
        
        assert result == "generate_resume"
    
    def test_route_after_relevance_dry_run(self):
        """Test routing in dry run mode."""
        from graph.workflow import route_after_relevance
        
        state = {"is_relevant": True, "dry_run": True}
        result = route_after_relevance(state)
        
        assert result == "log_skipped"
