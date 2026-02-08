# Rikurita

Automated job application system. Scrapes LinkedIn jobs via Apify, filters by relevance, generates tailored LaTeX resumes, and logs to CSV/Google Sheets.

## Setup

```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:
```
APIFY_API_TOKEN=your-token
LLM_BASE_URL=https://openrouter.ai/api/v1/chat/completions
LLM_MODEL=anthropic/claude-3-haiku
OPENROUTER_API_KEY=your-key
```

Optional LLM fallback (tries primary first, then fallback):
```
LLM_BASE_URL=http://localhost:1234/v1/chat/completions
LLM_MODEL=local-model
LLM_BASE_URL_FALLBACK=https://openrouter.ai/api/v1/chat/completions
LLM_MODEL_FALLBACK=anthropic/claude-3-haiku
```

Edit `config.yaml` with your job search settings.
Edit `templates/resume_data.yaml` with your resume content.

## Usage

```bash
python main.py init           # Create directories
python main.py check-config   # Validate setup
python main.py run            # Run workflow
python main.py run --dry-run  # Test without generating resumes
python main.py test-job <url> # Test single job URL
```

## Project Structure

```
config.yaml                    # Job search settings
templates/resume_data.yaml     # Your resume data
.env                           # API keys
graph/nodes/                   # Workflow nodes
utils/                         # API clients
track/
  applications.csv             # Application log
  resumes/{Company}/{Role}/    # Generated PDFs
```

## Configuration

`config.yaml`:
- `job_search.keywords` - LinkedIn search query
- `job_search.location` - Location filter
- `job_search.max_jobs_per_run` - Limit per run
- `job_search.relevance_threshold` - Min score (0-10) to generate resume

`templates/resume_data.yaml`:
- Personal info, education, experience, projects, skills
- Used by LLM to tailor resumes for each job

## Requirements

- Python 3.10+
- pdflatex or latexmk
- Apify account (LinkedIn scraping)
- OpenRouter API key or local LLM

## Troubleshooting

LaTeX fails: Check `track/resumes/**/*.tex` for syntax errors.
No jobs: Verify `APIFY_API_TOKEN` and search keywords.
LLM fails: Check `LLM_BASE_URL` and API key in `.env`.
