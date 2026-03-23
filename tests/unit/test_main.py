import pytest
import main


class DummyEngine:
    def process_url(self, url):
        return {
            "business_name": "Acme Co",
            "business_type": "Plumbing",
            "primary_service": "Foundation Package",
            "secondary_service": None,
            "fit_score": 80,
            "reasoning": "Good fit",
            "outreach_angle": "Upgrade site",
            "_status": "success",
            "_latency": "0.10s",
            "_usage": {
                "total_tokens": 10,
                "prompt_tokens": 7,
                "completion_tokens": 3,
            },
        }


@pytest.mark.unit
def test_main_outputs_success(monkeypatch, capsys):
    monkeypatch.setattr(main, "LeadEngine", DummyEngine)

    main.main("https://example.com")
    captured = capsys.readouterr()

    assert "SUCCESS: ADDED TO CRM" in captured.out
    assert "Acme Co" in captured.out
