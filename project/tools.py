from langchain_core.tools import tool
from browser_manager import browser_manager
import time



@tool
def get_page_text() -> str:
    """
    Extract the full visible text from the current webpage.

    Use this tool when:
        - You need to read results
        - You want to verify page content
        - You need to analyze textual output

    Returns:
        Visible text content of the page (truncated if very large).
    """
    
    page = browser_manager.get_page()
    if not page:
        return "Error: No browser page is open"

    try:
        page.wait_for_load_state("domcontentloaded")
        text = page.evaluate("document.body.innerText")
        return text[:20000]
    except Exception as e:
        return f"Error extracting page text: {e}"



@tool
def analyze_page_with_som() -> str:
    """
    Analyze the current webpage and list all interactive elements.

    This tool scans the webpage and assigns a temporary numeric ID
    (data-som-id) to clickable and input elements such as:
    - buttons
    - links
    - input fields
    - textareas
    - dropdowns

    Returns:
        A formatted list of interactive elements with:
        - ID
        - HTML tag
        - Type attribute (if any)
        - Visible text or placeholder

    Always call this tool FIRST before interacting with a page.
    """
    page = browser_manager.get_page()
    if not page:
        return "Error: No browser page is open"

    try:
        page.wait_for_load_state("domcontentloaded")

        script = """
        () => {
            document.querySelectorAll('.som-overlay-mark').forEach(el => el.remove());

            let interactives = document.querySelectorAll(
                'a, button, input, textarea, select, [role="button"], [tabindex]:not([tabindex="-1"])'
            );

            let results = [];
            let id = 1;

            interactives.forEach(el => {
                let rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;

                let som_id = id++;
                el.setAttribute('data-som-id', som_id);

                let tag = el.tagName.toLowerCase();
                let text = (
                    el.innerText ||
                    el.value ||
                    el.placeholder ||
                    el.getAttribute('aria-label') ||
                    ''
                ).trim().substring(0, 80);

                let type = el.getAttribute('type') || '';

                results.push(
                    `ID: ${som_id} | Tag: <${tag}> | Type: ${type} | Text: ${text}`
                );
            });

            return results;
        }
        """

        elements = page.evaluate(script)

        if not elements:
            return "No interactive elements found."

        return "Interactive Elements (SOM):\n" + "\n".join(elements[:200])

    except Exception as e:
        return f"Error analyzing page: {e}"


@tool
def click_element(selector_or_id: str) -> str:
    """
    Click an element on the webpage.

    Args:
        selector_or_id (str):
            Either:
            - A numeric ID returned from analyze_page_with_som
            - A valid CSS selector

    Use this tool to:
        - Press buttons
        - Click links
        - Submit forms

    Returns:
        Confirmation message or error.
    """
    page = browser_manager.get_page()
    if not page:
        return "Error: No browser page is open"

    try:
        if str(selector_or_id).isdigit():
            selector_or_id = f'[data-som-id="{selector_or_id}"]'

        locator = page.locator(selector_or_id).first

        if locator.count() == 0:
            return f"Element {selector_or_id} not found."

        locator.scroll_into_view_if_needed()
        locator.click(timeout=10000)
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_load_state("domcontentloaded")

        return f"Clicked {selector_or_id}"

    except Exception as e:
        return f"Click error: {e}"



@tool
def fill_element(selector_or_id: str, text: str) -> str:
    """
    Fill text into an input field.

    Args:
        selector_or_id (str):
            Numeric ID from analyze_page_with_som
            OR a CSS selector.
        text (str):
            The value to enter into the field.

    Use this tool to:
        - Enter search queries
        - Fill forms
        - Input user data

    Returns:
        Confirmation message or error.
    """
    page = browser_manager.get_page()
    if not page:
        return "Error: No browser page is open"

    try:
        if str(selector_or_id).isdigit():
            selector_or_id = f'[data-som-id="{selector_or_id}"]'

        locator = page.locator(selector_or_id).first

        if locator.count() == 0:
            return f"Element {selector_or_id} not found."

        locator.scroll_into_view_if_needed()
        locator.click()

        locator.fill("")
        locator.fill(text)

        locator.dispatch_event("input")
        locator.dispatch_event("change")

        return f"Filled {selector_or_id} with {text}"

    except Exception as e:
        return f"Fill error: {e}"


@tool
def press_key(key: str) -> str:
    """
    Simulate a keyboard key press.

    Args:
        key (str):
            Keyboard key such as:
            - "Enter"
            - "Tab"
            - "ArrowDown"
            - "Escape"

    Use this tool when:
        - Submitting forms via Enter
        - Navigating dropdowns
        - Handling modal dialogs

    Returns:
        Confirmation message.
    """
    page = browser_manager.get_page()
    if not page:
        return "Error: No browser page is open"

    try:
        page.keyboard.press(key)
        return f"Pressed {key}"
    except Exception as e:
        return f"Key press error: {e}"



@tool
def scroll_page(pixels: int = 1000) -> str:
    """
    Scroll the current webpage vertically.

    Args:
        pixels (int):
            Number of pixels to scroll down.
            Default is 1000.

    Use this tool when:
        - Content is not visible
        - Lazy-loaded elements need loading
        - Buttons are below the fold

    Returns:
        Confirmation message.
    """
    page = browser_manager.get_page()
    if not page:
        return "Error: No browser page is open"

    try:
        page.mouse.wheel(0, pixels)
        return f"Scrolled {pixels}px"
    except Exception as e:
        return f"Scroll error: {e}"



@tool
def extract_text_from_selector(selector_or_id: str) -> str:
    """
    Extract text content from a specific element.

    Args:
        selector_or_id (str):
            Numeric ID from analyze_page_with_som
            OR a CSS selector.

    Use this tool when:
        - You need specific result text
        - The full page text is too large
        - You want structured extraction

    Returns:
        Inner text of the element or error.
    """
    page = browser_manager.get_page()
    if not page:
        return "Error: No browser page is open"

    try:
        if str(selector_or_id).isdigit():
            selector_or_id = f'[data-som-id="{selector_or_id}"]'

        locator = page.locator(selector_or_id).first
        if locator.count() == 0:
            return "Element not found"

        return locator.inner_text()

    except Exception as e:
        return f"Extraction error: {e}"


@tool
def extract_attribute_from_selector(selector_or_id: str, attribute: str) -> str:
    """
    Extract a specific attribute value from an element.

    Args:
        selector_or_id (str):
            Numeric ID OR CSS selector.
        attribute (str):
            Attribute name (e.g., "href", "src", "value", "data-id").

    Returns:
        Attribute value or error.
    """

    page = browser_manager.get_page()
    if not page:
        return "Error: No browser page is open."

    try:
        if selector_or_id.isdigit():
            selector_or_id = f'[data-som-id="{selector_or_id}"]'

        locator = page.locator(selector_or_id).first

        if locator.count() == 0:
            return "Element not found."

        value = locator.get_attribute(attribute)

        if value is None:
            return f"Attribute '{attribute}' not found."

        return value

    except Exception as e:
        return f"Attribute extraction error: {str(e)}"



@tool
def ask_human_help(question: str) -> str:
    """
    Ask the human user for clarification or manual input.

    Use this tool when:
        - CAPTCHA appears
        - Login is required
        - Ambiguity cannot be resolved automatically
        - Critical decision is needed

    Args:
        question (str):
            Clear question to ask the user.

    Returns:
        User's input as string.
    """

    try:
        print("\n=== HUMAN ASSISTANCE REQUIRED ===")
        print(question)
        response = input("Your response: ")
        return response
    except Exception as e:
        return f"Human assistance error: {str(e)}"