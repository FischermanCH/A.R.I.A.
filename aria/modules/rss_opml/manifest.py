"""Declarative metadata for RSS OPML helpers."""

from typing import Any

MODULE_MANIFEST: dict[str, Any] = {
    "id": "rss_opml", "name": "RSS OPML", "parent": "rss",
    "status": "import_boundary_active", "risk": "medium_high",
    "lifecycle": "bootstrap_static",
    "description": "Owns pure RSS OPML parse and serialization helpers without importing or exporting user files or changing profiles.",
    "python": ["aria/modules/rss_opml/opml.py"],
    "tests": ["tests/test_rss_opml.py", "tests/test_module_registry.py"],
    "depends_on": [], "external_boundaries": [
                          {
                              "id": "xml",
                              "category": "library_service",
                              "disposition": "durable",
                          },
                      ],
    "explicitly_excluded": ["opml_import_or_export_execution", "connection_profile_mutation", "user_file_access", "runtime_access"],
    "acceptance": ".codex/aria_acceptance/provider-planning-policy-import-rail-alpha730.json",
    "build_allowed": False, "runtime_access_allowed": False,
}
