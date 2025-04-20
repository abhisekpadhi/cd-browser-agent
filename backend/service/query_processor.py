import json
from textwrap import dedent
import threading
from flask_sse import sse
from openai import AzureOpenAI
from config import openai
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import stealth_sync
from lib.browser_interactor import BrowserInteractor
import random
from agents.browser_action_generator_agent import browser_action_generator
from agents.action_plan_generator_agent import action_plan_generator
from datetime import datetime
from lib.utils import generate_screenshot_base64

class QueryProcessorService:
    def __init__(self, openai: AzureOpenAI):
          self.openai = openai

    def notify(self, json, app=None):
        if app is not None:
            with app.app_context(): 
                sse.publish(json)
                # sse.publish(json, type='status', channel=json["query_id"]) # for Production

    def generate_action_plan(self, user_query, query_id):
        plan = action_plan_generator.generate_action_plan(user_query=user_query, query_id=query_id)
        return plan

    
    def random_color(self):
        return f"#{random.randint(0, 0xFFFFFF):06x}"
    
    def draw_bounding_box_and_screenshot(self, page: Page, query_id: str, step_idx: int):
        # Select all buttons and input elements
        selector = "button, input, textarea, a"

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
        page.screenshot(path=screenshot_path, full_page=False)
        return screenshot_path
    
    def screenshot_vision_only(self, page: Page, query_id: str, step_idx: int):
        screenshot_path=f"./screenshots/{query_id}_{step_idx}.png"
        print("screenshot_vision_only, Taking screenshot")
    
        # Stop any further loading
        page.evaluate("window.stop()")
        print("screenshot_vision_only, Stopped page loading")
        
        page.screenshot(path=screenshot_path, full_page=False)
        print("screenshot_vision_only, screenshot taken")
        return screenshot_path

    def generate_browser_action_on_page(self, screenshot_path, action):
        actions = browser_action_generator.generate_page_actions(screenshot_path, action)
        return actions
    
    def generate_vision_only_action_on_page(self, screenshot_path, action):
        actions = browser_action_generator.generate_vision_only_actions(screenshot_path, action)
        return actions
    
    def act_on_box(self, page: Page, action: str):
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
                print("Page loaded after clicking link")

        
    def do_browser_actions(self, actions, page: Page): 
        for action in actions:
            self.act_on_box(page, action=action)

        threading.Event().wait(5)  # Simulate processing time
    
    def execute_action_plan(self, plan, app):
        self.notify({"message": f"Executing action plan for query ID: {plan['query_id']}"}, app=app)

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
            self.notify({"message": f"Browser launched"}, app=app)

            page = None
            try:
                page = browser.new_page()
                stealth_sync(page) # solve for captcha
                print(f"Query {query_id}: Created new page.")
                self.notify({"message": f"New page created"}, app=app)
                # Create a SyncBrowserInteractor instance for this task's page
                interactor = BrowserInteractor(browser) # Pass the browser instance
                interactor.goto(page=page, url=plan["goto"])
                
                self.notify({"message": f"Navigated to {plan['goto']}"}, app=app)

                
                action_plan_list = plan["action_plan"]

                """
                    browser_actions = [{
                        "box_click": 1,
                        "input_text": "system generated",
                        "extracted_data": ""
                    }]
                """
                last_actions = None


                # Skipping first action since it's usually navigating to the goto url
                for step_idx, action in enumerate(action_plan_list[1:]):
                    print("------------------------------")

                    print(f"Doing step {step_idx}: {action}")
                    self.notify({"message": f"Doing step {step_idx}: {action}"})

                    # if the action is in the vision_only list, then we need to generate the vision only action
                    if action in plan["vision_only"]:
                        screenshot_path = self.screenshot_vision_only(page=page, query_id=query_id, step_idx=step_idx)
                        self.notify({"message": f"Screenshot taken for vision only action", "img": generate_screenshot_base64(screenshot_path)}, app=app)
                        
                        actions = self.generate_vision_only_action_on_page(screenshot_path=screenshot_path, action=action)
                        self.notify({"message": f"Vision only actions generated", "actions": actions}, app=app)

                        last_actions = actions
                        
                        print("vision only actions generated", json.dumps(actions, indent=2))

                        continue

                    # draw bounding box & take screenshot
                    # self.draw_bounding_box_and_screenshot(page=page)
                    screenshot_path = self.draw_bounding_box_and_screenshot(page=page, query_id=query_id, step_idx=step_idx)
                    print(f"Screenshot saved as {screenshot_path}")
                    self.notify({"message": f"Screenshot taken for browser action", "img": generate_screenshot_base64(screenshot_path)}, app=app)

                    # generate the browser action - action agent - ip: screenshot, action, op: browser_actions
                    generated_actions = self.generate_browser_action_on_page(screenshot_path=screenshot_path, action=action)
                    print("browser actions generated", json.dumps(generated_actions, indent=2))
                    self.notify({"message": f"Browser actions generated", "actions": generated_actions}, app=app)
                    
                    last_actions = generated_actions

                    # do browser interaction
                    self.do_browser_actions(generated_actions, page)
                    print("browser actions done for step", step_idx)
                    self.notify({"message": f"Browser actions done for step {step_idx}", "actions": generated_actions}, app=app)
                
                print("All actions done", json.dumps(last_actions, indent=2))
                self.notify({"message": f"All actions done", "actions": last_actions}, app=app)
                
            except Exception as e:
                print(f"Error processing query {query_id}: {e}")
                self.notify({"message": f"An error occurred: {e}", "status": "error"}, app=app)
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
            query_data["status"] = "in_progress"
            with open(f"./jobs/{query_id}.json", "w") as f:
                json.dump(query_data, f)

            query = query_data["query"]

            # generate action plan
            action_plan = self.generate_action_plan(user_query=query, query_id=query_id)
            
            self.notify({"message": f"Action plan generated for query ID: {query_id}", "action_plan": action_plan}, app=app)

            # execute action plan
            self.execute_action_plan(plan=action_plan, app=app)

            self.notify({"message": f"Processing complete for query ID: {query_id}", "done": True}, app=app)

            # Update status to done
            query_data["status"] = "done"
            query_data["completed_at"] = datetime.now().isoformat()
            with open(f"./jobs/{query_id}.json", "w") as f:
                json.dump(query_data, f)

        except Exception as e:  
            print(f"Error processing query {query_id}: {str(e)}")

query_processor_service = QueryProcessorService(openai=openai)

# if __name__ == "__main__":
    # processor = QueryProcessorService(openai=openai)
    # result = processor.generate_action_plan(
    #     user_query="search for green frontier capital yourstory on google and get the headline of the first article", 
    #     query_id="47204a6b-8eb1-4d83-bcf1-2d7ba8cba740"
    # )
    # print(json.dumps(result, indent=4))
    # processor.execute_action_plan(plan={
    #     "goto": "https://www.google.com/",
    #     "action_plan": [
    #         "Open your web browser and go to https://www.google.com/.",
    #         "In the Google search bar, type 'green frontier capital yourstory' and press Enter.",
    #         "Click on the first article from YourStory to open it.",
    #         "Read the headline of the article."
    #     ],
    #     "goal": "The headline of the first article from YourStory about Green Frontier Capital.",
    #     "query_id": "47204a6b-8eb1-4d83-bcf1-2d7ba8cba740",
    #     "query": "search for green frontier capital yourstory on google and get the headline of the first article",
    #     "vision_only": [
    #         "Read the headline of the article."
    #     ]
    # }, app=None)