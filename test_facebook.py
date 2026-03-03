import os
import json
from facebook_client import get_facebook_page_data

def test_facebook():
    urls = [
        "https://web.facebook.com/escmyanmar/",  # Valid public page
        "https://www.facebook.com/nonexistent_page_123456789",  # Invalid page
        "https://facebook.com/SomeMalformedURL???"  # Malformed URL
    ]

    print("--- FACEBOOK API INTEGRATION TEST ---")
    
    app_id = os.getenv("FACEBOOK_APP_ID")
    if not app_id:
        print("WARNING: FACEBOOK_APP_ID missing from .env. Test will likely return errors.")

    for url in urls:
        print(f"\nProcessing: {url}")
        try:
            result = get_facebook_page_data(url)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"CRITICAL CRASH: {e}")

if __name__ == "__main__":
    test_facebook()
