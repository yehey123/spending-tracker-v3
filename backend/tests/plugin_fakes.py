"""Fake plugin objects for core tests (no AI SDKs needed)."""

from types import SimpleNamespace

from src.plugins import registry
from src.plugins.api import API_VERSION


class FakeCategorizer:
    api_version = API_VERSION

    def __init__(self, key="anthropic", reply="[]"):
        self.key = key
        self.reply = reply
        self.prompts: list[str] = []

    def has_credentials(self, settings):
        return True

    def classify(self, prompt, settings, ctx):
        self.prompts.append(prompt)
        return self.reply


def install_fake_categorizer(monkeypatch, key="anthropic", reply="[]") -> FakeCategorizer:
    fake = FakeCategorizer(key, reply)
    registry.reset_cache()
    monkeypatch.setattr(registry, "_cat_cache", {key: fake})
    return fake


class FakeEntryPoint:
    def __init__(self, name, obj=None, exc=None):
        self.name, self._obj, self._exc = name, obj, exc

    def load(self):
        if self._exc:
            raise self._exc
        return self._obj


def fake_descriptor(key="fakeai", api_version=API_VERSION, weight=2, max_side=1536):
    def build(settings, ctx):
        return SimpleNamespace(supports_categories=False, built_for=key)

    return SimpleNamespace(
        key=key, label=key.title(), api_version=api_version, config_fields=(),
        credit_weight=weight, max_side=max_side, build=build,
        has_credentials=lambda settings: True,
    )
