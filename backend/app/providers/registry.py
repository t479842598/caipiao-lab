"""供应商注册表：按优先级选源、failover、健康检查。"""

from __future__ import annotations

from .base import BaseProvider
from .c500 import C500Provider
from .csv_import import CsvImportProvider
from .cwl_official import CwlOfficialProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}
        for provider in (CwlOfficialProvider(), C500Provider(), CsvImportProvider()):
            self._providers[provider.code] = provider

    def all(self) -> list[BaseProvider]:
        return sorted(self._providers.values(), key=lambda p: p.priority)

    def get(self, code: str) -> BaseProvider:
        if code not in self._providers:
            raise KeyError(code)
        return self._providers[code]

    def candidates(self, game: str) -> list[BaseProvider]:
        return [p for p in self.all() if p.supports(game)]

    def primary_for(self, game: str) -> BaseProvider | None:
        candidates = self.candidates(game)
        return candidates[0] if candidates else None


registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return registry
