import json
from textwrap import dedent
import threading
from flask_sse import sse
from openai import AzureOpenAI
from config import openai
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import stealth_sync
from browser_interactor import BrowserInteractor
import random
from agents.webpage_action_generator_agent import webpage_action_generator


class QueryProcessorService:
    def __init__(self, openai: AzureOpenAI):
          self.openai = openai

    def notify(self, json, app=None):
        if app is not None:
            with app.app_context(): 
                sse.publish(json)

    def get_plan_cache(self, user_query: str) -> dict:
        # Try to read from plan_cache.json and return cached plan if it exists
        try:
            with open('plan_cache.json', 'r') as f:
                cache = json.load(f)
                if user_query in cache:
                    return cache[user_query]
        except (FileNotFoundError, json.JSONDecodeError):
            # Return None if file doesn't exist or is invalid JSON
            return None
        
        # Return None if query not found in cache
        return None
        

    def set_plan_cache(self, user_query: str, plan: dict):
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


    def generate_action_plan(self, user_query, query_id):
        cache = self.get_plan_cache(user_query=user_query)

        if cache is not None:
            # cache hit
            return cache
        
        prompt = f'''
            You are a human who uses web browser. 
            You will list step by step action plan to accomplish the user query.

            User query - {user_query}

            goal property is how to validate.
        '''  + "Output into this format - { \"goto\": \"url\", \"action_plan\": [], \"goal\": \"\" }"

        clean_prompt = dedent(prompt)

        response = self.openai.chat.completions.create(
            model="GPT4o-mini",
            messages=[{"role": "user", "content": clean_prompt}],
            temperature=0.3,
            max_tokens=300,
            top_p=0.95
        )
        result = response.choices[0].message.content
        # Parse the JSON string into a Python dictionary
        plan = json.loads(result)
        
        # Add query_id and query to the plan
        plan["query_id"] = query_id
        plan["query"] = user_query

        # set cache
        self.set_plan_cache(user_query=user_query, plan=plan)
        
        return plan
    
    def random_color(self):
        return f"#{random.randint(0, 0xFFFFFF):06x}"
    
    def draw_bounding_box_and_screenshot(self, page: Page, query_id: str, step_idx: int):
        # Select all buttons and input elements
        selector = "button, input, textarea"

        # Assign data-box-number to each element and get their bounding boxes
        boxes = page.eval_on_selector_all(
            selector,
            """
            (elements) => {
                return elements.map((el, idx) => {
                    el.setAttribute('data-box-number', idx + 1);
                    const rect = el.getBoundingClientRect();
                    return {
                        x: rect.x + window.scrollX,
                        y: rect.y + window.scrollY,
                        width: rect.width,
                        height: rect.height,
                        box_number: idx + 1,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || null
                    };
                });
            }
            """
        )

        # Draw overlays for each bounding box
        for box in boxes:
            color = self.random_color()
            page.evaluate(
                """
                ([box, color]) => {
                    const div = document.createElement('div');
                    div.style.position = 'absolute';
                    div.style.left = box.x + 'px';
                    div.style.top = box.y + 'px';
                    div.style.width = box.width + 'px';
                    div.style.height = box.height + 'px';
                    div.style.border = '3px solid ' + color;
                    div.style.zIndex = 9999;
                    div.style.pointerEvents = 'none';

                    const label = document.createElement('span');
                    label.textContent = box.box_number;
                    label.style.position = 'absolute';
                    label.style.left = '0';
                    label.style.top = '0';
                    label.style.background = color;
                    label.style.color = '#fff';
                    label.style.fontWeight = 'bold';
                    label.style.padding = '2px 6px';
                    label.style.fontSize = '16px';
                    div.appendChild(label);

                    document.body.appendChild(div);
                }
                """,
                [box, color]
            )

        # Take screenshot
        screenshot_path=f"./screenshots/{query_id}_{step_idx}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved as {screenshot_path}")
        return screenshot_path

    def generate_browser_action_on_page(self, screenshot_path, action):
        actions = webpage_action_generator.generate_page_actions(screenshot_path, action)
        return actions
    
    def act_on_box(self, page: Page, action: str):
        print("")
        box_number_to_act_on = action["box_click"]
        selector = f'[data-box-number="{box_number_to_act_on}"]'
        element = page.query_selector(selector)
        if element:
            tag = element.evaluate("el => el.tagName.toLowerCase()")
            input_type = element.evaluate("el => el.type?.toLowerCase()") if tag == "input" else None
            
            if tag == "button":
                element.click()
                print(f"Clicked button with box number {box_number_to_act_on}")
            elif tag == "input":
                if input_type == "submit":
                    element.click()
                    print(f"Clicked submit input with box number {box_number_to_act_on}")
                else:
                    element.fill(action["input_text"])
                    print(f"Filled input with box number {box_number_to_act_on}")
            elif tag == "textarea":
                element.fill(action["input_text"])
                print(f"Filled textarea with box number {box_number_to_act_on}")
            elif tag == "a":
                element.click()
                print(f"Clicked link with box number {box_number_to_act_on}")

        
    def do_browser_actions(self, actions, page: Page): 
        for action in actions:
            self.act_on_box(page, action=action)

        threading.Event().wait(5)  # Simulate processing time
    
    def execute_action_plan(self, plan, app):
        # Use sync_playwright within the thread
        with sync_playwright() as p:
            query_id = plan["query_id"]
            if query_id is None:
                return
            
            # Launch browser (or connect to existing) within the thread
            browser = p.chromium.launch(headless=False, channel="chrome") # Launch per thread for simplicity.
                                                    # Reusing a single instance across threads
                                                    # with sync API requires careful locking and page management.

            # Send a status update using SSE
            # sse.publish({"message": f"Starting processing for query ID: {query_id}"}, type='status', channel=query_id)
            self.notify({"message": f"Starting processing for query ID: {query_id}"})

            page = None
            try:
                page = browser.new_page()
                stealth_sync(page)
                print(f"Query {query_id}: Created new page.")

                # Create a SyncBrowserInteractor instance for this task's page
                interactor = BrowserInteractor(browser) # Pass the browser instance
                interactor.goto(page=page, url=plan["goto"])
                
                self.notify({"message": f"Navigated to example.com"})

                # Skipping first action since it's usually navigating to the goto url
                action_plan_list = plan["action_plan"]

                """
                    agent_decided_action = {
                        "box_click": 1,
                        "input_text": "system generated",
                        "extracted_data": ""
                    }
                """
                last_action = None

                screenshot_path = self.draw_bounding_box_and_screenshot(page=page, query_id=query_id, step_idx=1)
                actions = self.generate_browser_action_on_page(screenshot_path=screenshot_path, action=action_plan_list[1])
                print("actions - ", actions)
                self.do_browser_actions(actions, page)

                for step_idx, action in enumerate(action_plan_list[1:]):
                    print(f"will do step {step_idx}: {action}")

                    # draw bounding box & take screenshot
                    # self.draw_bounding_box_and_screenshot(page=page)

                    # generate the browser action - action agent - ip: screenshot, action, op: agent_decided_action

                    # do browser interaction


                # # Example: Extract the title
                # title = page.title() # Use the page object directly or go through interactor
                # print(f"Query {query_id}: Page title is '{title}'")
                # sse.publish({"message": f"Page title: {title}"}, type='status', channel=query_id)


                # # --- End Browser Interaction Logic ---
                
                self.notify({"message": f"Processing complete for query ID: {query_id}", "done": True})

            except Exception as e:
                print(f"Error processing query {query_id}: {e}")
                self.notify({"message": f"An error occurred: {e}", "status": "error"})
            finally:
                if page:
                    page.close()
                    print(f"Query {query_id}: Page closed.")
                if browser:
                    browser.close() # Close browser launched in this thread
        return


    def process_query(self, query_id, app):
        # Simulate some processing and send SSE updates
        try:
            # Read the query file
            with open(f"./jobs/{query_id}.json", "r") as f:
                query_data = json.load(f)

            query = query_data["query"]
                
            # Example processing - replace with actual logic
            messages = [
                "Starting processing...",
                f"Processing query: {query_data['query']}",
                "Processing complete"
            ]
            
            for msg in messages:
                # Push Flask app context before using `sse.publish`
                self.notify({"query_id": query_id, "message": msg })
                threading.Event().wait(1)  # Simulate processing time
                
        except Exception as e:  
            print(f"Error processing query {query_id}: {str(e)}")


if __name__ == "__main__":
    processor = QueryProcessorService(openai=openai)
    # result = processor.generate_action_plan(
    #     user_query="search for green frontier capital yourstory on google and get the headline of the first article", 
    #     query_id="ebd45c17-99d6-412c-ae3a-35f1231941b7"
    # )
    # print(json.dumps(result, indent=4))
    processor.execute_action_plan(plan={
        "goto": "https://www.google.com/",
        "action_plan": [
            "Open your web browser and go to https://www.google.com/.",
            "In the Google search bar, type 'green frontier capital yourstory' and press Enter.",
            "Look at the search results and find the first article from YourStory.",
            "Click on the first article from YourStory to open it.",
            "Read the headline of the article."
        ],
        "goal": "The headline of the first article from YourStory about Green Frontier Capital.",
        "query_id": "ebd45c17-99d6-412c-ae3a-35f1231941b7",
        "query": "search for green frontier capital yourstory on google and get the headline of the first article"
    }, app=None)