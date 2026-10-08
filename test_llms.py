import os
import json
from dotenv import load_dotenv
from google import genai
from groq import Groq

def test_llms():
    load_dotenv()
    
    with open('config.json', 'r') as f:
        config = json.load(f)
        
    try:
        with open('test_data.json', 'r', encoding='utf-8') as f:
            test_data = json.load(f)
    except FileNotFoundError:
        print("test_data.json not found! Please run the scraper snippet first.")
        return

    # Extract text from the saved test data
    yad2_text = test_data.get("yad2", [""])[0] if isinstance(test_data.get("yad2"), list) else test_data.get("yad2", "")
    madlan_text = test_data.get("madlan", "")
    
    items_to_test = {
        "Yad2": yad2_text,
        "Madlan": madlan_text
    }
    
    llm_models = config.get('llmModels', {})
    gemini_key = os.environ.get('GEMINI_API_KEY')
    groq_key = os.environ.get('GROQ_API_KEY')
    
    system_prompt = "You are an assistant that extracts apartment details into JSON. Always return valid JSON containing exactly these keys: address, rooms, floor, area, price, type. If a field is not found, use an empty string."
    
    def get_prompt(text):
        return f"""
        Extract apartment details from the following post/listing.
        Return a JSON object with the requested fields. If a field is not present, use an empty string.
        Fields to extract: address, rooms, floor, area, price, type (rent/sale).
        Post text:
        {text}
        """

    # Test Gemini Models
    if gemini_key:
        client = genai.Client(api_key=gemini_key)
        gemini_models = llm_models.get('gemini', [])
        if isinstance(gemini_models, str):
            gemini_models = [gemini_models]
            
        for model_name in gemini_models:
            print(f"\n=== Testing Gemini model '{model_name}' ===")
            for source, text in items_to_test.items():
                print(f"\n[{source} Item]: {text}")
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=get_prompt(text),
                        config=genai.types.GenerateContentConfig(
                            response_mime_type="application/json",
                            system_instruction=system_prompt
                        )
                    )
                    print(f"  [SUCCESS] {response.text.strip()}")
                except Exception as e:
                    print(f"  [ERROR] Failed to parse: {e}")
    
    # Test Groq Model
    if groq_key:
        # Avoid crashing if the key is the placeholder
        if groq_key == "your_groq_api_key_here":
            print("\n=== Testing Groq model ===")
            print("  [SKIP] Please replace 'your_groq_api_key_here' in .env with a real Groq API key.")
        else:
            groq_client = Groq(api_key=groq_key)
            groq_model = llm_models.get('groq')
            if groq_model:
                print(f"\n=== Testing Groq model '{groq_model}' ===")
                for source, text in items_to_test.items():
                    print(f"\n[{source} Item]: {text}")
                    try:
                        completion = groq_client.chat.completions.create(
                            model=groq_model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": get_prompt(text)}
                            ],
                            response_format={"type": "json_object"}
                        )
                        print(f"  [SUCCESS] {completion.choices[0].message.content.strip()}")
                    except Exception as e:
                        print(f"  [ERROR] Failed to parse: {e}")

if __name__ == '__main__':
    test_llms()
