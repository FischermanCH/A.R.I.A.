from __future__ import annotations

"""Legacy compatibility wrapper for the recipe runtime.

New code should import from `aria.core.recipe_runtime`. This module exists so
older tests, configs, and external imports do not break during the alpha
recipe-first migration.
"""

from aria.core import recipe_runtime as _recipe_runtime

globals().update({name: getattr(_recipe_runtime, name) for name in dir(_recipe_runtime) if not name.startswith("__")})

__all__ = [name for name in globals() if not name.startswith("__")]
