"""
Bot orchestrator — selects topic, runs the writer pipeline,
saves article, and logs the run. Can be triggered by scheduler or CLI.
"""
import os
import logging
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from . import database as db
from . import topics as topic_pool
from . import writer
from .seo import generate_unique_slug

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def run_bot(articles_per_run: Optional[int] = None) -> bool:
    """
    Execute one full publishing cycle.

    1. Pick an unused topic from the pool
    2. Generate the full article via Claude
    3. Save to PostgreSQL
    4. Log the run

    Returns True on success, False on failure.
    The web server continues running regardless of outcome.
    """
    n = articles_per_run or int(os.environ.get("ARTICLES_PER_DAY", "1"))
    success = True

    for _ in range(n):
        run_id = None
        log_lines = []

        def log(msg: str):
            logger.info(msg)
            log_lines.append(msg)

        try:
            # Pick next topic
            published_kws = db.get_published_keywords()
            log(f"Published articles so far: {len(published_kws)}")

            topic = topic_pool.get_next_topic(published_kws)
            if topic is None:
                log("No unpublished topics remaining — skipping run")
                return False

            seed_keyword = topic["keyword"]
            category = topic["category"]
            log(f"Selected topic: [{category}] {seed_keyword}")

            # Start run log
            run_id = db.start_run(seed_keyword)
            log(f"Run ID: {run_id}")

            # Generate article
            log("Generating article with Claude...")
            result = writer.generate_article(seed_keyword, category)
            log(f"Generated: {result['title']} ({result['word_count']} words, score={result['quality_score']})")

            # Build unique slug
            existing_slugs = db.get_published_slugs()
            slug = generate_unique_slug(result["title"], existing_slugs)
            log(f"Slug: {slug}")

            # Save article
            article_id = db.save_article({**result, "slug": slug})
            log(f"Saved as article ID {article_id}")

            # Build final URL
            site_url = os.environ.get("SITE_URL", "").rstrip("/")
            final_url = f"{site_url}/article/{slug}" if site_url else f"/article/{slug}"
            log(f"Published at: {final_url}")

            db.finish_run(run_id, "success", article_id, None, "\n".join(log_lines))
            log("Run complete ✓")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.exception(f"Bot run failed: {error_msg}")
            log_lines.append(f"ERROR: {error_msg}")
            if run_id:
                db.finish_run(run_id, "error", None, error_msg, "\n".join(log_lines))
            success = False

    return success


if __name__ == "__main__":
    # python -m src.bot
    run_bot()
