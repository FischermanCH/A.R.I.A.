from __future__ import annotations

"""Legacy compatibility wrapper for recipe web routes.

New code should import from `aria.web.recipes_routes`. `/skills*` remains a
redirect/backcompat surface during the alpha migration.
"""

from aria.web import recipes_routes as _recipes_routes

globals().update({name: getattr(_recipes_routes, name) for name in dir(_recipes_routes) if not name.startswith("__")})

__all__ = [name for name in globals() if not name.startswith("__")]
