from __future__ import annotations

RECIPE_STATUS_BADGE_LABEL = "recipe_status"
STORED_RECIPE_BADGE_LABEL = "stored_recipe"


def recipe_toolbox_keywords(*values: str) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in [*values, "recipe", "playbook", "automation", "aktion", "ablauf"]:
        clean = str(raw or "").strip().lower()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        rows.append(clean)
    return rows
