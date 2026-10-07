"""Lazy compatibility imports for exact deprecated module names."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
from types import ModuleType

from aria.modules.legacy_aliases import LEGACY_MODULE_ALIASES


class _LegacyModuleAliasLoader(importlib.abc.Loader):
    def __init__(self, legacy_name: str, canonical_name: str) -> None:
        self.legacy_name = legacy_name
        self.canonical_name = canonical_name

    def create_module(self, spec: object) -> ModuleType:  # noqa: ARG002
        module = importlib.import_module(self.canonical_name)
        sys.modules[self.legacy_name] = module
        return module

    def exec_module(self, module: ModuleType) -> None:
        sys.modules[self.legacy_name] = module


class LegacyModuleAliasFinder(importlib.abc.MetaPathFinder):
    """Resolve only exact deprecated names; unknown names fall through normally."""

    def find_spec(
        self,
        fullname: str,
        path: object = None,  # noqa: ARG002
        target: ModuleType | None = None,  # noqa: ARG002
    ) -> importlib.machinery.ModuleSpec | None:
        canonical_name = LEGACY_MODULE_ALIASES.get(fullname)
        if canonical_name is None:
            return None
        return importlib.util.spec_from_loader(
            fullname,
            _LegacyModuleAliasLoader(fullname, canonical_name),
        )


def install_legacy_module_aliases() -> LegacyModuleAliasFinder:
    """Install the exact alias finder once without importing canonical targets."""

    for finder in sys.meta_path:
        if isinstance(finder, LegacyModuleAliasFinder):
            return finder
    finder = LegacyModuleAliasFinder()
    sys.meta_path.insert(0, finder)
    return finder
