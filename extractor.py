import requests
from bs4 import BeautifulSoup
import re
import time
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Extractor:
    def __init__(self, timeout=5, max_chars=10000):
        self.timeout = timeout
        self.max_chars = max_chars

    def fetch_url(self, url, use_jina=False):
        """Fetches the content of a URL and returns the raw HTML or Markdown from Jina."""
        target_url = f"https://r.jina.ai/{url}" if use_jina else url
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        try:
            start_time = time.time()
            response = requests.get(target_url, headers=headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            latency = time.time() - start_time
            return response.text, latency
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch {url} (Jina={use_jina}): {str(e)}")

    def clean_html(self, content, is_markdown=False):
        """Extracts text content. If markdown (from Jina), return as is. Otherwise clean HTML."""
        if is_markdown:
            return content.strip()
            
        soup = BeautifulSoup(content, 'html.parser')

        # Remove script and style elements
        for script_or_style in soup(["script", "style", "nav", "footer", "header"]):
            script_or_style.decompose()

        # Get text
        text = soup.get_text(separator=' ')

        # Clean whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

        return text

    def process(self, url):
        """Processes a URL with smart fallback for SPAs/protected sites."""
        # Step 3: Update Extraction Router for Facebook
        if "facebook.com" in url.lower():
            from facebook_client import get_facebook_page_data
            result = get_facebook_page_data(url)
            
            # If API failed, return the error structure so the UI can handle it
            if "error" in result:
                result["url"] = url
                result["latency_fetch"] = 0.0
                result["char_count"] = 0
                result["text"] = f"Facebook Error: {result['error']}"
                return result
                
            # Otherwise, return it in the format expected by LeadEngine
            # (which expects a 'text' field for the AI Evaluator)
            return {
                "url": url,
                "text": result.get("text", ""),
                "latency_fetch": result.get("latency_fetch", 0.0),
                "char_count": len(result.get("text", "")),
                "platform": "facebook",
                "metadata": result
            }

        raw_text = ""
        latency = 0
        
        # 1. Try local extraction first
        try:
            html, lat = self.fetch_url(url)
            latency += lat
            raw_text = self.clean_html(html)
        except Exception as e:
            logger.warning(f"Local extraction for {url} failed: {e}. Trying fallback...")
            # If local fails, we leave raw_text empty and trigger fallback
            pass

        # 2. Check if result is suspicious or if local failed
        # suspicious = char count < 200 (usually just a logo or title)
        if len(raw_text.strip()) < 200:
            logger.info(f"Triggering Smart Fallback for {url} (Content length: {len(raw_text)})")
            try:
                jina_md, jina_latency = self.fetch_url(url, use_jina=True)
                raw_text = self.clean_html(jina_md, is_markdown=True)
                latency += jina_latency
            except Exception as fe:
                logger.error(f"Fallback to Jina failed: {fe}")
                # If both fail and we have nothing, raise the first error
                if not raw_text:
                    raise Exception(f"Extraction failed for {url}. Local error: {fe}")
        
        # Truncate to max_chars
        truncated_text = raw_text[:self.max_chars]
        
        return {
            "url": url,
            "text": truncated_text,
            "latency_fetch": latency,
            "char_count": len(truncated_text)
        }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        extractor = Extractor()
        try:
            result = extractor.process(sys.argv[1])
            print(f"URL: {result.get('url', sys.argv[1])}")
            print(f"Latency: {result['latency_fetch']:.2f}s")
            print(f"Chars: {result['char_count']}")
            print("-" * 20)
            print(result['text'][:500] + "...")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python extractor.py <url>")
