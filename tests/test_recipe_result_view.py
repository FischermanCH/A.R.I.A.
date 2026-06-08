from aria.core.recipe_result_view import build_recipe_execution_summary
from aria.core.recipe_result_view import format_recipe_step_marker
from aria.core.recipe_result_view import friendly_recipe_error_text


def test_format_recipe_step_marker_localizes_runtime_states() -> None:
    assert format_recipe_step_marker("1.ssh_run", language="de") == "1. ssh_run: ok"
    assert format_recipe_step_marker("2.sftp_read(skipped)", language="de") == "2. sftp_read: uebersprungen"
    assert format_recipe_step_marker("3.rss_read(error-continue)", language="en") == "3. rss_read: error, continued"


def test_build_recipe_execution_summary_keeps_legacy_marker_but_adds_readable_recipe_view() -> None:
    text = build_recipe_execution_summary(
        recipe_name="Linux Health",
        executed=["1.ssh_run", "2.discord_send(skipped)"],
        skipped=["notify"],
        result="uptime ok",
        ssh_summary="Technischer Lauf:\n- dns-node-01: ok, 0.4s",
        language="de",
    )

    assert "[Stored Recipe Steps] Linux Health" in text
    assert "Recipe-Lauf: Linux Health" in text
    assert "Status: abgeschlossen" in text
    assert "2 ausgefuehrt · 1 uebersprungen" in text
    assert "1. ssh_run: ok" in text
    assert "2. discord_send: uebersprungen" in text
    assert "Uebersprungene Schritte: notify" in text
    assert "Ergebnis:\nuptime ok" in text


def test_build_recipe_execution_summary_formats_skipped_step_markers() -> None:
    text = build_recipe_execution_summary(
        recipe_name="Notify",
        executed=["1.ssh_run"],
        skipped=["2.discord_send(skipped)"],
        result="ok",
        language="de",
    )

    assert "1 ausgefuehrt · 1 uebersprungen" in text
    assert "Uebersprungene Schritte: 2. discord_send: uebersprungen" in text


def test_friendly_recipe_error_text_maps_runtime_codes_to_operator_text() -> None:
    assert friendly_recipe_error_text("recipe_manifest_missing", language="de") == "Das Rezept-Manifest fehlt oder ist nicht mehr verfuegbar."
    assert friendly_recipe_error_text("recipe_unknown_step_type:docker_run", language="de") == "Das Rezept enthaelt einen nicht unterstuetzten Schritt-Typ: docker_run."
    assert friendly_recipe_error_text("recipe_smb_read_error:Unable to open directory", language="en") == "SMB read failed in the recipe: Unable to open directory"
