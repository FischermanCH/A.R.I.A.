from __future__ import annotations

from aria.web.main_request_helpers import MainRequestHelperDeps
from aria.web.main_request_helpers import build_main_request_helpers


def test_recipe_routing_info_uses_recipe_first_learned_i18n_keys() -> None:
    seen_keys: list[str] = []

    def translate(_lang: str, key: str, default: str) -> str:
        seen_keys.append(key)
        return default

    helpers = build_main_request_helpers(
        MainRequestHelperDeps(
            translate=translate,
            stored_recipe_desc_i18n_fallbacks={},
            get_auth_session_from_request=lambda _request: None,
            request_cookie_value=lambda _request, _name: "",
            username_cookie="aria_user",
        )
    )

    assert helpers.format_recipe_routing_info("de", "learned_promoted:linux-health") == "Learned recipe promoted into stored recipe: linux-health."
    assert helpers.format_recipe_routing_info("de", "learned_dismissed:linux-health") == "Learned recipe kept for observation: linux-health."
    assert helpers.format_recipe_routing_info("de", "learned_deleted:linux-health") == "Learned recipe deleted: linux-health."
    assert seen_keys == [
        "learned_recipes.info_promoted",
        "learned_recipes.info_dismissed",
        "learned_recipes.info_deleted",
    ]
