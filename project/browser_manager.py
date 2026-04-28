from playwright.sync_api import sync_playwright, Page, BrowserContext
from typing import Optional
import os


class BrowserManager:
    """
    Singleton Browser Manager
    - Launch once
    - Navigate multiple times
    - Close safely
    """

    _instance = None
    _playwright = None
    _browser: Optional[BrowserContext] = None
    _page: Optional[Page] = None
    _headless_mode: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
        return cls._instance

   

    def set_headless_mode(self, mode: bool):
        self._headless_mode = mode
        print(f">>> Headless mode: {self._headless_mode}")


    def launch_browser(self) -> str:
        try:
            if self._page and not self._page.is_closed():
                return "Browser already running"

            print(">>> Launching browser...")

            self._playwright = sync_playwright().start()

            user_data_dir = os.path.abspath("./profiles/main_profile")
            os.makedirs(user_data_dir, exist_ok=True)

            self._browser = self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=self._headless_mode,
                args=[
                    "--start-maximized",
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled"
                ],
                viewport=None
            )

            self._page = self._browser.pages[0]

            return "Browser launched successfully"

        except Exception as e:
            return f"Error launching browser: {str(e)}"



    def navigate(self, url: str) -> str:
        try:
            if not self._page or self._page.is_closed():
                self.launch_browser()

            print(f">>> Navigating to: {url}")

            self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
            self._page.wait_for_load_state("networkidle")

            return f"Navigated to {url}"

        except Exception as e:
            return f"Navigation error: {str(e)}"

   

    def get_page(self) -> Optional[Page]:
        return self._page


    def is_browser_open(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    

    def close_browser(self) -> str:
        try:
            if self._page:
                try:
                    self._page.close()
                except:
                    pass

            if self._browser:
                try:
                    self._browser.close()
                except:
                    pass

            if self._playwright:
                try:
                    self._playwright.stop()
                except:
                    pass

            self._page = None
            self._browser = None
            self._playwright = None

            return "Browser closed"

        except Exception as e:
            return f"Error closing browser: {e}"


browser_manager = BrowserManager()