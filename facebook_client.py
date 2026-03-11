import os
import requests
import logging
import re
import asyncio
import time
from dotenv import load_dotenv

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    filename='logs/extraction.log',
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def get_facebook_page_data_api(url: str) -> dict:
    """Retrieves public Page metadata using the Facebook Graph API."""
    start_time = time.time()
    app_id = os.getenv("FACEBOOK_APP_ID")
    app_secret = os.getenv("FACEBOOK_APP_SECRET")
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")

    if not access_token and app_id and app_secret:
        access_token = f"{app_id}|{app_secret}"

    if not access_token:
        return {"error": "Missing API credentials", "latency_fetch": time.time() - start_time}

    match = re.search(r"facebook\.com/([^/?#]+)", url)
    if not match:
        return {"error": f"Invalid URL format: {url}", "latency_fetch": time.time() - start_time}

    page_identifier = match.group(1).strip()
    graph_url = f"https://graph.facebook.com/v25.0/{page_identifier}"
    params = {
        "fields": "id,name,about,description,category,fan_count,link,website",
        "access_token": access_token
    }

    try:
        response = requests.get(graph_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "platform": "facebook",
            "page_id": data.get("id", ""),
            "name": data.get("name", ""),
            "description": data.get("about") or data.get("description", ""),
            "category": data.get("category", ""),
            "followers": data.get("fan_count", 0),
            "website": data.get("website", ""),
            "url": url,
            "latency_fetch": time.time() - start_time
        }
    except Exception as e:
        return {"error": str(e), "latency_fetch": time.time() - start_time}

async def get_facebook_page_data_browser(url: str) -> dict:
    """Retrieves public Page metadata using the browser client workaround."""
    start_time = time.time()
    try:
        from facebook_browser_client import FacebookBrowserClient
        async with FacebookBrowserClient(headless=True) as client:
            data = await client.extract_page_data(url)
            
            # Normalize to match API output structure
            normalized = {
                "platform": "facebook",
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "category": data.get("category", ""),
                "followers": data.get("followers", 0),
                "website": data.get("website", ""),
                "recent_posts": data.get("recent_posts", []),
                "url": url,
                "latency_fetch": time.time() - start_time
            }
            return normalized
    except Exception as e:
        logger.error(f"Browser extraction failed: {e}")
        return {"error": f"Browser workaround failed: {str(e)}", "latency_fetch": time.time() - start_time}

def get_facebook_page_data(url: str) -> dict:
    """
    Main entry point. Tries Graph API first, fallbacks to Browser Workaround.
    """
    total_latency = 0
    # 1. Try Graph API
    result = get_facebook_page_data_api(url)
    total_latency += result.get("latency_fetch", 0)
    
    # 2. If API fails (e.g. permission error, missing credentials), try Browser
    if "error" in result:
        logger.info(f"Graph API failed for {url}, trying browser workaround...")
        try:
            # Run the async browser extraction in a sync wrapper
            # Note: This might need careful handling depending on the environment
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                browser_result = loop.run_until_complete(get_facebook_page_data_browser(url))
            else:
                browser_result = asyncio.run(get_facebook_page_data_browser(url))
            
            total_latency += browser_result.get("latency_fetch", 0)
            result = browser_result
        except Exception as e:
            result = {
                "platform": "facebook",
                "error": f"Both API and Browser failed: {str(e)}",
                "url": url
            }

    # Add synthesized text field for AI Evaluator compatibility
    if "error" not in result:
        content_parts = [
            f"Business Name: {result.get('name', 'N/A')}",
            f"Category: {result.get('category', 'N/A')}",
            f"About: {result.get('description', 'N/A')}",
            f"Followers: {result.get('followers', 0)}",
            f"Website: {result.get('website', 'N/A')}",
            f"Recent Posts: {', '.join(result.get('recent_posts', []))}"
        ]
        result["text"] = "\n".join(part for part in content_parts if part)
    
    result["latency_fetch"] = total_latency
    return result
