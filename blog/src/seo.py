"""
SEO utilities — slug generation, JSON-LD schemas, meta helpers.
"""
import os
import re
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert text to URL-safe slug without external dependencies."""
    slug = text.lower().strip()
    slug = re.sub(r"[''`]", "", slug)          # remove apostrophes
    slug = re.sub(r"[^a-z0-9\s-]", " ", slug)  # keep alphanumeric, spaces, hyphens
    slug = re.sub(r"[\s_]+", "-", slug)         # spaces to hyphens
    slug = re.sub(r"-{2,}", "-", slug)          # collapse multiple hyphens
    slug = slug.strip("-")
    return slug[:80]


def generate_unique_slug(title: str, existing_slugs: set) -> str:
    base = slugify(title)
    if base not in existing_slugs:
        return base
    counter = 2
    while f"{base}-{counter}" in existing_slugs:
        counter += 1
    return f"{base}-{counter}"


def get_site_url() -> str:
    url = os.environ.get("SITE_URL", "https://dollardraft.com").rstrip("/")
    return url


def format_date_display(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.strftime("%B %d, %Y")


def format_date_iso(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.isoformat()


def article_json_ld(article: dict, site_url: str, site_name: str) -> str:
    published = format_date_iso(article.get("published_at"))
    updated = format_date_iso(article.get("updated_at") or article.get("published_at"))
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article.get("title", ""),
        "description": article.get("meta_description", ""),
        "url": f"{site_url}/article/{article.get('slug', '')}",
        "datePublished": published,
        "dateModified": updated,
        "author": {
            "@type": "Organization",
            "name": site_name,
            "url": site_url,
        },
        "publisher": {
            "@type": "Organization",
            "name": site_name,
            "url": site_url,
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"{site_url}/article/{article.get('slug', '')}",
        },
    }
    return json.dumps(schema, indent=2)


def organization_json_ld(site_name: str, site_url: str, tagline: str) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": site_name,
        "url": site_url,
        "description": tagline,
    }
    return json.dumps(schema, indent=2)


def website_json_ld(site_name: str, site_url: str, tagline: str) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site_name,
        "url": site_url,
        "description": tagline,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{site_url}/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }
    return json.dumps(schema, indent=2)


def build_open_graph(
    title: str,
    description: str,
    url: str,
    og_type: str = "article",
    site_name: str = "Dollar Draft",
) -> dict:
    return {
        "og:title": title,
        "og:description": description,
        "og:url": url,
        "og:type": og_type,
        "og:site_name": site_name,
        "twitter:card": "summary_large_image",
        "twitter:title": title,
        "twitter:description": description,
    }
