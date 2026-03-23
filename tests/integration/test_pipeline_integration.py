import pytest
import core
import extractor


class DummyEvaluator:
    def __init__(self):
        self.model = "dummy"

    def evaluate(self, content, rag_context=None, retry_count=1):
        return {
            "business_name": "Bangkok Bakery",
            "business_type": "Bakery",
            "primary_service": "Foundation Package",
            "secondary_service": None,
            "fit_score": 70,
            "reasoning": "Needs better presence",
            "outreach_angle": "Improve online ordering",
        }


class DummyCoda:
    def fetch_row_by_url(self, url):
        return False

    def insert_row(self, evaluation_data):
        return {"ok": True}


@pytest.mark.integration
def test_pipeline_with_real_extractor_and_rag(monkeypatch):
    def fake_fetch_url(self, url, use_jina=False):
        html = "<html><body><h1>Bangkok Bakery</h1><p>Fresh bread daily.</p></body></html>"
        return (html, 0.01)

    monkeypatch.setattr(extractor.Extractor, "fetch_url", fake_fetch_url)
    monkeypatch.setattr(core, "Evaluator", DummyEvaluator)
    monkeypatch.setattr(core, "CodaClient", DummyCoda)

    engine = core.LeadEngine()
    result = engine.process_url("https://example.com")

    assert result["_status"] == "success"
    assert result["business_name"] == "Bangkok Bakery"
