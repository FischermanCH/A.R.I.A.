from __future__ import annotations

from urllib.parse import quote_plus

from aria.core.learned_recipe_promotion import promote_learned_recipe_to_stored_recipe
from aria.core.learned_recipe_store import delete_learned_recipe_store_entry
from aria.core.learned_recipe_store import update_learned_recipe_store_entry

LEARNED_RECIPE_ACTION_PROMOTE = "promote"
LEARNED_RECIPE_ACTION_DISMISS = "dismiss"
LEARNED_RECIPE_ACTION_DELETE = "delete"

_DISMISS_PROMOTION_HINT = "admin:Dismissed from review for now; collect fresh evidence before revisiting."


def _append_recipe_action_info(target: str, info: str) -> str:
    clean_target = str(target or "").strip() or "/recipes/learned"
    separator = "&" if "?" in clean_target else "?"
    return f"{clean_target}{separator}saved=1&info={quote_plus(info)}"


def learned_recipe_admin_success_url(*, action: str, recipe_id: str, surface_path: str) -> str:
    clean_action = str(action or "").strip().lower()
    clean_recipe_id = str(recipe_id or "").strip()
    target = str(surface_path or "").strip() or "/recipes/learned"

    if clean_action == LEARNED_RECIPE_ACTION_PROMOTE:
        stored = promote_learned_recipe_to_stored_recipe(clean_recipe_id)
        info = f"learned_promoted:{stored['id']}"
    elif clean_action == LEARNED_RECIPE_ACTION_DISMISS:
        updated = update_learned_recipe_store_entry(
            clean_recipe_id,
            {
                "promotion_state": "observed",
                "promotion_hint": _DISMISS_PROMOTION_HINT,
            },
        )
        info = f"learned_dismissed:{updated['recipe_id']}"
    elif clean_action == LEARNED_RECIPE_ACTION_DELETE:
        delete_learned_recipe_store_entry(clean_recipe_id)
        info = f"learned_deleted:{clean_recipe_id}"
    else:
        raise ValueError(f"Unknown learned recipe admin action: {clean_action}")

    return _append_recipe_action_info(target, info)
