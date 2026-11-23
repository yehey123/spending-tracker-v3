"""Ollama provider: OCR resolves to the OpenAI-compatible client at OLLAMA_BASE_URL."""

from types import SimpleNamespace
from unittest.mock import patch

from src.domain.services.categorizer import _has_ai_credentials
from src.domain.services.statement_pipeline import _resolve_ocr


def _row(**kw):
    base = dict(ocr_provider="ollama", max_output_tokens=None, ai_model=None)
    return SimpleNamespace(**{**base, **kw})


def test_resolve_ocr_ollama_uses_configured_url_and_default_model():
    with patch("src.core.config.settings.ollama_base_url", "http://host.docker.internal:11434/v1"):
        p = _resolve_ocr(_row())
    assert type(p).__name__ == "OpenAIVisionProvider"
    assert str(p.client.base_url).rstrip("/") == "http://host.docker.internal:11434/v1"
    assert p.model == "ornith-1.5:9b"
    assert p.reasoning_effort == "none"  # thinking off: 15/15 accuracy at ~half the tokens


def test_cloud_openai_sends_no_reasoning_effort():
    p = _resolve_ocr(_row(ocr_provider="openai", openai_api_key="sk-test"))
    assert p.reasoning_effort is None


def test_resolve_ocr_ollama_honours_selected_model():
    assert _resolve_ocr(_row(ai_model="qwen3.8:27b")).model == "qwen3.8:27b"


def test_ollama_needs_no_api_key_for_categorisation():
    assert _has_ai_credentials(SimpleNamespace(ocr_provider="ollama")) is True
