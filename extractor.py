import requests
from bs4 import BeautifulSoup
import re
import time
import logging
from urllib.parse import unquote, urlparse, parse_qs
import json

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

        def first_non_empty(*values):
            for v in values:
                if v:
                    return v
            return ""

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        h1 = ""
        h1_tag = soup.find("h1")
        if h1_tag:
            h1 = h1_tag.get_text(strip=True)

        canonical = ""
        canonical_tag = soup.find("link", rel="canonical")
        if canonical_tag and canonical_tag.get("href"):
            canonical = canonical_tag["href"].strip()

        json_ld = self.extract_json_ld(soup)

        return {
            "name": first_non_empty(
                get_meta("og:site_name"),
                get_meta("og:title"),
                get_meta("twitter:title"),
                title,
                h1,
                json_ld.get("name", "")
            ),
            "description": first_non_empty(
                get_meta("description"),
                get_meta("og:description"),
                get_meta("twitter:description"),
                json_ld.get("description", "")
            ),
            "website": first_non_empty(
                get_meta("og:url"),
                canonical,
                json_ld.get("url", "")
            ),
            "category": first_non_empty(
                get_meta("category"),
                get_meta("article:section"),
                json_ld.get("category", "")
            ),
            "json_ld": json_ld
        }

    def extract_json_ld(self, soup):
        payloads = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = script.string or script.get_text()
                if not raw:
                    continue
                data = json.loads(raw.strip())
                if isinstance(data, list):
                    payloads.extend(data)
                else:
                    payloads.append(data)
            except Exception:
                continue

        normalized = {
            "name": "",
            "description": "",
            "url": "",
            "email": "",
            "telephone": "",
            "address": "",
            "sameAs": []
        }

        for item in payloads:
            if not isinstance(item, dict):
                continue
            if not normalized["name"]:
                normalized["name"] = item.get("name", "") or item.get("legalName", "")
            if not normalized["description"]:
                normalized["description"] = item.get("description", "")
            if not normalized["url"]:
                normalized["url"] = item.get("url", "")
            if not normalized["email"]:
                normalized["email"] = item.get("email", "")
            if not normalized["telephone"]:
                normalized["telephone"] = item.get("telephone", "")
            if not normalized["address"]:
                address = item.get("address", "")
                if isinstance(address, dict):
                    parts = [
                        address.get("streetAddress", ""),
                        address.get("addressLocality", ""),
                        address.get("addressRegion", ""),
                        address.get("postalCode", ""),
                        address.get("addressCountry", "")
                    ]
                    normalized["address"] = ", ".join([p for p in parts if p])
                elif isinstance(address, str):
                    normalized["address"] = address
            if not normalized["sameAs"]:
                same_as = item.get("sameAs", [])
                if isinstance(same_as, list):
                    normalized["sameAs"] = same_as

        return normalized

    # =========================
    # CONTACTS
    # =========================
    EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    PHONE_REGEX = r"\+?\d[\d\s\-]{7,15}"

    def _deobfuscate_email(self, text):
        cleaned = text.replace("[at]", "@").replace("(at)", "@").replace(" at ", "@")
        cleaned = cleaned.replace("[dot]", ".").replace("(dot)", ".").replace(" dot ", ".")
        return cleaned

    def extract_contacts(self, html, text=""):
        combined = f"{html}\n{text}"

        mailto_matches = re.findall(r"mailto:([^\"'>\s?]+)", combined, flags=re.IGNORECASE)
        emails = [self._deobfuscate_email(e) for e in mailto_matches if e]
        emails.extend(re.findall(self.EMAIL_REGEX, self._deobfuscate_email(combined)))

        tel_matches = re.findall(r"tel:([^\"'>\s?]+)", combined, flags=re.IGNORECASE)
        phones = [t for t in tel_matches if t]
        phones.extend(re.findall(self.PHONE_REGEX, combined))

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
    # ADDRESS
    # =========================
    def extract_address(self, soup, text=""):
        address_tag = soup.find("address")
        if address_tag:
            addr_text = address_tag.get_text(separator=" ", strip=True)
            if addr_text:
                return re.sub(r"\s+", " ", addr_text).strip()

        postal = soup.find(attrs={"itemtype": re.compile("PostalAddress", re.IGNORECASE)})
        if postal:
            addr_text = postal.get_text(separator=" ", strip=True)
            if addr_text:
                return re.sub(r"\s+", " ", addr_text).strip()

        # Heuristic street address match
        if text:
            street_match = re.search(
                r"\b\d{1,5}\s+[A-Za-z0-9.\- ]+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct|Circle|Cir)\b[^\n]{0,60}",
                text,
                flags=re.IGNORECASE
            )
            if street_match:
                return street_match.group(0).strip()

        return ""

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
                else:
                    paragraph = tag.find_next("p")
                    if paragraph:
                        services.append(paragraph.get_text(strip=True))

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for s in services:
            if s and s not in seen:
                deduped.append(s)
                seen.add(s)

        return deduped

    # =========================
    # SAFE INT
    # =========================
    def _safe_int(self, value):
        try:
            return int(str(value).replace(",", ""))
        except:
            return 0

    def _compose_text(self, result, raw_text):
        lines = []

        def add_line(label, value):
            if value:
                lines.append(f"{label}: {value}")

        add_line("Business Name", result.get("name", ""))
        add_line("Category", result.get("category", ""))
        add_line("Description", result.get("description", ""))
        add_line("Website", result.get("website", ""))
        add_line("Email", result.get("email", ""))
        add_line("Phone", result.get("phone", ""))
        add_line("Address", result.get("address", ""))

        social = result.get("social_links", {})
        if isinstance(social, dict):
            social_links = [v for v in social.values() if v]
            if social_links:
                add_line("Social Links", ", ".join(social_links))

        services = result.get("services", [])
        if services:
            add_line("Services", ", ".join(services))

        followers = result.get("followers", 0)
        if followers:
            add_line("Followers", followers)

        recent_posts = result.get("recent_posts", [])
        if recent_posts:
            posts_texts = []
            for post in recent_posts:
                if isinstance(post, dict):
                    text = post.get("text", "")
                else:
                    text = str(post)
                if text:
                    posts_texts.append(text)
            if posts_texts:
                add_line("Recent Posts", " | ".join(posts_texts))

        structured = "\n".join(lines).strip()
        if not raw_text:
            return structured[: self.max_chars] if structured else ""

        if structured:
            combined = f"{structured}\n\n{raw_text}"
        else:
            combined = raw_text

        if len(combined) <= self.max_chars:
            return combined

        if len(structured) >= self.max_chars:
            return structured[: self.max_chars]

        remaining = self.max_chars - len(structured) - 2
        return f"{structured}\n\n{raw_text[: max(0, remaining)]}"

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

                # Try to navigate to About section for richer metadata
                try:
                    page.click('a:has-text("About")', timeout=3000)
                    page.wait_for_timeout(3000)
                except:
                    pass

                content = page.content()
                text = page.inner_text("body")

                # Attempt to capture some posts
                try:
                    page.wait_for_selector('div[role="article"]', timeout=3000)
                    posts = page.locator('div[role="article"]').all()
                    recent_posts = []
                    for post in posts[:3]:
                        post_text = post.inner_text()
                        lines = [l.strip() for l in post_text.split("\n") if l.strip()]
                        if lines:
                            recent_posts.append(" ".join(lines[:3]))
                    if recent_posts:
                        result["recent_posts"] = [{"text": p[:200]} for p in recent_posts]
                except:
                    pass

                browser.close()

                # Followers
                match = re.search(r'([\d,]+)\s+followers', text.lower())
                if match:
                    result["followers"] = self._safe_int(match.group(1))

                # Name (title fallback)
                soup = BeautifulSoup(content, "html.parser")
                if soup.title:
                    result["name"] = soup.title.text.replace(" | Facebook", "").strip()

                # Description/About
                meta_desc = ""
                meta_tag = soup.find("meta", property="og:description")
                if meta_tag and meta_tag.get("content"):
                    meta_desc = meta_tag["content"].strip()

                if not result["description"] and meta_desc:
                    result["description"] = meta_desc

                # Category
                if not result["category"]:
                    cat_match = re.search(r"page\s*[·•]\s*([^\n]+)", text, flags=re.IGNORECASE)
                    if cat_match:
                        result["category"] = cat_match.group(1).strip()

                # Website
                for a in soup.find_all("a", href=True):
                    if "l.facebook.com/l.php?u=" in a["href"]:
                        parsed = urlparse(a["href"])
                        qs = parse_qs(parsed.query)
                        target = qs.get("u", [""])[0]
                        result["website"] = unquote(target) or a["href"]
                        break

                # Address / Location
                if not result["address"]:
                    addr_match = re.search(r"(Address|Location)\s*[:\-]\s*([^\n]+)", text, flags=re.IGNORECASE)
                    if addr_match:
                        result["address"] = addr_match.group(2).strip()

                result["text"] = text

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
                result["description"] = result["description"] or fb.get("description", "") or fb.get("about", "")
                result["followers"] = result["followers"] or self._safe_int(fb.get("followers"))
                result["category"] = result["category"] or fb.get("category", "")
                result["website"] = result["website"] or fb.get("website", "")
                if not result["recent_posts"]:
                    posts = fb.get("recent_posts", [])
                    if posts:
                        result["recent_posts"] = [{"text": p[:200]} for p in posts]

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

        result["text"] = self._compose_text(result, result["text"])
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

            meta = self.extract_metadata(soup)
            json_ld = meta.pop("json_ld", {})
            result.update(meta)
            result["social_links"].update(self.extract_social_links(soup))
            result["services"] = self.extract_services(soup)

            if json_ld:
                if json_ld.get("email") and not result["email"]:
                    result["email"] = json_ld.get("email", "")
                if json_ld.get("telephone") and not result["phone"]:
                    result["phone"] = json_ld.get("telephone", "")
                if json_ld.get("address") and not result["address"]:
                    result["address"] = json_ld.get("address", "")
                same_as = json_ld.get("sameAs", [])
                if same_as:
                    for link in same_as:
                        if not isinstance(link, str):
                            continue
                        if "facebook.com" in link and not result["social_links"]["facebook"]:
                            result["social_links"]["facebook"] = link
                        elif "instagram.com" in link and not result["social_links"]["instagram"]:
                            result["social_links"]["instagram"] = link
                        elif "linkedin.com" in link and not result["social_links"]["linkedin"]:
                            result["social_links"]["linkedin"] = link
                        elif "tiktok.com" in link and not result["social_links"]["tiktok"]:
                            result["social_links"]["tiktok"] = link

            if not result["address"]:
                result["address"] = self.extract_address(soup, raw_text)

        contacts = self.extract_contacts(html or raw_text, raw_text)
        if contacts.get("email") and not result["email"]:
            result["email"] = contacts.get("email", "")
        if contacts.get("phone") and not result["phone"]:
            result["phone"] = contacts.get("phone", "")

        truncated = raw_text[:self.max_chars]

        result["text"] = self._compose_text(result, truncated)
        result["char_count"] = len(result["text"])
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
