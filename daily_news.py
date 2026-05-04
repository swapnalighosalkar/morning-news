"""
daily_news.py - Runs via GitHub Actions every morning at 8am.
Reads config from environment variables (set as GitHub Secrets).
"""

import asyncio
import httpx
import os
from datetime import datetime
import brevo

# ─────────────────────────────────────────
# CONFIG — reads from environment variables
# Set these as GitHub Secrets in your repo
# ─────────────────────────────────────────

GNEWS_API_KEY  = os.environ["GNEWS_API_KEY"]
BREVO_API_KEY  = os.environ["BREVO_API_KEY"]
FROM_EMAIL     = os.environ["FROM_EMAIL"]
TO_EMAIL       = os.environ["TO_EMAIL"]

CATEGORY       = "world"   # world, technology, business, sports, health
MAX_ARTICLES   = 8

# ─────────────────────────────────────────

GNEWS_URL = "https://gnews.io/api/v4/top-headlines"


async def fetch_news() -> list[dict]:
    params = {
        "category": CATEGORY,
        "lang": "en",
        "max": MAX_ARTICLES,
        "apikey": GNEWS_API_KEY,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(GNEWS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    articles = []
    for item in data.get("articles", []):
        articles.append({
            "title":       item.get("title", ""),
            "description": item.get("description", ""),
            "url":         item.get("url", ""),
            "source":      item.get("source", {}).get("name", "Unknown"),
            "publishedAt": item.get("publishedAt", ""),
            "image":       item.get("image", ""),
        })
    return articles


def build_html_email(articles: list[dict], date_str: str) -> str:
    articles_html = ""
    for a in articles:
        img_html = f'<img src="{a["image"]}" style="width:100%;max-height:200px;object-fit:cover;border-radius:6px;margin-bottom:10px">' if a.get("image") else ""
        articles_html += f"""
        <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:18px;margin-bottom:16px">
          {img_html}
          <div style="font-size:11px;color:#6b7280;margin-bottom:6px">{a['source']} &nbsp;·&nbsp; {a['publishedAt'][:10]}</div>
          <a href="{a['url']}" style="font-size:17px;font-weight:600;color:#111827;text-decoration:none;line-height:1.4">{a['title']}</a>
          <p style="font-size:14px;color:#374151;margin:10px 0;line-height:1.6">{a['description']}</p>
          <a href="{a['url']}" style="font-size:13px;color:#2563eb;text-decoration:none">Read full article →</a>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div style="max-width:600px;margin:0 auto;padding:24px 16px">
    <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);border-radius:12px;padding:24px;margin-bottom:20px;text-align:center">
      <div style="font-size:28px;margin-bottom:6px">🌍</div>
      <h1 style="color:#ffffff;margin:0;font-size:22px;font-weight:600">Your Morning News Briefing</h1>
      <p style="color:#93c5fd;margin:6px 0 0;font-size:14px">{date_str} &nbsp;·&nbsp; Top {len(articles)} {CATEGORY.title()} Stories</p>
    </div>
    {articles_html}
    <div style="text-align:center;padding:16px;color:#9ca3af;font-size:12px">
      Delivered by GitHub Actions · Powered by GNews &amp; Brevo
    </div>
  </div>
</body>
</html>"""


def send_email(subject: str, html_body: str):
    client = brevo.Brevo(api_key=BREVO_API_KEY)
    response = client.transactional_emails.send_transac_email(
        sender=brevo.SendTransacEmailRequestSender(email=FROM_EMAIL, name="Morning News"),
        to=[brevo.SendTransacEmailRequestToItem(email=TO_EMAIL)],
        subject=subject,
        html_content=html_body,
    )
    print(f"Email sent! Response: {response}")


async def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching {CATEGORY} news...")
    articles = await fetch_news()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Got {len(articles)} articles")

    date_str  = datetime.now().strftime("%A, %d %B %Y")
    subject   = f"Morning News Briefing — {date_str}"
    html_body = build_html_email(articles, date_str)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending to {TO_EMAIL}...")
    send_email(subject, html_body)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done!")


if __name__ == "__main__":
    asyncio.run(main())
