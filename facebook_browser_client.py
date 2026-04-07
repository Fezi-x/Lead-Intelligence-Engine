import os
import json
import asyncio
import logging
import re
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, BrowserContext, Page

class FacebookLoginRequiredError(Exception):
    """Raised when Facebook redirects to a login page."""
    pass

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    filename='logs/extraction.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

AUTH_FILE = "facebook_auth.json"

class FacebookBrowserClient:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        
        if os.path.exists(AUTH_FILE):
            self.context = await self.browser.new_context(storage_state=AUTH_FILE)
        else:
            self.context = await self.browser.new_context()
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def login(self):
        """Allows manual login to persist session."""
        page = await self.context.new_page()
        await page.goto("https://www.facebook.com/")
        print("\n[IMPORTANT] Please log in manually in the browser window.")
        print("Once logged in, the script will save the session and close.")
        
        # Wait for the user to login - we'll look for an element that indicates login success
        # Like the "home" icon or profile picture
        try:
            await page.wait_for_selector('role=navigation', timeout=120000) # 2 minutes
            await self.context.storage_state(path=AUTH_FILE)
            print(f"Session saved to {AUTH_FILE}")
        except Exception as e:
            print(f"Login failed or timed out: {e}")
        finally:
            await page.close()

    async def extract_page_data(self, url: str) -> Dict[str, Any]:
        """Extracts data from a public Facebook page."""
        page = await self.context.new_page()
        result = {
            "platform": "facebook",
            "url": url,
            "name": "",
            "followers": 0,
            "category": "",
            "website": "",
            "description": "",
            "email": "",
            "phone": "",
            "address": "",
            "recent_posts": [],
            "error": None
        }

        try:
            # Add a small delay/randomization to look more human if needed
            await page.goto(url, wait_until="networkidle")
            
            # 1. Extract Basic Header Info (Name, Followers)
            try:
                name_elem = await page.wait_for_selector('h1', timeout=10000)
                if not name_elem:
                    raise Exception("Could not find h1 element")
                result["name"] = await name_elem.inner_text()
                
                # Double check for login indicators in the page content
                if "Log in" in result["name"] or "Facebook" == result["name"]:
                     content = await page.content()
                     if 'id="login_form"' in content or 'name="login"' in content:
                         raise FacebookLoginRequiredError("Facebook login wall detected (found login form).")
            except FacebookLoginRequiredError:
                raise
            except Exception:
                result["name"] = "Unknown"

            # 2. Extract Followers
            try:
                # Often in header: "75 followers • 2 likes"
                # Target the link specifically associated with followers
                follower_elem = page.locator('a[href*="/followers/"]')
                if await follower_elem.count() > 0:
                    follower_text = await follower_elem.first.inner_text()
                else:
                    # Fallback to general text search in header area
                    follower_text = await page.locator('div[role="main"] >> text=/followers/i').first.inner_text()
                
                if follower_text:
                    # Look for numbers near "followers"
                    match = re.search(r"([\d,.]+K?M?)\s+followers", follower_text, re.IGNORECASE)
                    if not match:
                        # Try finding the number BEFORE "followers"
                        match = re.search(r"([\d,.]+K?M?)\s*(?:followers|likes)", follower_text, re.IGNORECASE)
                    
                    if match:
                        raw_val = match.group(1).replace(",", "")
                        if "K" in raw_val.upper():
                            result["followers"] = int(float(raw_val.upper().replace("K", "")) * 1000)
                        elif "M" in raw_val.upper():
                            result["followers"] = int(float(raw_val.upper().replace("M", "")) * 1000000)
                        else:
                            result["followers"] = int(float(raw_val))
            except:
                pass

            # 3. Deep Extractions from About Section
            # Navigate to /about page for richer details
            about_url = url.rstrip('/') + '/about'
            try:
                await page.goto(about_url, wait_until="domcontentloaded")
                # Potential sub-tab "Contact and basic info"
                try:
                    contact_link = page.locator('a[href*="about_contact_and_basic_info"]')
                    if await contact_link.count() > 0:
                        await contact_link.first.click()
                        await page.wait_for_timeout(2000)
                except:
                    pass

                # Extract Details from About page
                about_content = await page.content()
                
                # Website
                try:
                    website_selector = 'a[href*="l.facebook.com"]:not([href*="facebook.com"]):not([href*="linkedin.com"]):not([href*="instagram.com"]):not([href*="twitter.com"]):not([href*="x.com"])'
                    website_locator = page.locator(website_selector)
                    if await website_locator.count() > 0:
                        result["website"] = (await website_locator.first.inner_text()).strip()
                except: pass

                # Email
                try:
                    email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', about_content)
                    if email_match:
                        result["email"] = email_match.group(1)
                except: pass

                # Category
                try:
                    # Find span that usually follows or is near "Page · [Category]"
                    cat_match = re.search(r"Page\s*[·•]\s*([^\n<]+)", about_content, flags=re.IGNORECASE)
                    if cat_match:
                        result["category"] = cat_match.group(1).strip()
                except: pass

                # Phone
                try:
                    # Look for phone patterns (min 8 digits, avoid long ID-like strings)
                    # Phone labels are usually preceded by a phone icon or "Phone" label
                    phone_match = re.search(r'(?:\+?\d[\d\s\-]{7,15})', about_content)
                    if phone_match:
                        val = phone_match.group(0).strip()
                        # Avoid long numeric strings > 12 chars without spaces/dashes (likely IDs)
                        if len(val.replace(" ", "").replace("-", "")) <= 15 and len(val.replace(" ", "").replace("-", "")) >= 7:
                            if not (val.isdigit() and len(val) > 12): 
                                result["phone"] = val
                except: pass
                
                # Address
                try:
                    # Look for address-like patterns or specific aria-labels
                    addr_locator = page.locator('//span[contains(text(), "Yangon")] | //span[contains(text(), "Myanmar")] | //div[contains(@aria-label, "Address")]')
                    if await addr_locator.count() > 0:
                        result["address"] = (await addr_locator.first.inner_text()).strip()
                except: pass

                # Description (from Intro if visible on About or back to main)
                if not result["description"]:
                    intro_match = re.search(r"Intro\n([^\n]+)", await page.inner_text("body"))
                    if intro_match:
                        result["description"] = intro_match.group(1).strip()

            except Exception as e:
                logger.warning(f"Deep extraction failed for {about_url}: {e}")

            # 4. Recent Posts (Back to main page)
            try:
                await page.goto(url, wait_until="networkidle")
                # Posts are usually in div[role="article"]
                await page.wait_for_selector('div[role="article"]', timeout=5000)
                posts = await page.locator('div[role="article"]').all()
                recent_posts = []
                for post in posts[:3]: # Get last 3 posts
                    text = await post.inner_text()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    if lines:
                        filtered = [l for l in lines if l.lower() not in ["like", "comment", "share", "write a comment"]]
                        if filtered:
                            recent_posts.append(" ".join(filtered[:3]))
                result["recent_posts"] = recent_posts
            except:
                pass

            # Save state again in case cookies updated
            await self.context.storage_state(path=AUTH_FILE)

        except Exception as e:
            logger.error(f"Extraction error for {url}: {e}")
            result["error"] = str(e)
        finally:
            await page.close()
        
        return result

if __name__ == "__main__":
    import sys
    
    async def run_login():
        async with FacebookBrowserClient(headless=False) as client:
            await client.login()

    if len(sys.argv) > 1 and sys.argv[1] == "--login":
        asyncio.run(run_login())
    else:
        # Quick test
        async def main():
            test_url = "https://www.facebook.com/facebook"
            async with FacebookBrowserClient(headless=True) as client:
                data = await client.extract_page_data(test_url)
                print(json.dumps(data, indent=2))
        
        asyncio.run(main())
