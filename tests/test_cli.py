from __future__ import annotations

import json

import aria.cli as cli


def test_cli_version_outputs_release_label(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_version_snapshot", lambda check_updates=False: {"version": "0.1.0", "label": "0.1.0-alpha57"})

    exit_code = cli.main(["--version"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "0.1.0-alpha57"


def test_cli_version_check_outputs_status_lines(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "_version_snapshot",
        lambda check_updates=False: {
            "version": "0.1.0",
            "label": "0.1.0-alpha57",
            "update_status": {
                "latest_label": "0.1.0-alpha58",
                "update_available": True,
                "checked_at": "2026-04-07T10:00:00+00:00",
                "source": "github-tags",
            },
        },
    )

    exit_code = cli.main(["version-check"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "installed=0.1.0-alpha57" in captured.out
    assert "latest=0.1.0-alpha58" in captured.out
    assert "status=update-available" in captured.out


def test_cli_version_check_supports_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "_version_snapshot",
        lambda check_updates=False: {
            "version": "0.1.0",
            "label": "0.1.0-alpha57",
            "update_status": {
                "latest_label": "0.1.0-alpha57",
                "update_available": False,
                "checked_at": "2026-04-07T10:00:00+00:00",
                "source": "github-tags",
            },
        },
    )

    exit_code = cli.main(["version-check", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["label"] == "0.1.0-alpha57"
    assert payload["update_status"]["update_available"] is False
