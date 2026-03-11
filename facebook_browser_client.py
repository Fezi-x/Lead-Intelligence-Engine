import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, BrowserContext, Page

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
            "recent_posts": [],
            "error": None
        }

        try:
            # Add a small delay/randomization to look more human if needed
            await page.goto(url, wait_until="networkidle")
            
            # 1. Extract Page Name
            # Facebook uses h1 for Page Name usually
            try:
                name_elem = await page.wait_for_selector('h1', timeout=10000)
                result["name"] = await name_elem.inner_text()
            except:
                result["name"] = "Unknown"

            # 2. Extract Followers / Likes
            try:
                # Target the link specifically associated with followers
                follower_elem = page.locator('a[href*="/followers/"]')
                follower_text = await follower_elem.first.inner_text()
                
                if follower_text:
                    match = re.search(r"([\d,.]+K?M?)\s+followers", follower_text, re.IGNORECASE)
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

            # 3. Extract Category and Website from Intro
            try:
                # Category: Facebook labels this with a bold "Page" text
                # Find the container that has "Page" in bold
                try:
                    cat_locator = page.locator('//strong[text()="Page"]/..')
                    if await cat_locator.count() > 0:
                        cat_text = await cat_locator.first.inner_text()
                        if "·" in cat_text:
                            result["category"] = cat_text.split("·")[-1].strip()
                except:
                    pass

                # Website: Target external links excluding common socials
                try:
                    website_selector = 'a[href*="l.facebook.com"]:not([href*="linkedin.com"]):not([href*="twitter.com"]):not([href*="x.com"]):not([href*="instagram.com"]):not([href*="youtube.com"])'
                    website_locator = page.locator(website_selector)
                    if await website_locator.count() > 0:
                        result["website"] = (await website_locator.first.inner_text()).strip()
                except:
                    pass
                
                # Description: Look for Intro section container
                intro_heading = page.get_by_role("heading", name="Intro")
                if await intro_heading.count() > 0:
                    intro_container = intro_heading.locator("xpath=./following-sibling::div | ./parent::div")
                    intro_text = await intro_container.inner_text()
                    lines = [l.strip() for l in intro_text.split('\n') if l.strip()]
                    if len(lines) > 1:
                        # The description is usually the first non-header, non-meta line
                        desc_candidates = [l for l in lines if l != "Intro" and "Page ·" not in l and l != result["website"] and "@" not in l]
                        if desc_candidates:
                            result["description"] = desc_candidates[0]
            except:
                pass

            # Fallbacks for category if still empty
            if not result["category"]:
                try:
                    cat_match = re.search(r"Page\s*·\s*(.+)", await page.content())
                    if cat_match:
                        result["category"] = cat_match.group(1).split('<')[0].strip()
                except:
                    pass

            # 4. Recent Posts
            # Posts are usually in div[role="article"]
            try:
                # Wait for some posts to load
                await page.wait_for_selector('div[role="article"]', timeout=5000)
                posts = await page.locator('div[role="article"]').all()
                recent_posts = []
                for post in posts[:3]: # Get last 3 posts
                    text = await post.inner_text()
                    # Clean up text
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    if lines:
                        # Filter out common UI words
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
