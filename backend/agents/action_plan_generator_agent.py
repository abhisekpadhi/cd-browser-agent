import json
from textwrap import dedent
from openai import AzureOpenAI
from config import openai
from config import ACTION_PLAN_CACHE_FILE_PATH

class ActionPlanGeneratorAgent:
    def __init__(self, openai: AzureOpenAI):
        self.openai = openai

    def recall(self, user_query: str) -> dict:
        # Try to read from plan_cache.json and return cached plan if it exists
        try:
            with open(ACTION_PLAN_CACHE_FILE_PATH, 'r') as f:
                cache = json.load(f)
                if user_query in cache:
                    return cache[user_query]
        except (FileNotFoundError, json.JSONDecodeError):
            # Return None if file doesn't exist or is invalid JSON
            return None
        
        # Return None if query not found in cache
        return None

    def remember(self, user_query: str, plan: dict):
        # Write the plan to plan_cache.json
        try:
            # Try to read existing cache first
            with open('plan_cache.json', 'r') as f:
                cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create new cache if file doesn't exist or is invalid
            cache = {}
            
            # Add/update the plan for this query
            cache[user_query] = plan
            
        # Write updated cache back to file
        with open('plan_cache.json', 'w') as f:
            json.dump(cache, f, indent=2)

    def generate_action_plan(self, user_query: str, query_id: str) -> dict:
        cache = self.recall(user_query=user_query)

        if cache is not None:
            # cache hit
            return cache
        
        prompt = f"""
You are a human who uses web browser. 
You will list step by step action plan to accomplish the user query.
Identifying a link and clicking on it is a single action.

User query - {user_query}

add a property in output called "vision_only", it will be list of steps for which we only need to extract information from the webpage that don't need a browser action.

goal property is how to validate.

output must be in json format.
"""  + "Output into this format - { \"goto\": \"url\", \"action_plan\": [], \"goal\": \"\" }"

        clean_prompt = dedent(prompt)

        response = self.openai.chat.completions.create(
            model="GPT4o-mini",
            messages=[{"role": "user", "content": clean_prompt}],
            temperature=0.3,
            max_tokens=300,
            top_p=0.95,
            response_format={"type": "json_object"}
        )
        result = response.choices[0].message.content
        # Parse the JSON string into a Python dictionary
        plan = json.loads(result)
        
        # Add query_id and query to the plan
        plan["query_id"] = query_id
        plan["query"] = user_query

        # set cache
        self.remember(user_query=user_query, plan=plan)
        
        return plan

action_plan_generator = ActionPlanGeneratorAgent(openai=openai)
