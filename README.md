# Rikurita 🚀

**Automated Job Application System** - A LangGraph-powered workflow that scrapes LinkedIn jobs via Apify, evaluates job relevance using AI, generates customized LaTeX resumes, and tracks applications in Google Sheets.

## Features

- 🔍 **Automated Job Scraping** - Fetches jobs from LinkedIn via Apify API
- 🤖 **AI-Powered Relevance Filtering** - Uses LLMs to score job fit (0-10)
- 📄 **Customized Resume Generation** - Creates tailored LaTeX resumes for each position
- 📊 **Google Sheets Tracking** - Logs all applications with full metadata
- 🗂️ **Organized File Structure** - Saves resumes in `resumes/{company}/{role}/` format
- ⏰ **Scheduling Support** - Run once, on schedule, or test with specific jobs
- 🔄 **Retry Logic** - Exponential backoff for API calls

## Quick Start

### 1. Create Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example env file
copy .env.example .env

# Edit .env with your API keys
```

Required API keys:
- `OPENROUTER_API_KEY` - Get from [OpenRouter](https://openrouter.ai/)
- `APIFY_API_TOKEN` - Get from [Apify](https://apify.com/)
- `GOOGLE_SHEET_ID` - Your Google Sheet ID for tracking

### 4. Initialize Project

```bash
python main.py init
```

This creates required directories and copies templates.

### 5. Validate Configuration

```bash
python main.py check-config
```

### 6. Run Workflow

```bash
# Dry run (no resumes generated)
python main.py run --dry-run

# Full run
python main.py run

# Test with specific job
python main.py test-job <linkedin-job-url>

# Run on schedule
python main.py schedule --interval daily --time 09:00
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python main.py run` | Run workflow once |
| `python main.py run --dry-run` | Dry run without generating resumes |
| `python main.py schedule --interval daily` | Run on schedule (hourly/daily/weekly) |
| `python main.py test-job <url>` | Test with a specific LinkedIn job URL |
| `python main.py check-config` | Validate all configuration files |
| `python main.py init` | Initialize project structure |

## Project Structure

```
rikurita/
├── main.py                 # CLI entry point
├── config.yaml             # User configuration
├── resume_data.yaml        # Your resume data
├── .env                    # API keys (create from .env.example)
├── graph/
│   ├── workflow.py         # LangGraph workflow definition
│   ├── state.py            # State schema
│   └── nodes/              # Workflow nodes
│       ├── scheduler.py
│       ├── apify_scraper.py
│       ├── relevance_check.py
│       ├── resume_generator.py
│       ├── latex_compiler.py
│       └── sheets_logger.py
├── utils/
│   ├── openrouter_client.py
│   ├── apify_client.py
│   └── sheets_client.py
├── templates/
│   └── base_resume.tex
├── resumes/                # Generated resumes
│   └── {Company}/
│       └── {Role}/
│           ├── resume_{company}_{role}_{date}.pdf
│           └── resume_{company}_{role}_{date}.tex
└── logs/                   # Application logs
```

## Configuration

### config.yaml

```yaml
user_profile:
  name: "Your Name"
  background:
    summary: "Your professional summary"
    skills: ["Python", "ML", "Data Science"]
  target_criteria:
    desired_roles: ["Data Scientist", "ML Engineer"]
    preferred_locations: ["Remote", "Paris"]

job_search:
  keywords: "machine learning engineer intern"
  location: "france"
  max_jobs_per_run: 50
  relevance_threshold: 7  # Minimum score to generate resume

llm_settings:
  model: "anthropic/claude-3.5-sonnet"
```

### resume_data.yaml

Contains your structured resume data (experience, education, skills, projects) that the LLM uses to generate customized resumes.

## Google Sheets Tracking

The workflow logs applications with these columns:

| Column | Description |
|--------|-------------|
| Timestamp | When logged |
| Job Post Link | LinkedIn URL |
| Job Title | Position title |
| Job Type | Full-time, Part-time, etc. |
| Seniority Level | Entry, Mid-Senior, etc. |
| Posted At | When job was posted |
| Company Name | Company |
| Company Website | Company URL |
| Salary | Compensation info |
| Description | Job description |
| Resume Path | Local path to PDF |
| Application URL | Apply link |
| Relevance Score | 0-10 LLM score |
| Application Status | Applied/Pending/Skipped |
| Notes | Match reasoning |

## Google Sheets Setup

1. Create a new Google Sheet
2. Enable Google Sheets API in [Google Cloud Console](https://console.cloud.google.com/)
3. Create a service account and download credentials JSON
4. Share the sheet with the service account email
5. Set `GOOGLE_SHEETS_CREDENTIALS_PATH` and `GOOGLE_SHEET_ID` in `.env`

## Requirements

- Python 3.10+
- pdflatex or latexmk (for resume compilation)
- Internet connection for API calls

## Workflow Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Scheduler  │────▶│ Fetch Jobs  │────▶│  Get Next   │
│   (Start)   │     │   (Apify)   │     │    Job      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┘
                    ▼
              ┌─────────────┐
              │   Check     │
              │ Relevance   │
              │  (LLM)      │
              └──────┬──────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
   [Score ≥ 7]              [Score < 7]
         │                       │
         ▼                       ▼
  ┌─────────────┐         ┌─────────────┐
  │  Generate   │         │    Log      │
  │   Resume    │         │  Skipped    │
  │   (LLM)     │         └──────┬──────┘
  └──────┬──────┘                │
         │                       │
         ▼                       │
  ┌─────────────┐                │
  │  Compile    │                │
  │   LaTeX     │                │
  └──────┬──────┘                │
         │                       │
         ▼                       │
  ┌─────────────┐                │
  │   Log to    │◀───────────────┘
  │   Sheets    │
  └──────┬──────┘
         │
         ▼
   [More jobs?]────Yes────▶ Get Next Job
         │
         No
         │
         ▼
  ┌─────────────┐
  │   Print     │
  │  Summary    │
  └─────────────┘
```

## Troubleshooting

### LaTeX compilation fails
- Ensure pdflatex or latexmk is installed
- Check the saved .tex file for syntax errors
- Run `python main.py check-config` to verify setup

### Apify returns no jobs
- Check your APIFY_API_TOKEN
- Verify the LinkedIn Jobs Scraper actor is available
- Try adjusting search keywords or location

### Google Sheets not logging
- Verify service account has access to the sheet
- Check credentials path in .env
- Ensure Google Sheets API is enabled

## License

MIT
