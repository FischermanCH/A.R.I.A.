from __future__ import annotations

import aria.main as main_mod


def test_read_raw_config_uses_cache_and_returns_isolated_copies(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("ui:\n  title: Cache Test\n", encoding="utf-8")

    monkeypatch.setattr(main_mod, "CONFIG_PATH", config_path)
    main_mod._clear_raw_config_cache()

    original_safe_load = main_mod.yaml.safe_load
    call_count = {"value": 0}

    def _counting_safe_load(stream):  # type: ignore[no-untyped-def]
        call_count["value"] += 1
        return original_safe_load(stream)

    monkeypatch.setattr(main_mod.yaml, "safe_load", _counting_safe_load)

    first = main_mod._read_raw_config()
    second = main_mod._read_raw_config()

    assert first["ui"]["title"] == "Cache Test"
    assert second["ui"]["title"] == "Cache Test"
    assert call_count["value"] == 1

    first["ui"]["title"] = "Mutated"
    third = main_mod._read_raw_config()
    assert third["ui"]["title"] == "Cache Test"

    config_path.write_text("ui:\n  title: Cache Changed\n", encoding="utf-8")
    fourth = main_mod._read_raw_config()

    assert fourth["ui"]["title"] == "Cache Changed"
    assert call_count["value"] == 2


def test_write_raw_config_refreshes_cache_without_extra_reload(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("ui:\n  title: Before Write\n", encoding="utf-8")

    monkeypatch.setattr(main_mod, "CONFIG_PATH", config_path)
    main_mod._clear_raw_config_cache()

    payload = {"ui": {"title": "After Write"}}
    main_mod._write_raw_config(payload)

    original_safe_load = main_mod.yaml.safe_load
    call_count = {"value": 0}

    def _counting_safe_load(stream):  # type: ignore[no-untyped-def]
        call_count["value"] += 1
        return original_safe_load(stream)

    monkeypatch.setattr(main_mod.yaml, "safe_load", _counting_safe_load)

    data = main_mod._read_raw_config()

    assert data["ui"]["title"] == "After Write"
    assert call_count["value"] == 0


def test_dynamic_proxy_reads_latest_target_object() -> None:
    class _Target:
        def __init__(self, label: str, enabled: bool) -> None:
            self.label = label
            self.enabled = enabled

        def __bool__(self) -> bool:
            return self.enabled

    holder = {"current": _Target("alpha", False)}
    proxy = main_mod._DynamicProxy(lambda: holder["current"])

    assert proxy.label == "alpha"
    assert bool(proxy) is False

    holder["current"] = _Target("beta", True)

    assert proxy.label == "beta"
    assert bool(proxy) is True
    assert repr(proxy) == repr(holder["current"])
