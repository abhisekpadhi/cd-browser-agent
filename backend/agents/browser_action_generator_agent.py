import json
from textwrap import dedent
import base64
from openai import AzureOpenAI
from config import openai
from config import BROWSER_ACTION_CACHE_FILE_PATH
from lib.utils import generate_screenshot_base64

class BrowserActionGeneratorAgent:
    def __init__(self, openai: AzureOpenAI) -> None:
        self.openai = openai
        pass

    def recall(self, screenshot_path: str, action: str,) -> dict:
        # Try to read from webpage_action_cache.json and return cached data if it exists
        try:
            with open(BROWSER_ACTION_CACHE_FILE_PATH, 'r') as f:
                cache = json.load(f)
                cache_key = f"{screenshot_path}:{action}"
                if cache_key in cache:
                    return cache[cache_key]
        
        except (FileNotFoundError, json.JSONDecodeError):
            # Return empty dict if file doesn't exist or is invalid JSON
            return None
        
        # Return None if query not found in cache
        return None

    def remember(self, screenshot_path: str, action: str, data: dict) -> None:
        try:
            # Try to read existing cache first
            with open(BROWSER_ACTION_CACHE_FILE_PATH, 'r') as f:
                cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create new cache if file doesn't exist or is invalid
            cache = {}
        
        # Create cache key from screenshot path and action
        cache_key = f"{screenshot_path}:{action}"
            
        # Add/update the cache entry
        cache[cache_key] = data
            
        # Write updated cache back to file
        with open(BROWSER_ACTION_CACHE_FILE_PATH, 'w') as f:
            json.dump(cache, f, indent=2)
        pass

    def generate_page_actions(self, screenshot_path: str, action: str):

        cache = self.recall(screenshot_path=screenshot_path, action=action)

        if cache is not None:
            # cache hit
            return cache
        
        print("generate_page_actions cache miss >", screenshot_path, action)
        
        # Read and encode the image
        image_base64 = generate_screenshot_base64(screenshot_path)

        prompt = f"""
This is screenshot of a webpage with highligted boxes.

We need to perform this action: {action}

Output should be sequential list of action that will be performed in order.

If no value then use null, dont use default.

""" + "Give me list of browser actions in this schema - { \"box_click\": 1, \"input_text\": \"system generated\", \"extracted_data\": \"\" }" + """

box_click denotes which highlighted box to click
input_text is what user needs to enter
extracted_data will hold if any data needed to be extracted from the page

output must be in json format.
"""

        
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

        print("browser action generator messages", json.dumps(messages, indent=4))

        response = self.openai.chat.completions.create(
            model="GPT4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=300,
            top_p=0.95,
            response_format={"type": "json_object"}
        )
        result = response.choices[0].message.content

        print("webpage action openai call result", result)
        
        # Parse the JSON string into a Python dictionary
        data = json.loads(result)
        
        # set cache
        self.remember(screenshot_path=screenshot_path, action=action, data=data)
        
        return data
    
    def generate_vision_only_actions(self, screenshot_path: str, action: str):
        cache = self.recall(screenshot_path=screenshot_path, action=action)

        if cache is not None:
            # cache hit
            return cache
        
        print("generate_page_actions cache miss >", screenshot_path, action)
        
        # Read and encode the image
        image_base64 = generate_screenshot_base64(screenshot_path)

        prompt = f"""
This is screenshot of a webpage.

We need to perform this action: {action}

If no value then use null, dont use default.

""" + "Give me list of browser actions in this schema - { \"box_click\": 1, \"input_text\": \"system generated\", \"extracted_data\": \"\" }" + """

box_click will be null
input_text will be null
extracted_data will hold if any data needed to be extracted from the page

output must be in json format.
"""

        
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

        print("vision only action generator messages", json.dumps(messages, indent=4))

        response = self.openai.chat.completions.create(
            model="GPT4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=300,
            top_p=0.95,
            response_format={"type": "json_object"}
        )
        result = response.choices[0].message.content

        print("vision only action openai call result", result)
        
        # Parse the JSON string into a Python dictionary
        data = json.loads(result)
        
        # set cache
        self.remember(screenshot_path=screenshot_path, action=action, data=data)
        
        return data
    
# singleton
browser_action_generator = BrowserActionGeneratorAgent(openai=openai)
