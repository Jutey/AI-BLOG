"""
PostgreSQL database layer — connection, schema init, and all CRUD operations.
"""
import os
import logging
from contextlib import contextmanager
from typing import Optional
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def _get_dsn() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    # Railway sometimes gives postgres:// — psycopg2 requires postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def get_connection():
    return psycopg2.connect(_get_dsn())


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables and indexes if they don't exist. Safe to call on every startup."""
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id              SERIAL PRIMARY KEY,
                title           TEXT NOT NULL,
                slug            TEXT UNIQUE NOT NULL,
                keyword         TEXT UNIQUE NOT NULL,
                category        TEXT,
                meta_description TEXT,
                search_intent   TEXT,
                excerpt         TEXT,
                html_content    TEXT NOT NULL,
                word_count      INTEGER,
                reading_time    INTEGER,
                status          TEXT DEFAULT 'published',
                quality_score   INTEGER,
                fact_check_notes TEXT,
                created_at      TIMESTAMP DEFAULT NOW(),
                published_at    TIMESTAMP DEFAULT NOW(),
                updated_at      TIMESTAMP DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id          SERIAL PRIMARY KEY,
                started_at  TIMESTAMP DEFAULT NOW(),
                finished_at TIMESTAMP,
                status      TEXT,
                keyword     TEXT,
                article_id  INTEGER,
                error       TEXT,
                log         TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_slug         ON articles(slug)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_keyword      ON articles(keyword)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_category     ON articles(category)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_status       ON articles(status)")

        # ── Scheduled articles (management panel) ────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_articles (
                id                   SERIAL PRIMARY KEY,
                title                TEXT,
                keyword              TEXT NOT NULL,
                category             TEXT,
                status               TEXT DEFAULT 'draft',
                scheduled_for        TIMESTAMP,
                created_at           TIMESTAMP DEFAULT NOW(),
                updated_at           TIMESTAMP DEFAULT NOW(),
                article_data_json    TEXT,
                generated_html       TEXT,
                quality_score        INTEGER,
                published_article_id INTEGER
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sched_status        ON scheduled_articles(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sched_scheduled_for ON scheduled_articles(scheduled_for)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sched_created_at    ON scheduled_articles(created_at DESC)")

        logger.info("Database initialized")


# ─── Read helpers ────────────────────────────────────────────────────────────

def _fetchall(query: str, params=()) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def _fetchone(query: str, params=()) -> Optional[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def _fetchval(query: str, params=()):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        row = cur.fetchone()
        return row[0] if row else None


# ─── Article reads ───────────────────────────────────────────────────────────

def get_article_count() -> int:
    return _fetchval("SELECT COUNT(*) FROM articles WHERE status = 'published'") or 0


def get_latest_article() -> Optional[dict]:
    return _fetchone(
        "SELECT * FROM articles WHERE status = 'published' ORDER BY published_at DESC LIMIT 1"
    )


def get_articles(limit: int = 10, offset: int = 0, category: Optional[str] = None) -> list[dict]:
    if category:
        return _fetchall(
            "SELECT * FROM articles WHERE status = 'published' AND category = %s "
            "ORDER BY published_at DESC LIMIT %s OFFSET %s",
            (category, limit, offset),
        )
    return _fetchall(
        "SELECT * FROM articles WHERE status = 'published' ORDER BY published_at DESC LIMIT %s OFFSET %s",
        (limit, offset),
    )


def get_article_by_slug(slug: str) -> Optional[dict]:
    return _fetchone(
        "SELECT * FROM articles WHERE slug = %s AND status = 'published'", (slug,)
    )


def get_articles_by_category(category: str, limit: int = 9, offset: int = 0) -> tuple[list[dict], int]:
    rows = _fetchall(
        "SELECT * FROM articles WHERE status = 'published' AND category = %s "
        "ORDER BY published_at DESC LIMIT %s OFFSET %s",
        (category, limit, offset),
    )
    total = _fetchval(
        "SELECT COUNT(*) FROM articles WHERE status = 'published' AND category = %s", (category,)
    ) or 0
    return rows, total


def get_related_articles(category: str, exclude_slug: str, limit: int = 3) -> list[dict]:
    return _fetchall(
        "SELECT * FROM articles WHERE status = 'published' AND category = %s AND slug != %s "
        "ORDER BY published_at DESC LIMIT %s",
        (category, exclude_slug, limit),
    )


def get_categories() -> list[str]:
    rows = _fetchall(
        "SELECT DISTINCT category FROM articles WHERE status = 'published' AND category IS NOT NULL "
        "ORDER BY category"
    )
    return [r["category"] for r in rows]


def get_all_articles_for_sitemap() -> list[dict]:
    return _fetchall(
        "SELECT slug, updated_at, published_at, category FROM articles WHERE status = 'published' "
        "ORDER BY published_at DESC"
    )


def get_published_keywords() -> set:
    rows = _fetchall("SELECT keyword FROM articles")
    return {r["keyword"] for r in rows if r.get("keyword")}


def get_published_slugs() -> set:
    rows = _fetchall("SELECT slug FROM articles")
    return {r["slug"] for r in rows if r.get("slug")}


# ─── Article writes ──────────────────────────────────────────────────────────

def save_article(data: dict) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO articles
               (title, slug, keyword, category, meta_description, search_intent,
                excerpt, html_content, word_count, reading_time, quality_score, fact_check_notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",
            (
                data["title"], data["slug"], data["keyword"], data.get("category"),
                data.get("meta_description"), data.get("search_intent"),
                data.get("excerpt"), data["html_content"],
                data.get("word_count", 0), data.get("reading_time", 5),
                data.get("quality_score", 75), data.get("fact_check_notes", ""),
            ),
        )
        article_id = cur.fetchone()[0]
        logger.info(f"Saved article id={article_id} slug={data['slug']}")
        return article_id


# ─── Run log ─────────────────────────────────────────────────────────────────

def start_run(keyword: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO runs (status, keyword) VALUES ('running', %s) RETURNING id",
            (keyword,),
        )
        return cur.fetchone()[0]


def finish_run(run_id: int, status: str, article_id: Optional[int], error: Optional[str], log: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """UPDATE runs
               SET finished_at = NOW(), status = %s, article_id = %s, error = %s, log = %s
               WHERE id = %s""",
            (status, article_id, error, log, run_id),
        )


def get_recent_runs(limit: int = 10) -> list[dict]:
    return _fetchall(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT %s", (limit,)
    )


# ─── Scheduled articles ───────────────────────────────────────────────────────

_VALID_SCHED_SORTS = {
    "created_at", "updated_at", "scheduled_for", "title",
    "keyword", "category", "status", "quality_score",
}


def create_scheduled_article(data: dict) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO scheduled_articles
               (title, keyword, category, status, scheduled_for,
                article_data_json, generated_html, quality_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                data.get("title"), data["keyword"], data.get("category"),
                data.get("status", "draft"), data.get("scheduled_for"),
                data.get("article_data_json"), data.get("generated_html"),
                data.get("quality_score"),
            ),
        )
        return cur.fetchone()[0]


def update_scheduled_article(id: int, data: dict) -> bool:
    allowed = {
        "title", "keyword", "category", "status", "scheduled_for",
        "article_data_json", "generated_html", "quality_score", "published_article_id",
    }
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = %s" for k in fields) + ", updated_at = NOW()"
    values = list(fields.values()) + [id]
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE scheduled_articles SET {set_clause} WHERE id = %s", values
        )
        return cur.rowcount > 0


def delete_scheduled_article(id: int) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM scheduled_articles WHERE id = %s", (id,))
        return cur.rowcount > 0


def get_scheduled_articles(
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    limit: int = 15,
    offset: int = 0,
) -> tuple[list[dict], int]:
    sort = sort if sort in _VALID_SCHED_SORTS else "created_at"
    order_sql = "ASC" if order.lower() == "asc" else "DESC"

    conditions: list[str] = []
    params: list = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    if search:
        conditions.append("(title ILIKE %s OR keyword ILIKE %s OR category ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = _fetchval(f"SELECT COUNT(*) FROM scheduled_articles {where}", tuple(params)) or 0
    rows = _fetchall(
        f"SELECT id, title, keyword, category, status, scheduled_for, created_at, "
        f"updated_at, quality_score, published_article_id, "
        f"(generated_html IS NOT NULL AND generated_html != '') AS has_content "
        f"FROM scheduled_articles {where} "
        f"ORDER BY {sort} {order_sql} LIMIT %s OFFSET %s",
        tuple(params) + (limit, offset),
    )
    return rows, total


def get_scheduled_article(id: int) -> Optional[dict]:
    return _fetchone(
        "SELECT * FROM scheduled_articles WHERE id = %s", (id,)
    )


def get_scheduled_article_counts() -> dict:
    rows = _fetchall(
        "SELECT status, COUNT(*) AS n FROM scheduled_articles GROUP BY status"
    )
    counts = {r["status"]: r["n"] for r in rows}
    return {
        "draft":     counts.get("draft", 0),
        "generating": counts.get("generating", 0),
        "scheduled": counts.get("scheduled", 0),
        "published": counts.get("published", 0),
        "failed":    counts.get("failed", 0),
        "total":     sum(counts.values()),
    }


def get_due_scheduled_articles() -> list[dict]:
    """Articles with status='scheduled' whose scheduled_for time has arrived."""
    return _fetchall(
        "SELECT * FROM scheduled_articles "
        "WHERE status = 'scheduled' AND scheduled_for <= NOW() "
        "ORDER BY scheduled_for ASC LIMIT 5"
    )


def get_scheduled_article_keywords() -> set:
    """Keywords in the scheduled queue (any non-failed status) — used to avoid duplicates."""
    rows = _fetchall(
        "SELECT keyword FROM scheduled_articles WHERE status NOT IN ('failed')"
    )
    return {r["keyword"].lower() for r in rows if r.get("keyword")}


def publish_scheduled_article(scheduled_id: int, slug: str) -> int:
    """
    Move a scheduled article into the main articles table.
    Returns the new article id.
    Raises ValueError if the article has no generated content.
    """
    import json as _json

    scheduled = get_scheduled_article(scheduled_id)
    if not scheduled:
        raise ValueError(f"Scheduled article {scheduled_id} not found")
    if not scheduled.get("generated_html"):
        raise ValueError(f"Scheduled article {scheduled_id} has no generated content yet")

    # Parse stored metadata
    try:
        meta = _json.loads(scheduled.get("article_data_json") or "{}")
    except Exception:
        meta = {}

    article_data = {
        "title":            scheduled["title"] or scheduled["keyword"],
        "slug":             slug,
        "keyword":          scheduled["keyword"],
        "category":         scheduled.get("category"),
        "meta_description": meta.get("meta_description", ""),
        "search_intent":    meta.get("search_intent", "informational"),
        "excerpt":          meta.get("excerpt", ""),
        "html_content":     scheduled["generated_html"],
        "word_count":       meta.get("word_count", 0),
        "reading_time":     meta.get("reading_time", 5),
        "quality_score":    scheduled.get("quality_score") or meta.get("quality_score", 75),
        "fact_check_notes": meta.get("fact_check_notes", ""),
    }

    article_id = save_article(article_data)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE scheduled_articles "
            "SET status = 'published', published_article_id = %s, updated_at = NOW() "
            "WHERE id = %s",
            (article_id, scheduled_id),
        )

    return article_id
