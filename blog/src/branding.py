"""
Dollar Draft brand constants — logo, colors, and category styling.
"""

LOGO_SVG = """<svg width="30" height="30" viewBox="0 0 30 30" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Dollar Draft logo">
  <rect x="2" y="2" width="19" height="26" rx="3.5" fill="#2563EB"/>
  <rect x="6.5" y="9.5" width="10" height="2.25" rx="1.125" fill="white" opacity="0.88"/>
  <rect x="6.5" y="14.5" width="7" height="2.25" rx="1.125" fill="white" opacity="0.65"/>
  <rect x="6.5" y="19.5" width="8.5" height="2.25" rx="1.125" fill="white" opacity="0.50"/>
  <circle cx="24" cy="7" r="5.5" fill="#16A34A"/>
  <text x="24" y="10.5" text-anchor="middle" fill="white" font-size="7" font-weight="700" font-family="-apple-system,BlinkMacSystemFont,sans-serif">$</text>
</svg>"""

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect x="1" y="1" width="20" height="27" rx="4" fill="#2563EB"/>
  <rect x="5" y="9" width="12" height="3" rx="1.5" fill="white" opacity="0.9"/>
  <rect x="5" y="15" width="8" height="3" rx="1.5" fill="white" opacity="0.65"/>
  <rect x="5" y="21" width="10" height="3" rx="1.5" fill="white" opacity="0.5"/>
  <circle cx="27" cy="7" r="5" fill="#16A34A"/>
  <text x="27" y="10.5" text-anchor="middle" fill="white" font-size="7" font-weight="700" font-family="sans-serif">$</text>
</svg>"""

COLORS = {
    "bg": "#FAFAF7",
    "card": "#FFFFFF",
    "text": "#111827",
    "muted": "#6B7280",
    "blue": "#2563EB",
    "green": "#16A34A",
    "border": "#E5E7EB",
}

CATEGORY_STYLES = {
    "Credit Repair":    {"bg": "#EFF6FF", "color": "#1D4ED8", "css": "badge-credit-repair"},
    "Credit Cards":     {"bg": "#F5F3FF", "color": "#6D28D9", "css": "badge-credit-cards"},
    "Debt Relief":      {"bg": "#FEF2F2", "color": "#B91C1C", "css": "badge-debt-relief"},
    "Bad Credit Loans": {"bg": "#FFF7ED", "color": "#C2410C", "css": "badge-bad-credit-loans"},
    "Insurance":        {"bg": "#F0FDFA", "color": "#0F766E", "css": "badge-insurance"},
    "Banking":          {"bg": "#F0FDF4", "color": "#15803D", "css": "badge-banking"},
    "Medical Debt":     {"bg": "#FDF4FF", "color": "#86198F", "css": "badge-medical-debt"},
    "Bankruptcy":       {"bg": "#FFF1F2", "color": "#9F1239", "css": "badge-bankruptcy"},
    "Tax Debt":         {"bg": "#FFFBEB", "color": "#92400E", "css": "badge-tax-debt"},
    "Investing Basics": {"bg": "#ECFDF5", "color": "#065F46", "css": "badge-investing-basics"},
}

ALL_CATEGORIES = list(CATEGORY_STYLES.keys())


def get_category_css_class(category: str) -> str:
    style = CATEGORY_STYLES.get(category)
    return style["css"] if style else "badge-default"


def get_category_style(category: str) -> dict:
    return CATEGORY_STYLES.get(category, {"bg": "#F3F4F6", "color": "#374151", "css": "badge-default"})
