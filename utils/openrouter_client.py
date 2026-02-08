"""
OpenRouter API Client

Wrapper for OpenRouter API supporting multiple LLM models with retry logic.
"""

import os
import time
import logging
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""
    
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key. Defaults to OPENROUTER_API_KEY env var.
            model: Model identifier to use for requests.
            max_retries: Maximum number of retry attempts for failed requests.
            base_delay: Base delay in seconds for exponential backoff.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable.")
        
        # Use model from parameter, env variable, or default
        self.model = model or os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
        self.max_retries = max_retries
        self.base_delay = base_delay
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/rikurita",
            "X-Title": "Rikurita Job Application System",
        }
    
    def _make_request(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> dict:
        """
        Make a request to OpenRouter API with retry logic.
        
        Args:
            messages: List of message dictionaries with role and content.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            
        Returns:
            API response as dictionary.
            
        Raises:
            requests.RequestException: If all retries fail.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.BASE_URL,
                    headers=self.headers,
                    json=payload,
                    timeout=120,
                )
                response.raise_for_status()
                return response.json()
                
            except requests.RequestException as e:
                last_exception = e
                delay = self.base_delay * (2 ** attempt)
                logger.warning(
                    f"OpenRouter request failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
        
        logger.error(f"OpenRouter request failed after {self.max_retries} attempts")
        raise last_exception
    
    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """
        Send a chat message and get a response.
        
        Args:
            prompt: User message content.
            system_prompt: Optional system message to set context.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            
        Returns:
            The assistant's response text.
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self._make_request(messages, max_tokens, temperature)
        
        return response["choices"][0]["message"]["content"]
    
    def check_job_relevance(
        self,
        job_description: str,
        user_background: dict,
        target_criteria: dict,
    ) -> dict:
        """
        Analyze job relevance using LLM.
        
        Args:
            job_description: Full job description text.
            user_background: User's background information.
            target_criteria: User's job search criteria.
            
        Returns:
            Dictionary with relevance_score (0-10), reasoning, and matching_points.
        """
        system_prompt = """You are an expert career advisor analyzing job fit.
Evaluate the job description against the candidate's background and criteria.
Return your analysis in the following exact JSON format:
{
    "relevance_score": <number 0-10>,
    "reasoning": "<explanation of the score>",
    "matching_points": ["<key matching point 1>", "<key matching point 2>", ...],
    "missing_requirements": ["<missing requirement 1>", ...]
}

Score guidelines:
- 9-10: Perfect match, meets all requirements
- 7-8: Strong match, meets most requirements
- 5-6: Partial match, some gaps
- 3-4: Weak match, significant gaps
- 0-2: Poor match, not suitable

Only return valid JSON, no additional text."""

        prompt = f"""Analyze this job posting against the candidate profile:

## Job Description:
{job_description}

## Candidate Background:
{self._format_background(user_background)}

## Target Criteria:
{self._format_criteria(target_criteria)}

Provide your analysis in JSON format."""

        response = self.chat(prompt, system_prompt, temperature=0.2)
        
        # Parse JSON response
        import json
        try:
            # Try to extract JSON from response (handle potential markdown code blocks)
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            json_str = json_str.strip()
            
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse relevance response as JSON: {e}")
            return {
                "relevance_score": 0,
                "reasoning": f"Failed to parse response: {response[:200]}",
                "matching_points": [],
                "missing_requirements": [],
            }
    
    def generate_customized_resume(
        self,
        resume_data: dict,
        job_description: str,
        company_name: str,
        job_title: str,
        matching_points: list[str],
    ) -> str:
        """
        Generate a customized LaTeX resume.
        
        Args:
            resume_data: Structured resume data from YAML.
            job_description: Job description to tailor resume for.
            company_name: Target company name.
            job_title: Target job title.
            matching_points: Key points that match between resume and job.
            
        Returns:
            Complete LaTeX code for the customized resume.
        """
        system_prompt = """You are an expert resume writer creating tailored LaTeX resumes.
Generate a complete, compilable LaTeX resume customized for the specific job.

Guidelines:
1. Use the provided LaTeX template structure exactly
2. Emphasize experiences and skills that match the job requirements
3. Naturally integrate keywords from the job description
4. Reorder bullet points to highlight most relevant achievements first
5. Adapt the professional summary to align with the role
6. Keep the resume to one page
7. Return ONLY valid LaTeX code, no explanations

The LaTeX code must compile without errors using pdflatex."""

        prompt = f"""Create a customized resume for this application:

## Target Position:
- Company: {company_name}
- Role: {job_title}

## Job Description:
{job_description}

## Key Matching Points to Emphasize:
{chr(10).join(f'- {point}' for point in matching_points)}

## Resume Data:
{self._format_resume_data(resume_data)}

## LaTeX Template Structure:
Use this exact structure and formatting:

\\documentclass[11pt,a4paper]{{article}}

\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage[margin=0.7in]{{geometry}}
\\usepackage{{enumitem}}
\\usepackage{{hyperref}}
\\usepackage{{titlesec}}

\\pagestyle{{empty}}
\\setlist[itemize]{{left=0pt, label={{--}}, nosep, after=\\vspace{{1pt}}, topsep=0pt}}
\\titleformat{{\\section}}{{\\large\\bfseries\\uppercase}}{{}}{{0em}}{{}}[\\titlerule]
\\titlespacing{{\\section}}{{0pt}}{{6pt}}{{3pt}}

\\newcommand{{\\resumeItem}}[1]{{\\item\\small{{#1}}}}
\\newcommand{{\\resumeSubheading}}[4]{{
  \\vspace{{1pt}}
  \\noindent\\textbf{{#1}} \\hfill #2 \\\\
  \\textit{{#3}} \\hfill \\textit{{#4}}
  \\vspace{{0pt}}
}}
\\newcommand{{\\resumeProjectHeading}}[2]{{
  \\vspace{{1pt}}
  \\noindent\\textbf{{#1}} \\hfill \\textit{{#2}}
  \\vspace{{0pt}}
}}

Generate the complete resume with sections: Header, Education, Certifications, Experience, Projects, Skills, Extracurricular Activities.
Customize bullet points and ordering to match the job requirements.
Return only the LaTeX code starting with \\documentclass and ending with \\end{{document}}."""

        response = self.chat(prompt, system_prompt, max_tokens=6000, temperature=0.4)
        
        # Extract LaTeX code if wrapped in markdown
        latex_code = response.strip()
        if latex_code.startswith("```"):
            parts = latex_code.split("```")
            if len(parts) >= 2:
                latex_code = parts[1]
                if latex_code.startswith("latex"):
                    latex_code = latex_code[5:]
                elif latex_code.startswith("tex"):
                    latex_code = latex_code[3:]
            latex_code = latex_code.strip()
        
        return latex_code
    
    def _format_background(self, background: dict) -> str:
        """Format background dict as readable string."""
        lines = []
        if "summary" in background:
            lines.append(f"Summary: {background['summary']}")
        if "skills" in background:
            lines.append(f"Skills: {', '.join(background['skills'])}")
        if "experience_years" in background:
            lines.append(f"Experience: {background['experience_years']} years")
        return "\n".join(lines)
    
    def _format_criteria(self, criteria: dict) -> str:
        """Format criteria dict as readable string."""
        lines = []
        if "desired_roles" in criteria:
            lines.append(f"Desired Roles: {', '.join(criteria['desired_roles'])}")
        if "desired_industries" in criteria:
            lines.append(f"Industries: {', '.join(criteria['desired_industries'])}")
        if "preferred_locations" in criteria:
            lines.append(f"Locations: {', '.join(criteria['preferred_locations'])}")
        if "deal_breakers" in criteria:
            lines.append(f"Deal Breakers: {', '.join(criteria['deal_breakers'])}")
        return "\n".join(lines)
    
    def _format_resume_data(self, data: dict) -> str:
        """Format resume data dict as readable YAML-like string."""
        import yaml
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
