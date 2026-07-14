"""Unit tests for app.classifier — LLM call is mocked so no API key/network is needed."""

import app.classifier as classifier


def test_empty_text_returns_others(monkeypatch):
    result = classifier.classify_ticket("")
    assert result == {"category": "Others", "confidence": 0.0}


def test_whitespace_only_text_returns_others():
    result = classifier.classify_ticket("   ")
    assert result == {"category": "Others", "confidence": 0.0}


def test_high_confidence_valid_category_is_kept(monkeypatch):
    monkeypatch.setattr(
        classifier, "_call_llm", lambda text: {"category": "Login Issue", "confidence": 0.92}
    )
    result = classifier.classify_ticket("I cannot login to my account.")
    assert result == {"category": "Login Issue", "confidence": 0.92}


def test_low_confidence_is_downgraded_to_others(monkeypatch):
    monkeypatch.setattr(
        classifier, "_call_llm", lambda text: {"category": "Payment", "confidence": 0.4}
    )
    result = classifier.classify_ticket("Something vague.")
    assert result["category"] == "Others"
    assert result["confidence"] == 0.4


def test_unknown_category_is_coerced_to_others(monkeypatch):
    monkeypatch.setattr(
        classifier, "_call_llm", lambda text: {"category": "Shipping", "confidence": 0.95}
    )
    result = classifier.classify_ticket("Where is my package?")
    assert result["category"] == "Others"


def test_llm_failure_falls_back_to_others(monkeypatch):
    def boom(text):
        raise RuntimeError("API down")

    monkeypatch.setattr(classifier, "_call_llm", boom)
    result = classifier.classify_ticket("Some ticket text.")
    assert result == {"category": "Others", "confidence": 0.0}
