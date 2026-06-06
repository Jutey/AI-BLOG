"""
All HTTP routes — public pages, SEO files, health check, and admin panel.
All database calls are wrapped with try/except so the site stays up
even when the database is unavailable or not yet configured.
"""
import os
import math
import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import Response, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from . import database as db
from .seo import (
    get_site_url, format_date_display, format_date_iso,
    article_json_ld, organization_json_ld, website_json_ld,
)
from .analytics import get_ga_script, get_adsense_script
from .branding import LOGO_SVG, FAVICON_SVG, ALL_CATEGORIES, get_category_css_class, get_category_style
from . import bot

logger = logging.getLogger(__name__)

router = APIRouter()

_templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=_templates_dir)

# ─── Jinja2 filters ──────────────────────────────────────────────────────────

templates.env.filters["format_date"] = format_date_display
templates.env.filters["format_iso"] = format_date_iso
templates.env.filters["category_class"] = get_category_css_class
templates.env.filters["category_style"] = get_category_style


# ─── Safe DB helper ───────────────────────────────────────────────────────────

def _safe_db(fn, *args, default=None, **kwargs):
    """Call a database function and return default on any error."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning(f"DB call {fn.__name__} failed: {e}")
        return default


# ─── Context builder ─────────────────────────────────────────────────────────

def _base_ctx(request: Request) -> dict:
    """Common context injected into every template."""
    return {
        "request": request,
        "site_name": os.environ.get("SITE_NAME", "Dollar Draft"),
        "site_tagline": os.environ.get("SITE_TAGLINE", "Personal finance, simplified daily."),
        "site_url": get_site_url(),
        "contact_email": os.environ.get("CONTACT_EMAIL", ""),
        "ga_script": get_ga_script(),
        "adsense_script": get_adsense_script(),
        "adsense_client": os.environ.get("ADSENSE_CLIENT_ID", ""),
        "ai_disclosure": os.environ.get("ENABLE_AI_DISCLOSURE", "true").lower() == "true",
        "default_author": os.environ.get("DEFAULT_AUTHOR", "Dollar Draft Editorial"),
        "logo_svg": LOGO_SVG,
        "favicon_svg": FAVICON_SVG,
        "all_categories": ALL_CATEGORIES,
        "current_year": datetime.utcnow().year,
    }


# ─── Public routes ────────────────────────────────────────────────────────────

@router.get("/")
async def home(request: Request):
    ctx = _base_ctx(request)

    featured = _safe_db(db.get_latest_article)
    articles = _safe_db(db.get_articles, limit=9, offset=(1 if featured else 0), default=[])
    # Don't show featured article again in the grid
    if featured and articles and articles[0].get("id") == featured.get("id"):
        articles = articles[1:]
    active_categories = _safe_db(db.get_categories, default=[])
    total_articles = _safe_db(db.get_article_count, default=0)

    ctx.update({
        "featured": featured,
        "articles": articles,
        "active_categories": active_categories,
        "total_articles": total_articles,
        "page_title": f"{ctx['site_name']} — {ctx['site_tagline']}",
        "page_description": ctx["site_tagline"],
        "org_jsonld": organization_json_ld(ctx["site_name"], ctx["site_url"], ctx["site_tagline"]),
        "website_jsonld": website_json_ld(ctx["site_name"], ctx["site_url"], ctx["site_tagline"]),
    })
    return templates.TemplateResponse("home.html", ctx)


@router.get("/article/{slug}")
async def article_page(slug: str, request: Request):
    article = _safe_db(db.get_article_by_slug, slug)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    related = _safe_db(db.get_related_articles, article.get("category", ""), slug, limit=3, default=[])
    ctx = _base_ctx(request)
    site_url = ctx["site_url"]
    ctx.update({
        "article": article,
        "related": related,
        "article_url": f"{site_url}/article/{slug}",
        "article_jsonld": article_json_ld(article, site_url, ctx["site_name"]),
        "page_title": f"{article['title']} | {ctx['site_name']}",
        "page_description": article.get("meta_description", "")[:160],
        "category_css": get_category_css_class(article.get("category", "")),
    })
    return templates.TemplateResponse("article.html", ctx)


@router.get("/category/{category_name}")
async def category_page(category_name: str, request: Request, page: int = 1):
    per_page = 9
    offset = (page - 1) * per_page
    result = _safe_db(db.get_articles_by_category, category_name, limit=per_page, offset=offset, default=([], 0))
    articles, total = result if isinstance(result, tuple) else ([], 0)
    if page == 1 and not articles:
        # Return the page anyway with empty state — don't 404 on valid category names
        total = 0
    total_pages = math.ceil(total / per_page) if total else 1
    ctx = _base_ctx(request)
    ctx.update({
        "category": category_name,
        "articles": articles,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "page_title": f"{category_name} | {ctx['site_name']}",
        "page_description": f"Personal finance guides about {category_name.lower()}. "
                            f"Clear advice on {category_name.lower()} from Dollar Draft.",
        "category_css": get_category_css_class(category_name),
        "category_style": get_category_style(category_name),
    })
    return templates.TemplateResponse("category.html", ctx)


# ─── SEO files ────────────────────────────────────────────────────────────────

@router.get("/sitemap.xml")
async def sitemap(request: Request):
    articles = _safe_db(db.get_all_articles_for_sitemap, default=[])
    categories = _safe_db(db.get_categories, default=[])
    ctx = _base_ctx(request)
    ctx.update({"articles": articles, "categories": categories})
    content = templates.env.get_template("sitemap.xml").render(**ctx)
    return Response(content=content, media_type="application/xml")


@router.get("/rss.xml")
async def rss_feed(request: Request):
    articles = _safe_db(db.get_articles, limit=20, default=[])
    ctx = _base_ctx(request)
    ctx["articles"] = articles
    content = templates.env.get_template("rss.xml").render(**ctx)
    return Response(content=content, media_type="application/rss+xml")


@router.get("/robots.txt")
async def robots(request: Request):
    ctx = _base_ctx(request)
    content = templates.env.get_template("robots.txt").render(**ctx)
    return Response(content=content, media_type="text/plain")


# ─── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    scheduler_enabled = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"
    db_ok = False
    count = 0
    latest_title = None

    try:
        count = db.get_article_count()
        latest = db.get_latest_article()
        latest_title = latest.get("title") if latest else None
        db_ok = True
    except Exception as e:
        logger.warning(f"Health check DB error: {e}")

    return JSONResponse({
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "articles": count,
        "latest_article": latest_title,
        "scheduler": "enabled" if scheduler_enabled else "disabled",
    })


# ─── Admin ────────────────────────────────────────────────────────────────────

def _check_admin(secret: str) -> bool:
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    return bool(admin_secret) and secret == admin_secret


@router.get("/admin")
async def admin_dashboard(request: Request, secret: str = "", message: str = ""):
    if not _check_admin(secret):
        raise HTTPException(status_code=401, detail="Unauthorized — ADMIN_SECRET required")

    articles = _safe_db(db.get_articles, limit=20, default=[])
    runs = _safe_db(db.get_recent_runs, limit=10, default=[])
    count = _safe_db(db.get_article_count, default=0)
    scheduler_enabled = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"

    ctx = _base_ctx(request)
    ctx.update({
        "admin_secret": secret,
        "articles": articles,
        "runs": runs,
        "article_count": count,
        "scheduler_enabled": scheduler_enabled,
        "message": message,
        "page_title": "Admin — Dollar Draft",
    })
    return templates.TemplateResponse("admin.html", ctx)


@router.post("/admin/run")
async def admin_run(request: Request, secret: str = "", background_tasks: BackgroundTasks = None):
    if not _check_admin(secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(bot.run_bot)
    return RedirectResponse(
        f"/admin?secret={secret}&message=Article+generation+started+in+background.+Refresh+in+60+seconds.",
        status_code=303,
    )
