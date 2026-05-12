from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi.responses import JSONResponse, Response

from aria.core.recipe_manifests import delete_stored_recipe_manifest
from aria.core.recipe_manifests import recipe_manifest_file
from aria.core.recipe_manifests import sanitize_recipe_id
from aria.web.recipes_wizard_save import remove_custom_recipe_config

RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]


def delete_stored_recipe_and_config(
    recipe_id: str,
    *,
    read_raw_config: RawConfigReader,
    write_raw_config: RawConfigWriter,
    reload_runtime: RuntimeReloader,
) -> dict[str, Any]:
    result = delete_stored_recipe_manifest(recipe_id)
    raw = read_raw_config()
    raw = remove_custom_recipe_config(raw, recipe_id)
    write_raw_config(raw)
    reload_runtime()
    return result


def stored_recipe_export_response(recipe_id: str) -> Response:
    clean_id = sanitize_recipe_id(recipe_id)
    path: Path = recipe_manifest_file(clean_id)
    if not path.exists():
        return JSONResponse({"error": "not_found"}, status_code=404)
    content = path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{clean_id}.json"'},
    )
