#!/usr/bin/env python3
"""Madlan scraper (Camoufox edition)."""
import os
import re
import time

from camoufox.sync_api import Camoufox
from utils import load_config, send_telegram, check_new_items, format_apartment_message, format_apartment_change_message

def parse_madlan_text(text):
    """Normalize Madlan's A/B test layouts into a dict."""
    parts = [p.strip() for p in text.split('|') if p.strip()]
    
    price = next((p for p in reversed(parts) if '₪' in p), "")
    address = ""
    rooms = ""
    floor = ""
    area = ""
    
    if len(parts) >= 5:
        # New format
        address = parts[1] if "ירידת מחיר" in parts[0] else parts[0]
        for i, p in enumerate(parts):
            if 'חד׳' in p and i > 0:
                rooms = parts[i-1]
            if 'קומה' in p and i > 0:
                floor = parts[i-1]
            if ('מ״ר' in p or 'מ"ר' in p) and i > 0:
                area = parts[i-1]
    else:
        # Old format
        price = next((p for p in parts if '₪' in p), price)
        stats = next((p for p in parts if 'חד׳' in p), "")
        if stats:
            import re
            m_rooms = re.search(r'([\d\.]+) חד', stats)
            if m_rooms: rooms = m_rooms.group(1)
            m_area = re.search(r'([\d\.]+) מ', stats)
            if m_area: area = m_area.group(1)
        address = next((p for p in parts if '₪' not in p and 'חד׳' not in p and "תיווך" not in p and "ירידת מחיר" not in p), "")
        
    return {
        "address": address,
        "rooms": rooms,
        "floor": floor,
        "area": area,
        "price": price
    }

def scrape_madlan_items(page, url):
    """Return {item_id: text} for the listings on the page."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    for _ in range(15):
        time.sleep(2)
        try:
            if not page.evaluate("() => !!document.body"):
                continue
            rows = page.evaluate(
                r"""() => Array.from(document.querySelectorAll('div[data-auto="listed-bulletin"]'))
                       .map(el => {
                           const linkEl = el.querySelector('a[data-auto="listed-bulletin-clickable"]');
                           const href = linkEl ? linkEl.getAttribute('href') : '';
                           const text = (el.innerText || '').replace(/\n+/g, ' | ').trim();
                           return { href, text };
                       })
                       .filter(r => r.text.length > 10 && r.href)"""
            )
        except Exception:
            continue
        if rows:
            items = {}
            for r in rows:
                m = re.search(r"/listings/([a-zA-Z0-9_-]+)", r["href"])
                if m:
                    full_href = r["href"] if r["href"].startswith("http") else f"https://www.madlan.co.il{r['href'] if r['href'].startswith('/') else '/' + r['href']}"
                    items.setdefault(m.group(1), (parse_madlan_text(r["text"][:220]), full_href))
            if items:
                return items
    raise RuntimeError("Could not extract Madlan listings (markup change or challenge)")


def scrape(page, topic, url, token, chat_id):
    send_telegram(token, chat_id, f"Starting scanning {topic} on link:\n{url}")
    try:
        items = scrape_madlan_items(page, url)
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
    projects = [p for p in config.get("madlanProjects", []) if not p.get("disabled")]
    for p in config.get("madlanProjects", []):
        if p.get("disabled"):
            print(f'Topic "{p.get("topic")}" is disabled. Skipping.')
    if not projects:
        print("No enabled Madlan projects in config.json")
        return
    with Camoufox(headless=True, window=(1400, 1000)) as browser:
        page = browser.new_page()
        for p in projects:
            scrape(page, p["topic"], p["url"], token, chat_id)


if __name__ == "__main__":
    main()
