import requests
from bs4 import BeautifulSoup
import re
import time
import logging

from playwright.sync_api import sync_playwright # type: ignore

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class Extractor:
    def __init__(self, timeout=5, max_chars=10000):
        self.timeout = timeout
        self.max_chars = max_chars

    # BASE SCHEMA
    def base_schema(self, url, source):
        return {
            "url": url,
            "source": source,

            "name": "",
            "category": "",
            "description": "",

            "website": "",
            "phone": "",
            "email": "",
            "address": "",

            "social_links": {
                "facebook": "",
                "instagram": "",
                "linkedin": "",
                "tiktok": ""
            },

            "followers": 0,
            "recent_posts": [],
            "services": [],

            "text": "",
            "char_count": 0,
            "latency_fetch": 0,

            "errors": []
        }

    # =========================
    # FETCH (requests + jina)
    # =========================
    def fetch_url(self, url, use_jina=False):
        target_url = f"https://r.jina.ai/{url}" if use_jina else url

        try:
            start = time.time()
            res = requests.get(target_url, timeout=self.timeout)
            res.raise_for_status()
            return res.text, time.time() - start
        except Exception as e:
            raise Exception(f"fetch_failed (jina={use_jina}): {str(e)}")

    # =========================
    # CLEAN HTML
    # =========================
    def clean_html(self, html):
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator=" ")
        return re.sub(r"\s+", " ", text).strip()

    # =========================
    # METADATA
    # =========================
    def extract_metadata(self, soup):
        def get_meta(name):
            tag = soup.find("meta", property=name) or soup.find("meta", attrs={"name": name})
            return tag["content"].strip() if tag and tag.get("content") else ""

        title = soup.title.string.strip() if soup.title else ""

        return {
            "name": get_meta("og:site_name") or get_meta("og:title") or title,
            "description": get_meta("description") or get_meta("og:description"),
            "website": get_meta("og:url"),
            "category": get_meta("category")
        }

    # =========================
    # CONTACTS
    # =========================
    EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    PHONE_REGEX = r"\+?\d[\d\s\-]{7,15}"

    def extract_contacts(self, html):
        emails = re.findall(self.EMAIL_REGEX, html)
        phones = re.findall(self.PHONE_REGEX, html)

        return {
            "email": emails[0] if emails else "",
            "phone": phones[0] if phones else ""
        }

    # =========================
    # SOCIAL LINKS
    # =========================
    def extract_social_links(self, soup):
        links = {"facebook": "", "instagram": "", "linkedin": "", "tiktok": ""}

        for a in soup.find_all("a", href=True):
            href = a["href"]

            if "facebook.com" in href:
                links["facebook"] = href
            elif "instagram.com" in href:
                links["instagram"] = href
            elif "linkedin.com" in href:
                links["linkedin"] = href
            elif "tiktok.com" in href:
                links["tiktok"] = href

        return links

    # =========================
    # SERVICES
    # =========================
    def extract_services(self, soup):
        keywords = ["services", "what we do", "our solutions", "offerings"]
        services = []

        for tag in soup.find_all(["h1", "h2", "h3"]):
            text = tag.get_text(strip=True).lower()

            if any(k in text for k in keywords):
                ul = tag.find_next("ul")
                if ul:
                    services.extend([li.get_text(strip=True) for li in ul.find_all("li")])

        return services

    # =========================
    # SAFE INT
    # =========================
    def _safe_int(self, value):
        try:
            return int(str(value).replace(",", ""))
        except:
            return 0

    # =========================
    # PLAYWRIGHT FACEBOOK
    # =========================
    def extract_facebook_playwright(self, url, result):
        start = time.time()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=15000)

                page.wait_for_timeout(4000)

                content = page.content()
                text = page.inner_text("body")

                browser.close()

                # Try to navigate to About section
                try:
                    page.click('a:has-text("About")', timeout=3000)
                    page.wait_for_timeout(3000)
                except:
                    pass

                result["text"] = text

                # Followers
                match = re.search(r'([\d,]+)\s+followers', text.lower())
                if match:
                    result["followers"] = self._safe_int(match.group(1))

                # Name (title fallback)
                soup = BeautifulSoup(content, "html.parser")
                if soup.title:
                    result["name"] = soup.title.text.replace(" | Facebook", "").strip()

                # Website
                for a in soup.find_all("a", href=True):
                    if "l.facebook.com/l.php?u=" in a["href"]:
                        result["website"] = a["href"]
                        break

                # Posts (basic capture)
                posts = text.split("\n")
                result["recent_posts"] = [{"text": p[:200]} for p in posts if len(p) > 50][:3]

                result["latency_fetch"] += time.time() - start

        except Exception as e:
            result["errors"].append(f"playwright_failed: {str(e)}")

        return result

    # =========================
    # FACEBOOK PIPELINE
    # =========================
    def extract_facebook(self, url):
        result = self.base_schema(url, "facebook")

        # STEP 1: Playwright (primary)
        result = self.extract_facebook_playwright(url, result)

        # STEP 2: API fallback
        if result["followers"] == 0 and not result["description"]:
            try:
                from facebook_client import get_facebook_page_data
                fb = get_facebook_page_data(url)

                result["name"] = result["name"] or fb.get("name", "")
                result["description"] = result["description"] or fb.get("about", "")
                result["followers"] = result["followers"] or self._safe_int(fb.get("followers"))

            except Exception as e:
                result["errors"].append(f"api_failed: {str(e)}")

        # STEP 3: Jina fallback
        if len(result["text"]) < 100:
            try:
                jina, lat = self.fetch_url(url, use_jina=True)
                result["text"] = jina
                result["latency_fetch"] += lat
            except Exception as e:
                result["errors"].append(f"jina_failed: {str(e)}")

        result["char_count"] = len(result["text"])
        return result

    # =========================
    # WEBSITE
    # =========================
    def extract_website(self, url):
        result = self.base_schema(url, "website")

        html = ""
        raw_text = ""
        latency = 0

        try:
            html, lat = self.fetch_url(url)
            latency += lat
            raw_text = self.clean_html(html)
        except Exception as e:
            result["errors"].append(str(e))

        if len(raw_text) < 200:
            try:
                jina, lat = self.fetch_url(url, use_jina=True)
                raw_text = jina
                latency += lat
            except Exception as e:
                result["errors"].append(str(e))

        if html:
            soup = BeautifulSoup(html, "html.parser")

            result.update(self.extract_metadata(soup))
            result["social_links"].update(self.extract_social_links(soup))
            result["services"] = self.extract_services(soup)

        result.update(self.extract_contacts(html or raw_text))

        truncated = raw_text[:self.max_chars]

        result["text"] = truncated
        result["char_count"] = len(truncated)
        result["latency_fetch"] = latency

        return result

    # =========================
    # MAIN
    # =========================
    def process(self, url):
        if any(x in url.lower() for x in ["facebook.com", "fb.com"]):
            return self.extract_facebook(url)
        return self.extract_website(url)


# =========================
# CLI
# =========================
if __name__ == "__main__":
    import sys

    extractor = Extractor()

    if len(sys.argv) > 1:
        res = extractor.process(sys.argv[1])

        print(f"URL: {res['url']}")
        print(f"Source: {res['source']}")
        print(f"Name: {res['name']}")
        print(f"Followers: {res['followers']}")
        print(f"Email: {res['email']}")
        print(f"Phone: {res['phone']}")
        print("-" * 40)
        print(res["text"][:500])
    else:
        print("Usage: python extractor.py <url>")