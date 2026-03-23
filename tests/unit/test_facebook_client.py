import pytest
import facebook_client as fc


@pytest.mark.unit
def test_facebook_api_invalid_url_returns_error(monkeypatch):
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "test")

    result = fc.get_facebook_page_data_api("https://example.com")
    assert "error" in result


@pytest.mark.unit
def test_facebook_fallback_to_browser(monkeypatch):
    def fake_api(url):
        return {"error": "fail", "latency_fetch": 0.01}

    async def fake_browser(url):
        return {
            "platform": "facebook",
            "name": "Test Page",
            "description": "About us",
            "category": "Bakery",
            "followers": 123,
            "website": "https://example.com",
            "recent_posts": ["Fresh bread"],
            "url": url,
            "latency_fetch": 0.02,
        }

    monkeypatch.setattr(fc, "get_facebook_page_data_api", fake_api)
    monkeypatch.setattr(fc, "get_facebook_page_data_browser", fake_browser)

    result = fc.get_facebook_page_data("https://facebook.com/testpage")

    assert "text" in result
    assert "Business Name" in result["text"]
    assert result["name"] == "Test Page"
