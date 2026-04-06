import pytest
from extractor import Extractor


@pytest.mark.unit
def test_clean_html_strips_noise():
    html = """
    <html>
      <head>
        <style>.hidden{display:none}</style>
        <script>console.log('x')</script>
      </head>
      <body>
        <header>HEADER TEXT</header>
        <nav>NAV TEXT</nav>
        <main>
          <h1>Acme Plumbing</h1>
          <p>We fix pipes fast.</p>
        </main>
        <footer>FOOTER TEXT</footer>
      </body>
    </html>
    """
    extractor = Extractor()
    text = extractor.clean_html(html)
    assert "Acme Plumbing" in text
    assert "HEADER TEXT" not in text
    assert "NAV TEXT" not in text
    assert "FOOTER TEXT" not in text
    assert "console.log" not in text


@pytest.mark.unit
def test_process_falls_back_to_jina_for_short_content(monkeypatch):
    extractor = Extractor(max_chars=500)

    def fake_fetch_url(url, use_jina=False):
        if use_jina:
            return ("# Title\n\nLong content " * 10, 0.2)
        return ("<html><body>Hi</body></html>", 0.1)

    monkeypatch.setattr(extractor, "fetch_url", fake_fetch_url)
    result = extractor.process("https://example.com")

    assert "Long content" in result["text"]
    assert result["latency_fetch"] >= 0.2
    assert result["char_count"] == len(result["text"])


@pytest.mark.unit
def test_process_truncates_content(monkeypatch):
    extractor = Extractor(max_chars=20)

    def fake_fetch_url(url, use_jina=False):
        return ("<html><body>" + "A" * 200 + "</body></html>", 0.05)

    monkeypatch.setattr(extractor, "fetch_url", fake_fetch_url)
    result = extractor.process("https://example.com")

    assert len(result["text"]) == 20
    assert result["char_count"] == 20


@pytest.mark.unit
def test_extracts_rich_metadata_contacts_and_services(monkeypatch):
    extractor = Extractor(max_chars=1000)

    html = """
    <html>
      <head>
        <title>Acme Plumbing</title>
        <meta property="og:site_name" content="Acme Plumbing Co." />
        <meta property="og:description" content="Fast emergency plumbing services." />
        <meta property="og:url" content="https://acmeplumbing.example.com" />
      </head>
      <body>
        <h1>Acme Plumbing</h1>
        <address>123 Main St, Austin, TX 78701</address>
        <a href="mailto:hello@acmeplumbing.example.com">Email</a>
        <a href="tel:+15125551234">Call</a>
        <a href="https://facebook.com/acmeplumbing">Facebook</a>
        <a href="https://instagram.com/acmeplumbing">Instagram</a>
        <section>
          <h2>Services</h2>
          <ul>
            <li>Drain Cleaning</li>
            <li>Water Heater Repair</li>
          </ul>
        </section>
        <p>We handle residential and commercial plumbing.</p>
      </body>
    </html>
    """

    def fake_fetch_url(url, use_jina=False):
        return (html, 0.1)

    monkeypatch.setattr(extractor, "fetch_url", fake_fetch_url)

    result = extractor.process("https://acmeplumbing.example.com")

    assert result["name"] == "Acme Plumbing Co."
    assert "Fast emergency plumbing services." in result["description"]
    assert result["website"] == "https://acmeplumbing.example.com"
    assert result["email"] == "hello@acmeplumbing.example.com"
    assert result["phone"] == "+15125551234"
    assert "Austin" in result["address"]
    assert result["social_links"]["facebook"].endswith("facebook.com/acmeplumbing")
    assert result["social_links"]["instagram"].endswith("instagram.com/acmeplumbing")
    assert "Drain Cleaning" in result["services"]
    assert "Business Name: Acme Plumbing Co." in result["text"]
