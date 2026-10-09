#!/usr/bin/env python3
"""Facebook Groups scraper (Camoufox edition with LLM parsing)."""
import json
import os
import re
import time
from camoufox.sync_api import Camoufox
from google import genai
from pydantic import BaseModel, Field
from groq import Groq

from utils import logger, load_config, send_telegram, check_new_items, format_apartment_message, format_apartment_change_message, process_items_with_llm, DATA_DIR, sort_ids_by_date
from datetime import datetime, timedelta

def parse_fb_date(date_str):
    if not date_str:
        return ""
    now = datetime.now()
    date_str = date_str.lower().strip()
    
    if 'just now' in date_str or 'now' == date_str or 'now' in date_str.split():
        return now.isoformat()
        
    m = re.search(r'(\d+)\s*(m|min|mins|minute|minutes)', date_str)
    if m:
        return (now - timedelta(minutes=int(m.group(1)))).isoformat()
        
    m = re.search(r'(\d+)\s*(h|hr|hrs|hour|hours)', date_str)
    if m:
        return (now - timedelta(hours=int(m.group(1)))).isoformat()
        
    m = re.search(r'(\d+)\s*(d|day|days)', date_str)
    if m:
        return (now - timedelta(days=int(m.group(1)))).isoformat()
        
    m = re.search(r'(\d+)\s*(w|week|weeks)', date_str)
    if m:
        return (now - timedelta(weeks=int(m.group(1)))).isoformat()
        
    m = re.search(r'(\d+)\s*(y|year|years)', date_str)
    if m:
        return (now - timedelta(days=int(m.group(1))*365)).isoformat()
        
    try:
        d_str = re.sub(r'\s+at\s+', ' ', date_str)
        d = datetime.strptime(d_str, "%B %d %I:%M %p")
        d = d.replace(year=now.year)
        if d > now:
            d = d.replace(year=now.year - 1)
        return d.isoformat()
    except ValueError:
        pass
        
    try:
        d = datetime.strptime(date_str, "%B %d")
        d = d.replace(year=now.year)
        if d > now:
            d = d.replace(year=now.year - 1)
        return d.isoformat()
    except ValueError:
        pass
        
    return ""

def scrape_facebook_items(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    
    # Dismiss potential popups (like "See more on Facebook") if not logged in
    try:
        page.evaluate("""() => {
            let closeBtn = document.querySelector('div[aria-label="Close"]');
            if (closeBtn) closeBtn.click();
        }""")
    except Exception:
        pass
        
    for _ in range(5):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        
    try:
        # On FB groups, feed items usually have role="article" or similar.
        rows = page.evaluate(
            r"""() => {
                const posts = Array.from(document.querySelectorAll('div[role="article"]'));
                return posts.map(el => {
                    const links = Array.from(el.querySelectorAll('a[href*="/groups/"][href*="/permalink/"], a[href*="/groups/"][href*="/posts/"]'));
                    const href = links.length > 0 ? links[0].getAttribute('href') : '';
                    const dateText = links.length > 0 ? links[0].innerText : '';
                    
                    const textNodes = Array.from(el.querySelectorAll('div[dir="auto"]'));
                    const text = textNodes.map(n => n.innerText).join('\n').trim();
                    return { href, text, dateText };
                }).filter(r => r.text.length > 20 && r.href);
            }"""
        )
    except Exception as e:
        logger.error(f"Error extracting from DOM: {e}")
        rows = []
        
    items = {}
    for r in rows:
        # Extract post ID from href
        m = re.search(r"/(?:permalink|posts)/(\d+)", r["href"])
        if m:
            post_id = m.group(1)
            full_href = r["href"] if r["href"].startswith("http") else f"https://www.facebook.com{r['href'] if r['href'].startswith('/') else '/' + r['href']}"
            full_href = full_href.split('?')[0]  # Clean query params
            
            dates = {}
            if r.get("dateText"):
                parsed = parse_fb_date(r["dateText"])
                if parsed:
                    dates["published_at"] = parsed
                    
            items[post_id] = (r["text"], full_href, dates)
            
    if not items:
        try:
            page.screenshot(path="fb_error.png")
            with open("fb_error.html", "w", encoding="utf-8") as f:
                f.write(page.content())
        except Exception:
            pass
        raise RuntimeError("Could not extract Facebook listings.")
        
    return items

def scrape(page, topic, group_url, filters, token, chat_id, api_key, groq_api_key):
    import html
    start_msg = f'Starting scanning {topic} on <a href="{html.escape(group_url)}">link</a>'
    try:
        raw_items = scrape_facebook_items(page, group_url)
        items = process_items_with_llm(raw_items, topic, filters, api_key, groq_api_key)
        
        new_ids, updated_ids = check_new_items(topic, items)
        
        new_ids = sort_ids_by_date(new_ids, items)
        updated_ids = sort_ids_by_date(updated_ids, items)
        
        results = []
        if new_ids:
            lines = []
            for i in new_ids:
                lines.append(format_apartment_message(items[i][0], items[i][1]))
            results.append(f"🌟 {len(new_ids)} New items:\n" + "\n----------\n".join(lines))
            
        if updated_ids:
            lines = []
            for item in updated_ids:
                if isinstance(item, tuple):
                    i, changes = item
                    lines.append(format_apartment_change_message(items[i][0], changes, items[i][1]))
                else:
                    i = item
                    lines.append(format_apartment_message(items[i][0], items[i][1]))
            results.append(f"🔄 {len(updated_ids)} Updated items (Price changed):\n" + "\n----------\n".join(lines))
            
        if results:
            safe_results = [html.escape(r) for r in results]
            final_msg = start_msg + "\n\n" + "\n\n".join(safe_results)
        else:
            final_msg = start_msg + "\n\nNo new or updated items"
            
        send_telegram(token, chat_id, final_msg, parse_mode="HTML")
    except Exception as e:
        send_telegram(token, chat_id, f"Scan workflow failed... 😥\nError: {e}")
        raise

def main():
    config = load_config()
    token = os.environ.get("API_TOKEN")
    chat_id = os.environ.get("CHAT_ID")
    api_key = os.environ.get("GEMINI_API_KEY") or config.get("llmApiKey")
    groq_api_key = os.environ.get("GROQ_API_KEY") or config.get("groqApiKey")
    
    projects = [p for p in config.get("facebookProjects", []) if p.get("enabled")]
    for p in config.get("facebookProjects", []):
        if not p.get("enabled"):
            logger.info(f'Topic "{p.get("topic")}" is disabled. Skipping.')
            
    if not projects:
        logger.info("No enabled Facebook projects in config.json")
        return
        
    c_user = os.environ.get("FB_C_USER")
    xs = os.environ.get("FB_XS")
    
    import urllib.parse
    if xs:
        xs = urllib.parse.unquote(xs)
        
    cookies = config.get("facebookCookies", [])
    if c_user and xs:
        cookies.extend([
            {"name": "c_user", "value": c_user, "domain": ".facebook.com"},
            {"name": "xs", "value": xs, "domain": ".facebook.com"}
        ])
    
    with Camoufox(headless=True, humanize=True, window=(1400, 1000)) as browser:
        context = browser.new_context()
        if cookies:
            valid_cookies = []
            for c in cookies:
                if c.get("name") and c.get("value"):
                    c["domain"] = c.get("domain", ".facebook.com")
                    c["path"] = c.get("path", "/")
                    valid_cookies.append(c)
            if valid_cookies:
                context.add_cookies(valid_cookies)
                
        page = context.new_page()
        for p in projects:
            scrape(page, p["topic"], p["url"], p.get("filters", {}), token, chat_id, api_key, groq_api_key)

if __name__ == "__main__":
    main()
