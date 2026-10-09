import json
import os
import time
from facebook_scraper import scrape_facebook_items
from utils import load_config, process_items_with_llm
from camoufox.sync_api import Camoufox
import urllib.parse

def main():
    config = load_config()
    api_key = None
    groq_api_key = os.environ.get("GROQ_API_KEY") or config.get("groqApiKey")
    
    fb_project = config["facebookProjects"][0]
    
    c_user = os.environ.get("FB_C_USER")
    xs = urllib.parse.unquote(os.environ.get("FB_XS", ""))
        
    print(f"Scraping FB URL: {fb_project['url']}")
    print(f"Filters applied: {fb_project.get('filters', {})}")
    
    with Camoufox(headless=True, humanize=True, window=(1400, 1000)) as browser:
        context = browser.new_context()
        if c_user and xs:
            context.add_cookies([
                {"name": "c_user", "value": c_user, "domain": ".facebook.com", "path": "/"},
                {"name": "xs", "value": xs, "domain": ".facebook.com", "path": "/"}
            ])
                
        page = context.new_page()
        raw_items = scrape_facebook_items(page, fb_project["url"])
        print(f"Total raw items on page: {len(raw_items)}")
        
        # Limit to 5 items to avoid Groq rate limits, plus 2 injected dummy items that perfectly match
        sample_items = {k: v for i, (k, v) in enumerate(raw_items.items()) if i < 3}
        
        # Inject one that SHOULD pass
        sample_items["DUMMY_PASS"] = ("להשכרה בשכונת שיכון דן! דירת 4 חדרים מהממת ומרווחת. מחיר: 9000 שח לחודש. כולל חניה. כניסה מיידית.", "https://dummy.com/pass", {})
        # Inject one that SHOULD fail (price too high)
        sample_items["DUMMY_FAIL_PRICE"] = ("להשכרה בשכונת הדר יוסף, דירת 4 חדרים. מחיר 12000 שח.", "https://dummy.com/fail", {})
        
        print(f"Processing {len(sample_items)} items with LLM...")
        
        unfiltered = process_items_with_llm(sample_items, fb_project["topic"], {}, api_key, groq_api_key)
        filtered = process_items_with_llm(sample_items, fb_project["topic"], fb_project.get("filters", {}), api_key, groq_api_key)
        
        print("\n" + "="*50)
        print("SCRAPE RESULTS (Sampled)")
        print("="*50)
        for item_id, item_data in unfiltered.items():
            parsed, url = item_data
            passed = item_id in filtered
            
            print(f"\n[Post ID: {item_id}]")
            print(f"Passed all filters? {'YES ✅' if passed else 'NO ❌'}")
            if not passed:
                print("Reason for rejection:")
                # simple logic to explain
                if parsed.get("price"):
                    import re
                    price_val = int(re.sub(r'[^\d]', '', str(parsed.get("price"))))
                    if price_val > fb_project["filters"]["maxPrice"]:
                        print(f" - Price ({price_val}) is higher than maxPrice ({fb_project['filters']['maxPrice']})")
                if parsed.get("rooms"):
                    import re
                    rooms_val = float(re.sub(r'[^\d\.]', '', str(parsed.get("rooms"))))
                    if rooms_val < fb_project["filters"]["minRooms"]:
                        print(f" - Rooms ({rooms_val}) is lower than minRooms ({fb_project['filters']['minRooms']})")
                        
                keywords = fb_project["filters"]["keywords"]
                raw_text_lower = parsed.get("_raw_text", "").lower()
                addr = str(parsed.get("address") or "").lower()
                has_kw = any(kw.lower() in raw_text_lower or kw.lower() in addr for kw in keywords)
                if not has_kw:
                    print(f" - Missing required keywords: {keywords}")
                    
            print(f"Extracted Data: ")
            print(f"  - Address: {parsed.get('address')}")
            print(f"  - Rooms: {parsed.get('rooms')}")
            print(f"  - Price: {parsed.get('price')}")
            print(f"  - Type: {parsed.get('type')}")

if __name__ == "__main__":
    main()
