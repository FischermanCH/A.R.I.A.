from __future__ import annotations

"""Legacy compatibility wrapper for stored recipe manifests.

New code should import from `aria.core.recipe_manifests`. This module keeps old
`custom_skills` imports working while the product surface is recipe-first.
"""

from aria.core import recipe_manifests as _recipe_manifests

globals().update({name: getattr(_recipe_manifests, name) for name in dir(_recipe_manifests) if not name.startswith("__")})

__all__ = [name for name in globals() if not name.startswith("__")]
