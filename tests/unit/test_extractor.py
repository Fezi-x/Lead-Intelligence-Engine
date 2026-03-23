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
