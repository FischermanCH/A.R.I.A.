from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from aria.modules import MODULE_MANIFESTS


ROOT = Path(__file__).resolve().parents[1]


def _product_sources() -> list[tuple[Path, str]]:
    paths = [
        *sorted((ROOT / "aria").rglob("*.py")),
        *sorted((ROOT / "aria" / "templates").glob("*.html")),
        ROOT / "aria" / "static" / "style.css",
        ROOT / "Dockerfile",
        ROOT / "config" / "config.example.yaml",
    ]
    return [(path, path.read_text(encoding="utf-8")) for path in paths if path.is_file()]


def _manifest_values(key: str) -> set[str]:
    return {
        str(value)
        for manifest in MODULE_MANIFESTS.values()
        for value in manifest.get(key, ())
    }


def test_every_template_has_a_current_owner_or_product_consumer() -> None:
    patterns = _manifest_values("templates")
    sources = _product_sources()
    unclassified: list[str] = []

    for path in sorted((ROOT / "aria" / "templates").glob("*.html")):
        manifest_owned = any(fnmatch(path.name, pattern) for pattern in patterns)
        referenced = any(path != source_path and path.name in text for source_path, text in sources)
        if not manifest_owned and not referenced:
            unclassified.append(path.name)

    assert unclassified == []


def test_every_static_asset_has_an_exact_prefix_or_product_consumer() -> None:
    exact = _manifest_values("static")
    prefixes = _manifest_values("static_prefixes")
    sources = _product_sources()
    unclassified: list[str] = []

    for path in sorted(p for p in (ROOT / "aria" / "static").rglob("*") if p.is_file()):
        relative = path.relative_to(ROOT / "aria" / "static").as_posix()
        manifest_owned = relative in exact or any(relative.startswith(prefix) for prefix in prefixes)
        referenced = any(path != source_path and relative in text for source_path, text in sources)
        if not manifest_owned and not referenced:
            unclassified.append(relative)

    assert unclassified == []


def test_every_prompt_and_lexicon_has_an_owner_reference() -> None:
    prompt_prefixes = _manifest_values("prompts")
    sources = _product_sources()
    unclassified: list[str] = []

    for path in sorted(p for p in (ROOT / "prompts").rglob("*") if p.is_file()):
        relative = path.relative_to(ROOT).as_posix()
        manifest_owned = any(relative.startswith(prefix) for prefix in prompt_prefixes)
        referenced = any(relative in text for source_path, text in sources if source_path != path)
        if not manifest_owned and not referenced:
            unclassified.append(relative)

    for path in sorted((ROOT / "aria" / "lexicons").glob("*.json")):
        relative = path.relative_to(ROOT / "aria").as_posix()
        referenced = any(relative in text or path.name in text for source_path, text in sources if source_path != path)
        if not referenced:
            unclassified.append(relative)

    assert unclassified == []


def test_sample_roots_match_their_directory_loader_contracts() -> None:
    connections = sorted((ROOT / "samples" / "connections").glob("*"))
    security = sorted((ROOT / "samples" / "security").glob("*"))
    recipes = {path.name for path in (ROOT / "samples" / "recipes").glob("*.json")}
    legacy_skills = {path.name for path in (ROOT / "samples" / "skills").glob("*.json")}

    assert connections and all(path.name.endswith(".sample.yaml") for path in connections)
    assert security and all(path.name.endswith(".sample.yaml") for path in security)
    assert recipes == {
        "ssh-disk-usage-all-hosts.json",
        "ssh-updates-check-all-hosts.json",
        "ssh-uptime-all-hosts.json",
    }
    assert legacy_skills == set()

    support_source = (ROOT / "aria" / "modules" / "connections_mutations" / "support_helpers.py").read_text(
        encoding="utf-8"
    )
    recipe_source = (ROOT / "aria" / "modules" / "recipe_store" / "template_import.py").read_text(
        encoding="utf-8"
    )
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert '"samples" / "connections"' in support_source
    assert '"samples" / "security"' in support_source
    assert '"samples" / "recipes"' in recipe_source
    assert '"samples" / "skills"' in recipe_source
    assert "COPY samples /app/samples" in dockerfile
