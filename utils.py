import json
import os
import urllib.parse
import urllib.request

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def generate_raw_string(val: dict) -> str:
    parts = []
    if val.get('address'): parts.append(val['address'])
    if val.get('rooms'): parts.append(f"{val['rooms']} חד׳")
    if val.get('floor'): parts.append(f"קומה {val['floor']}")
    if val.get('area'): parts.append(f"{val['area']} מ״ר")
    if val.get('price'): parts.append(val['price'])
    return " | ".join(parts)

def format_apartment_message(val, url):
    if isinstance(val, dict):
        return f"{generate_raw_string(val)}\n{url}"
    return f"{val}\n{url}"

def format_apartment_change_message(val, changes, url):
    change_str = ", ".join(changes)
    if isinstance(val, dict):
        return f"[{change_str}]\n{generate_raw_string(val)}\n{url}"
    return f"[{change_str}]\n{val}\n{url}"

def load_config():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def send_telegram(token, chat_id, text, parse_mode=None):
    if not token or not chat_id:
        print("[telegram skipped — no token/chatId]\n" + text)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    chunks = []
    if len(text) <= 4000:
        chunks = [text]
    else:
        current_chunk = ""
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 > 4000:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        data = urllib.parse.urlencode(payload).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
                r.read()
        except Exception as e:  # noqa: BLE001
            print(f"Telegram send failed: {e}")

def check_new_items(topic, items, parser=None):
    path = os.path.join(DATA_DIR, f"{topic}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}

    # Backwards compatibility: migrate old list format
    if isinstance(saved, list):
        saved = {i: "" for i in saved}

    current = list(items.keys())
    new_ids = []
    updated_ids = []

    for i in current:
        if i not in saved:
            new_ids.append(i)
        else:
            old_val = saved[i]
            new_val = items[i][0]
            if isinstance(new_val, dict):
                if isinstance(old_val, dict):
                    changes = []
                    for k in new_val:
                        if k == "price" and old_val.get(k) != new_val[k]:
                            changes.append(f"{k}: {old_val.get(k)} -> {new_val[k]}")
                    if changes:
                        updated_ids.append((i, changes))
                else:
                    if parser:
                        old_dict = parser(old_val)
                        changes = []
                        for k in new_val:
                            if k == "price" and old_dict.get(k) != new_val[k]:
                                changes.append(f"{k}: {old_dict.get(k)} -> {new_val[k]}")
                        if changes:
                            updated_ids.append((i, changes))
                    else:
                        raw_new = generate_raw_string(new_val)
                        old_val_norm = old_val.replace('\n', '|')
                        if old_val_norm != raw_new and old_val != "":
                            updated_ids.append(i)
            elif old_val != new_val and old_val != "":
                # Fallback for old string comparison
                updated_ids.append(i)

    # State pruning: keep only currently visible items, save their latest text
    updated_state = {i: items[i][0] for i in current}

    if new_ids or updated_ids or updated_state != saved:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(updated_state, f, ensure_ascii=False, indent=2)
        with open(os.path.join(os.path.dirname(__file__), "push_me"), "w") as f:
            f.write("")
            
    return new_ids, updated_ids

from google import genai
from pydantic import BaseModel, Field
from groq import Groq

class ApartmentData(BaseModel):
    address: str = Field(description="Address or neighborhood of the apartment. Use empty string if not found.")
    rooms: str = Field(description="Number of rooms, e.g. '3', '4.5'. Use empty string if not found.")
    floor: str = Field(description="Floor number, e.g. '2', 'קרקע'. Use empty string if not found.")
    area: str = Field(description="Area in square meters. Use empty string if not found.")
    price: str = Field(description="Price including currency symbol if present, e.g. '4000 ₪'. Use empty string if not found.")
    type: str = Field(description="Type of listing: 'rent' (השכרה) or 'sale' (מכירה). Use empty string if not found.")

def parse_with_llm(gemini_client: genai.Client, groq_client: Groq, text: str) -> dict:
    prompt = f"""
    Extract apartment details from the following post/listing.
    Return a JSON object with the requested fields. If a field is not present, use an empty string.
    Fields to extract: address, rooms, floor, area, price, type (rent/sale).
    Post text:
    {text}
    """
    
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

def process_items_with_llm(raw_items, topic, filters, api_key, groq_api_key):
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
    for item_id, (raw_text, url) in raw_items.items():
        parsed_data = None
        
        if item_id in saved:
            old_val = saved[item_id]
            if isinstance(old_val, dict) and old_val.get("_raw_text") == raw_text:
                parsed_data = dict(old_val)
                
        if not parsed_data:
            if gemini_client or groq_client:
                print(f"Parsing item {item_id} with LLM...")
                parsed_data = parse_with_llm(gemini_client, groq_client, raw_text)
                parsed_data["_raw_text"] = raw_text
            else:
                print("No LLM API key, skipping parsing.")
                continue
                
        passes = True
        if filters:
            if filters.get("type") and parsed_data.get("type"):
                if filters["type"] not in parsed_data["type"].lower() and parsed_data["type"].lower() not in filters["type"]:
                    passes = False
                    
            if filters.get("max_price") and parsed_data.get("price"):
                import re
                try:
                    price_val = int(re.sub(r'[^\d]', '', parsed_data["price"]))
                    if price_val > filters["max_price"]:
                        passes = False
                except ValueError:
                    pass
        
        if passes:
            processed_items[item_id] = (parsed_data, url)
            
    return processed_items
