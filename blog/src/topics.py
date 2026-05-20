"""
Topic pool — 111 high-CPC personal finance keywords organized by category.
Includes rotation logic so the bot never repeats a published keyword.
"""
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TOPICS: dict[str, list[str]] = {
    "Credit Repair": [
        "how to remove collections from credit report",
        "how to dispute hard inquiries fast",
        "credit repair letters that actually work",
        "goodwill deletion letter how to write",
        "how to remove late payments from credit report",
        "pay for delete letter template guide",
        "how to dispute charge-offs on credit report",
        "credit score requirements for different loan types",
        "how long negative items stay on credit report",
        "are credit repair companies worth it",
        "DIY credit repair step by step guide",
        "how to rebuild credit after collections",
    ],
    "Credit Cards": [
        "credit cards for 500 credit score",
        "best balance transfer cards no annual fee",
        "secured credit cards that graduate to unsecured",
        "best credit cards for rebuilding credit",
        "credit cards with instant approval bad credit",
        "store credit cards that are easy to get approved for",
        "credit cards for fair credit score",
        "how to get approved for a credit card with bad credit",
        "prepaid debit cards that build credit",
        "is a credit card annual fee worth paying",
        "credit card rewards programs for beginners",
        "how to use credit cards to build credit fast",
    ],
    "Debt Relief": [
        "how to get out of payday loan debt",
        "debt settlement vs bankruptcy which is better",
        "how to negotiate with debt collectors",
        "what happens when debt goes to collections",
        "statute of limitations on debt by state",
        "how to handle zombie debt collectors",
        "debt validation letter how to write one",
        "national debt relief how does it work",
        "how to stop wage garnishment",
        "debt consolidation loans pros and cons",
        "hardship programs credit card companies offer",
        "snowball vs avalanche debt payoff method",
    ],
    "Bad Credit Loans": [
        "personal loans for debt consolidation bad credit",
        "emergency loans same day deposit no credit check",
        "cash advance apps that work with Chime",
        "best personal loans for 550 credit score",
        "online loans for bad credit instant approval",
        "credit unions that help people with bad credit",
        "bad credit car loans what to expect",
        "title loans vs personal loans comparison",
        "tribal loans pros cons and risks",
        "installment loans vs payday loans which is safer",
        "peer to peer lending for bad credit borrowers",
        "cosigner loans how they work and who qualifies",
    ],
    "Insurance": [
        "SR-22 insurance by state cost guide",
        "cheap renters insurance for people with bad credit",
        "car insurance after DUI complete state guide",
        "cheapest car insurance for high risk drivers",
        "non-owner SR-22 insurance what it is and cost",
        "health insurance options when you are unemployed",
        "life insurance with pre-existing conditions guide",
        "gap insurance is it worth buying",
        "umbrella insurance what does it cover",
        "dental insurance that covers implants",
        "vision insurance is it worth buying",
        "home warranty vs homeowners insurance difference",
    ],
    "Banking": [
        "how to build credit from zero complete guide",
        "second chance checking accounts best options",
        "best online banks with no credit check",
        "Chime vs Varo vs Dave comparison 2024",
        "online banks with early direct deposit",
        "best high yield savings accounts for beginners",
        "money market account vs savings account",
        "how to open a bank account with bad credit",
        "overdraft protection is it worth having",
        "best prepaid debit cards for unbanked adults",
        "how FDIC insurance protects your money",
        "credit union vs bank which is better for you",
    ],
    "Medical Debt": [
        "what happens if you don't pay medical bills",
        "how to negotiate medical bills and reduce them",
        "medical debt forgiveness programs complete guide",
        "does medical debt affect your credit score",
        "hospital charity care programs how to apply",
        "how to spot and dispute medical billing errors",
        "medical debt statute of limitations by state",
        "can hospitals garnish wages for unpaid medical debt",
        "how to negotiate a medical debt settlement",
        "surprise medical billing protections explained",
        "CareCredit risks what to know before applying",
    ],
    "Bankruptcy": [
        "chapter 7 vs chapter 13 bankruptcy explained",
        "how to file bankruptcy step by step guide",
        "bankruptcy exemptions by state complete guide",
        "how long does bankruptcy stay on credit report",
        "how to rebuild credit after bankruptcy",
        "bankruptcy means test how it works",
        "what debts can be discharged in bankruptcy",
        "alternatives to bankruptcy worth considering",
        "chapter 7 bankruptcy timeline what to expect",
        "is hiring a bankruptcy attorney worth the cost",
    ],
    "Tax Debt": [
        "IRS payment plan options how to set one up",
        "offer in compromise IRS how to qualify",
        "IRS currently not collectible status explained",
        "how to stop IRS wage garnishment",
        "IRS fresh start program eligibility guide",
        "IRS penalty abatement first time offender",
        "back taxes how to catch up what to do first",
        "tax levy vs tax lien what is the difference",
        "state tax debt resolution options",
        "tax debt relief companies how they work",
    ],
    "Investing Basics": [
        "how to start investing with 100 dollars",
        "index funds for beginners complete guide",
        "Roth IRA vs traditional IRA which is better",
        "compound interest explained with examples",
        "dollar cost averaging strategy how it works",
        "why build an emergency fund before investing",
        "how to invest in ETFs for beginners",
        "I bonds how they work pros and cons",
        "health savings account investment strategy",
        "how to open a brokerage account step by step",
    ],
}

# Rotation order — cycles through all categories before repeating
CATEGORY_ORDER = list(TOPICS.keys())


def get_all_topics() -> list[dict]:
    """Flat list of all topics with their category."""
    result = []
    for category, keywords in TOPICS.items():
        for kw in keywords:
            result.append({"keyword": kw, "category": category})
    return result


def get_next_topic(published_keywords: set) -> Optional[dict]:
    """
    Select the next topic to publish.

    Strategy:
      1. Filter out already-published keywords.
      2. Rotate through categories to ensure variety.
      3. Within each category, pick randomly to avoid predictable ordering.
      4. If all topics are exhausted, return None (rare — 111 topics).
    """
    published_lower = {k.lower().strip() for k in published_keywords}

    # Build available topics per category
    available: dict[str, list[str]] = {}
    for category, keywords in TOPICS.items():
        remaining = [k for k in keywords if k.lower().strip() not in published_lower]
        if remaining:
            available[category] = remaining

    if not available:
        logger.warning("All topics have been published — topic pool exhausted")
        return None

    # Pick category in rotation order, preferring least recently published
    for category in CATEGORY_ORDER:
        if category in available:
            keyword = random.choice(available[category])
            logger.info(f"Selected topic: [{category}] {keyword}")
            return {"keyword": keyword, "category": category}

    # Fallback: pick any available category
    category = random.choice(list(available.keys()))
    keyword = random.choice(available[category])
    return {"keyword": keyword, "category": category}
