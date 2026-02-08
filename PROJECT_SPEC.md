# PROJECT SPECIFICATION: Rikurita - Job Application Automation System

## Project Overview
Build an automated job application system called **Rikurita** using LangGraph that scrapes LinkedIn jobs via Apify, checks relevance using an LLM, customizes resumes in LaTeX format, and tracks applications in Google Sheets.

**Project Name**: rikurita
**Python Environment**: Use a virtual environment (venv) for dependency isolation

## Technical Stack Requirements
- **Framework**: LangGraph (Python)
- **LLM Provider**: OpenRouter API (support multiple models)
- **Job Scraping**: Apify API (LinkedIn Jobs Actor)
- **Resume Format**: LaTeX (compiled to PDF)
- **Database**: Google Sheets API
- **Scheduling**: Python schedule library or cron-compatible trigger

## Workflow Architecture

### Node 1: Schedule Trigger
- Create a triggerable entry point for the workflow
- Support both manual execution and scheduled runs (configurable interval)
- Accept configuration parameters (job search criteria, target roles, locations)

### Node 2: Fetch Jobs (Apify Integration)
- Connect to Apify API using LinkedIn Jobs scraper
- Input parameters:
  - Job title/keywords
  - Location
  - Experience level
  - Date posted (last 24h/week)
  - Number of results (default: 100)
- Output: Structured job listings with:
  - **Job post link** (LinkedIn URL)
  - **Job title**
  - **Job type** (Full-time, Part-time, Contract, Internship)
  - **Seniority level** (Entry level, Mid-Senior, Director, Executive)
  - **Posted at** (date/time when job was posted)
  - **Company name**
  - **Company website** (if available)
  - **Salary** (range or specific amount, if disclosed)
  - **Job description** (full text)
  - **Application URL** (direct apply link if different from post link)
  - Location
  - Required skills

### Node 3: Loop Over Jobs
- Iterate through each job listing from Apify
- Maintain state for processed vs unprocessed jobs
- Track progress through the list

### Node 4: Check Job Relevance (LLM Filter)
- Use OpenRouter API to analyze job fit
- Prompt the LLM with:
  - User's resume/background (from config file)
  - User's target criteria (desired skills, industries, seniority)
  - Job description
- LLM should return:
  - Relevance score (0-10)
  - Match reasoning
  - Key matching points
  - Threshold: Only proceed if score ≥ 7

### Node 5: Filter Node
- Conditional branch based on relevance score
- If relevant (≥7): proceed to customization
- If not relevant: log and skip to next job

### Node 6: Customize Resume (LLM + LaTeX)
- Use OpenRouter API to generate tailored resume
- Provide LLM with:
  - Base resume content (JSON/YAML format)
  - Job description
  - Company information
  - Keywords to emphasize
- LLM outputs:
  - Customized LaTeX resume code
  - Tailored summary/objective
  - Reordered/emphasized relevant experience
  - Keywords from job description naturally integrated

### Node 7: Format & Compile LaTeX
- Take LaTeX code from LLM
- Validate LaTeX syntax
- Compile to PDF using pdflatex or similar
- Handle compilation errors gracefully
- **File Organization Structure**:
  ```
  resumes/
  ├── {company_name}/
  │   └── {role_title}/
  │       ├── resume_{company}_{role}_{date}.pdf
  │       └── resume_{company}_{role}_{date}.tex
  ```
- Naming convention: `resume_{company}_{role}_{date}.pdf`
- Create company folder if it doesn't exist
- Create role folder inside company folder if it doesn't exist
- Store both .tex source and compiled .pdf in the role-specific folder

### Node 8: Create Public Link (Optional)
- Upload PDF to cloud storage (Google Drive or similar)
- Generate shareable link
- Return link for application submission

### Node 9: Add to Google Sheets Database
- Connect to Google Sheets API
- Log each application with columns:
  - **Timestamp** (date/time of application submission)
  - **Job Post Link** (LinkedIn job URL)
  - **Job Title**
  - **Job Type** (Full-time, Part-time, Contract, Internship)
  - **Seniority Level** (Entry level, Mid-Senior, Director, Executive)
  - **Posted At** (when job was originally posted)
  - **Company Name**
  - **Company Website**
  - **Salary** (range or amount)
  - **Description** (truncated or full text)
  - **Resume Path** (local file path: `resumes/{company}/{role}/resume_{company}_{role}_{date}.pdf`)
  - **Application URL** (direct apply link)
  - **Relevance Score** (0-10 from LLM)
  - **Application Status** (Applied/Pending/Skipped)
  - **Notes/Match Reasoning** (LLM's explanation of relevance)

## Configuration Requirements

### Environment Variables (.env)
```
OPENROUTER_API_KEY=your_key_here
APIFY_API_TOKEN=your_token_here
GOOGLE_SHEETS_CREDENTIALS_PATH=path/to/credentials.json
GOOGLE_SHEET_ID=your_sheet_id
```

### User Configuration File (config.yaml)
```yaml
user_profile:
  name: "Your Name"
  email: "email@example.com"
  phone: "+1234567890"
  linkedin: "linkedin.com/in/yourprofile"

  background:
    summary: "Your professional summary"
    skills: ["Python", "ML", "Data Science"]
    experience_years: 5

  target_criteria:
    desired_roles: ["Data Scientist", "ML Engineer"]
    desired_industries: ["Tech", "Finance"]
    minimum_salary: 100000
    preferred_locations: ["Remote", "New York", "San Francisco"]
    deal_breakers: ["No visa sponsorship", "Required relocation"]

job_search:
  keywords: "machine learning engineerintern"
  location: "france"
  experience_level: "intern"
  max_jobs_per_run: 50

resume_template:
  base_latex_file: "templates/base_resume.tex"
  style: "modern"  # modern, classic, academic
```

### Base Resume Data (resume_data.yaml)
```yaml
personal:
  name: "Your Name"
  title: "Your Title"
  email: "email@example.com"

experience:
  - company: "Company A"
    role: "Senior Engineer"
    dates: "2020-2024"
    achievements:
      - "Achievement 1"
      - "Achievement 2"

education:
  - degree: "Master of Science"
    institution: "University Name"
    year: 2020

skills:
  technical: ["Python", "TensorFlow", "AWS"]
  soft: ["Leadership", "Communication"]
```

## Code Structure

```
rikurita/                      # Project root
├── venv/                      # Virtual environment (create with: python -m venv venv)
├── README.md
├── requirements.txt
├── .env.example
├── config.yaml
├── resume_data.yaml
├── main.py                    # Entry point
├── graph/
│   ├── __init__.py
│   ├── workflow.py           # LangGraph workflow definition
│   ├── state.py              # State schema
│   └── nodes/
│       ├── __init__.py
│       ├── scheduler.py      # Scheduling logic
│       ├── apify_scraper.py  # Job fetching
│       ├── relevance_check.py # LLM filtering
│       ├── resume_generator.py # LaTeX generation
│       ├── latex_compiler.py  # PDF compilation
│       └── sheets_logger.py   # Database logging
├── templates/
│   └── base_resume.tex       # LaTeX template
├── utils/
│   ├── __init__.py
│   ├── openrouter_client.py  # OpenRouter API wrapper
│   ├── apify_client.py       # Apify API wrapper
│   └── sheets_client.py      # Google Sheets wrapper
└── resumes/                   # Generated resumes organized by company/role
    ├── Google/
    │   ├── Software_Engineer/
    │   │   ├── resume_Google_Software_Engineer_2024-01-15.pdf
    │   │   └── resume_Google_Software_Engineer_2024-01-15.tex
    │   └── ML_Engineer/
    │       ├── resume_Google_ML_Engineer_2024-01-16.pdf
    │       └── resume_Google_ML_Engineer_2024-01-16.tex
    └── Meta/
        └── Data_Scientist/
            ├── resume_Meta_Data_Scientist_2024-01-15.pdf
            └── resume_Meta_Data_Scientist_2024-01-15.tex
```

## Key Implementation Requirements

1. **State Management**: Define a comprehensive state schema that tracks:
   - Current job being processed with all fields:
     - Job post link, title, type, seniority level, posted at
     - Company name, website, salary
     - Description, application URL
   - All jobs list (array of job objects)
   - Relevance scores and reasoning
   - Generated resume paths (with company/role folder structure)
   - Application statuses
   - Tracking metadata for Google Sheets insertion

2. **File Organization**:
   - Implement automatic folder creation for `resumes/{company}/{role}/`
   - Sanitize company and role names for filesystem compatibility (remove special characters, replace spaces with underscores)
   - Handle duplicate applications to same company/role (append timestamp or version number)
   - Store both .tex source and .pdf compiled files in the same folder

3. **Error Handling**:
   - Retry logic for API calls (exponential backoff)
   - Graceful degradation if LaTeX compilation fails
   - Logging of all errors to file
   - Continue processing remaining jobs even if one fails
   - Handle filesystem errors (permissions, disk space, invalid characters)

4. **Rate Limiting**:
   - Respect Apify API rate limits
   - Add delays between OpenRouter calls if needed
   - Batch Google Sheets updates to minimize API calls

5. **Observability**:
   - Detailed logging at each node
   - Progress indicators
   - Summary report at end of run (jobs processed, applications created)
   - Log the full file path of each generated resume

6. **Testing**:
   - Unit tests for each node
   - Integration test with mock APIs
   - Test LaTeX compilation with sample data
   - Test folder creation and file naming logic

7. **CLI Interface**:
```bash
# Run workflow once
python main.py --run-once

# Run on schedule
python main.py --schedule daily

# Test with specific job URL
python main.py --test-job <url>

# Dry run (no actual applications)
python main.py --dry-run
```

## Package Management

### Core Dependencies (requirements.txt)
```
langgraph>=0.0.1
langchain>=0.1.0
langchain-core>=0.1.0
requests>=2.31.0
python-dotenv>=1.0.0
pyyaml>=6.0
gspread>=5.11.0
oauth2client>=4.1.3
apify-client>=1.5.0
python-dateutil>=2.8.2
schedule>=1.2.0
```

### System Dependencies
- pdflatex (TeX Live or MiKTeX)
- Python 3.10+

## Deliverables

1. Complete working code following the structure above
2. **Virtual Environment Setup**:
   - Include instructions to create venv: `python -m venv venv`
   - Activation instructions for different OS (Windows/Linux/Mac)
   - All dependencies installable via `pip install -r requirements.txt`
3. README with:
   - Setup instructions (including venv setup)
   - API key configuration steps
   - Usage examples
   - Troubleshooting guide
   - Explanation of resume folder structure
   - Google Sheets column headers reference
4. requirements.txt with all dependencies
5. Example config files (.env.example, config.yaml.example)
6. Sample LaTeX resume template
7. Unit tests for critical functions
8. Ensure `resumes/` folder structure is automatically created on first run

## Additional Features (Nice to Have)

- Email notifications when high-relevance jobs are found
- Web dashboard to view application pipeline
- Support for multiple resume versions (technical vs managerial)
- A/B testing different resume formats
- Integration with application tracking systems
- Cover letter generation
- Automatic follow-up scheduling

## Success Criteria

- Workflow successfully fetches 50+ jobs from Apify
- All job data fields are correctly extracted and tracked:
  - Job post link, title, type, seniority, posted date
  - Company name, website, salary
  - Description, application URL
- LLM accurately filters relevant jobs (manual verification of 10 samples)
- LaTeX resumes compile without errors
- All applications logged to Google Sheets correctly with all required columns
- Resume files properly organized in `resumes/{company}/{role}/` structure
- System runs for 1 week without crashes
- Generated resumes are professional and tailored

## Notes

- Prioritize code quality and maintainability
- Use type hints throughout
- Follow PEP 8 style guide
- Include docstrings for all functions
- Make the system modular so components can be swapped (e.g., different LLM providers)
- Ensure all job data fields are preserved throughout the workflow and logged to Google Sheets
