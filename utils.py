import json
import os
import urllib.parse
import urllib.request
import logging
import sys

logger = logging.getLogger("scraper")
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler("scraper.log", encoding="utf-8")
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)



CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def generate_raw_string(val: dict) -> str:
    parts = []
    if val.get('address'): parts.append(val['address'])
    if val.get('rooms'): parts.append(f"{val['rooms']} חד׳")
    if val.get('floor'): parts.append(f"קומה {val['floor']}")
    if val.get('area'): parts.append(f"{val['area']} מ״ר")
    if val.get('price'):
        price = val['price']
        if isinstance(price, int):
            parts.append(f"{price:,} ₪")
        else:
            parts.append(str(price))
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
        logger.info("[telegram skipped — no token/chatId]\n" + text)
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
            logger.error(f"Telegram send failed: {e}")

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
                        if k == "price":
                            old_p = old_val.get(k)
                            new_p = new_val[k]
                            if isinstance(old_p, str) and old_p != "":
                                import re
                                try:
                                    old_p = int(re.sub(r'[^\d]', '', old_p))
                                except ValueError:
                                    pass
                            if old_p != new_p and old_p not in ("", None):
                                changes.append(f"{k}: {old_val.get(k)} -> {new_p}")
                    if changes:
                        updated_ids.append((i, changes))
                else:
                    if parser:
                        old_dict = parser(old_val)
                        changes = []
                        for k in new_val:
                            if k == "price":
                                old_p = old_dict.get(k)
                                new_p = new_val[k]
                                if isinstance(old_p, str) and old_p != "":
                                    import re
                                    try:
                                        old_p = int(re.sub(r'[^\d]', '', old_p))
                                    except ValueError:
                                        pass
                                if old_p != new_p and old_p not in ("", None):
                                    changes.append(f"{k}: {old_dict.get(k)} -> {new_p}")
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
    price: int | None = Field(description="Price as a number. Extract only the digits, e.g. 4000. Use null if not found.", default=None)
    type: str = Field(description="Type of listing: 'rent' (השכרה) or 'sale' (מכירה). Use empty string if not found.")

def parse_with_llm(gemini_client: genai.Client, groq_client: Groq, text: str) -> dict:
    config = load_config()
    llm_models = config.get("llmModels", {})
    groq_model = llm_models.get("groq", "llama3-70b-8192")
    gemini_models = llm_models.get("gemini", ["gemini-2.5-flash", "gemini-3.8-flash"])

    prompt = f"""
    Extract apartment details from the following post/listing.
    Return a JSON object with the requested fields. If a field is not present, use an empty string.
    Fields to extract: address, rooms, floor, area, price, type (rent/sale).
    Post text:
    {text}
    """
    
    parsed_data = None
    if groq_client:
        try:
            logger.info(f"Attempting parsing with Groq ({groq_model})...")
            completion = groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an assistant that extracts apartment details into JSON. Always return valid JSON containing exactly these keys: address, rooms, floor, area, price, type. If a field is not found, use an empty string."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            parsed_data = json.loads(completion.choices[0].message.content)
        except Exception as e:
            logger.warning(f"Groq parsing failed, falling back to Gemini... {e}")

    if not parsed_data and gemini_client:
        models_to_try = ['gemini-3.5-flash-lite', 'gemini-3.8-flash']
        for model_name in models_to_try:
            try:
                logger.info(f"Attempting parsing with {model_name}...")
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ApartmentData,
                    ),
                )
                parsed_data = json.loads(response.text)
                break
            except genai.errors.ClientError as e:
                if e.code == 429:
                    logger.warning(f"Rate limit reached for {model_name} (429).")
                else:
                    logger.error(f"{model_name} API Error: {e}")
            except Exception as e:
                logger.error(f"Unknown error with {model_name}: {e}")
                
    if not parsed_data:
        logger.error("All LLM parsing attempts failed.")
        parsed_data = {
            "address": "", "rooms": "", "floor": "", "area": "", "price": None, "type": ""
        }
        
    if parsed_data.get("price"):
        import re
        try:
            price_val = int(re.sub(r'[^\d]', '', str(parsed_data["price"])))
            parsed_data["price"] = price_val
        except ValueError:
            parsed_data["price"] = None
    else:
        parsed_data["price"] = None
        
    return parsed_data

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
                is_empty = not any(old_val.get(k) for k in ["address", "rooms", "floor", "price", "type", "area"])
                if not is_empty:
                    parsed_data = dict(old_val)
                    if parsed_data.get("price") and isinstance(parsed_data["price"], str):
                        import re
                        try:
                            parsed_data["price"] = int(re.sub(r'[^\d]', '', parsed_data["price"]))
                        except ValueError:
                            parsed_data["price"] = None
                
        if not parsed_data:
            if gemini_client or groq_client:
                logger.info(f"Parsing item {item_id} with LLM...\nRaw text:\n{raw_text}")
                parsed_data = parse_with_llm(gemini_client, groq_client, raw_text)
                parsed_data["_raw_text"] = raw_text
            else:
                logger.warning("No LLM API key, skipping parsing.")
                continue
                
        passes = True
        if filters:
            if filters.get("type") and parsed_data.get("type"):
                if filters["type"] not in parsed_data["type"].lower() and parsed_data["type"].lower() not in filters["type"]:
                    passes = False
                    
            if filters.get("max_price") and parsed_data.get("price"):
                import re
                try:
                    price_val = int(re.sub(r'[^\d]', '', str(parsed_data["price"])))
                    if price_val > filters["max_price"]:
                        passes = False
                except ValueError:
                    pass
        
        if passes:
            processed_items[item_id] = (parsed_data, url)
            
    return processed_items
