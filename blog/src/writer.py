"""
AI writer pipeline — multi-step Claude API workflow for generating
high-quality, SEO-optimized personal finance articles.
"""
import os
import json
import re
import time
import logging
from typing import Optional

import anthropic

from .safety import validate_content, sanitize_content, inject_disclaimer

logger = logging.getLogger(__name__)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
MAX_RETRIES = 1
RETRY_DELAY = 10


# ─── Claude client ────────────────────────────────────────────────────────────

def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


def _call_claude(prompt: str, system: str, max_tokens: int = 4096, attempt: int = 0) -> str:
    """Call Claude API with one automatic retry on failure."""
    client = _get_client()
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        if attempt < MAX_RETRIES:
            logger.warning(f"Claude API error (attempt {attempt+1}): {e} — retrying in {RETRY_DELAY}s")
            time.sleep(RETRY_DELAY)
            return _call_claude(prompt, system, max_tokens, attempt + 1)
        raise


def _parse_json(text: str) -> dict:
    """Extract JSON from Claude response, handling markdown code fences."""
    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip ```json ... ``` fences
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Grab first { ... } block
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot parse JSON from Claude response. Preview: {text[:400]}")


# ─── Step 1: Topic expansion ─────────────────────────────────────────────────

def step1_expand_topic(seed_keyword: str, category: str) -> dict:
    logger.info(f"Step 1 — expanding topic: {seed_keyword}")
    system = (
        "You are a senior SEO content strategist specializing in personal finance. "
        "Return only valid JSON — no markdown, no explanation."
    )
    prompt = f"""Expand this personal finance keyword into a complete content brief.

Seed keyword: {seed_keyword}
Category: {category}

Return ONLY this JSON structure (no markdown):
{{
  "title": "Full SEO title 60-70 characters",
  "keyword": "Primary target keyword — same as or close expansion of seed",
  "category": "{category}",
  "meta_description": "Compelling meta description 150-160 chars",
  "search_intent": "informational",
  "angle": "Unique editorial angle that makes this guide stand out",
  "target_reader": "Specific person this is written for — be concrete",
  "disclaimer_needed": true
}}"""
    return _parse_json(_call_claude(prompt, system, max_tokens=1024))


# ─── Step 2: Outline ─────────────────────────────────────────────────────────

def step2_create_outline(brief: dict) -> dict:
    logger.info("Step 2 — creating outline")
    system = (
        "You are a senior personal finance editor. "
        "Return only valid JSON — no markdown, no explanation."
    )
    prompt = f"""Create a detailed, specific article outline.

Title: {brief['title']}
Keyword: {brief['keyword']}
Category: {brief['category']}
Angle: {brief.get('angle', '')}
Target reader: {brief.get('target_reader', '')}

Return ONLY this JSON (no markdown):
{{
  "intro_hook": "Opening sentence that immediately addresses the reader's pain point",
  "h2_sections": [
    {{"heading": "H2 heading", "key_points": ["point 1", "point 2", "point 3"]}}
  ],
  "comparison_table": {{
    "description": "What the table compares (options, products, strategies)",
    "columns": ["Column 1", "Column 2", "Column 3"]
  }},
  "faq_questions": [
    "Question 1?",
    "Question 2?",
    "Question 3?",
    "Question 4?"
  ],
  "cta": "Specific action the reader should take next",
  "watchout_heading": "What to Watch Out For heading specific to this topic"
}}

Include 5-7 H2 sections. Be specific to this topic — avoid generic sections."""
    return _parse_json(_call_claude(prompt, system, max_tokens=2048))


# ─── Step 3: Write article ───────────────────────────────────────────────────

def step3_write_article(brief: dict, outline: dict) -> str:
    logger.info("Step 3 — writing article HTML")
    system = """You are an expert personal finance writer who creates clear, useful, trustworthy content for everyday Americans.

Your writing style:
- Clear and direct — like a knowledgeable friend explaining money
- Empathetic to financial struggles and embarrassment
- Practical and actionable — tell people exactly what to do
- Honest about limitations and variations

COMPLIANCE RULES (non-negotiable):
- Never quote specific interest rates from named companies
- Never say "guaranteed approval" or "guaranteed" about any financial product
- Never claim to remove accurate negative information from credit reports
- Never give legal conclusions — say "may", "can", "typically", "often", "depending on your state"
- Never fabricate state laws or settlement amounts
- Always note that terms vary by lender/state/situation

OUTPUT RULES:
- Output clean HTML only — NO html/head/body/doctype tags
- Start with <p> or <h2> — never with a heading tag before any content
- Do NOT include a disclaimer section — it will be added automatically"""

    sections_text = json.dumps(outline.get("h2_sections", []), indent=2)
    faq_text = json.dumps(outline.get("faq_questions", []), indent=2)

    prompt = f"""Write a complete, high-quality personal finance article.

BRIEF:
Title: {brief['title']}
Primary keyword: {brief['keyword']}
Category: {brief['category']}
Target reader: {brief.get('target_reader', 'someone dealing with a financial challenge')}
Angle: {brief.get('angle', '')}

OUTLINE:
Opening hook: {outline.get('intro_hook', '')}
Sections: {sections_text}
Comparison table focus: {outline.get('comparison_table', {}).get('description', 'compare the main options')}
Table columns: {json.dumps(outline.get('comparison_table', {}).get('columns', []))}
FAQ questions: {faq_text}
CTA: {outline.get('cta', 'take action')}
Watch-out heading: {outline.get('watchout_heading', 'What to Watch Out For')}

REQUIREMENTS:
1. Length: 1,600–2,400 words
2. Use "{brief['keyword']}" in the first 100 words naturally
3. Use the keyword 4-8 times total throughout — never stuff it
4. Cover every H2 section from the outline
5. Include a comparison/options <table> with <thead> and <tbody>
6. Include a "pros and cons" section (table or formatted list)
7. Include a warning callout: <div class="callout callout-warning"><p>...</p></div>
8. Include a tip callout somewhere: <div class="callout callout-tip"><p>...</p></div>
9. Include the FAQ section — each question as <h3>, answer as <p>
10. End with a CTA box: <div class="cta-box"><h3>...</h3><p>...</p></div>
11. Use <strong> for the first mention of important terms
12. Do NOT add a disclaimer section

Write the complete article HTML now. Start with <p>."""

    return _call_claude(prompt, system, max_tokens=6000)


# ─── Step 4: Quality check ───────────────────────────────────────────────────

def step4_quality_check(article_html: str, keyword: str) -> dict:
    logger.info("Step 4 — quality check")
    system = (
        "You are a senior finance content editor. "
        "Return only valid JSON — no markdown, no explanation."
    )
    preview = article_html[:3500] + ("...[truncated]" if len(article_html) > 3500 else "")
    prompt = f"""Review this personal finance article for quality, accuracy, SEO, and compliance.

Primary keyword: {keyword}

Article HTML:
{preview}

Return ONLY this JSON:
{{
  "quality_score": 85,
  "passes": true,
  "issues": ["list specific problems, or empty list"],
  "suggested_fixes": ["specific fix instructions if score < 80"],
  "keyword_in_intro": true,
  "has_table": true,
  "has_faq": true,
  "has_callouts": true,
  "compliance_ok": true,
  "estimated_word_count": 1800,
  "fact_check_notes": "Any claims that should be verified or softened"
}}

Scoring guide:
90-100: Excellent — publish immediately
80-89: Good — minor polish at most
70-79: Needs targeted revision
<70: Needs significant rewrite

Check for: adequate length (1,500+ words), keyword in first 100 words,
no banned claims, useful & actionable content, table and FAQ present,
compliant language (may/can/typically/depending on state)."""
    return _parse_json(_call_claude(prompt, system, max_tokens=1024))


# ─── Step 5: Revision ────────────────────────────────────────────────────────

def step5_revise_article(article_html: str, issues: list[str], keyword: str) -> str:
    logger.info(f"Step 5 — revising article ({len(issues)} issues)")
    system = (
        "You are a senior finance content editor. Fix the specified issues and return improved article HTML. "
        "Output ONLY the revised HTML — no explanation. Start with <p> or <h2>. "
        "Do NOT include html/head/body/doctype tags or a disclaimer section."
    )
    issues_text = "\n".join(f"- {issue}" for issue in issues)
    prompt = f"""Revise this personal finance article to fix the issues listed below.

Primary keyword: {keyword}

ISSUES TO FIX:
{issues_text}

ORIGINAL ARTICLE:
{article_html}

Return ONLY the revised article HTML. Maintain the full length and structure."""
    return _call_claude(prompt, system, max_tokens=6000)


# ─── Main pipeline ────────────────────────────────────────────────────────────

def generate_article(seed_keyword: str, category: str, existing_slugs: Optional[set] = None) -> dict:
    """
    Full multi-step article generation pipeline.
    Returns a dict ready for database insertion.
    """
    enable_disclosure = os.environ.get("ENABLE_AI_DISCLOSURE", "true").lower() == "true"

    # Step 1 — topic expansion
    brief = step1_expand_topic(seed_keyword, category)
    logger.info(f"Brief title: {brief.get('title')}")

    # Step 2 — outline
    outline = step2_create_outline(brief)

    # Step 3 — write
    article_html = step3_write_article(brief, outline)

    # Step 4 — quality check
    qc = step4_quality_check(article_html, brief.get("keyword", seed_keyword))
    score = qc.get("quality_score", 75)
    logger.info(f"Quality score: {score}")

    # Step 5 — revise if needed
    if score < 80 or not qc.get("passes", True):
        issues = qc.get("issues", []) + qc.get("suggested_fixes", [])
        if issues:
            article_html = step5_revise_article(article_html, issues, brief.get("keyword", seed_keyword))
            qc2 = step4_quality_check(article_html, brief.get("keyword", seed_keyword))
            score = max(score, qc2.get("quality_score", score))

    # Safety validation and sanitization
    is_safe, violations = validate_content(article_html)
    if not is_safe:
        logger.warning(f"Sanitizing {len(violations)} safety violations")
        article_html = sanitize_content(article_html)

    # Inject disclaimer (and optional AI disclosure)
    article_html = inject_disclaimer(article_html, brief.get("category", category), enable_disclosure)

    # Metrics
    text_only = re.sub(r"<[^>]+>", " ", article_html)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    word_count = len(text_only.split())
    reading_time = max(1, round(word_count / 200))

    # Excerpt
    excerpt = text_only[:280].rsplit(" ", 1)[0] + "..." if len(text_only) > 280 else text_only

    return {
        "keyword": brief.get("keyword", seed_keyword),
        "title": brief.get("title", seed_keyword.title()),
        "category": brief.get("category", category),
        "meta_description": brief.get("meta_description", ""),
        "search_intent": brief.get("search_intent", "informational"),
        "excerpt": excerpt,
        "html_content": article_html,
        "word_count": word_count,
        "reading_time": reading_time,
        "quality_score": score,
        "fact_check_notes": qc.get("fact_check_notes", ""),
    }
