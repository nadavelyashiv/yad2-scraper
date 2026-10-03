#!/usr/bin/env python3
"""Madlan scraper (Camoufox edition)."""
import os
import re
import time

from camoufox.sync_api import Camoufox
from utils import load_config, send_telegram, check_new_items, format_apartment_message, format_apartment_change_message, process_items_with_llm



def scrape_madlan_items(page, url):
    """Return {item_id: text} for the listings on the page."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    for _ in range(15):
        time.sleep(2)
        try:
            if not page.evaluate("() => !!document.body"):
                continue
            rows = page.evaluate(
                r"""() => {
                    let links = Array.from(document.querySelectorAll('a[data-auto="listed-bulletin-clickable"]'));
                    if (links.length === 0) {
                        links = Array.from(document.querySelectorAll('a')).filter(a => a.href && a.href.includes('/listings/'));
                    }
                    return links.map(el => {
                        const href = el.getAttribute('href') || el.href || '';
                        let text = (el.innerText || '').replace(/\n+/g, ' | ').trim();
                        if (text.length < 10 && el.parentElement) {
                            text = (el.parentElement.innerText || '').replace(/\n+/g, ' | ').trim();
                        }
                        if (text.length < 10 && el.parentElement && el.parentElement.parentElement) {
                            text = (el.parentElement.parentElement.innerText || '').replace(/\n+/g, ' | ').trim();
                        }
                        return { href, text };
                    }).filter(r => r.text.length > 10 && r.href && r.href.includes('/listings/'));
                }"""
            )
        except Exception:
            continue
        if rows:
            items = {}
            for r in rows:
                m = re.search(r"/listings/([a-zA-Z0-9_-]+)", r["href"])
                if m:
                    full_href = r["href"] if r["href"].startswith("http") else f"https://www.madlan.co.il{r['href'] if r['href'].startswith('/') else '/' + r['href']}"
                    items.setdefault(m.group(1), (r["text"], full_href))
            if items:
                return items
    try:
        page.screenshot(path="madlan_error.png")
        with open("madlan_error.html", "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception:
        pass
    raise RuntimeError("Could not extract Madlan listings (markup change or challenge)")


def scrape(page, topic, url, token, chat_id, api_key, groq_api_key):
    import html
    start_msg = f'Starting scanning {topic} on <a href="{html.escape(url)}">link</a>'
    try:
        raw_items = scrape_madlan_items(page, url)
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
            scrape(page, p["topic"], p["url"], token, chat_id, api_key, groq_api_key)


if __name__ == "__main__":
    main()
