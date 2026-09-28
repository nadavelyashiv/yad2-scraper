#!/usr/bin/env python3
"""Madlan scraper (Camoufox edition)."""
import os
import re
import time

from camoufox.sync_api import Camoufox
from utils import load_config, send_telegram, check_new_items

def scrape_madlan_items(page, url):
    """Return {item_id: text} for the listings on the page."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    for _ in range(15):
        time.sleep(2)
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
        if rows:
            items = {}
            for r in rows:
                m = re.search(r"/listings/([a-zA-Z0-9_-]+)", r["href"])
                if m:
                    full_href = r["href"] if r["href"].startswith("http") else f"https://www.madlan.co.il{r['href'] if r['href'].startswith('/') else '/' + r['href']}"
                    items.setdefault(m.group(1), (r["text"][:220], full_href))
            if items:
                return items
    raise RuntimeError("Could not extract Madlan listings (markup change or challenge)")


def scrape(page, topic, url, token, chat_id):
    send_telegram(token, chat_id, f"Starting scanning {topic} on link:\n{url}")
    try:
        items = scrape_madlan_items(page, url)
        new_ids = check_new_items(topic, items)
        if new_ids:
            lines = [f"{items[i][0]}\n{items[i][1]}" for i in new_ids]
            msg = f"{len(new_ids)} new items:\n" + "\n----------\n".join(lines)
            send_telegram(token, chat_id, msg)
        else:
            send_telegram(token, chat_id, "No new items were added")
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
