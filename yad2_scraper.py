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
from utils import load_config, send_telegram, check_new_items

ITEM_ID_RE = re.compile(r"/item/(?:[^/?]+/)*([a-z0-9]+)(?:\?|$)", re.I)

def scrape_items(page, url):
    """Return {item_id: text} for the listings on the page."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    for _ in range(15):
        time.sleep(2)
        if not page.evaluate("() => !!document.body"):
            continue
        title = page.title()
        if title == "Radware Page":
            continue  # challenge not cleared yet
        rows = page.evaluate(
            r"""() => Array.from(document.querySelectorAll('a[href*="/item/"]'))
                   .map(el => ({
                       href: el.getAttribute('href') || '',
                       text: (el.innerText || '').replace(/\n+/g, ' | ').trim()
                   }))
                   .filter(r => r.text.length > 10)"""
        )
        if rows:
            items = {}
            for r in rows:
                m = ITEM_ID_RE.search(r["href"])
                if m:
                    href = r["href"]
                    full_href = href if href.startswith("http") else f"https://www.yad2.co.il{href if href.startswith('/') else '/' + href}"
                    items.setdefault(m.group(1), (r["text"][:220], full_href))
            if items:
                return items
    raise RuntimeError("Could not extract listings (Radware challenge or markup change)")


def scrape(page, topic, url, token, chat_id):
    send_telegram(token, chat_id, f"Starting scanning {topic} on link:\n{url}")
    try:
        items = scrape_items(page, url)
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
