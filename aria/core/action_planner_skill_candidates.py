from __future__ import annotations

"""Legacy compatibility wrapper for recipe action candidates.

New code should import from `aria.core.action_planner_recipe_candidates`.
"""

from aria.core import action_planner_recipe_candidates as _recipe_candidates

globals().update({name: getattr(_recipe_candidates, name) for name in dir(_recipe_candidates) if not name.startswith("__")})

__all__ = [name for name in globals() if not name.startswith("__")]
