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
