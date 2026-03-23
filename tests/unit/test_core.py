import pytest
import core


class DummyExtractor:
    def process(self, url):
        return {
            "url": url,
            "text": "We are a local bakery offering cakes.",
            "latency_fetch": 0.01,
            "char_count": 38,
        }


class DummyEvaluator:
    def __init__(self):
        self.model = "dummy"

    def evaluate(self, content, rag_context=None, retry_count=1):
        return {
            "business_name": "Sweet Bakery",
            "business_type": "Bakery",
            "primary_service": "Foundation Package",
            "secondary_service": None,
            "fit_score": 75,
            "reasoning": "Needs a better site",
            "outreach_angle": "Improve ordering flow",
        }


class DummyCoda:
    def fetch_row_by_url(self, url):
        return False

    def insert_row(self, evaluation_data):
        return {"ok": True}


class DummyRAG:
    def retrieve(self, content):
        return ["Consider local SEO."]


@pytest.mark.unit
def test_lead_engine_success(monkeypatch):
    monkeypatch.setattr(core, "Extractor", DummyExtractor)
    monkeypatch.setattr(core, "Evaluator", DummyEvaluator)
    monkeypatch.setattr(core, "CodaClient", DummyCoda)
    monkeypatch.setattr(core, "RAG", DummyRAG)

    engine = core.LeadEngine()
    result = engine.process_url("https://example.com")

    assert result["_status"] == "success"
    assert result["business_name"] == "Sweet Bakery"
    assert "_latency" in result
