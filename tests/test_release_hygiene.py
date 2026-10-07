from __future__ import annotations

import json
import ast
import os
import re
import shlex
import subprocess
import tomllib
from pathlib import Path

from aria.modules.release_update.release_meta import DEFAULT_RELEASE_LABEL


ROOT = Path(__file__).resolve().parents[1]

DEMO_RECIPE_PROMPTS = {
    "prompts/recipes/coffee-fueled-incident-brief.md",
    "prompts/recipes/cosmic-release-radar.md",
    "prompts/recipes/documentation-dust-sweeper.md",
    "prompts/recipes/mobile-screenshot-scout.md",
    "prompts/recipes/retro-keyboard-researcher.md",
    "prompts/recipes/rubber-duck-standup.md",
}

LOCAL_PRIVATE_PATHS = {
    "config/config.yaml",
    "config/secrets.env",
    "data/",
    *DEMO_RECIPE_PROMPTS,
}

PUBLIC_TREE_FORBIDDEN_PREFIXES = {
    ".cache/",
    ".claude/",
    ".codex/",
    "data/",
    "docs/backlog/",
    "docs/internal/",
    "docs/local/",
    "test-results/",
}

PUBLIC_TREE_FORBIDDEN_EXACT = {
    "docs/AI_CONTEXT.md",
    "config/config.yaml",
    "config/secrets.env",
    *DEMO_RECIPE_PROMPTS,
}

PRIVATE_OPERATOR_PATH_PATTERNS: tuple[str, ...] = ()

PRIVATE_LITERAL_ENV = "ARIA_RELEASE_FORBIDDEN_LITERALS"
PRIVATE_LITERAL_FILE = ROOT / ".release-hygiene.local"
GENERIC_PRIVATE_PATTERNS = (
    re.compile(r"/(?:Users|home)/(?!(?:user|username|aria|app|runner|tmp|opt|var)(?:/|\b))[^/\s'\"`]+"),
    re.compile(
        r"\b(?![a-z0-9.-]*(?:example|local)[a-z0-9.-]*\.lan\b)"
        r"(?!(?:dns-node-[0-9]+|mgmt|fileserver)\.lan\b)"
        r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.lan\b",
        re.I,
    ),
)
SPLIT_PRIVATE_LITERAL = re.compile(
    r"(?:"
    r"(['\"])/(?:Users|home)/\1\s*\+\s*(['\"])[^'\"]+\2"
    r"|"
    r"(['\"])[a-z0-9-]+\.\3\s*\+\s*(['\"])[^'\"]+\.lan\4"
    r")",
    re.I,
)


def _local_forbidden_literals() -> tuple[str, ...]:
    values = [item.strip() for item in os.getenv(PRIVATE_LITERAL_ENV, "").split(os.pathsep) if item.strip()]
    if PRIVATE_LITERAL_FILE.is_file():
        values.extend(
            line.strip()
            for line in PRIVATE_LITERAL_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    return tuple(dict.fromkeys(values))


def _constant_strings_from_source(text: str) -> tuple[str, ...]:
    """Fold Python constant concatenations without publishing private literals here."""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ()
    values: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
            continue
        try:
            value = ast.literal_eval(node)
        except (ValueError, TypeError):
            continue
        if isinstance(value, str):
            values.append(value)
    return tuple(values)


def test_gitignore_blocks_generated_packaging_outputs() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    for pattern in {"*.egg-info/", "build/", "dist/", "*.whl", "*.tar", "*.tar.gz"}:
        assert pattern in gitignore


def test_gitignore_blocks_agent_browser_and_editor_state() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    for pattern in {".codex/", ".claude/", ".cache/", "test-results/", ".idea/", ".vscode/"}:
        assert pattern in gitignore


def test_gitignore_blocks_local_user_and_demo_data() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    for pattern in LOCAL_PRIVATE_PATHS:
        assert pattern in gitignore


def test_gitignore_blocks_internal_working_docs() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    internal_docs = {
        "docs/AI_CONTEXT.md",
        "docs/local/",
        "docs/backlog/",
        "docs/internal/",
        "docs/product/agentic-context-performance-plan.md",
        "docs/product/agentic-context-routing-dev-plan.md",
        "docs/product/agentic-context-runtime-v2.md",
        "docs/product/agentic-learning-loop-v2.md",
        "docs/product/deterministic-meaning-audit.md",
        "docs/product/llm-first-local-context-routing.md",
        "docs/product/qdrant-collections.md",
        "docs/product/qdrant-meta-catalog-redesign.md",
    }

    for pattern in internal_docs:
        assert pattern in gitignore


def test_dockerignore_blocks_internal_working_docs() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    internal_docs = {
        "docs/AI_CONTEXT.md",
        "docs/local/",
        "docs/backlog/",
        "docs/internal/",
        "docs/product/agentic-context-performance-plan.md",
        "docs/product/agentic-context-routing-dev-plan.md",
        "docs/product/agentic-context-runtime-v2.md",
        "docs/product/agentic-learning-loop-v2.md",
        "docs/product/deterministic-meaning-audit.md",
        "docs/product/llm-first-local-context-routing.md",
        "docs/product/qdrant-collections.md",
        "docs/product/qdrant-meta-catalog-redesign.md",
    }

    for pattern in internal_docs:
        assert pattern in dockerignore


def test_container_packages_only_public_product_release_authority() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert "COPY pyproject.toml README.md CHANGELOG.md LICENSE /app/" in dockerfile
    assert (
        "COPY docs/release/docker-hub-overview.md "
        "/app/docs/release/docker-hub-overview.md"
    ) in dockerfile
    assert "docs/release/*" in dockerignore
    assert "!docs/release/docker-hub-overview.md" in dockerignore
    assert "docs/release/" not in dockerignore


def test_dockerignore_blocks_local_user_and_demo_data() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    for pattern in LOCAL_PRIVATE_PATHS:
        assert pattern in dockerignore


def test_public_tree_does_not_track_local_user_or_demo_data() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    forbidden = sorted(
        path
        for path in tracked
        if path in {"config/config.yaml", "config/secrets.env"}
        or path.startswith("data/")
        or path in DEMO_RECIPE_PROMPTS
    )

    assert forbidden == []


def test_public_release_tree_does_not_track_private_or_internal_artifacts() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    forbidden = sorted(
        path
        for path in tracked
        if path in PUBLIC_TREE_FORBIDDEN_EXACT
        or any(path.startswith(prefix) for prefix in PUBLIC_TREE_FORBIDDEN_PREFIXES)
    )

    assert forbidden == []


def test_git_add_candidate_tree_has_no_private_operator_evidence_or_secret_shapes() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    candidates = [
        ROOT / raw.decode("utf-8", "surrogateescape")
        for raw in result.stdout.split(b"\0")
        if raw
    ]
    forbidden_patterns = (*PRIVATE_OPERATOR_PATH_PATTERNS, *_local_forbidden_literals())
    secret_shapes = (
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b"),
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
        re.compile("-" * 5 + r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY" + "-" * 5),
    )
    offenders: list[str] = []
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT)
        generic_scan_exempt = relative.parts[0] in {"tests", "samples"}
        generic_private = (
            not generic_scan_exempt
            and any(pattern.search(text) for pattern in GENERIC_PRIVATE_PATTERNS)
        )
        split_private = bool(SPLIT_PRIVATE_LITERAL.search(text))
        folded_private = any(
                (
                    not generic_scan_exempt
                    and any(pattern.search(value) for pattern in GENERIC_PRIVATE_PATTERNS)
                )
            or any(literal in value for literal in forbidden_patterns)
            for value in _constant_strings_from_source(text)
        )
        if (
            any(pattern in text for pattern in forbidden_patterns)
            or generic_private
            or split_private
            or folded_private
            or any(pattern.search(text) for pattern in secret_shapes)
        ):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_docker_copy_roots_are_covered_by_public_hygiene_exclusions() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    copied_roots: set[str] = set()
    for line in dockerfile.splitlines():
        stripped = line.strip()
        if not stripped.startswith("COPY "):
            continue
        parts = shlex.split(stripped)
        if "--from=docker_cli" in parts:
            continue
        copied_roots.update(part for part in parts[1:-1] if not part.startswith("--"))

    if "." in copied_roots or "docs" in copied_roots:
        for pattern in {"docs/AI_CONTEXT.md", "docs/backlog/", "docs/internal/", "docs/local/"}:
            assert pattern in dockerignore
    if "." in copied_roots or "prompts" in copied_roots:
        for pattern in DEMO_RECIPE_PROMPTS:
            assert pattern in dockerignore
    if "." in copied_roots or "config" in copied_roots:
        for pattern in {"config/config.yaml", "config/secrets.env"}:
            assert pattern in dockerignore
    if "." in copied_roots:
        assert "data/" in dockerignore


def test_python_package_data_does_not_publish_private_roots() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]
    aria_data = set(package_data["aria"])

    assert aria_data
    for pattern in aria_data:
        assert not pattern.startswith(("docs/", "config/", "prompts/", "samples/", "data/", ".codex/"))


def test_release_note_template_does_not_embed_private_operator_paths() -> None:
    template = (ROOT / "docs" / "release" / "github-release-notes-template.md").read_text(encoding="utf-8")

    for pattern in PRIVATE_OPERATOR_PATH_PATTERNS:
        assert pattern not in template


def test_release_label_matches_current_alpha_backlog_version() -> None:
    backlog = (ROOT / "docs" / "backlog" / "alpha-backlog.md").read_text(encoding="utf-8")
    match = re.search(r"aktuell (?:gebaut|versioniert): `([^`]+)`", backlog)

    assert match is not None
    assert DEFAULT_RELEASE_LABEL == match.group(1)


def test_source_runtime_assets_are_present_for_container_builds() -> None:
    required_files = [
        ROOT / "constraints" / "runtime.txt",
        ROOT / "prompts" / "persona.md",
        ROOT / "prompts" / "recipes" / "memory.md",
        ROOT / "prompts" / "recipes" / "memory_compress.md",
        ROOT / "samples" / "recipes" / "ssh-uptime-all-hosts.json",
        ROOT / "samples" / "security" / "guardrails.sample.yaml",
        ROOT / "config" / "config.example.yaml",
        ROOT / "config" / "secrets.env.example",
        ROOT / "docs" / "release" / "internal-build-smoke-test.md",
        ROOT / "docs" / "product" / "connection-action-contract.md",
        ROOT / "docs" / "product" / "connection-provider-manifest-checklist.md",
        ROOT / "docs" / "product" / "operator-observability-guardrails.md",
        ROOT / "docs" / "product" / "legacy-recipe-compatibility-audit.md",
    ]

    missing = [path.relative_to(ROOT).as_posix() for path in required_files if not path.exists()]

    assert missing == []


def test_static_css_has_balanced_blocks() -> None:
    css = (ROOT / "aria" / "static" / "style.css").read_text(encoding="utf-8")
    depth = 0
    for index, char in enumerate(css):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        assert depth >= 0, f"unexpected closing brace at byte {index}"

    assert depth == 0


def test_chat_layout_keeps_window_fixed_and_history_scrollable() -> None:
    css = (ROOT / "aria" / "static" / "style.css").read_text(encoding="utf-8")
    template = (ROOT / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert ".app-shell:has(.chat-layout-fill)" in css
    assert "--aria-visual-viewport-height: 100dvh;" in css
    assert "height: calc(var(--aria-visual-viewport-height, 100dvh) - 4rem);" in css
    assert "overflow: hidden;" in css
    assert '<div class="chat-box-wrap">' in template
    assert ".chat-layout-fill .chat-box-wrap" in css
    assert ".chat-box-wrap .chat-box" in css
    assert ".chat-layout-fill .chat-box" in css
    assert "flex: 1 1 auto;" in css
    assert "max-height: none;" in css
    assert "overflow-y: auto;" in css
    assert "min-height: clamp(10rem, 40svh, 18rem);" in css
    assert "window.visualViewport" in template
    assert "scrollMessagesToLatest" in template


def test_chat_prompt_queue_controls_are_present() -> None:
    css = (ROOT / "aria" / "static" / "style.css").read_text(encoding="utf-8")
    template = (ROOT / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert 'id="chat-queue"' in template
    assert 'id="chat-queue-toggle"' in template
    assert 'id="chat-queue-list"' in template
    assert "enqueuePrompt" in template
    assert "moveQueuedPrompt" in template
    assert "editQueuedPrompt" in template
    assert "deleteQueuedPrompt" in template
    assert "startNextQueuedPrompt" in template
    assert "queueCollapseThreshold = 2" in template
    assert "queueExpanded" in template
    assert ".chat-queue-item" in css
    assert ".chat-queue-action" in css
    assert ".chat-queue-toggle" in css
    assert '.chat-queue[data-collapsed="true"]' in css


def test_chat_export_controls_are_present() -> None:
    css = (ROOT / "aria" / "static" / "style.css").read_text(encoding="utf-8")
    template = (ROOT / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert "installChatExportControls" in template
    assert "buildChatExportMarkdown" in template
    assert "exportCurrentChat" in template
    assert "navigator.clipboard.writeText" in template
    assert "downloadChatExport" in template
    assert 'id="chat-export-button"' in template
    assert "{{ icon('copy', 'chat-export-icon') }}" in template
    assert 'class="toolbox-summary-text"' in template
    assert ".chat-tools-head" in css
    assert ".chat-export-button" in css
    assert ".chat-export-status" in css
    assert ".toolbox-summary-text" in css


def test_memory_browser_keeps_ios_touch_navigation_usable() -> None:
    css = (ROOT / "aria" / "static" / "style.css").read_text(encoding="utf-8")

    assert ".memory-drilldown-stage" in css
    assert "touch-action: pan-x pan-y pinch-zoom;" in css
    assert "-webkit-overflow-scrolling: touch;" in css
    assert "@media (hover: none), (pointer: coarse)" in css
    assert ".memory-drilldown-stage-controls button" in css
    assert "min-height: 2.75rem;" in css
    assert "font-size: 0.78rem;" in css


def test_chat_has_no_legacy_auto_memory_indicator() -> None:
    template = (ROOT / "aria" / "templates" / "chat.html").read_text(encoding="utf-8")

    assert "memory_admin_auto_memory_path" not in template
    assert "auto-memory-indicator" not in template
    assert "chat.debug_auto_memory_learning" not in template


def test_mobile_viewport_uses_ios_safe_area() -> None:
    template = (ROOT / "aria" / "templates" / "base.html").read_text(encoding="utf-8")
    reconnect_shell = (ROOT / "aria" / "static" / "update-reconnect-sw.js").read_text(encoding="utf-8")

    assert "viewport-fit=cover" in template
    assert "viewport-fit=cover" in reconnect_shell


def test_admin_config_mobile_guards_cover_small_viewports() -> None:
    css = (ROOT / "aria" / "static" / "style.css").read_text(encoding="utf-8")

    assert ".admin-nav-group-summary" in css
    assert "min-height: 44px;" in css
    assert ".config-admin-return-link" in css
    assert "flex: 1 1 100%;" in css
    assert ".context-help-link" in css
    assert "white-space: normal;" in css
    assert "@media (max-width: 860px)" in css
    assert "@media (max-width: 700px)" in css
    assert "@media (max-width: 640px)" in css


def test_stats_navigation_uses_immediate_busy_indicator() -> None:
    template = (ROOT / "aria" / "templates" / "base.html").read_text(encoding="utf-8")

    assert "module_route_path('stats_ui', '/stats')" in template
    assert 'data-busy-immediate="true"' in template


def test_dockerfile_uses_runtime_constraints_for_reproducible_installs() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    constraints = (ROOT / "constraints" / "runtime.txt").read_text(encoding="utf-8")

    assert "FROM docker:26-cli@sha256:" in dockerfile
    assert "FROM python:3.12-slim@sha256:" in dockerfile
    assert "COPY constraints /app/constraints" in dockerfile
    assert "-c /app/constraints/runtime.txt" in dockerfile
    assert "--no-build-isolation" in dockerfile
    assert "pip==25.0.1" in dockerfile
    for package in ("litellm==", "openai==", "aiohttp==", "pydantic==", "fastapi==", "qdrant-client=="):
        assert package in constraints


def test_sample_recipe_manifests_are_recipe_first() -> None:
    sample_dir = ROOT / "samples" / "recipes"
    manifests = sorted(sample_dir.glob("*.json"))

    assert manifests
    for path in manifests:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), path.name
        assert str(payload.get("id", "")).strip(), path.name
        assert str(payload.get("name", "")).strip(), path.name
        prompt_file = str(payload.get("prompt_file", "") or "").strip()
        if prompt_file:
            assert prompt_file.startswith("prompts/recipes/"), path.name


def test_legacy_recipe_compatibility_policy_is_explicit() -> None:
    audit = (ROOT / "docs" / "product" / "legacy-recipe-compatibility-audit.md").read_text(encoding="utf-8")

    assert "Muss vorerst bleiben" in audit
    assert "Darf nicht neu verwendet werden" in audit
    assert "Migration-Gate" in audit
    assert "`skills:`" in audit
    assert "`/skills*`" in audit
    assert "recipe-first" in audit
