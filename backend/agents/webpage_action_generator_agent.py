import json
from textwrap import dedent
import base64
from openai import AzureOpenAI
from config import openai
from config import WEBPAGE_ACTION_CACHE_FILE_PATH

class WebpageActionGeneratorAgent:
    def __init__(self, openai: AzureOpenAI) -> None:
        self.openai = openai
        pass

    def get_cache(self, screenshot_path: str, action: str,) -> dict:
        # Try to read from webpage_action_cache.json and return cached data if it exists
        try:
            with open(WEBPAGE_ACTION_CACHE_FILE_PATH, 'r') as f:
                cache = json.load(f)
                cache_key = f"{screenshot_path}:{action}"
                return cache[cache_key]
        except (FileNotFoundError, json.JSONDecodeError):
            # Return empty dict if file doesn't exist or is invalid JSON
            return None

    def set_cache(self, screenshot_path: str, action: str, data: dict) -> None:
        try:
            # Try to read existing cache first
            with open(WEBPAGE_ACTION_CACHE_FILE_PATH, 'r') as f:
                cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create new cache if file doesn't exist or is invalid
            cache = {}
        
        # Create cache key from screenshot path and action
        cache_key = f"{screenshot_path}:{action}"
            
        # Add/update the cache entry
        cache[cache_key] = data
            
        # Write updated cache back to file
        with open(WEBPAGE_ACTION_CACHE_FILE_PATH, 'w') as f:
            json.dump(cache, f, indent=2)
        pass

    def generate_page_actions(self, screenshot_path: str, action: str) -> None:

        cache = self.get_cache(screenshot_path=screenshot_path, action=action)

        if cache is not None:
            # cache hit
            print("Cache hit -----")
            return cache
        
        # Read and encode the image
        with open(screenshot_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

        prompt = (
            "This is screenshot of a webpage with highligted boxes.\n\n"
            "We need to perform this action: In the Google search bar, type 'green frontier capital yourstory' and press Enter.\n\n"
            "Give me list of browser actions in this schema - \n"
            '{ \"box_click\": 1, \"input_text\": \"system generated\", \"extracted_data\": \"\" }\n\n'
            "box_click denotes which highlighted box to click\n"
            "input_text is what user needs to enter\n"
            "extracted_data will hold if any data needed to be extracted from the page\n\n"
            "Output should be sequential list of action that will be performed in order.\n"
            "If no value then use None, dont use default.\n\n"
            "only output json"
        )

        prompt = f"""
This is screenshot of a webpage with highligted boxes.

We need to perform this action: In the Google search bar, type 'green frontier capital yourstory' and press Enter.

box_click denotes which highlighted box to click
input_text is what user needs to enter
extracted_data will hold if any data needed to be extracted from the page

Each action should be atomic, only one action at a time.
Output should be sequential list of action that will be performed in order.
If no value then use None, dont use default.

Only output json.

""" + "Give me list of browser actions in this schema - { \"box_click\": 1, \"input_text\": \"system generated\", \"extracted_data\": \"\" }"

        
        clean_prompt = dedent(prompt)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": clean_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]

        # print("webpage action generator messages", json.dumps(messages, indent=4))

        response = self.openai.chat.completions.create(
            model="GPT4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=300,
            top_p=0.95
        )
        result = response.choices[0].message.content

        print("webpage action openai call result", result)
        
        # Parse the JSON string into a Python dictionary
        data = json.loads(result)
        
        # set cache
        self.set_cache(screenshot_path=screenshot_path, action=action, data=data)
        
        return data
    
# singleton
webpage_action_generator = WebpageActionGeneratorAgent(openai=openai)
