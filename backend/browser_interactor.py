import threading
from playwright.sync_api import sync_playwright, Browser, Page


# Global instance of the synchronous Browser instance
# We'll manage pages per task
browser_instance: Browser = None
# A lock to protect access to the shared browser instance (basic protection)
browser_lock = threading.Lock()

class BrowserInteractor:
    """Synchronous Browser Interactor."""
    def __init__(self, browser_instance: Browser):
        self._browser = browser_instance

    def new_page(self) -> Page:
        """Creates a new synchronous page."""
        return self._browser.new_page()

    def goto(self, page: Page, url):
        """Navigates to a given URL using a specific page."""
        page.goto(url)
        print(f"Navigated to: {url}")

    def click(self, page: Page, selector):
        """Clicks on an element using a specific page."""
        page.click(selector)
        print(f"Clicked on: {selector}")

    def extract_text(self, page: Page, selector):
        """Extracts text from an element using a specific page."""
        element = page.query_selector(selector)
        if element:
            text = element.inner_text()
            print(f"Extracted text from {selector}: {text}")
            return text
        else:
            print(f"Element not found: {selector}")
            return None

    def input_text(self, page: Page, selector, text):
        """Inputs text into an element using a specific page."""
        page.fill(selector, text)
        print(f"Inputted text '{text}' into: {selector}")
