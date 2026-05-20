"""
Content safety for finance publishing.
Scans for banned claims and injects appropriate disclaimers.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Phrases that can never appear in published content
BANNED_PHRASES = [
    "guaranteed approval",
    "guaranteed to be approved",
    "100% approval",
    "erase debt instantly",
    "erase your debt",
    "remove accurate",
    "delete accurate",
    "legally avoid paying",
    "avoid paying legally owed",
    "avoid paying your debt",
    "never have to pay",
    "don't have to pay",
    "guaranteed to remove",
    "fake apr",
    "we guarantee",
    "we promise you'll",
    "instantly boost your score",
    "instant credit repair",
    "fix your credit overnight",
    "secret loophole",
    "loophole banks don't want",
    "government secret",
    "banks don't want you to know",
]

GENERAL_DISCLAIMER = """<div class="disclaimer-box">
<strong>Disclaimer</strong><br>
The information on this page is for general educational purposes only and does not constitute financial, legal, or tax advice. Credit terms, interest rates, loan availability, insurance requirements, and other conditions vary by state, lender, and individual circumstance. Always verify current details directly with the relevant institution or service provider before making any financial decision. For legal matters including bankruptcy or tax issues, consult a qualified attorney or CPA licensed in your state.
</div>"""

CATEGORY_DISCLAIMERS = {
    "Bankruptcy": """<div class="disclaimer-box">
<strong>Legal Disclaimer</strong><br>
Bankruptcy law is complex and varies by state and individual situation. The information on this page is educational only and is not legal advice. Filing for bankruptcy has serious long-term financial consequences. Consult a licensed bankruptcy attorney before making any decisions. Many offer free initial consultations.
</div>""",

    "Tax Debt": """<div class="disclaimer-box">
<strong>Tax Disclaimer</strong><br>
Tax laws and IRS programs change frequently. The information on this page is educational only and is not tax or legal advice. Tax situations vary significantly by individual. Consult a licensed CPA, enrolled agent, or tax attorney before pursuing any IRS resolution strategy.
</div>""",

    "Insurance": """<div class="disclaimer-box">
<strong>Insurance Disclaimer</strong><br>
Insurance rates, requirements, and coverage options vary significantly by state, insurer, and individual factors including driving record, credit score, and claims history. The information on this page is educational only. Always compare quotes directly from licensed insurers or a licensed insurance agent in your state.
</div>""",

    "Investing Basics": """<div class="disclaimer-box">
<strong>Investment Disclaimer</strong><br>
Investing involves risk, including possible loss of principal. Past performance does not guarantee future results. The information on this page is educational only and is not investment advice. Consider your financial situation, risk tolerance, and goals before investing. A licensed financial advisor can help you build a plan suited to your needs.
</div>""",
}

AI_DISCLOSURE = """<div class="ai-disclosure">
<strong>AI-Assisted Content:</strong> This article was researched and drafted with AI assistance and reviewed for accuracy. It reflects general information available as of the publication date.
</div>"""


def validate_content(html: str) -> tuple[bool, list[str]]:
    """
    Check for banned phrases in article HTML.
    Returns (is_safe, list_of_violations).
    """
    html_lower = html.lower()
    violations = []
    for phrase in BANNED_PHRASES:
        if phrase in html_lower:
            violations.append(f"Banned phrase found: '{phrase}'")
    if violations:
        logger.warning(f"Content safety violations: {violations}")
    return len(violations) == 0, violations


def sanitize_content(html: str) -> str:
    """
    Remove or replace known banned phrases with safer alternatives.
    Called as a last resort if Claude generates problematic content.
    """
    replacements = {
        "guaranteed approval": "potential approval (results vary)",
        "guaranteed to be approved": "may be approved (results vary)",
        "erase debt instantly": "address debt over time",
        "instant credit repair": "credit improvement over time",
        "fix your credit overnight": "improve your credit over time",
        "secret loophole": "legal strategy",
        "banks don't want you to know": "many borrowers overlook",
    }
    result = html
    for bad, good in replacements.items():
        result = re.sub(re.escape(bad), good, result, flags=re.IGNORECASE)
    return result


def inject_disclaimer(html: str, category: str, ai_disclosure: bool = True) -> str:
    """
    Append the appropriate disclaimer and optional AI disclosure to article HTML.
    """
    disclaimer = CATEGORY_DISCLAIMERS.get(category, GENERAL_DISCLAIMER)
    result = html.rstrip()
    result += "\n\n" + disclaimer
    if ai_disclosure:
        result += "\n\n" + AI_DISCLOSURE
    return result
