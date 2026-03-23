import json
import pytest
import evaluator as evaluator_module


class DummyUsage:
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 5
        self.total_tokens = 15


class DummyCompletion:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]
        self.usage = DummyUsage()


class DummyCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return DummyCompletion(self._content)


class DummyChat:
    def __init__(self, content):
        self.completions = DummyCompletions(content)


class DummyGroq:
    def __init__(self, api_key, content=None):
        self.chat = DummyChat(content)


@pytest.mark.unit
def test_evaluator_parses_and_validates(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")

    dummy_json = {
        "business_name": "Acme",
        "business_type": "Plumbing",
        "primary_service": "Service A",
        "secondary_service": None,
        "fit_score": 90,
        "reasoning": "Good fit",
        "outreach_angle": "Hello",
    }

    content = json.dumps(dummy_json)

    def fake_groq(api_key):
        return DummyGroq(api_key, content=content)

    monkeypatch.setattr(evaluator_module, "Groq", fake_groq)
    monkeypatch.setattr(
        evaluator_module.Evaluator,
        "_load_services",
        lambda self: {"services": [{"name": "Service A"}]},
    )
    monkeypatch.setattr(
        evaluator_module.Evaluator,
        "_load_prompt",
        lambda self: "Prompt [SERVICES_JSON]",
    )

    evaluator = evaluator_module.Evaluator(model="dummy")
    result = evaluator.evaluate("content")

    assert result["primary_service"] == "Service A"
    assert "_usage" in result
    assert result["_usage"]["total_tokens"] == 15


@pytest.mark.unit
def test_evaluator_rejects_invalid_service(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")

    dummy_json = {
        "business_name": "Acme",
        "business_type": "Plumbing",
        "primary_service": "Not In List",
        "secondary_service": None,
        "fit_score": 90,
        "reasoning": "Good fit",
        "outreach_angle": "Hello",
    }

    content = json.dumps(dummy_json)

    def fake_groq(api_key):
        return DummyGroq(api_key, content=content)

    monkeypatch.setattr(evaluator_module, "Groq", fake_groq)
    monkeypatch.setattr(
        evaluator_module.Evaluator,
        "_load_services",
        lambda self: {"services": [{"name": "Service A"}]},
    )
    monkeypatch.setattr(
        evaluator_module.Evaluator,
        "_load_prompt",
        lambda self: "Prompt [SERVICES_JSON]",
    )

    evaluator = evaluator_module.Evaluator(model="dummy")
    with pytest.raises(ValueError):
        evaluator.evaluate("content")
