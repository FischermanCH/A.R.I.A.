from __future__ import annotations

import importlib
from pathlib import Path


def test_connection_admin_legacy_path_is_identity_alias() -> None:
    legacy = importlib.import_module("aria.modules.connections_profiles.admin")
    canonical = importlib.import_module("aria.modules.connections_profiles.admin")

    assert legacy is canonical
    assert legacy.CONNECTION_ADMIN_SPECS is canonical.CONNECTION_ADMIN_SPECS
    assert legacy.CONNECTION_CREATE_SPECS is canonical.CONNECTION_CREATE_SPECS
    assert legacy.CONNECTION_UPDATE_SPECS is canonical.CONNECTION_UPDATE_SPECS
    assert legacy.ConnectionAdminError is canonical.ConnectionAdminError
    assert legacy.create_connection_profile is canonical.create_connection_profile
    assert legacy.update_connection_profile is canonical.update_connection_profile
    assert legacy.delete_connection_profile is canonical.delete_connection_profile


def test_connection_admin_i18n_root_keeps_aria_location() -> None:
    canonical = importlib.import_module("aria.modules.connections_profiles.admin")
    aria_root = Path(__file__).resolve().parents[1] / "aria"

    assert canonical._CONNECTION_ADMIN_I18N.base_dir == aria_root / "i18n"
