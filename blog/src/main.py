"""
FastAPI application entry point.
Initializes database, mounts routes, and starts the APScheduler background scheduler.
"""
import os
import logging

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.exceptions import HTTPException
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

from . import database as db
from .routes import router, templates
from .branding import LOGO_SVG, FAVICON_SVG, ALL_CATEGORIES
from .analytics import get_ga_script
from .seo import get_site_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Dollar Draft",
    description="AI-powered personal finance publishing platform",
    docs_url=None,
    redoc_url=None,
)

app.include_router(router)

_scheduler: BackgroundScheduler | None = None


# ─── Startup / shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("Dollar Draft starting up…")

    # Database
    try:
        db.init_db()
        count = db.get_article_count()
        logger.info(f"Database ready — {count} articles published")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Don't crash the process — scheduler and web server still run

    # Scheduler
    global _scheduler
    scheduler_enabled = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"
    if scheduler_enabled and _scheduler is None:
        _start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def _start_scheduler():
    global _scheduler
    from .bot import run_bot

    publish_hour = int(os.environ.get("PUBLISH_HOUR_UTC", "14"))
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_bot,
        trigger="cron",
        hour=publish_hour,
        minute=0,
        id="daily_publish",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    _scheduler.start()

    # Log next scheduled run
    jobs = _scheduler.get_jobs()
    if jobs:
        next_run = jobs[0].next_run_time
        logger.info(f"Scheduler active — next run at {next_run} UTC (hour={publish_hour}:00)")
    else:
        logger.info(f"Scheduler active — daily at {publish_hour}:00 UTC")


# ─── Error handlers ───────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    ctx = {
        "request": request,
        "site_name": os.environ.get("SITE_NAME", "Dollar Draft"),
        "site_tagline": os.environ.get("SITE_TAGLINE", "Personal finance, simplified daily."),
        "site_url": get_site_url(),
        "ga_script": get_ga_script(),
        "logo_svg": LOGO_SVG,
        "favicon_svg": FAVICON_SVG,
        "all_categories": ALL_CATEGORIES,
        "contact_email": os.environ.get("CONTACT_EMAIL", ""),
        "current_year": 2025,
        "page_title": "Page Not Found — Dollar Draft",
    }
    return templates.TemplateResponse("404.html", ctx, status_code=404)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url}: {exc}")
    return HTMLResponse(
        content="<h1>Something went wrong.</h1><p>Please try again shortly.</p>",
        status_code=500,
    )
