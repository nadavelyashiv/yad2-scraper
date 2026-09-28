import json
import os
import urllib.parse
import urllib.request

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def send_telegram(token, chat_id, text):
    if not token or not chat_id:
        print("[telegram skipped — no token/chatId]\n" + text)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    chunks = []
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
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": chunk}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
                r.read()
        except Exception as e:  # noqa: BLE001
            print(f"Telegram send failed: {e}")

def check_new_items(topic, items):
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
        elif saved[i] != items[i][0] and saved[i] != "":
            # Only trigger update if we actually had previous text and it changed
            updated_ids.append(i)

    # State pruning: keep only currently visible items, save their latest text
    updated_state = {i: items[i][0] for i in current}

    if new_ids or updated_ids or updated_state != saved:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(updated_state, f, ensure_ascii=False, indent=2)
        with open(os.path.join(os.path.dirname(__file__), "push_me"), "w") as f:
            f.write("")
            
    return new_ids, updated_ids
