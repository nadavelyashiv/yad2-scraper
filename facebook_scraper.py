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

from utils import load_config, send_telegram, check_new_items, format_apartment_message, format_apartment_change_message, DATA_DIR

class ApartmentData(BaseModel):
    address: str = Field(description="Address or neighborhood of the apartment. Use empty string if not found.")
    rooms: str = Field(description="Number of rooms, e.g. '3', '4.5'. Use empty string if not found.")
    floor: str = Field(description="Floor number, e.g. '2', 'קרקע'. Use empty string if not found.")
    area: str = Field(description="Area in square meters. Use empty string if not found.")
    price: str = Field(description="Price including currency symbol if present, e.g. '4000 ₪'. Use empty string if not found.")
    type: str = Field(description="Type of listing: 'rent' (השכרה) or 'sale' (מכירה). Use empty string if not found.")

def parse_with_llm(gemini_client: genai.Client, groq_client: Groq, text: str) -> dict:
    prompt = f"""
    Extract apartment details from the following Facebook post.
    Return a JSON object with the requested fields. If a field is not present, use an empty string.
    Fields to extract: address, rooms, floor, area, price, type (rent/sale).
    Post text:
    {text}
    """
    
    # Attempt 1: Groq
    if groq_client:
        try:
            print("Attempting parsing with Groq...")
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an assistant that extracts apartment details into JSON. Always return valid JSON containing exactly these keys: address, rooms, floor, area, price, type. If a field is not found, use an empty string."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            print("Groq parsing failed, falling back to Gemini...", e)

    # Attempt 2 & 3: Gemini Fallbacks
    if gemini_client:
        models_to_try = ['gemini-2.5-flash', 'gemini-1.5-flash']
        for model_name in models_to_try:
            try:
                print(f"Attempting parsing with {model_name}...")
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ApartmentData,
                    ),
                )
                return json.loads(response.text)
            except genai.errors.ClientError as e:
                if e.code == 429:
                    print(f"Rate limit reached for {model_name} (429).")
                else:
                    print(f"{model_name} API Error:", e)
            except Exception as e:
                print(f"Unknown error with {model_name}:", e)
                
    print("All LLM parsing attempts failed.")
    return {
        "address": "", "rooms": "", "floor": "", "area": "", "price": "", "type": ""
    }

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
                    
                    const textNodes = Array.from(el.querySelectorAll('div[dir="auto"]'));
                    const text = textNodes.map(n => n.innerText).join('\n').trim();
                    return { href, text };
                }).filter(r => r.text.length > 20 && r.href);
            }"""
        )
    except Exception as e:
        print("Error extracting from DOM:", e)
        rows = []
        
    items = {}
    for r in rows:
        # Extract post ID from href
        m = re.search(r"/(?:permalink|posts)/(\d+)", r["href"])
        if m:
            post_id = m.group(1)
            full_href = r["href"] if r["href"].startswith("http") else f"https://www.facebook.com{r['href'] if r['href'].startswith('/') else '/' + r['href']}"
            full_href = full_href.split('?')[0]  # Clean query params
            items[post_id] = (r["text"], full_href)
            
    if not items:
        try:
            page.screenshot(path="fb_error.png")
            with open("fb_error.html", "w", encoding="utf-8") as f:
                f.write(page.content())
        except Exception:
            pass
        raise RuntimeError("Could not extract Facebook listings.")
        
    return items

def process_and_filter(raw_items, topic, filters, api_key, groq_api_key):
    path = os.path.join(DATA_DIR, f"{topic}.json")
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}
        
    gemini_client = genai.Client(api_key=api_key) if api_key else None
    try:
        groq_client = Groq(api_key=groq_api_key) if groq_api_key else None
    except Exception:
        groq_client = None
    
    processed_items = {}
    for post_id, (raw_text, url) in raw_items.items():
        parsed_data = None
        
        # Check cache
        if post_id in saved:
            old_val = saved[post_id]
            if isinstance(old_val, dict) and old_val.get("_raw_text") == raw_text:
                parsed_data = dict(old_val)
                
        # Parse if not cached
        if not parsed_data:
            if gemini_client or groq_client:
                print(f"Parsing post {post_id} with LLM...")
                parsed_data = parse_with_llm(gemini_client, groq_client, raw_text)
                parsed_data["_raw_text"] = raw_text
            else:
                print("No LLM API key, skipping parsing.")
                continue
                
        # Apply filters
        passes = True
        
        if filters.get("type") and parsed_data.get("type"):
            if filters["type"] not in parsed_data["type"].lower() and parsed_data["type"].lower() not in filters["type"]:
                passes = False
                
        if passes and filters.get("minRooms") and parsed_data.get("rooms"):
            try:
                rooms_val = float(re.search(r"[\d\.]+", parsed_data["rooms"]).group())
                if rooms_val < filters["minRooms"]:
                    passes = False
            except Exception:
                pass
                
        if passes and filters.get("maxRooms") and parsed_data.get("rooms"):
            try:
                rooms_val = float(re.search(r"[\d\.]+", parsed_data["rooms"]).group())
                if rooms_val > filters["maxRooms"]:
                    passes = False
            except Exception:
                pass

        if passes and filters.get("maxPrice") and parsed_data.get("price"):
            try:
                price_val = float(re.search(r"[\d]+", parsed_data["price"].replace(',', '')).group())
                if price_val > filters["maxPrice"]:
                    passes = False
            except Exception:
                pass
                
        if passes and filters.get("minPrice") and parsed_data.get("price"):
            try:
                price_val = float(re.search(r"[\d]+", parsed_data["price"].replace(',', '')).group())
                if price_val < filters["minPrice"]:
                    passes = False
            except Exception:
                pass
                
        if passes and filters.get("keywords") and isinstance(filters["keywords"], list):
            found_keyword = False
            text_to_search = raw_text + " " + parsed_data.get("address", "")
            for kw in filters["keywords"]:
                if kw in text_to_search:
                    found_keyword = True
                    break
            if not found_keyword:
                passes = False
                
        if passes:
            processed_items[post_id] = (parsed_data, url)
            
    return processed_items

def scrape(page, topic, group_url, filters, token, chat_id, api_key, groq_api_key):
    import html
    start_msg = f'Starting scanning {topic} on <a href="{html.escape(group_url)}">link</a>'
    try:
        raw_items = scrape_facebook_items(page, group_url)
        items = process_and_filter(raw_items, topic, filters, api_key, groq_api_key)
        
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
    except Exception as e:
        send_telegram(token, chat_id, f"Scan workflow failed... 😥\nError: {e}")
        raise

def main():
    config = load_config()
    token = os.environ.get("API_TOKEN") or config.get("telegramApiToken")
    chat_id = os.environ.get("CHAT_ID") or config.get("chatId")
    api_key = os.environ.get("GEMINI_API_KEY") or config.get("llmApiKey")
    groq_api_key = os.environ.get("GROQ_API_KEY") or config.get("groqApiKey")
    
    projects = [p for p in config.get("facebookProjects", []) if not p.get("disabled")]
    for p in config.get("facebookProjects", []):
        if p.get("disabled"):
            print(f'Topic "{p.get("topic")}" is disabled. Skipping.')
            
    if not projects:
        print("No enabled Facebook projects in config.json")
        return
        
    c_user = os.environ.get("FB_C_USER")
    xs = os.environ.get("FB_XS")
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
