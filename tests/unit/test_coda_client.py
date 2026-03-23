import json
import pytest
import requests
import coda_client


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"Status {self.status_code}")

    def json(self):
        return self._payload


@pytest.mark.unit
def test_get_columns(monkeypatch):
    monkeypatch.setenv("CODA_API_TOKEN", "token")
    monkeypatch.setenv("CODA_DOC_ID", "doc")
    monkeypatch.setenv("CODA_TABLE_ID", "table")

    def fake_get(url, headers, timeout=10):
        return DummyResponse({"items": [{"name": "Business URL"}, {"name": "Fit Score"}]})

    monkeypatch.setattr(coda_client.requests, "get", fake_get)

    client = coda_client.CodaClient()
    cols = client._get_columns()
    assert cols == ["Business URL", "Fit Score"]


@pytest.mark.unit
def test_fetch_row_by_url(monkeypatch):
    monkeypatch.setenv("CODA_API_TOKEN", "token")
    monkeypatch.setenv("CODA_DOC_ID", "doc")
    monkeypatch.setenv("CODA_TABLE_ID", "table")

    def fake_get(url, headers, params=None, timeout=10):
        return DummyResponse({"items": [{"id": "row1"}]})

    monkeypatch.setattr(coda_client.requests, "get", fake_get)

    client = coda_client.CodaClient()
    assert client.fetch_row_by_url("https://example.com") is True


@pytest.mark.unit
def test_insert_row_filters_missing_columns(monkeypatch):
    monkeypatch.setenv("CODA_API_TOKEN", "token")
    monkeypatch.setenv("CODA_DOC_ID", "doc")
    monkeypatch.setenv("CODA_TABLE_ID", "table")

    client = coda_client.CodaClient()

    monkeypatch.setattr(client, "_get_columns", lambda: ["Business URL", "Fit Score"])

    captured = {}

    def fake_post(url, headers, json=None, timeout=15):
        captured["payload"] = json
        return DummyResponse({"items": [{"id": "row1"}]})

    monkeypatch.setattr(coda_client.requests, "post", fake_post)

    payload = {
        "url": "https://example.com",
        "business_name": "Acme",
        "fit_score": 88,
        "reasoning": "Good fit",
        "outreach_angle": "Hello",
    }

    client.insert_row(payload)

    cells = captured["payload"]["rows"][0]["cells"]
    columns = {c["column"] for c in cells}
    assert columns == {"Business URL", "Fit Score"}
