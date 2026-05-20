# Dollar Draft

A complete, production-ready AI personal finance blog platform. Deploy once on Railway and it writes, formats, SEO-optimizes, and publishes one high-quality article every morning — automatically.

---

## What It Is

Dollar Draft is a self-contained publishing machine:

- **AI writing pipeline** — multi-step Claude workflow: topic selection → outline → article → quality check → revision if needed
- **SEO-ready from day one** — canonical URLs, Open Graph, Twitter cards, JSON-LD schema, sitemap.xml, RSS feed
- **Premium editorial design** — minimal, fast, mobile-first — no CSS framework, no WordPress
- **Content safety** — finance-specific guardrails, automatic disclaimers, banned phrase detection
- **Monetization-ready** — AdSense placeholders, affiliate link slots, clean article structure

---

## Features

| Feature | Detail |
|---|---|
| AI content | Claude multi-step pipeline (expand → outline → write → QC → revise) |
| Topics | 111 seed keywords across 10 high-CPC personal finance categories |
| SEO | Title, meta, canonical, OG, Twitter, JSON-LD, sitemap, RSS |
| Design | Inter font, warm editorial palette, premium cards, responsive |
| Scheduler | APScheduler cron — publishes at your chosen UTC hour daily |
| Database | PostgreSQL — articles, run logs, settings |
| Admin | Web dashboard + manual run button at `/admin?secret=XXX` |
| Health | JSON health endpoint at `/health` |
| Safety | Finance disclaimers, banned phrases, AI disclosure |
| Monetization | AdSense placeholder slots, affiliate-ready structure |

---

## Tech Stack

- **Python 3.11+** with FastAPI
- **Jinja2** templating
- **PostgreSQL** via psycopg2-binary
- **APScheduler** for cron scheduling
- **Anthropic Claude API** for content generation
- **Railway** for hosting (web service + PostgreSQL plugin)

---

## Railway Setup (Deploy in 10 Minutes)

### 1. Create a Railway project

Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.

Connect your GitHub and select this repository.

### 2. Add PostgreSQL

Inside your Railway project → **+ New** → **Database** → **PostgreSQL**.

Railway automatically sets the `DATABASE_URL` environment variable.

### 3. Add environment variables

In Railway: **Settings** → **Variables**. Add:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `DATABASE_URL` | Set automatically by Railway Postgres plugin |
| `SITE_URL` | `https://yourdomain.com` (or your Railway URL for now) |
| `SITE_NAME` | `Dollar Draft` |
| `SITE_TAGLINE` | `Personal finance, simplified daily.` |
| `PUBLISH_HOUR_UTC` | `14` (2pm UTC = 10am ET) |
| `ARTICLES_PER_DAY` | `1` |
| `ENABLE_SCHEDULER` | `true` |
| `ADMIN_SECRET` | A strong random string |
| `ENABLE_AI_DISCLOSURE` | `true` |

Optional:

| Variable | Value |
|---|---|
| `GOOGLE_ANALYTICS_ID` | `G-XXXXXXXXXX` |
| `ADSENSE_CLIENT_ID` | `ca-pub-XXXXXXXXXXXXXXXX` |
| `DEFAULT_AUTHOR` | `Dollar Draft Editorial` |
| `CONTACT_EMAIL` | `hello@yourdomain.com` |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` (default) or `claude-opus-4-7` |

### 4. Deploy

Railway automatically deploys when you push to main. The `railway.toml` handles everything:

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn src.main:app --host 0.0.0.0 --port $PORT"
```

The app will:
1. Connect to PostgreSQL and create tables on first boot
2. Start serving the website immediately (empty state until first article)
3. Start the scheduler — first article publishes at `PUBLISH_HOUR_UTC`

---

## Add a Custom Domain

Railway: **Settings** → **Domains** → **Custom Domain** → enter your domain.

Add the CNAME record Railway shows you in your DNS provider.

Update `SITE_URL` to your custom domain.

---

## Manual Article Generation

Run the bot immediately without waiting for the scheduler:

**Via admin panel:**
```
https://yourdomain.com/admin?secret=YOUR_ADMIN_SECRET
```
Click **Generate Article Now**.

**Via Railway CLI:**
```bash
railway run python -c "from src.bot import run_bot; run_bot()"
```

**Via SSH / Railway shell:**
```bash
python -c "from src.bot import run_bot; run_bot()"
```

---

## Scheduler

The scheduler runs `bot.run_bot()` once daily at `PUBLISH_HOUR_UTC` (UTC).

- Set `PUBLISH_HOUR_UTC=14` for 2:00 PM UTC (10 AM Eastern, 7 AM Pacific)
- Set `ARTICLES_PER_DAY=1` for one article per run
- Set `ENABLE_SCHEDULER=false` to disable (manual-only mode)

The scheduler is resilient — if the Claude API call fails, it logs the error and does not crash the web server. The site continues serving existing articles.

---

## AdSense Setup

1. Publish at least 20–30 quality articles first
2. Apply at [google.com/adsense](https://adsense.google.com)
3. Once approved, paste your ad unit code into `src/templates/base.html` where you see the `<!-- ADSENSE SLOT -->` comments
4. Set `ADSENSE_CLIENT_ID` in Railway environment variables

The article template already has three ad slot positions:
- Top of article
- Footer of article

Do not add fake ad units or placeholder revenue numbers to articles.

---

## Google Search Console

1. Go to [search.google.com/search-console](https://search.google.com/search-console)
2. Add your domain property
3. Submit your sitemap: `https://yourdomain.com/sitemap.xml`
4. Monitor indexing — new articles typically appear within 1–7 days

---

## Sitemap Submission

Your sitemap is auto-generated at `/sitemap.xml`. Submit to:

- **Google Search Console** → Sitemaps → add `sitemap.xml`
- **Bing Webmaster Tools** → Sitemaps
- **robots.txt** already points to the sitemap automatically

---

## Monetization Roadmap

**Month 1–2:** Publish articles, build content library

**Month 3:** Apply for Google AdSense (requires quality content + traffic)

**Month 4+:**
- Add affiliate links for credit cards (Credit Karma, NerdWallet, CardRatings programs)
- Add personal loan affiliate links (LendingTree, Credible)
- Add insurance affiliate links (EverQuote, MediaAlpha)
- Add email list opt-in (ConvertKit, Beehiiv)

**Long-term:** Sponsored content, direct ad deals, email newsletter

All affiliate links should be added manually to specific articles. Do not let the AI generate fake affiliate links or guaranteed rates.

---

## How to Change Topics

Edit `src/topics.py`. The `TOPICS` dict maps category names to lists of seed keywords.

Add new keywords to any category. Remove keywords you don't want. The bot checks the database before picking a topic — it never repeats a published keyword.

To add a new category:
1. Add it to `TOPICS` in `topics.py`
2. Add the badge CSS class in `src/templates/base.html`
3. Add it to `CATEGORY_STYLES` in `src/branding.py`

---

## How to Change the Design

All CSS is in `src/templates/base.html` inside the `<style>` block.

CSS variables at the top control the color palette:

```css
:root {
  --bg:    #FAFAF7;  /* warm white background */
  --blue:  #2563EB;  /* primary accent */
  --green: #16A34A;  /* secondary accent */
  ...
}
```

Change `--blue` and `--green` to match your brand.

The logo is an inline SVG in `src/branding.py`. Replace the `LOGO_SVG` string with your own SVG.

---

## How to Change the AI Model

Set the `CLAUDE_MODEL` environment variable:

- `claude-sonnet-4-6` — default, best balance of quality and cost
- `claude-opus-4-7` — highest quality, higher cost (~3–5x more per article)
- `claude-haiku-4-5-20251001` — fastest and cheapest, lower quality

---

## Troubleshooting Railway

**App won't start:**
- Check that `DATABASE_URL` is set (Railway Postgres plugin auto-sets this)
- Check Railway logs for Python import errors
- Make sure `ANTHROPIC_API_KEY` is set

**Articles not generating:**
- Visit `/health` to check scheduler status
- Visit `/admin?secret=YOUR_SECRET` to manually trigger and see error messages
- Check Railway logs for `ERROR` lines

**Database errors:**
- The app creates tables automatically on startup
- If you see `relation does not exist`, restart the Railway service to re-run startup

**Scheduler not running:**
- Verify `ENABLE_SCHEDULER=true`
- Railway free plans may sleep — upgrade to a paid plan to keep the process alive
- Use Railway's cron jobs as an alternative if needed

---

## Cost Estimate

| Service | Cost |
|---|---|
| Railway Hobby plan | ~$5–10/month (web service + Postgres) |
| Claude API (claude-sonnet-4-6, 1 article/day) | ~$0.05–0.15 per article (~$2–5/month) |
| Claude API (claude-opus-4-7, 1 article/day) | ~$0.50–1.50 per article (~$15–45/month) |
| Custom domain | ~$10–15/year |

Railway offers trial credits for new accounts. Claude API costs depend on article length and model choice.

These are estimates only. Actual costs depend on Railway plan, Claude model, article length, and usage.

---

## Content Disclaimer

Dollar Draft generates general educational personal finance content. It is not a licensed financial advisor, attorney, or CPA. Articles include automatic disclaimers appropriate to each category.

The system is configured to avoid:
- Guaranteed approval claims
- Specific rate quotes from named lenders
- Legal advice stated as fact
- Fabricated state laws or settlement amounts

Always review generated content before relying on it for any financial decision.

---

## Project Structure

```
blog/
├── src/
│   ├── main.py          FastAPI app + APScheduler
│   ├── routes.py        All HTTP routes
│   ├── bot.py           Publishing orchestrator
│   ├── writer.py        Claude multi-step pipeline
│   ├── database.py      PostgreSQL layer
│   ├── topics.py        111 keyword seeds + rotation logic
│   ├── safety.py        Content safety + disclaimers
│   ├── seo.py           Slugs, JSON-LD, Open Graph
│   ├── branding.py      Logo SVG, colors, category styles
│   ├── analytics.py     Google Analytics injection
│   └── templates/
│       ├── base.html    Full CSS + layout
│       ├── home.html    Homepage
│       ├── article.html Article page
│       ├── category.html Category archive
│       ├── admin.html   Admin dashboard
│       ├── sitemap.xml  Dynamic sitemap
│       ├── rss.xml      RSS feed
│       ├── robots.txt   Robots
│       └── 404.html     Error page
├── requirements.txt
├── railway.toml
├── .env.example
└── README.md
```
