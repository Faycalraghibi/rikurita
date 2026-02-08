"""
Unit Tests for Utility Modules

Tests for OpenRouter, Apify, and Google Sheets clients.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestApifyJobScraper:
    """Tests for ApifyJobScraper client."""

    @pytest.fixture
    def mock_apify_response(self):
        """Return mock Apify job listing data."""
        return [
            {
                "id": "123456",
                "link": "https://linkedin.com/jobs/view/123456",
                "title": "Machine Learning Engineer",
                "company": "TechCorp",
                "location": "Paris, France",
                "employmentType": "Full-time",
                "seniorityLevel": "Mid-Senior",
                "postedAt": "2024-01-15T10:00:00Z",
                "companyUrl": "https://techcorp.com",
                "salary": "€50,000 - €70,000",
                "description": "We are looking for an ML Engineer...",
                "applyLink": "https://techcorp.com/careers/123",
                "skills": ["Python", "TensorFlow", "AWS"],
            },
            {
                "id": "789012",
                "link": "https://linkedin.com/jobs/view/789012",
                "title": "Data Scientist Intern",
                "company": "StartupAI",
                "location": "Remote",
                "employmentType": "Internship",
                "description": "Join our data science team...",
            },
        ]

    @patch.dict(os.environ, {"APIFY_API_TOKEN": "test_token"})
    def test_parse_job_item(self, mock_apify_response):
        """Test parsing of Apify job item."""
        from utils.apify_client import ApifyJobScraper

        scraper = ApifyJobScraper()
        job = scraper._parse_job_item(mock_apify_response[0])

        assert job.job_id == "123456"
        assert job.title == "Machine Learning Engineer"
        assert job.company_name == "TechCorp"
        assert job.job_type == "Full-time"
        assert job.seniority_level == "Mid-Senior"
        assert job.location == "Paris, France"
        assert "Python" in job.required_skills

    @patch.dict(os.environ, {"APIFY_API_TOKEN": "test_token"})
    def test_parse_minimal_job_item(self, mock_apify_response):
        """Test parsing of job item with minimal data."""
        from utils.apify_client import ApifyJobScraper

        scraper = ApifyJobScraper()
        job = scraper._parse_job_item(mock_apify_response[1])

        assert job.title == "Data Scientist Intern"
        assert job.company_name == "StartupAI"
        assert job.job_type == "Internship"  # Should handle alternate field name

    @patch.dict(os.environ, {"APIFY_API_TOKEN": "test_token"})
    def test_job_to_dict(self, mock_apify_response):
        """Test JobListing to_dict method."""
        from utils.apify_client import ApifyJobScraper

        scraper = ApifyJobScraper()
        job = scraper._parse_job_item(mock_apify_response[0])
        job_dict = job.to_dict()

        assert isinstance(job_dict, dict)
        assert job_dict["title"] == "Machine Learning Engineer"
        assert job_dict["company_name"] == "TechCorp"
        assert isinstance(job_dict["required_skills"], list)


class TestOpenRouterClient:
    """Tests for OpenRouterClient."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
    def test_client_initialization(self):
        """Test client initializes with environment variable."""
        from utils.openrouter_client import OpenRouterClient

        client = OpenRouterClient()
        assert client.api_key == "test_key"
        assert "Authorization" in client.headers

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
    def test_format_background(self):
        """Test background formatting."""
        from utils.openrouter_client import OpenRouterClient

        client = OpenRouterClient()
        background = {
            "summary": "Experienced developer",
            "skills": ["Python", "ML"],
            "experience_years": 5,
        }

        formatted = client._format_background(background)

        assert "Experienced developer" in formatted
        assert "Python" in formatted
        assert "5 years" in formatted

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
    def test_format_criteria(self):
        """Test criteria formatting."""
        from utils.openrouter_client import OpenRouterClient

        client = OpenRouterClient()
        criteria = {
            "desired_roles": ["ML Engineer", "Data Scientist"],
            "preferred_locations": ["Remote", "Paris"],
        }

        formatted = client._format_criteria(criteria)

        assert "ML Engineer" in formatted
        assert "Remote" in formatted


class TestGoogleSheetsClient:
    """Tests for GoogleSheetsClient."""

    def test_column_headers(self):
        """Test expected column headers are defined."""
        from utils.sheets_client import COLUMN_HEADERS

        required_headers = [
            "Timestamp",
            "Job Post Link",
            "Job Title",
            "Company Name",
            "Relevance Score",
            "Application Status",
            "Resume Path",
        ]

        for header in required_headers:
            assert header in COLUMN_HEADERS


class TestStateSchema:
    """Tests for workflow state schema."""

    def test_job_data_dataclass(self):
        """Test JobData dataclass."""
        from graph.state import JobData

        job = JobData(
            job_id="123",
            title="ML Engineer",
            company_name="TechCorp",
        )

        assert job.job_id == "123"
        assert job.title == "ML Engineer"

        job_dict = job.to_dict()
        assert isinstance(job_dict, dict)
        assert job_dict["title"] == "ML Engineer"

    def test_job_data_from_dict(self):
        """Test JobData from_dict method."""
        from graph.state import JobData

        data = {
            "job_id": "456",
            "title": "Data Scientist",
            "company_name": "DataCo",
            "location": "Paris",
        }

        job = JobData.from_dict(data)

        assert job.job_id == "456"
        assert job.title == "Data Scientist"
        assert job.location == "Paris"

    def test_relevance_result(self):
        """Test RelevanceResult dataclass."""
        from graph.state import RelevanceResult

        result = RelevanceResult(
            score=8.5,
            reasoning="Good match",
            matching_points=["Python", "ML experience"],
        )

        assert result.is_relevant()  # Default threshold is 7
        assert result.is_relevant(threshold=8)
        assert not result.is_relevant(threshold=9)

    def test_create_initial_state(self):
        """Test initial state creation."""
        from graph.state import create_initial_state

        config = {
            "job_search": {
                "keywords": "ML engineer",
                "relevance_threshold": 8,
            }
        }
        resume_data = {"personal": {"name": "Test User"}}

        state = create_initial_state(config, resume_data, dry_run=True)

        assert state["config"] == config
        assert state["resume_data"] == resume_data
        assert state["dry_run"] is True
        assert state["relevance_threshold"] == 8
        assert state["all_jobs"] == []
        assert state["jobs_processed"] == 0


class TestApplicationStatus:
    """Tests for ApplicationStatus enum."""

    def test_status_values(self):
        """Test ApplicationStatus enum values."""
        from graph.state import ApplicationStatus

        assert ApplicationStatus.PENDING.value == "Pending"
        assert ApplicationStatus.APPLIED.value == "Applied"
        assert ApplicationStatus.SKIPPED.value == "Skipped"
        assert ApplicationStatus.FAILED.value == "Failed"
