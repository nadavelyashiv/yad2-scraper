#!/usr/bin/env python3
"""Madlan scraper."""
import os
import re

import time
from camoufox.sync_api import Camoufox
from bs4 import BeautifulSoup

from utils import logger, load_config, send_telegram, check_new_items, format_apartment_message, format_apartment_change_message, process_items_with_llm, sort_ids_by_date
from datetime import datetime

def parse_madlan_date(d_str):
    try:
        d_str_clean = d_str.replace(" GMT ", " ")
        d = datetime.strptime(d_str_clean, "%a %b %d %H:%M:%S %Y")
        return d.isoformat()
    except Exception:
        return d_str

def scrape_madlan_items(page, url):
    """Return {item_id: (text, url, dates)} for the listings on the page."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("a[href*='/listings/']", timeout=20000)
    except:
        # Fallback wait if it didn't find the selector, might just be empty results or still loading
        time.sleep(5)
    
    html_content = page.content()
    
    dates_map = {}
    for item_id in set(re.findall(r'/listings/([a-zA-Z0-9_-]+)', html_content)):
        idx = html_content.find(f'"{item_id}"')
        if idx == -1: idx = html_content.find(item_id)
        if idx != -1:
            snippet = html_content[idx:idx+3000]
            m = re.search(r'lastUpdated":"([^"]+)"', snippet)
            if m:
                dates_map[item_id] = {'updated_at': parse_madlan_date(m.group(1))}

    soup = BeautifulSoup(html_content, "html.parser")
    links = soup.find_all("a", attrs={"data-auto": "listed-bulletin-clickable"})
    if not links:
        # Fallback to all links containing /listings/
        all_links = soup.find_all("a", href=True)
        links = [a for a in all_links if "/listings/" in a.get("href")]
    
    items = {}
    for a in links:
        href = a.get("href", "")
        text = a.get_text(separator=" | ", strip=True)
        
        if len(text) < 10 and a.parent:
            text = a.parent.get_text(separator=" | ", strip=True)
        if len(text) < 10 and a.parent and a.parent.parent:
            text = a.parent.parent.get_text(separator=" | ", strip=True)
            
        if len(text) > 10 and "/listings/" in href:
            m = re.search(r"/listings/([a-zA-Z0-9_-]+)", href)
            if m:
                item_id = m.group(1)
                full_href = href if href.startswith("http") else f"https://www.madlan.co.il{href if href.startswith('/') else '/' + href}"
                items.setdefault(item_id, (text, full_href, dates_map.get(item_id, {})))
                
    if items:
        return items
    
    logger.error("Could not extract Madlan listings (markup change or challenge). Returning empty results.")
    return {}


def scrape(page, topic, url, token, chat_id, api_key, groq_api_key):
    import html
    start_msg = f'Starting scanning {topic} on <a href="{html.escape(url)}">link</a>'
    try:
        raw_items = scrape_madlan_items(page, url)
        items = process_items_with_llm(raw_items, topic, None, api_key, groq_api_key)
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
    except Exception as e:  # noqa: BLE001
        send_telegram(token, chat_id, f"Scan workflow failed... 😥\nError: {e}")
        raise


def main():
    config = load_config()
    token = os.environ.get("API_TOKEN")
    chat_id = os.environ.get("CHAT_ID")
    api_key = os.environ.get("GEMINI_API_KEY")
    groq_api_key = os.environ.get("GROQ_API_KEY")
    
    projects = [p for p in config.get("madlanProjects", []) if not p.get("disabled")]
    for p in config.get("madlanProjects", []):
        if p.get("disabled"):
            logger.info(f'Topic "{p.get("topic")}" is disabled. Skipping.')
    if not projects:
        logger.info("No enabled Madlan projects in config.json")
        return
    
    with Camoufox(headless=True, humanize=True, window=(1400, 1000)) as browser:
        page = browser.new_page()
        for p in projects:
            scrape(page, p["topic"], p["url"], token, chat_id, api_key, groq_api_key)


if __name__ == "__main__":
    main()
