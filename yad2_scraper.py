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
from utils import load_config, send_telegram, check_new_items, format_apartment_message, format_apartment_change_message

ITEM_ID_RE = re.compile(r"/item/(?:[^/?]+/)*([a-z0-9]+)(?:\?|$)", re.I)

def parse_yad2_text(text):
    """Normalize Yad2 layout into a dict."""
    import re
    parts = [p.strip() for p in text.split('|') if p.strip()]
    price = ""
    address = ""
    rooms = ""
    floor = ""
    area = ""
    
    stats_part = next((p for p in parts if 'חדרים' in p), "")
    if stats_part:
        stats_split = [s.strip() for s in stats_part.split('•')]
        for s in stats_split:
            if 'חדרים' in s:
                rooms = s.replace('חדרים', '').strip()
            elif 'קומה' in s:
                floor = s.replace('קומה', '').strip()
            elif 'מ״ר' in s or 'מ"ר' in s:
                area = s.replace('מ״ר', '').replace('מ"ר', '').strip()
                
    price_part = next((p for p in parts if '₪' in p and 'ירד ב' not in p), "")
    if not price_part and 'למידע נוסף' in parts:
        price_part = 'למידע נוסף'
    price = price_part

    stats_index = -1
    for i, p in enumerate(parts):
        if 'חדרים' in p:
            stats_index = i
            break
            
    if stats_index > 0:
        addr_candidates = []
        for p in parts[:stats_index]:
            if p == price or 'ירד ב' in p or p == 'למידע נוסף':
                continue
            if re.match(r'^[a-zA-Z\s\.\&]+$', p):
                continue
            if 'נדל"ן' in p or 'נכסים' in p or "תיווך" in p or "יזמות" in p or 'nadlan' in p.lower():
                continue
            addr_candidates.append(p)
        address = ", ".join(addr_candidates)
        
    return {
        "address": address,
        "rooms": rooms,
        "floor": floor,
        "area": area,
        "price": price
    }

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
                    items.setdefault(m.group(1), (parse_yad2_text(r["text"][:220]), full_href))
            if items:
                return items
    raise RuntimeError("Could not extract listings (Radware challenge or markup change)")


def scrape(page, topic, url, token, chat_id):
    send_telegram(token, chat_id, f"Starting scanning {topic} on link:\n{url}")
    try:
        items = scrape_items(page, url)
        new_ids, updated_ids = check_new_items(topic, items)
        
        msg_parts = []
        if new_ids:
            lines = []
            for i in new_ids:
                lines.append(format_apartment_message(items[i][0], items[i][1]))
            msg_parts.append(f"🌟 {len(new_ids)} New items:\n" + "\n----------\n".join(lines))
            
        if updated_ids:
            lines = []
            for item in updated_ids:
                if isinstance(item, tuple):
                    i, changes = item
                    lines.append(format_apartment_change_message(items[i][0], changes, items[i][1]))
                else:
                    i = item
                    lines.append(format_apartment_message(items[i][0], items[i][1]))
            msg_parts.append(f"🔄 {len(updated_ids)} Updated items (Price/Details changed):\n" + "\n----------\n".join(lines))
            
        if msg_parts:
            send_telegram(token, chat_id, "\n\n".join(msg_parts))
        else:
            send_telegram(token, chat_id, "No new or updated items")
    except Exception as e:  # noqa: BLE001
        send_telegram(token, chat_id, f"Scan workflow failed... 😥\nError: {e}")
        raise


def main():
    config = load_config()
    token = os.environ.get("API_TOKEN") or config.get("telegramApiToken")
    chat_id = os.environ.get("CHAT_ID") or config.get("chatId")
    projects = [p for p in config.get("yad2Projects", []) if not p.get("disabled")]
    for p in config.get("yad2Projects", []):
        if p.get("disabled"):
            print(f'Topic "{p.get("topic")}" is disabled. Skipping.')
    if not projects:
        print("No enabled Yad2 projects in config.json")
        return
    with Camoufox(headless=True, window=(1400, 1000)) as browser:
        page = browser.new_page()
        for p in projects:
            scrape(page, p["topic"], p["url"], token, chat_id)


if __name__ == "__main__":
    main()
