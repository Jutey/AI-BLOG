"""
Dollar Draft Management Panel — isolated admin system for scheduling and lifecycle management.
Accessible via /manage?secret=ADMIN_SECRET

Does NOT modify the existing publishing pipeline, writer, scheduler, or admin dashboard.
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import database as db
from . import writer
from . import topics as topic_pool
from .seo import generate_unique_slug, get_site_url, format_date_display, format_date_iso
from .branding import LOGO_SVG, FAVICON_SVG, ALL_CATEGORIES, get_category_css_class, get_category_style

logger = logging.getLogger(__name__)

manage_router = APIRouter()

_tpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
_templates = Jinja2Templates(directory=_tpl_dir)

# ─── Jinja2 filters ──────────────────────────────────────────────────────────

_templates.env.filters["format_date"] = format_date_display
_templates.env.filters["format_iso"] = format_date_iso
_templates.env.filters["category_class"] = get_category_css_class
_templates.env.filters["category_style"] = get_category_style


def _fmt_local(dt: Optional[datetime]) -> str:
    """Format datetime for <input type='datetime-local'>."""
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M")


_templates.env.filters["fmt_local"] = _fmt_local


# ─── Auth ─────────────────────────────────────────────────────────────────────

def _require_secret(secret: str):
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    if not admin_secret or secret != admin_secret:
        raise HTTPException(status_code=401, detail="Unauthorized — ADMIN_SECRET required")


# ─── Context ──────────────────────────────────────────────────────────────────

def _base_ctx(request: Request) -> dict:
    return {
        "request": request,
        "site_name": os.environ.get("SITE_NAME", "Dollar Draft"),
        "site_tagline": os.environ.get("SITE_TAGLINE", "Personal finance, simplified daily."),
        "site_url": get_site_url(),
        "contact_email": os.environ.get("CONTACT_EMAIL", ""),
        "logo_svg": LOGO_SVG,
        "favicon_svg": FAVICON_SVG,
        "all_categories": ALL_CATEGORIES,
        "ga_script": "",
        "adsense_client": "",
        "ai_disclosure": False,
        "default_author": os.environ.get("DEFAULT_AUTHOR", "Dollar Draft Editorial"),
        "current_year": datetime.utcnow().year,
    }


def _safe(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning(f"DB {fn.__name__} failed: {e}")
        return default


# ─── Background tasks ─────────────────────────────────────────────────────────

def _bg_generate_draft(keyword: str, category: str, scheduled_id: int):
    """
    Background task: run writer pipeline and save result to scheduled_articles.
    Called from /manage/generate and /manage/generate-bulk.
    """
    try:
        logger.info(f"[bg] Generating draft for: {keyword}")
        result = writer.generate_article(keyword, category)

        meta = {
            "meta_description": result.get("meta_description", ""),
            "search_intent":    result.get("search_intent", "informational"),
            "excerpt":          result.get("excerpt", ""),
            "word_count":       result.get("word_count", 0),
            "reading_time":     result.get("reading_time", 5),
            "fact_check_notes": result.get("fact_check_notes", ""),
        }

        db.update_scheduled_article(scheduled_id, {
            "title":              result["title"],
            "keyword":            result["keyword"],
            "category":           result["category"],
            "status":             "draft",
            "generated_html":     result["html_content"],
            "quality_score":      result["quality_score"],
            "article_data_json":  json.dumps(meta),
        })
        logger.info(f"[bg] Draft complete: {result['title']} (id={scheduled_id})")

    except Exception as e:
        logger.error(f"[bg] Draft generation failed for scheduled_id={scheduled_id}: {e}")
        db.update_scheduled_article(scheduled_id, {
            "status": "failed",
            "article_data_json": json.dumps({"error": str(e)}),
        })


def _bg_generate_bulk(keywords: list[str], category: str):
    """
    Background task: generate multiple drafts sequentially.
    Each article gets its own row in scheduled_articles.
    """
    for kw in keywords:
        # Create placeholder row first so the user sees progress on refresh
        sid = _safe(db.create_scheduled_article, {
            "keyword":  kw,
            "category": category,
            "title":    kw,
            "status":   "generating",
        }, default=None)
        if sid:
            _bg_generate_draft(kw, category, sid)


# ─── Routes ───────────────────────────────────────────────────────────────────

@manage_router.get("/manage")
async def manage_dashboard(
    request: Request,
    secret: str = "",
    status: str = "",
    page: int = 1,
    q: str = "",
    sort: str = "created_at",
    order: str = "desc",
    message: str = "",
):
    _require_secret(secret)

    per_page = 15
    offset = (page - 1) * per_page

    counts = _safe(db.get_scheduled_article_counts, default={
        "draft": 0, "generating": 0, "scheduled": 0, "published": 0, "failed": 0, "total": 0
    })

    articles, total = _safe(
        db.get_scheduled_articles,
        status=status or None,
        search=q or None,
        sort=sort,
        order=order,
        limit=per_page,
        offset=offset,
        default=([], 0),
    )

    total_pages = max(1, (total + per_page - 1) // per_page)
    runs = _safe(db.get_recent_runs, limit=10, default=[])

    scheduler_enabled = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"
    publish_hour = int(os.environ.get("PUBLISH_HOUR_UTC", "14"))
    article_count = _safe(db.get_article_count, default=0)

    # Compute next scheduler run time string
    now = datetime.utcnow()
    next_hour = now.replace(minute=0, second=0, microsecond=0)
    if next_hour.hour >= publish_hour:
        from datetime import timedelta
        next_run_str = (next_hour.replace(hour=publish_hour) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M UTC")
    else:
        next_run_str = next_hour.replace(hour=publish_hour).strftime("%Y-%m-%d %H:%M UTC")

    ctx = _base_ctx(request)
    ctx.update({
        "secret": secret,
        "counts": counts,
        "articles": articles,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "per_page": per_page,
        "status_filter": status,
        "search_query": q,
        "sort": sort,
        "order": order,
        "runs": runs,
        "scheduler_enabled": scheduler_enabled,
        "publish_hour": publish_hour,
        "next_run_str": next_run_str,
        "article_count": article_count,
        "message": message,
        "page_title": "Management Panel — Dollar Draft",
    })
    return _templates.TemplateResponse("admin_panel.html", ctx)


@manage_router.post("/manage/generate")
async def manage_generate(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: str = "",
    keyword: str = Form(...),
    category: str = Form(...),
):
    _require_secret(secret)

    keyword = keyword.strip()
    if not keyword:
        return _redirect(secret, "error_keyword_required")

    # Check if keyword is already queued or published
    existing_kws = _safe(db.get_scheduled_article_keywords, default=set())
    published_kws = _safe(db.get_published_keywords, default=set())
    if keyword.lower() in {k.lower() for k in (existing_kws | published_kws)}:
        return _redirect(secret, f"Keyword already exists in drafts or published articles: {keyword}")

    # Create placeholder row immediately — user sees it in the table right away
    sid = db.create_scheduled_article({
        "keyword":  keyword,
        "category": category,
        "title":    keyword,
        "status":   "generating",
    })

    background_tasks.add_task(_bg_generate_draft, keyword, category, sid)
    return _redirect(secret, f"Generating draft for: {keyword} — refresh in 2–4 minutes.")


@manage_router.post("/manage/generate-bulk")
async def manage_generate_bulk(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: str = "",
    category: str = Form(...),
    count: int = Form(...),
):
    _require_secret(secret)

    count = max(1, min(count, 20))  # cap at 20 per request

    # Pick unused keywords from the topic pool for this category
    all_kws = topic_pool.TOPICS.get(category, [])
    published_kws  = _safe(db.get_published_keywords, default=set())
    scheduled_kws  = _safe(db.get_scheduled_article_keywords, default=set())
    used = {k.lower() for k in (published_kws | scheduled_kws)}
    available = [kw for kw in all_kws if kw.lower() not in used]

    if not available:
        return _redirect(secret, f"No unused keywords available in {category}.")

    selected = available[:count]
    actual = len(selected)

    background_tasks.add_task(_bg_generate_bulk, selected, category)
    return _redirect(secret, f"Bulk generation started: {actual} article(s) for {category}. Refresh in a few minutes.")


@manage_router.post("/manage/publish/{scheduled_id}")
async def manage_publish(
    request: Request,
    scheduled_id: int,
    secret: str = "",
):
    _require_secret(secret)

    scheduled = _safe(db.get_scheduled_article, scheduled_id)
    if not scheduled:
        return _redirect(secret, f"Article {scheduled_id} not found.")
    if not scheduled.get("generated_html"):
        return _redirect(secret, f"Article {scheduled_id} has no generated content — wait for generation to complete.")

    try:
        existing_slugs = _safe(db.get_published_slugs, default=set())
        slug = generate_unique_slug(scheduled.get("title") or scheduled["keyword"], existing_slugs)
        article_id = db.publish_scheduled_article(scheduled_id, slug)
        return _redirect(secret, f"Published! Article ID {article_id} is now live at /article/{slug}")
    except Exception as e:
        logger.error(f"Publish failed for scheduled_id={scheduled_id}: {e}")
        db.update_scheduled_article(scheduled_id, {"status": "failed"})
        return _redirect(secret, f"Publish failed: {e}")


@manage_router.post("/manage/schedule/{scheduled_id}")
async def manage_schedule(
    request: Request,
    scheduled_id: int,
    secret: str = "",
    scheduled_for: str = Form(...),
    action: str = Form("schedule"),
):
    _require_secret(secret)

    if action == "unschedule":
        db.update_scheduled_article(scheduled_id, {"status": "draft", "scheduled_for": None})
        return _redirect(secret, "Article unscheduled and moved back to drafts.")

    try:
        dt = datetime.fromisoformat(scheduled_for)
        db.update_scheduled_article(scheduled_id, {
            "status": "scheduled",
            "scheduled_for": dt,
        })
        return _redirect(secret, f"Scheduled for {dt.strftime('%Y-%m-%d %H:%M UTC')}")
    except ValueError:
        return _redirect(secret, "Invalid date format.")


@manage_router.post("/manage/update/{scheduled_id}")
async def manage_update(
    request: Request,
    scheduled_id: int,
    secret: str = "",
    title: str = Form(""),
    keyword: str = Form(""),
    category: str = Form(""),
    meta_description: str = Form(""),
):
    _require_secret(secret)

    updates: dict = {}
    if title.strip():
        updates["title"] = title.strip()
    if keyword.strip():
        updates["keyword"] = keyword.strip()
    if category.strip():
        updates["category"] = category.strip()

    if meta_description.strip():
        # Merge into article_data_json
        existing = _safe(db.get_scheduled_article, scheduled_id) or {}
        try:
            meta = json.loads(existing.get("article_data_json") or "{}")
        except Exception:
            meta = {}
        meta["meta_description"] = meta_description.strip()
        updates["article_data_json"] = json.dumps(meta)

    if updates:
        db.update_scheduled_article(scheduled_id, updates)
        return _redirect(secret, "Article metadata updated.")
    return _redirect(secret, "No changes to save.")


@manage_router.post("/manage/delete/{scheduled_id}")
async def manage_delete(
    request: Request,
    scheduled_id: int,
    secret: str = "",
):
    _require_secret(secret)
    deleted = _safe(db.delete_scheduled_article, scheduled_id, default=False)
    msg = "Article deleted." if deleted else f"Could not delete article {scheduled_id}."
    return _redirect(secret, msg)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _redirect(secret: str, message: str) -> RedirectResponse:
    from urllib.parse import quote
    return RedirectResponse(
        f"/manage?secret={secret}&message={quote(message)}",
        status_code=303,
    )
