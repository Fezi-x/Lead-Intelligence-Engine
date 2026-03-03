import requests
from bs4 import BeautifulSoup
import re
import time

class Extractor:
    def __init__(self, timeout=5, max_chars=10000):
        self.timeout = timeout
        self.max_chars = max_chars

    def fetch_url(self, url):
        """Fetches the content of a URL and returns the raw HTML."""
        try:
            start_time = time.time()
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            latency = time.time() - start_time
            return response.text, latency
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch URL {url}: {str(e)}")

    def clean_html(self, html):
        """Extracts text content from HTML, removing scripts, styles, and extra whitespace."""
        soup = BeautifulSoup(html, 'html.parser')

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
        """Processes a URL: fetch -> clean -> truncate -> return."""
        html, latency = self.fetch_url(url)
        raw_text = self.clean_html(html)
        
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
            print(f"URL: {result['url']}")
            print(f"Latency: {result['latency_fetch']:.2f}s")
            print(f"Chars: {result['char_count']}")
            print("-" * 20)
            print(result['text'][:500] + "...")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python extractor.py <url>")
