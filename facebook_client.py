import os
import requests
import logging
import re
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

def get_facebook_page_data(url: str) -> dict:
    """
    Retrieves public Page metadata using the Facebook Graph API.
    Does not use HTML scraping or login flows.
    """
    app_id = os.getenv("FACEBOOK_APP_ID")
    app_secret = os.getenv("FACEBOOK_APP_SECRET")
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")

    # Auto-generate access token if not provided
    if not access_token and app_id and app_secret:
        access_token = f"{app_id}|{app_secret}"

    if not access_token:
        error_msg = "Missing Facebook API credentials (ID, Secret, or Token)."
        logger.error(error_msg)
        return {
            "platform": "facebook",
            "error": error_msg,
            "source_url": url
        }

    # Extract page identifier (username or ID)
    # Handles https://facebook.com/SomeBusiness or https://www.facebook.com/SomeBusiness/
    match = re.search(r"facebook\.com/([^/?#]+)", url)
    if not match:
        error_msg = f"Could not extract Page identifier from URL: {url}"
        logger.error(error_msg)
        return {
            "platform": "facebook",
            "error": error_msg,
            "source_url": url
        }

    page_identifier = match.group(1).strip()
    
    # Graph API endpoint
    graph_url = f"https://graph.facebook.com/v19.0/{page_identifier}"
    params = {
        "fields": "id,name,about,description,category,fan_count,link,website",
        "access_token": access_token
    }

    try:
        response = requests.get(graph_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Normalize output
        normalized = {
            "platform": "facebook",
            "page_id": data.get("id", ""),
            "name": data.get("name", ""),
            "description": data.get("about") or data.get("description", ""),
            "category": data.get("category", ""),
            "followers": data.get("fan_count", 0),
            "website": data.get("website", ""),
            "source_url": url
        }
        
        # Add synthesized text field for AI Evaluator compatibility
        content_parts = [
            f"Business Name: {normalized['name']}",
            f"Category: {normalized['category']}",
            f"About: {normalized['description']}",
            f"Followers: {normalized['followers']}",
            f"Website: {normalized['website']}"
        ]
        normalized["text"] = "\n".join(part for part in content_parts if part)
        
        return normalized

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else "Unknown"
        error_reason = f"Graph API Error ({status_code}): {str(e)}"
        logger.error(f"{error_reason} for URL: {url}")
        return {
            "platform": "facebook",
            "error": error_reason,
            "source_url": url
        }
    except Exception as e:
        error_reason = f"Internal Error: {str(e)}"
        logger.error(f"{error_reason} for URL: {url}")
        return {
            "platform": "facebook",
            "error": error_reason,
            "source_url": url
        }
