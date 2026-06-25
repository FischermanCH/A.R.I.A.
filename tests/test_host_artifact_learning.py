from __future__ import annotations

import asyncio

import aria.core.pipeline as pipeline_mod
from aria.core.host_artifact_learning import build_app_identity_hypothesis
from aria.core.host_artifact_learning import extract_host_artifact_signals
from aria.core.host_artifact_learning import host_artifact_discovery_outcome_events
from aria.core.config import Settings
from aria.core.pipeline import Pipeline


def test_extract_host_artifact_signals_finds_app_inventory_from_runtime_text() -> None:
    signals = extract_host_artifact_signals(
        """
        /srv/aria/docker-compose.yml
        /srv/aria/Dockerfile
        aria.service active running
        tcp LISTEN 0.0.0.0:8080
        docker compose ps: healthy
        """,
        payload={"connection_ref": "app-host", "connection_kind": "ssh", "capability": "ssh_command"},
    )

    assert signals["has_signal"] is True
    assert "/srv/aria/docker-compose.yml" in signals["paths"]
    assert "docker-compose.yml" in signals["files"]
    assert "Dockerfile" in signals["files"]
    assert "aria.service" in signals["services"]
    assert "8080" in signals["ports"]
    assert "healthy" in signals["health_terms"]
    assert "docker" in signals["package_terms"]
    assert signals["connection_ref"] == "app-host"


def test_build_app_identity_hypothesis_infers_docker_compose_app() -> None:
    signals = extract_host_artifact_signals(
        "/srv/aria/docker-compose.yml\n/srv/aria/Dockerfile\naria.service active\n0.0.0.0:8080 LISTEN\ndocker compose ps healthy"
    )

    hypothesis = build_app_identity_hypothesis(signals)

    assert hypothesis["runtime_kind"] == "docker_compose"
    assert hypothesis["app_root"] == "/srv/aria"
    assert "port:8080" in hypothesis["health_surfaces"]
    assert "docker compose up -d" in hypothesis["install_update_surfaces"]
    assert "record current container image/tag" in hypothesis["rollback_surfaces"]
    assert hypothesis["confidence"] == "medium"


def test_build_app_identity_hypothesis_infers_node_and_python_apps() -> None:
    node = build_app_identity_hypothesis(extract_host_artifact_signals("/opt/web/package.json\nnpm install\n*:3000 LISTEN"))
    python = build_app_identity_hypothesis(extract_host_artifact_signals("/opt/api/pyproject.toml\n/opt/api/requirements.txt\npip install"))

    assert node["runtime_kind"] == "node"
    assert node["app_root"] == "/opt/web"
    assert "npm install/build" in node["install_update_surfaces"]
    assert "record current package versions" in node["rollback_surfaces"]
    assert python["runtime_kind"] == "python"
    assert python["app_root"] == "/opt/api"
    assert "pip install" in python["install_update_surfaces"]


def test_build_app_identity_hypothesis_infers_systemd_app() -> None:
    signals = extract_host_artifact_signals("app.service active running\nsystemctl status app.service\n127.0.0.1:9000 listening")

    hypothesis = build_app_identity_hypothesis(signals)

    assert hypothesis["runtime_kind"] == "systemd"
    assert "service:app.service" in hypothesis["health_surfaces"]
    assert "systemctl restart <service>" in hypothesis["install_update_surfaces"]


def test_host_artifact_discovery_outcome_events_create_review_only_candidates() -> None:
    events = host_artifact_discovery_outcome_events(
        message="finde heraus was auf dem host installiert ist",
        user_id="u1",
        request_id="req-1",
        result_text="/opt/app/compose.yaml\napp.service failed\n*:9000 LISTEN\nnpm install info",
        payload={"connection_ref": "linux-app", "connection_kind": "ssh", "capability": "ssh_command"},
    )

    artifact_types = [event["artifact_type"] for event in events]

    assert artifact_types == ["app_artifact_candidate", "app_identity_candidate", "health_check_candidate", "install_plan_candidate"]
    assert events[0]["source"] == "host_artifact_discovery"
    assert events[0]["risk"] == "low"
    assert events[1]["risk"] == "low"
    assert events[2]["risk"] == "low"
    assert events[3]["risk"] == "medium"
    assert events[0]["metadata"]["promotion_allowed"] is False
    assert events[0]["evidence"]["connection_ref"] == "linux-app"
    assert "compose.yaml" in events[0]["evidence"]["observed_files"]
    assert events[1]["metadata"]["runtime_kind"] == "docker_compose"
    assert events[1]["evidence"]["app_identity_hypothesis"]["app_root"] == "/opt/app"
    assert events[3]["evidence"]["install_update_plan_draft"]["plan_kind"] == "install_update_plan_draft"
    assert events[3]["evidence"]["install_update_plan_draft"]["requires_confirmation"] is True
    assert events[3]["evidence"]["install_update_plan_draft"]["runtime_activation_allowed"] is False
    assert events[3]["evidence"]["install_update_plan_validation"]["runtime_activation_allowed"] is False
    assert events[3]["evidence"]["install_update_plan_validation"]["promotion_allowed"] is False
    assert events[3]["evidence"]["health_check_drafts"]
    assert events[3]["evidence"]["regression_drafts"]
    assert events[3]["evidence"]["pytest_skeleton_proposal"]["proposal_kind"] == "pytest_skeleton_proposal"
    assert events[3]["evidence"]["pytest_skeleton_proposal"]["write_allowed"] is False
    assert events[3]["metadata"]["plan_kind"] == "install_update_plan_draft"
    assert events[3]["metadata"]["validation_state"] in {"blocked", "review_required"}
    assert events[3]["metadata"]["health_check_draft_count"] >= 1
    assert events[3]["metadata"]["regression_draft_count"] >= 1
    assert events[3]["metadata"]["pytest_skeleton_proposal"] == "pytest_skeleton_proposal"


def test_host_artifact_discovery_outcome_events_include_recalled_artifact_review_patterns() -> None:
    patterns = [
        {
            "pattern_type": "artifact_pattern_candidate",
            "effect": "encourage",
            "summary": "Accepted pytest skeleton shape",
            "collection": "aria_learning_candidates_u1",
            "point_id": "pattern-1",
            "score": 0.9,
            "write_allowed": False,
            "runtime_activation_allowed": False,
        }
    ]

    events = host_artifact_discovery_outcome_events(
        message="finde heraus was auf dem host installiert ist",
        user_id="u1",
        result_text="/opt/app/compose.yaml\napp.service failed\n*:9000 LISTEN",
        artifact_review_patterns=patterns,
    )

    proposal = events[3]["evidence"]["pytest_skeleton_proposal"]
    assert proposal["artifact_review_pattern_count"] == 1
    assert proposal["artifact_review_patterns"][0]["effect"] == "encourage"
    assert events[3]["evidence"]["artifact_review_patterns"] == patterns


def test_host_artifact_discovery_ignores_plain_text_without_artifacts() -> None:
    events = host_artifact_discovery_outcome_events(
        message="sag hallo",
        user_id="u1",
        result_text="hello world",
    )

    assert events == []


class _PromptLoader:
    def get_persona(self) -> str:
        return "Du bist ARIA"


def test_pipeline_schedules_host_artifact_learning_outcomes(monkeypatch) -> None:
    captured: list[dict] = []

    async def fake_capture_learning_outcome(**kwargs):
        captured.append(dict(kwargs))
        return {"captured": True}

    async def _run() -> None:
        settings = Settings.model_validate(
            {
                "llm": {"model": "fake"},
                "memory": {"enabled": True},
                "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
            }
        )
        pipeline = Pipeline(settings=settings, prompt_loader=_PromptLoader(), llm_client=None)
        pipeline.memory_skill = object()  # type: ignore[assignment]
        monkeypatch.setattr(pipeline_mod, "capture_learning_outcome", fake_capture_learning_outcome)

        await pipeline._schedule_host_artifact_learning_outcomes(
            message="inventarisiere die app",
            user_id="u1",
            request_id="req-1",
            result_text="/srv/app/docker-compose.yml\napp.service active\n0.0.0.0:8080 LISTEN",
            payload={"connection_ref": "app-host", "connection_kind": "ssh", "capability": "ssh_command"},
        )
        await asyncio.sleep(0)

    asyncio.run(_run())

    artifact_types = [item["event"]["artifact_type"] for item in captured]
    assert artifact_types == ["app_artifact_candidate", "app_identity_candidate", "health_check_candidate", "install_plan_candidate"]
    assert captured[0]["event"]["source"] == "host_artifact_discovery"
