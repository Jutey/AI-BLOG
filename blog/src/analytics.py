"""
Google Analytics injection helper.
"""
import os


def get_ga_script() -> str:
    ga_id = os.environ.get("GOOGLE_ANALYTICS_ID", "").strip()
    if not ga_id:
        return ""
    return f"""<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga_id}');
</script>"""


def get_adsense_script() -> str:
    client_id = os.environ.get("ADSENSE_CLIENT_ID", "").strip()
    if not client_id:
        return ""
    return f'<!-- AdSense: replace data-ad-client and data-ad-slot values after approval -->'
