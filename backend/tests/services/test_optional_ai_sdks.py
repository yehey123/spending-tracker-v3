import importlib
import sys

import pytest

# Provider modules still live in core until step 3 (moving to plugin).

_MODS = [
    "src.domain.services.ocr.claude",
    "src.domain.services.ocr.openai_vision",
    "src.domain.services.ocr.gemini_vision",
    "src.domain.services.ocr.vertex_vision",
    "src.domain.services.statement_pipeline",
]


@pytest.fixture
def no_ai_sdks(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    monkeypatch.setitem(sys.modules, "openai", None)
    yield
    monkeypatch.undo()
    for m in _MODS:
        if m in sys.modules:
            importlib.reload(sys.modules[m])


def test_pipeline_and_tesseract_import_without_ai_sdks(no_ai_sdks):
    for m in _MODS:
        importlib.reload(importlib.import_module(m))
    p = sys.modules["src.domain.services.statement_pipeline"]
    assert p.TesseractProvider is not None
    assert not hasattr(p, "OpenAIVisionProvider")  # core no longer imports providers


def test_ai_provider_raises_clear_error_without_sdk(no_ai_sdks):
    from src.domain.services.ocr.base import AIPackagesMissing
    from src.domain.services.ocr.claude import ClaudeVisionProvider
    from src.domain.services.ocr.openai_vision import OpenAIVisionProvider

    with pytest.raises(AIPackagesMissing, match="INSTALL_AI=1"):
        OpenAIVisionProvider(api_key="k")
    with pytest.raises(AIPackagesMissing, match="INSTALL_AI=1"):
        ClaudeVisionProvider(api_key="k")
