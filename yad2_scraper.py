#!/usr/bin/env python3
"""Yad2 scraper (Camoufox edition).

Yad2 is now behind Radware Bot Manager and renders listings client-side as a
Next.js SPA, so the original bare-fetch + `.feeditem .pic` approach returns
nothing. This drives a stealth Firefox (Camoufox) that clears the challenge,
then keys off each listing's stable item id (from its `/item/<id>` link)
instead of image URLs.

Config lives in config.json (same shape as before):
  { "telegramApiToken": null, "chatId": null,
    "projects": [{ "topic": "...", "url": "...", "disabled": false }] }
API_TOKEN / CHAT_ID env vars override the config values.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

from camoufox.sync_api import Camoufox
from utils import load_config, send_telegram, check_new_items, format_apartment_message, format_apartment_change_message, process_items_with_llm

ITEM_ID_RE = re.compile(r"/item/(?:[^/?]+/)*([a-z0-9]+)(?:\?|$)", re.I)



def scrape_items(page, url):
    """Return {item_id: text} for the listings on the page."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    for _ in range(15):
        time.sleep(2)
        try:
            if not page.evaluate("() => !!document.body"):
                continue
            title = page.title()
            if title == "Radware Page":
                continue  # challenge not cleared yet
            rows = page.evaluate(
                r"""() => Array.from(document.querySelectorAll('div[class*="feedItemBox"] a[href*="/item/"]'))
                       .map(el => ({
                           href: el.getAttribute('href') || '',
                           text: (el.innerText || '').replace(/\n+/g, ' | ').trim()
                       }))
                       .filter(r => r.text.length > 10)"""
            )
        except Exception:
            # Execution context might be destroyed if page is navigating/reloading (e.g. Radware cleared)
            continue
        if rows:
            items = {}
            for r in rows:
                m = ITEM_ID_RE.search(r["href"])
                if m:
                    href = r["href"]
                    full_href = href if href.startswith("http") else f"https://www.yad2.co.il{href if href.startswith('/') else '/' + href}"
                    items.setdefault(m.group(1), (r["text"], full_href))
            if items:
                return items
    raise RuntimeError("Could not extract listings (Radware challenge or markup change)")


def scrape(page, topic, url, token, chat_id, api_key, groq_api_key):
    import html
    start_msg = f'Starting scanning {topic} on <a href="{html.escape(url)}">link</a>'
    try:
        raw_items = scrape_items(page, url)
        items = process_items_with_llm(raw_items, topic, None, api_key, groq_api_key)
        new_ids, updated_ids = check_new_items(topic, items)
        
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
    except Exception as e:  # noqa: BLE001
        send_telegram(token, chat_id, f"Scan workflow failed... 😥\nError: {e}")
        raise


def main():
    config = load_config()
    token = os.environ.get("API_TOKEN")
    chat_id = os.environ.get("CHAT_ID")
    api_key = os.environ.get("GEMINI_API_KEY")
    groq_api_key = os.environ.get("GROQ_API_KEY")
    
    projects = [p for p in config.get("yad2Projects", []) if p.get("enabled")]
    for p in config.get("yad2Projects", []):
        if not p.get("enabled"):
            print(f'Topic "{p.get("topic")}" is disabled. Skipping.')
    if not projects:
        print("No enabled Yad2 projects in config.json")
        return
    with Camoufox(headless=True, window=(1400, 1000)) as browser:
        page = browser.new_page()
        for p in projects:
            scrape(page, p["topic"], p["url"], token, chat_id, api_key, groq_api_key)


if __name__ == "__main__":
    main()
