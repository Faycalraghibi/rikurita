#!/usr/bin/env python3
"""
Rikurita - Job Application Automation System

Main entry point with CLI interface.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
import yaml
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from graph.workflow import run_workflow, create_workflow
from graph.state import create_initial_state
from graph.nodes.scheduler import load_config, load_resume_data
from utils.apify_client import ApifyJobScraper

# Load environment variables
load_dotenv()

# Configure logging
def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # File handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / "rikurita.log",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Rikurita - Automated Job Application System"""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Run without generating resumes")
@click.option("--config", "-c", type=click.Path(exists=True), default="config.yaml", help="Path to config file")
@click.option("--resume-data", "-r", type=click.Path(exists=True), default="resume_data.yaml", help="Path to resume data file")
@click.pass_context
def run(ctx: click.Context, dry_run: bool, config: str, resume_data: str) -> None:
    """Run the job application workflow once."""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Loading configuration...")
        config_data = load_config(config)
        resume_data_dict = load_resume_data(resume_data)
        
        if dry_run:
            logger.info("DRY RUN MODE - No resumes will be generated")
        
        logger.info("Starting workflow...")
        final_state = run_workflow(
            config=config_data,
            resume_data=resume_data_dict,
            dry_run=dry_run,
        )
        
        # Exit with appropriate code
        if final_state.get("errors"):
            sys.exit(1)
        sys.exit(0)
        
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Workflow failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--interval", type=click.Choice(["hourly", "daily", "weekly"]), default="daily", help="Schedule interval")
@click.option("--time", "-t", type=str, default="09:00", help="Time to run (HH:MM format)")
@click.option("--dry-run", is_flag=True, help="Run without generating resumes")
@click.pass_context
def schedule(ctx: click.Context, interval: str, time: str, dry_run: bool) -> None:
    """Run the workflow on a schedule."""
    import schedule as schedule_lib
    import time as time_module
    
    logger = logging.getLogger(__name__)
    
    def job():
        logger.info(f"Scheduled job triggered at {time}")
        try:
            config_data = load_config()
            resume_data_dict = load_resume_data()
            run_workflow(
                config=config_data,
                resume_data=resume_data_dict,
                dry_run=dry_run,
            )
        except Exception as e:
            logger.exception(f"Scheduled job failed: {e}")
    
    # Parse time
    hour, minute = time.split(":")
    time_str = f"{hour}:{minute}"
    
    if interval == "hourly":
        schedule_lib.every().hour.at(f":{minute}").do(job)
        logger.info(f"Scheduled to run every hour at :{minute}")
    elif interval == "daily":
        schedule_lib.every().day.at(time_str).do(job)
        logger.info(f"Scheduled to run daily at {time_str}")
    elif interval == "weekly":
        schedule_lib.every().monday.at(time_str).do(job)
        logger.info(f"Scheduled to run every Monday at {time_str}")
    
    logger.info("Press Ctrl+C to stop the scheduler")
    
    try:
        while True:
            schedule_lib.run_pending()
            time_module.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")


@cli.command()
@click.argument("job_url")
@click.option("--dry-run", is_flag=True, help="Run without generating resume")
@click.pass_context
def test_job(ctx: click.Context, job_url: str, dry_run: bool) -> None:
    """Test the workflow with a specific job URL."""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Testing with job URL: {job_url}")
        
        # Fetch job details
        scraper = ApifyJobScraper()
        job = scraper.get_job_details(job_url)
        
        if not job:
            logger.error("Failed to fetch job details")
            sys.exit(1)
        
        logger.info(f"Job: {job.title} at {job.company_name}")
        logger.info(f"Description: {job.description[:200]}...")
        
        # Load config and resume data
        config_data = load_config()
        resume_data_dict = load_resume_data()
        
        # Create initial state with the fetched job
        from graph.state import create_initial_state
        initial_state = create_initial_state(
            config=config_data,
            resume_data=resume_data_dict,
            dry_run=dry_run,
        )
        initial_state["all_jobs"] = [job.to_dict()]
        initial_state["total_jobs"] = 1
        
        # Create and run workflow
        workflow = create_workflow()
        final_state = workflow.invoke(initial_state)
        
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def check_config(ctx: click.Context) -> None:
    """Validate configuration files."""
    logger = logging.getLogger(__name__)
    
    errors = []
    
    # Check config.yaml
    try:
        config = load_config()
        logger.info("✓ config.yaml loaded successfully")
        
        # Check required fields
        if not config.get("job_search", {}).get("keywords"):
            errors.append("Missing job_search.keywords in config.yaml")
        if not config.get("user_profile"):
            logger.warning("⚠ user_profile not configured - relevance checking may be inaccurate")
            
    except FileNotFoundError:
        errors.append("config.yaml not found")
    except Exception as e:
        errors.append(f"config.yaml error: {e}")
    
    # Check resume_data.yaml
    try:
        resume_data = load_resume_data()
        logger.info("✓ resume_data.yaml loaded successfully")
    except FileNotFoundError:
        errors.append("resume_data.yaml not found")
    except Exception as e:
        errors.append(f"resume_data.yaml error: {e}")
    
    # Check .env
    import os
    if not os.getenv("OPENROUTER_API_KEY"):
        errors.append("OPENROUTER_API_KEY not set in .env")
    else:
        logger.info("✓ OPENROUTER_API_KEY configured")
        
    if not os.getenv("APIFY_API_TOKEN"):
        errors.append("APIFY_API_TOKEN not set in .env")
    else:
        logger.info("✓ APIFY_API_TOKEN configured")
    
    if not os.getenv("GOOGLE_SHEET_ID"):
        logger.info("ℹ Google Sheets not configured - using local CSV tracking (applications.csv)")
    else:
        logger.info("✓ GOOGLE_SHEET_ID configured")
    
    # Check LaTeX compiler
    import shutil
    if shutil.which("pdflatex"):
        logger.info("✓ pdflatex found")
    elif shutil.which("latexmk"):
        logger.info("✓ latexmk found")
    else:
        logger.warning("⚠ No LaTeX compiler found - resumes will be saved as .tex only")
        logger.warning("  Install MiKTeX or TeX Live to enable PDF compilation")
    
    # Summary
    if errors:
        logger.error("\n✗ Configuration errors found:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)
    else:
        logger.info("\n✓ All configuration checks passed!")


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize project with example configuration files."""
    logger = logging.getLogger(__name__)
    
    # Create directories
    dirs = ["resumes", "logs", "templates", "credentials"]
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
        logger.info(f"Created directory: {dir_name}/")
    
    # Create .env from .env.example if it doesn't exist
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        import shutil
        shutil.copy(env_example, env_file)
        logger.info("Created .env from .env.example")
        logger.warning("⚠ Remember to add your API keys to .env!")
    
    # Copy base resume template if it doesn't exist
    template_src = Path("main.tex")
    template_dst = Path("templates/base_resume.tex")
    
    if template_src.exists() and not template_dst.exists():
        import shutil
        shutil.copy(template_src, template_dst)
        logger.info(f"Copied {template_src} to {template_dst}")
    
    logger.info("\n✓ Project initialized!")
    logger.info("\nNext steps:")
    logger.info("1. Add your API keys to .env")
    logger.info("2. Review and customize config.yaml")
    logger.info("3. Update resume_data.yaml with your information")
    logger.info("4. Run: python main.py check-config")
    logger.info("5. Run: python main.py run --dry-run")


if __name__ == "__main__":
    cli()
