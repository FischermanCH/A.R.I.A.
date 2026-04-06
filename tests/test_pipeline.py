import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from aria.core.auto_memory import AutoMemoryExtractor
from aria.core.capability_context import CapabilityContextStore
from aria.core.config import Settings
from aria.core.pipeline import Pipeline
from aria.skills.base import SkillResult


class FakePromptLoader:
    def get_persona(self) -> str:
        return "Du bist ARIA"


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content
        self.usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


class FakeLLMClient:
    def __init__(self) -> None:
        self.calls = 0
        self.last_messages = []

    async def chat(self, messages):
        self.calls += 1
        self.last_messages = messages
        assert messages[0]["role"] == "system"
        return FakeLLMResponse("ok")


class FeedResolverLLMClient(FakeLLMClient):
    def __init__(self, ref: str):
        super().__init__()
        self.ref = ref

    async def chat(self, messages):
        self.calls += 1
        self.last_messages = messages
        assert messages[0]["role"] == "system"
        return FakeLLMResponse(json.dumps({"ref": self.ref, "confidence": "high", "reason": "host passt"}))


class FakeMemorySkill:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute(self, query: str, params: dict[str, object]) -> SkillResult:
        self.calls.append({"query": query, "params": dict(params)})
        return SkillResult(skill_name=str(params.get("action", "memory")), content="", success=True)


class FakeMemoryAssistSkill(FakeMemorySkill):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        super().__init__()
        self.rows = rows
        self.search_calls: list[dict[str, object]] = []

    async def search_memories(
        self,
        user_id: str,
        query: str,
        type_filter: str = "all",
        top_k: int = 10,
    ) -> list[dict[str, object]]:
        self.search_calls.append(
            {
                "user_id": user_id,
                "query": query,
                "type_filter": type_filter,
                "top_k": top_k,
            }
        )
        return list(self.rows)


async def _run_pipeline() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    result = await pipeline.process("Hallo", user_id="u1", source="test")
    assert result.text == "ok"
    assert result.intents == ["chat"]
    assert result.usage["total_tokens"] == 15
    assert llm.calls == 1


def test_pipeline_single_llm_call() -> None:
    asyncio.run(_run_pipeline())


def test_pipeline_collects_skill_detail_lines_for_chat_badges() -> None:
    async def _run() -> None:
        settings = Settings.model_validate(
            {
                "llm": {"model": "fake"},
                "memory": {"enabled": False},
                "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
            }
        )
        llm = FakeLLMClient()
        pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

        async def fake_run_skills(*args, **kwargs):
            _ = (args, kwargs)
            return [
                SkillResult(
                    skill_name="memory_recall",
                    content="[DOKUMENT: demo.pdf] HDR ist automatisch aktiv.",
                    success=True,
                    metadata={
                        "detail_lines": [
                            "Quelle: demo.pdf · aria_docs_demo_manuals · Chunk 3/12",
                        ]
                    },
                )
            ]

        pipeline._run_skills = fake_run_skills  # type: ignore[method-assign]

        result = await pipeline.process("Ist HDR aktiv?", user_id="u1", source="test")

        assert result.text == "ok"
        assert result.detail_lines == [
            "Quelle: demo.pdf · aria_docs_demo_manuals · Chunk 3/12",
        ]
        assert llm.calls == 1

    asyncio.run(_run())


def test_pipeline_uses_litellm_pricing_fallback_for_known_chat_models() -> None:
    async def _run() -> None:
        settings = Settings.model_validate(
            {
                "llm": {"model": "gpt-5.1"},
                "memory": {"enabled": False},
                "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
                "pricing": {
                    "enabled": True,
                    "currency": "USD",
                    "chat_models": {},
                    "embedding_models": {},
                },
            }
        )
        pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=FakeLLMClient())

        result = await pipeline.process("Hallo", user_id="u1", source="test")

        assert result.chat_cost_usd is not None
        assert result.chat_cost_usd > 0.0
        assert result.total_cost_usd == result.chat_cost_usd

    asyncio.run(_run())


def test_custom_skill_router_does_not_overmatch_linux_update_skill_on_generic_storage_prompt() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)
    runtime_skills = [
        {
            "id": "linux-updates-check-template",
            "name": "Linux Updates Check Template",
            "description": (
                "Read-only Beispielskill fuer Debian/Ubuntu Linux-Server. "
                "Prueft via SSH, ob Paket-Updates verfuegbar sind, ohne etwas zu installieren."
            ),
            "keywords": [
                "brauchen meine linux server updates",
                "gibt es updates auf meinem linux server",
                "pruefe linux updates",
                "check server updates",
                "apt updates pruefen",
                "server updates check",
            ],
            "connections": ["ssh"],
            "steps": [{"id": "s1", "type": "ssh_run", "name": "Check", "params": {}, "on_error": "stop"}],
            "enabled": True,
        }
    ]

    intents = pipeline._match_custom_skill_intents(
        "Erkläre mir den Unterschied zwischen LVM, ZFS und Btrfs für einen Homelab-Server, "
        "mit Fokus auf Snapshots, Recovery und praktischer Admin-Wartung. "
        "Gib mir am Ende eine klare Empfehlung für einen Ubuntu-Server mit Docker.",
        runtime_skills,
    )

    assert intents == []


def test_extract_memory_store_text() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=FakeLLMClient())
    text = pipeline._extract_memory_store_text("Merk dir, dass mein NAS 10.0.10.100 hat.")
    assert text == "mein NAS 10.0.10.100 hat"


def test_auto_memory_extractor_finds_basic_facts() -> None:
    decision = AutoMemoryExtractor.decide("Hostname: server-main, IP: 10.0.1.1")
    assert decision.facts
    assert any("10.0.1.1" in fact for fact in decision.facts)


def test_pipeline_custom_skill_runtime_llm_task() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "net-check.json").write_text(
            json.dumps(
                {
                    "id": "net-check",
                    "name": "Net Check",
                    "router_keywords": ["netzcheck", "ping host"],
                    "description": "Prueft Netzwerk-Infos.",
                    "connections": ["ssh"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "llm_transform",
                            "name": "Kurzfassung",
                            "params": {"prompt": "Analysiere Netzwerkstatus knapp.\n{query}"},
                            "on_error": "stop",
                        }
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    net-check:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(pipeline.process("Bitte netzcheck für den host", user_id="u1", source="test"))
        assert "custom_skill:net-check" in result.intents
        assert llm.calls == 2
        assert llm.last_messages
        user_prompt = str(llm.last_messages[1]["content"])
        assert "Custom Skill Steps" in user_prompt
        assert "Ergebnis:" in user_prompt


def test_pipeline_custom_skill_runtime_ssh_missing_connection_reports_error() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "sys-update.json").write_text(
            json.dumps(
                {
                    "id": "sys-update",
                    "name": "System Update",
                    "router_keywords": ["update server"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "ssh_run",
                            "name": "Update",
                            "params": {
                                "connection_ref": "missing-connection",
                                "command": "sudo apt update && sudo apt upgrade -y",
                            },
                            "on_error": "stop",
                        }
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    sys-update:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(pipeline.process("please update server", user_id="u1", source="test"))
        assert "custom_skill:sys-update" in result.intents
        assert llm.calls == 1
        assert any(err.startswith("custom_skill_ssh_connection_not_found") for err in result.skill_errors)


def test_pipeline_custom_skill_runtime_discord_respects_profile_toggle() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "discord": {
                    "ops-alerts": {
                        "webhook_url": "https://discord.example/webhook",
                        "allow_skill_messages": False,
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "discord-report.json").write_text(
            json.dumps(
                {
                    "id": "discord-report",
                    "name": "Discord Report",
                    "router_keywords": ["discord report"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "discord_send",
                            "name": "Send",
                            "params": {
                                "connection_ref": "ops-alerts",
                                "message": "Test {query}",
                            },
                            "on_error": "stop",
                        }
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    discord-report:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(pipeline.process("please discord report", user_id="u1", source="test"))
        assert "custom_skill:discord-report" in result.intents
        assert llm.calls == 1
        assert any(err.startswith("custom_skill_discord_messages_disabled") for err in result.skill_errors)


def test_pipeline_prefers_rule_based_custom_skill_before_capability_path() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "discord": {
                    "ops-alerts": {
                        "webhook_url": "https://discord.example/webhook",
                        "allow_skill_messages": True,
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "discord-report.json").write_text(
            json.dumps(
                {
                    "id": "discord-report",
                    "name": "Discord Report",
                    "router_keywords": ["schick einen test nach discord", "discord test senden"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "chat_send",
                            "name": "Chat",
                            "params": {"chat_message": "Skill gewann"},
                            "on_error": "stop",
                        }
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    discord-report:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        async def _unexpected_capability(*_args, **_kwargs):
            raise AssertionError("Capability path should not run before a matching custom skill.")

        pipeline._try_capability_action = _unexpected_capability  # type: ignore[method-assign]

        result = asyncio.run(
            pipeline.process(
                "Schick einen Test nach Discord mit dem Inhalt Hallo",
                user_id="u1",
                source="test",
            )
        )

        assert "custom_skill:discord-report" in result.intents
        assert result.text == "Skill gewann"


def test_pipeline_custom_skill_runtime_sftp_write_and_read() -> None:
    remote_files: dict[str, bytes] = {}

    class FakeSFTPHandle:
        def __init__(self, path: str, mode: str) -> None:
            self.path = path
            self.mode = mode
            self.buffer = remote_files.get(path, b"")

        def read(self) -> bytes:
            return self.buffer

        def write(self, content: str | bytes) -> None:
            payload = content.encode("utf-8") if isinstance(content, str) else content
            remote_files[self.path] = payload

        def __enter__(self) -> "FakeSFTPHandle":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakeSFTPClient:
        def open(self, path: str, mode: str) -> FakeSFTPHandle:
            return FakeSFTPHandle(path, mode)

        def stat(self, path: str) -> object:
            if path not in {"", "/", "/data"}:
                raise FileNotFoundError(path)
            return object()

        def mkdir(self, path: str) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeSSHClient:
        def set_missing_host_key_policy(self, _policy: object) -> None:
            return None

        def connect(self, **_kwargs: object) -> None:
            return None

        def open_sftp(self) -> FakeSFTPClient:
            return FakeSFTPClient()

        def close(self) -> None:
            return None

    fake_paramiko = SimpleNamespace(
        SSHClient=FakeSSHClient,
        AutoAddPolicy=lambda: object(),
    )

    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "sftp": {
                    "nas-share": {
                        "host": "10.0.1.20",
                        "port": 22,
                        "user": "backup",
                        "password": "secret",
                        "root_path": "/data",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td, patch.dict(sys.modules, {"paramiko": fake_paramiko}):
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "sftp-report.json").write_text(
            json.dumps(
                {
                    "id": "sftp-report",
                    "name": "SFTP Report",
                    "router_keywords": ["sftp report"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "sftp_write",
                            "name": "Write",
                            "params": {
                                "connection_ref": "nas-share",
                                "remote_path": "report.txt",
                                "content": "Report: {query}",
                            },
                            "on_error": "stop",
                        },
                        {
                            "id": "s2",
                            "type": "sftp_read",
                            "name": "Read",
                            "params": {
                                "connection_ref": "nas-share",
                                "remote_path": "report.txt",
                            },
                            "on_error": "stop",
                        },
                        {
                            "id": "s3",
                            "type": "chat_send",
                            "name": "Chat",
                            "params": {"chat_message": "{prev_output}"},
                            "on_error": "stop",
                        },
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    sftp-report:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(pipeline.process("please sftp report", user_id="u1", source="test"))
        assert "custom_skill:sftp-report" in result.intents
        assert result.text == "Report: please sftp report"
        assert remote_files["/data/report.txt"] == b"Report: please sftp report"


def test_pipeline_custom_skill_runtime_sftp_uses_key_path_auth(monkeypatch, tmp_path) -> None:
    remote_files: dict[str, bytes] = {"/data/report.txt": b"via-key"}
    connect_calls: list[dict[str, object]] = []

    class FakeSFTPHandle:
        def __init__(self, path: str, mode: str) -> None:
            self.path = path
            self.mode = mode

        def read(self) -> bytes:
            return remote_files[self.path]

        def __enter__(self) -> "FakeSFTPHandle":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class FakeSFTPClient:
        def open(self, path: str, mode: str) -> FakeSFTPHandle:
            return FakeSFTPHandle(path, mode)

        def close(self) -> None:
            return None

    class FakeSSHClient:
        def set_missing_host_key_policy(self, _policy: object) -> None:
            return None

        def connect(self, **kwargs: object) -> None:
            connect_calls.append(kwargs)

        def open_sftp(self) -> FakeSFTPClient:
            return FakeSFTPClient()

        def close(self) -> None:
            return None

    fake_paramiko = SimpleNamespace(
        SSHClient=FakeSSHClient,
        AutoAddPolicy=lambda: object(),
    )

    key_path = tmp_path / "data" / "ssh_keys" / "nas-share_ed25519"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private-key", encoding="utf-8")
    monkeypatch.setattr("aria.core.skill_runtime.BASE_DIR", tmp_path)

    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "sftp": {
                    "nas-share": {
                        "host": "10.0.1.20",
                        "port": 22,
                        "user": "backup",
                        "key_path": "data/ssh_keys/nas-share_ed25519",
                        "root_path": "/data",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td, patch.dict(sys.modules, {"paramiko": fake_paramiko}):
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "sftp-report.json").write_text(
            json.dumps(
                {
                    "id": "sftp-report",
                    "name": "SFTP Report",
                    "router_keywords": ["sftp key report"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "sftp_read",
                            "name": "Read",
                            "params": {
                                "connection_ref": "nas-share",
                                "remote_path": "report.txt",
                            },
                            "on_error": "stop",
                        },
                        {
                            "id": "s2",
                            "type": "chat_send",
                            "name": "Chat",
                            "params": {"chat_message": "{prev_output}"},
                            "on_error": "stop",
                        },
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    sftp-report:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(pipeline.process("please sftp key report", user_id="u1", source="test"))
        assert "custom_skill:sftp-report" in result.intents
        assert result.text == "via-key"
        assert connect_calls
        assert connect_calls[0]["key_filename"] == str(key_path)
        assert "password" not in connect_calls[0]


def test_pipeline_skill_status_is_deterministic_without_llm_call() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True},
            "auto_memory": {"enabled": True},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "server-update.json").write_text(
            json.dumps(
                {
                    "id": "server-update",
                    "name": "Server Update",
                    "router_keywords": ["update server"],
                    "description": "Fuehrt Updates auf Servern aus.",
                    "connections": ["ssh", "discord"],
                    "steps": [{"id": "s1", "type": "ssh_run", "params": {"connection_ref": "srv1", "command": "uptime"}}],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    server-update:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(
            pipeline.process("Welche Skills sind aktiv?", user_id="u1", source="test", auto_memory_enabled=True)
        )
        assert result.intents == ["skill_status"]
        assert result.usage["total_tokens"] == 0
        assert "Skills (Runtime-Status)" in result.text
        assert "Aktiv:" in result.text
        assert "Deaktiviert:" in result.text
        assert "[Custom] Server Update" in result.text
        assert llm.calls == 0


def test_pipeline_skill_status_current_skills_phrase_is_deterministic() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True},
            "auto_memory": {"enabled": True},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "server-update.json").write_text(
            json.dumps(
                {
                    "id": "server-update",
                    "name": "Server Update",
                    "router_keywords": ["update server"],
                    "description": "Fuehrt Updates auf Servern aus.",
                    "connections": ["ssh", "discord"],
                    "steps": [{"id": "s1", "type": "ssh_run", "params": {"connection_ref": "srv1", "command": "uptime"}}],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    server-update:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(
            pipeline.process("Was sind deine aktuellen Skills?", user_id="u1", source="test", auto_memory_enabled=True)
        )
        assert result.intents == ["skill_status"]
        assert result.usage["total_tokens"] == 0
        assert "Skills (Runtime-Status)" in result.text
        assert "[Custom] Server Update" in result.text
        assert llm.calls == 0


def test_pipeline_custom_skill_chat_send_direct_response() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "echo-chat.json").write_text(
            json.dumps(
                {
                    "id": "echo-chat",
                    "name": "Echo Chat",
                    "router_keywords": ["echochat"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "chat_send",
                            "name": "Direktantwort",
                            "params": {"chat_message": "Direkt: {query}"},
                            "on_error": "stop",
                        }
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    echo-chat:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(pipeline.process("echochat test 123", user_id="u1", source="test"))
        assert "custom_skill:echo-chat" in result.intents
        assert result.text == "Direkt: echochat test 123"
        assert result.usage["total_tokens"] == 0
        assert llm.calls == 0


def test_pipeline_custom_skill_does_not_persist_auto_memory_session_context() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True},
            "auto_memory": {"enabled": True},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)
    fake_memory = FakeMemorySkill()
    pipeline.memory_skill = fake_memory

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "sys-update.json").write_text(
            json.dumps(
                {
                    "id": "sys-update",
                    "name": "System Update",
                    "router_keywords": ["systemupdate"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "chat_send",
                            "params": {"chat_message": "Update laeuft fuer: {query}"},
                        }
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    sys-update:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(
            pipeline.process(
                "systemupdate server-main",
                user_id="u1",
                source="test",
                auto_memory_enabled=True,
                session_collection="aria_sessions_u1_260326",
            )
        )

        assert "custom_skill:sys-update" in result.intents
        assert result.text == "Update laeuft fuer: systemupdate server-main"
        persisted_actions = [
            call
            for call in fake_memory.calls
            if str(call["params"].get("action", "")).strip() == "store"
        ]
        assert persisted_actions == []


def test_pipeline_auto_memory_does_not_persist_transient_question_to_session() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True},
            "auto_memory": {"enabled": True},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=FakeLLMClient())
    fake_memory = FakeMemorySkill()
    pipeline.memory_skill = fake_memory

    result = asyncio.run(
        pipeline.process(
            "wie lange braucht saturn bis er einmal um die sonne gekreist ist ?",
            user_id="u1",
            source="test",
            auto_memory_enabled=True,
            memory_collection="aria_facts_u1",
            session_collection="aria_sessions_u1_260403",
        )
    )

    assert result.intents == ["chat"]
    persisted_calls = [
        call
        for call in fake_memory.calls
        if str(call["params"].get("action", "")).strip() == "store"
    ]
    assert persisted_calls == []


def test_pipeline_auto_memory_persists_declarative_user_context_to_session_and_facts() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True},
            "auto_memory": {"enabled": True},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=FakeLLMClient())
    fake_memory = FakeMemorySkill()
    pipeline.memory_skill = fake_memory

    result = asyncio.run(
        pipeline.process(
            "Mein NAS heisst atlas und laeuft auf 10.0.10.100.",
            user_id="u1",
            source="test",
            auto_memory_enabled=True,
            memory_collection="aria_facts_u1",
            session_collection="aria_sessions_u1_260403",
        )
    )

    assert result.intents == ["chat"]
    persisted_calls = [
        call
        for call in fake_memory.calls
        if str(call["params"].get("action", "")).strip() == "store"
    ]
    stored_texts = [str(call["params"].get("text", "")) for call in persisted_calls]
    stored_collections = [str(call["params"].get("collection", "")) for call in persisted_calls]
    assert any("10.0.10.100" in text for text in stored_texts)
    assert "aria_facts_u1" in stored_collections
    assert "aria_sessions_u1_260403" in stored_collections


def test_pipeline_uses_llm_custom_skill_fallback_after_no_capability_match() -> None:
    class SkillPickerLLMClient(FakeLLMClient):
        async def chat(self, messages):
            self.calls += 1
            self.last_messages = messages
            assert messages[0]["role"] == "system"
            return FakeLLMResponse(
                json.dumps(
                    {
                        "id": "server-update",
                        "confidence": "high",
                        "reason": "natuerlicher update-wunsch",
                    }
                )
            )

    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = SkillPickerLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        skills_dir = root / "data" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "server-update.json").write_text(
            json.dumps(
                {
                    "id": "server-update",
                    "name": "Server Update",
                    "description": "Fuehrt Server Updates aus und meldet das Ergebnis direkt im Chat.",
                    "router_keywords": ["server update starten"],
                    "steps": [
                        {
                            "id": "s1",
                            "type": "chat_send",
                            "name": "Direktantwort",
                            "params": {"chat_message": "Update wird vorbereitet."},
                            "on_error": "stop",
                        }
                    ],
                    "enabled_default": True,
                }
            ),
            encoding="utf-8",
        )
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "skills:\n  custom:\n    server-update:\n      enabled: true\n",
            encoding="utf-8",
        )

        pipeline._custom_skills_dir = skills_dir
        pipeline._config_path = config_dir / "config.yaml"
        pipeline._custom_skill_cache = {"sign": None, "rows": []}

        result = asyncio.run(
            pipeline.process(
                "kannst du die beiden systeme patchen",
                user_id="u1",
                source="test",
            )
        )
        assert "custom_skill:server-update" in result.intents
        assert result.text == "Update wird vorbereitet."
        assert result.usage["total_tokens"] == 0
        assert llm.calls == 1


def test_extract_held_packages_from_apt_output() -> None:
    sample = """
Reading package lists... Done
The following packages have been kept back:
  ubuntu-drivers-common webmin
0 upgraded, 0 newly installed, 0 to remove and 2 not upgraded.
"""
    rows = Pipeline._extract_held_packages(sample)
    assert "ubuntu-drivers-common" in rows
    assert "webmin" in rows


def test_format_held_packages_summary_contains_safe_fix() -> None:
    summary = Pipeline._format_held_packages_summary(
        {"srv-a": ["ubuntu-drivers-common", "webmin"]},
        {"srv-a": "root@10.0.1.10"},
    )
    assert "Zurückgehaltene Pakete" in summary
    assert "srv-a (root@10.0.1.10)" in summary
    assert "sudo apt install --only-upgrade ubuntu-drivers-common webmin" in summary


def test_format_ssh_step_run_summary_contains_duration_and_warnings() -> None:
    from aria.core.skill_runtime import _format_ssh_step_run_summary

    text = _format_ssh_step_run_summary(
        [
            {
                "connection_ref": "server-main",
                "target": "demo_user@10.0.1.1",
                "exit_code": 0,
                "duration_seconds": 12.4,
                "held_packages": ["webmin"],
                "warning_hints": ["apt-key/GPG"],
            }
        ]
    )
    assert "Technischer Lauf:" in text
    assert "server-main" in text
    assert "12.4s" in text
    assert "1 gehalten" in text
    assert "apt-key/GPG" in text


def test_build_safe_fix_plan_from_skill_results() -> None:
    rows = [
        SkillResult(
            skill_name="custom_skill_x",
            content="ok",
            success=True,
            metadata={
                "custom_held_packages_by_connection": {
                    "srv-a": ["ubuntu-drivers-common", "webmin"],
                    "srv-b": ["ubuntu-drivers-common"],
                }
            },
        )
    ]
    plan = Pipeline._build_safe_fix_plan(rows)
    assert {"connection_ref": "srv-a", "packages": ["ubuntu-drivers-common", "webmin"]} in plan
    assert {"connection_ref": "srv-b", "packages": ["ubuntu-drivers-common"]} in plan


def test_pipeline_capability_router_sftp_write_direct_response() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "sftp": {
                    "server-main": {
                        "host": "10.0.3.160",
                        "user": "demo_user",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    called: dict[str, str] = {}

    def fake_write(connection_ref: str, remote_path: str, content: str) -> str:
        called["connection_ref"] = connection_ref
        called["remote_path"] = remote_path
        called["content"] = content
        return f"WROTE {remote_path} via {connection_ref}: {content}"

    pipeline._skill_runtime.execute_sftp_write = fake_write  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'schreib mir auf dem server server-main die datei /tmp/info.txt mit inhalt "Hallo ARIA"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_write"]
    assert result.text == "WROTE /tmp/info.txt via server-main: Hallo ARIA"
    assert result.detail_lines == [
        "Ausgeführt via SFTP-Profil `server-main`",
        "Pfad: /tmp/info.txt",
    ]
    assert called == {
        "connection_ref": "server-main",
        "remote_path": "/tmp/info.txt",
        "content": "Hallo ARIA",
    }
    assert llm.calls == 0


def test_pipeline_capability_router_uses_single_sftp_profile_as_default() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "sftp": {
                    "server-main": {
                        "host": "10.0.3.160",
                        "user": "demo_user",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_list(connection_ref: str, remote_path: str) -> str:
        calls.append((connection_ref, remote_path))
        return f"LIST {remote_path} via {connection_ref}"

    pipeline._skill_runtime.execute_sftp_list = fake_list  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "liste mir auf dem server die dateien in /tmp",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_list"]
    assert result.text == "LIST /tmp via server-main"
    assert result.detail_lines == [
        "Ausgeführt via SFTP-Profil `server-main`",
        "Pfad: /tmp",
    ]
    assert calls == [("server-main", "/tmp")]
    assert llm.calls == 0


def test_pipeline_capability_router_uses_memory_hint_for_sftp_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "sftp": {
                    "server-main": {"host": "10.0.3.160", "user": "demo_user"},
                    "server-alert": {"host": "10.0.3.161", "user": "demo_user"},
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)
    pipeline.memory_skill = FakeMemoryAssistSkill(
        [{"text": "Für Server-Dateien nutze ich meist server-alert via SFTP."}]
    )

    calls: list[tuple[str, str]] = []

    def fake_read(connection_ref: str, remote_path: str) -> str:
        calls.append((connection_ref, remote_path))
        return f"READ {remote_path} via {connection_ref}"

    pipeline._skill_runtime.execute_sftp_read = fake_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "lies mir die datei /etc/hosts auf dem server",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_read"]
    assert result.text == "READ /etc/hosts via server-alert"
    assert result.detail_lines == [
        "Ausgeführt via SFTP-Profil `server-alert`",
        "Pfad: /etc/hosts",
    ]
    assert calls == [("server-alert", "/etc/hosts")]
    assert llm.calls == 0


def test_pipeline_capability_router_uses_recent_context_for_same_server_phrase() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        context_store = CapabilityContextStore(root / "capability_context.json")
        settings = Settings.model_validate(
            {
                "llm": {"model": "fake"},
                "memory": {"enabled": False},
                "connections": {
                    "sftp": {
                        "server-main": {"host": "10.0.3.160", "user": "demo_user"},
                        "server-alert": {"host": "10.0.3.161", "user": "demo_user"},
                    }
                },
                "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
            }
        )
        llm = FakeLLMClient()
        pipeline = Pipeline(
            settings=settings,
            prompt_loader=FakePromptLoader(),
            llm_client=llm,
            capability_context_store=context_store,
        )

        write_calls: list[tuple[str, str, str]] = []
        read_calls: list[tuple[str, str]] = []

        def fake_write(connection_ref: str, remote_path: str, content: str) -> str:
            write_calls.append((connection_ref, remote_path, content))
            return f"WROTE {remote_path} via {connection_ref}: {content}"

        def fake_read(connection_ref: str, remote_path: str) -> str:
            read_calls.append((connection_ref, remote_path))
            return f"READ {remote_path} via {connection_ref}"

        pipeline._skill_runtime.execute_sftp_write = fake_write  # type: ignore[method-assign]
        pipeline._skill_runtime.execute_sftp_read = fake_read  # type: ignore[method-assign]

        first = asyncio.run(
            pipeline.process(
                'Schreib mir auf server-main die Datei /tmp/info.txt mit Inhalt "Hallo"',
                user_id="u1",
                source="test",
            )
        )
        second = asyncio.run(
            pipeline.process(
                "Lies mir wie letztes Mal die Datei /etc/hosts",
                user_id="u1",
                source="test",
            )
        )

        assert first.intents == ["capability:file_write"]
        assert second.intents == ["capability:file_read"]
        assert write_calls == [("server-main", "/tmp/info.txt", "Hallo")]
        assert read_calls == [("server-main", "/etc/hosts")]
        assert second.detail_lines == [
            "Ausgeführt via SFTP-Profil `server-main`",
            "Pfad: /etc/hosts",
        ]
        assert llm.calls == 0


def test_pipeline_capability_router_uses_recent_context_for_same_path_phrase() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        context_store = CapabilityContextStore(root / "capability_context.json")
        settings = Settings.model_validate(
            {
                "llm": {"model": "fake"},
                "memory": {"enabled": False},
                "connections": {
                    "sftp": {
                        "server-main": {"host": "10.0.3.160", "user": "demo_user"},
                    }
                },
                "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
            }
        )
        llm = FakeLLMClient()
        pipeline = Pipeline(
            settings=settings,
            prompt_loader=FakePromptLoader(),
            llm_client=llm,
            capability_context_store=context_store,
        )

        list_calls: list[tuple[str, str]] = []

        def fake_list(connection_ref: str, remote_path: str) -> str:
            list_calls.append((connection_ref, remote_path))
            return f"LIST {remote_path} via {connection_ref}"

        pipeline._skill_runtime.execute_sftp_list = fake_list  # type: ignore[method-assign]

        context_store.remember_action(
            "u1",
            capability="file_list",
            connection_kind="sftp",
            connection_ref="server-main",
            path="/tmp/info.txt",
        )

        result = asyncio.run(
            pipeline.process(
                "Zeige mir die Dateien im gleichen Ordner",
                user_id="u1",
                source="test",
            )
        )

        assert result.intents == ["capability:file_list"]
        assert result.text == "LIST /tmp via server-main"
        assert result.detail_lines == [
            "Ausgeführt via SFTP-Profil `server-main`",
            "Pfad: /tmp",
        ]
        assert list_calls == [("server-main", "/tmp")]
        assert llm.calls == 0


def test_pipeline_capability_router_uses_explicit_smb_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "smb": {
                    "share-office": {
                        "host": "10.0.3.200",
                        "share": "office",
                        "user": "demo_user",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_list(connection_ref: str, remote_path: str) -> str:
        calls.append((connection_ref, remote_path))
        return f"SMB LIST {remote_path} via {connection_ref}"

    pipeline._skill_runtime.execute_smb_list = fake_list  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Zeige mir die Dateien auf dem NAS share-office",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_list"]
    assert result.text == "SMB LIST . via share-office"
    assert result.detail_lines == [
        "Ausgeführt via SMB-Profil `share-office`",
        "Pfad: .",
    ]
    assert calls == [("share-office", ".")]
    assert llm.calls == 0


def test_pipeline_capability_router_uses_single_smb_profile_as_default() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "smb": {
                    "share-office": {
                        "host": "10.0.3.200",
                        "share": "office",
                        "user": "demo_user",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_read(connection_ref: str, remote_path: str) -> str:
        calls.append((connection_ref, remote_path))
        return f"SMB READ {remote_path} via {connection_ref}"

    pipeline._skill_runtime.execute_smb_read = fake_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Öffne die Datei /docs/readme.txt im NAS",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_read"]
    assert result.text == "SMB READ /docs/readme.txt via share-office"
    assert result.detail_lines == [
        "Ausgeführt via SMB-Profil `share-office`",
        "Pfad: /docs/readme.txt",
    ]
    assert calls == [("share-office", "/docs/readme.txt")]
    assert llm.calls == 0


def test_pipeline_capability_router_uses_smb_host_alias_for_docker_directory_prompt() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "smb": {
                    "nas-docker": {
                        "host": "nas-demo",
                        "share": "docker",
                        "user": "demo_user",
                        "root_path": "/docker",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_list(connection_ref: str, remote_path: str) -> str:
        calls.append((connection_ref, remote_path))
        return f"SMB LIST {remote_path} via {connection_ref}"

    pipeline._skill_runtime.execute_smb_list = fake_list  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Zeige mir die Daten aus dem docker Verzeichnis von nas-demo",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_list"]
    assert result.text == "SMB LIST . via nas-docker"
    assert result.detail_lines == [
        "Ausgeführt via SMB-Profil `nas-docker`",
        "Pfad: .",
    ]
    assert calls == [("nas-docker", ".")]
    assert llm.calls == 0


def test_pipeline_capability_router_uses_real_numbered_smb_ref_for_docker_directory_prompt() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "smb": {
                    "nas-docker-01": {
                        "host": "10.0.5.230",
                        "share": "docker",
                        "user": "demo",
                        "root_path": "",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_list(connection_ref: str, remote_path: str) -> str:
        calls.append((connection_ref, remote_path))
        return f"SMB LIST {remote_path} via {connection_ref}"

    pipeline._skill_runtime.execute_smb_list = fake_list  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Zeige mir die Daten aus dem docker Verzeichnis von nas-demo",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_list"]
    assert result.text == "SMB LIST . via nas-docker-01"
    assert result.detail_lines == [
        "Ausgeführt via SMB-Profil `nas-docker-01`",
        "Pfad: .",
    ]
    assert calls == [("nas-docker-01", ".")]
    assert llm.calls == 0


def test_pipeline_capability_router_uses_smb_alias_for_what_files_are_in_my_share_phrase() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "smb": {
                    "nas-docker": {
                        "host": "synrs816-01",
                        "share": "Ronny",
                        "user": "demo_user",
                        "aliases": ["mein Share", "Ronny Share"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_list(connection_ref: str, remote_path: str) -> str:
        calls.append((connection_ref, remote_path))
        return f"SMB LIST {remote_path} via {connection_ref}"

    pipeline._skill_runtime.execute_smb_list = fake_list  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Was für Dateien liegen in meinem Share",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_list"]
    assert result.text == "SMB LIST . via nas-docker"
    assert result.detail_lines == [
        "Ausgeführt via SMB-Profil `nas-docker`",
        "Pfad: .",
    ]
    assert calls == [("nas-docker", ".")]
    assert llm.calls == 0


def test_pipeline_capability_action_returns_friendly_error_instead_of_raising() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "smb": {
                    "nas-docker-01": {
                        "host": "10.0.5.230",
                        "share": "docker",
                        "user": "demo",
                        "root_path": "",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    def fake_list(_connection_ref: str, _remote_path: str) -> str:
        raise RuntimeError("Zielverzeichnis aktuell nicht erreichbar")

    pipeline._skill_runtime.execute_smb_list = fake_list  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Zeige mir die Daten aus dem docker Verzeichnis von nas-demo",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:file_list"]
    assert "konnte nicht ausgeführt werden" in result.text
    assert "Zielverzeichnis aktuell nicht erreichbar" in result.text
    assert result.skill_errors == ["capability_file_list_error:RuntimeError"]
    assert llm.calls == 0


def test_pipeline_capability_router_reads_rss_feed_via_explicit_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "rss": {
                    "security-feed": {
                        "feed_url": "https://example.org/feed.xml",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[str] = []

    def fake_rss_read(connection_ref: str) -> str:
        calls.append(connection_ref)
        return "Neueste Einträge aus `security-feed`:\n1. ARIA News"

    pipeline._skill_runtime.execute_rss_read = fake_rss_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Zeig mir den RSS Feed security-feed",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:feed_read"]
    assert result.text == "Neueste Einträge aus `security-feed`:\n1. ARIA News"
    assert result.detail_lines == [
        "Ausgeführt via RSS-Profil `security-feed`",
    ]
    assert calls == ["security-feed"]
    assert llm.calls == 0


def test_pipeline_capability_router_reads_rss_feed_via_natural_phrase() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "rss": {
                    "heise-online-news": {
                        "feed_url": "https://example.org/heise.xml",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[str] = []

    def fake_rss_read(connection_ref: str) -> str:
        calls.append(connection_ref)
        return "Neueste Einträge aus `heise-online-news`:\n1. ARIA News"

    pipeline._skill_runtime.execute_rss_read = fake_rss_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "was gibts neues auf heise online news",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:feed_read"]
    assert result.text == "Neueste Einträge aus `heise-online-news`:\n1. ARIA News"
    assert result.detail_lines == [
        "Ausgeführt via RSS-Profil `heise-online-news`",
    ]
    assert calls == ["heise-online-news"]
    assert llm.calls == 0


def test_pipeline_capability_router_reads_rss_feed_via_shorter_natural_phrase() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "rss": {
                    "heise-online-news": {
                        "feed_url": "https://example.org/heise.xml",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[str] = []

    def fake_rss_read(connection_ref: str) -> str:
        calls.append(connection_ref)
        return "Neueste Einträge aus `heise-online-news`:\n1. ARIA News"

    pipeline._skill_runtime.execute_rss_read = fake_rss_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "was gibts neues auf heise online",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:feed_read"]
    assert result.text == "Neueste Einträge aus `heise-online-news`:\n1. ARIA News"
    assert result.detail_lines == [
        "Ausgeführt via RSS-Profil `heise-online-news`",
    ]
    assert calls == ["heise-online-news"]
    assert llm.calls == 0


def test_pipeline_capability_router_resolves_rss_feed_via_llm_semantics() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "rss": {
                    "tech-news-1": {
                        "feed_url": "https://www.heise.de/rss/heise-atom.xml",
                    },
                    "security-feed": {
                        "feed_url": "https://example.org/security.xml",
                    },
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FeedResolverLLMClient("tech-news-1")
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[str] = []

    def fake_rss_read(connection_ref: str) -> str:
        calls.append(connection_ref)
        return "Neueste Einträge aus `tech-news-1`:\n1. ARIA News"

    pipeline._skill_runtime.execute_rss_read = fake_rss_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "was gibts neues bei heise",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:feed_read"]
    assert result.text == "Neueste Einträge aus `tech-news-1`:\n1. ARIA News"
    assert result.detail_lines == [
        "Ausgeführt via RSS-Profil `tech-news-1`",
    ]
    assert calls == ["tech-news-1"]
    assert llm.calls == 0


def test_pipeline_capability_router_reads_rss_feed_via_short_news_typo_phrase() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "rss": {
                    "heise-feed": {
                        "feed_url": "https://www.heise.de/rss/heise-atom.xml",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[str] = []

    def fake_rss_read(connection_ref: str) -> str:
        calls.append(connection_ref)
        return "Neueste Einträge aus `heise-feed`:\n1. ARIA News"

    pipeline._skill_runtime.execute_rss_read = fake_rss_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "was für news gibs auf heise",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:feed_read"]
    assert result.text == "Neueste Einträge aus `heise-feed`:\n1. ARIA News"
    assert result.detail_lines == [
        "Ausgeführt via RSS-Profil `heise-feed`",
    ]
    assert calls == ["heise-feed"]
    assert llm.calls == 0


def test_pipeline_capability_router_sends_webhook_via_explicit_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "webhook": {
                    "incident-hook": {
                        "url": "https://example.org/hook",
                        "method": "POST",
                        "content_type": "application/json",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_webhook_send(connection_ref: str, content: str) -> str:
        calls.append((connection_ref, content))
        return f"Webhook gesendet via `{connection_ref}`"

    pipeline._skill_runtime.execute_webhook_send = fake_webhook_send  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Sende per Webhook incident-hook "Server down auf mgmt"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:webhook_send"]
    assert result.text == "Webhook gesendet via `incident-hook`"
    assert result.detail_lines == [
        "Ausgeführt via Webhook-Profil `incident-hook`",
    ]
    assert calls == [("incident-hook", "Server down auf mgmt")]
    assert llm.calls == 0


def test_pipeline_capability_router_sends_webhook_via_explicit_ref_name() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "webhook": {
                    "n8n-test-webhook": {
                        "url": "https://example.org/hook",
                        "method": "POST",
                        "content_type": "application/json",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_webhook_send(connection_ref: str, content: str) -> str:
        calls.append((connection_ref, content))
        return f"Webhook {connection_ref}: {content}"

    pipeline._skill_runtime.execute_webhook_send = fake_webhook_send  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Schicke per n8n-test-webhook einen test mit inhalt "ARIA was here"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:webhook_send"]
    assert result.text == "Webhook n8n-test-webhook: ARIA was here"
    assert result.detail_lines == [
        "Ausgeführt via Webhook-Profil `n8n-test-webhook`",
    ]
    assert calls == [("n8n-test-webhook", "ARIA was here")]
    assert llm.calls == 0


def test_pipeline_capability_router_calls_http_api_with_similar_webhook_ref_present() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "webhook": {
                    "n8n-test-webhook": {
                        "url": "https://example.org/hook",
                        "method": "POST",
                        "content_type": "application/json",
                    }
                },
                "http_api": {
                    "n8n-test-web-api": {
                        "base_url": "https://example.org/api",
                        "health_path": "/health",
                        "method": "GET",
                    }
                },
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str, str]] = []

    def fake_api_request(connection_ref: str, path: str, content: str) -> str:
        calls.append((connection_ref, path, content))
        return "API OK"

    pipeline._skill_runtime.execute_http_api_request = fake_api_request  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "rufe die API n8n-test-web-api /health auf",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:api_request"]
    assert result.text == "API OK"
    assert result.detail_lines == [
        "Ausgeführt via HTTP API-Profil `n8n-test-web-api`",
        "Pfad: /health",
    ]
    assert calls == [("n8n-test-web-api", "/health", "")]
    assert llm.calls == 0


def test_pipeline_capability_router_sends_discord_via_explicit_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "discord": {
                    "alerts-discord": {
                        "webhook_url": "https://discord.example/webhook",
                        "allow_skill_messages": True,
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_discord_send(connection_ref: str, content: str) -> str:
        calls.append((connection_ref, content))
        return f"Discord gesendet via `{connection_ref}`"

    pipeline._skill_runtime.execute_discord_send = fake_discord_send  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Schicke eine Test Nachricht nach Discord alerts-discord "ARIA lebt"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:discord_send"]
    assert result.text == "Discord gesendet via `alerts-discord`"
    assert result.detail_lines == [
        "Ausgeführt via Discord-Profil `alerts-discord`",
    ]
    assert calls == [("alerts-discord", "ARIA lebt")]
    assert llm.calls == 0


def test_pipeline_capability_router_sends_discord_via_metadata_title_alias() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "discord": {
                    "alerts-discord": {
                        "webhook_url": "https://discord.example/webhook",
                        "allow_skill_messages": True,
                        "title": "Alerts",
                        "tags": ["discord"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_discord_send(connection_ref: str, content: str) -> str:
        calls.append((connection_ref, content))
        return f"Discord gesendet via `{connection_ref}`"

    pipeline._skill_runtime.execute_discord_send = fake_discord_send  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Schick das an alerts "ARIA lebt"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:discord_send"]
    assert result.text == "Discord gesendet via `alerts-discord`"
    assert result.detail_lines == [
        "Ausgeführt via Discord-Profil `alerts-discord`",
    ]
    assert calls == [("alerts-discord", "ARIA lebt")]
    assert llm.calls == 0


def test_pipeline_capability_router_calls_http_api_via_explicit_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "http_api": {
                    "inventory-api": {
                        "base_url": "https://api.example.org",
                        "health_path": "/health",
                        "method": "GET",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str, str]] = []

    def fake_api_request(connection_ref: str, path: str, content: str) -> str:
        calls.append((connection_ref, path, content))
        return '{\n  "status": "ok"\n}'

    pipeline._skill_runtime.execute_http_api_request = fake_api_request  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Rufe die API inventory-api /health auf",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:api_request"]
    assert result.text == '{\n  "status": "ok"\n}'
    assert result.detail_lines == [
        "Ausgeführt via HTTP API-Profil `inventory-api`",
        "Pfad: /health",
    ]
    assert calls == [("inventory-api", "/health", "")]
    assert llm.calls == 0


def test_pipeline_capability_router_calls_http_api_via_metadata_title_alias() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "http_api": {
                    "inventory-api": {
                        "base_url": "https://api.example.org",
                        "health_path": "/health",
                        "method": "GET",
                        "title": "Inventory",
                        "tags": ["endpoint"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str, str]] = []

    def fake_api_request(connection_ref: str, path: str, content: str) -> str:
        calls.append((connection_ref, path, content))
        return "API OK"

    pipeline._skill_runtime.execute_http_api_request = fake_api_request  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Rufe den inventory endpoint /health auf",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:api_request"]
    assert result.text == "API OK"
    assert result.detail_lines == [
        "Ausgeführt via HTTP API-Profil `inventory-api`",
        "Pfad: /health",
    ]
    assert calls == [("inventory-api", "/health", "")]
    assert llm.calls == 0


def test_pipeline_capability_router_sends_email_via_explicit_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "email": {
                    "alerts-mail": {
                        "smtp_host": "smtp.example.org",
                        "user": "alerts@example.org",
                        "from_email": "alerts@example.org",
                        "to_email": "ops@example.org",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_email_send(connection_ref: str, content: str) -> str:
        calls.append((connection_ref, content))
        return "Mail gesendet via `alerts-mail` an ops@example.org"

    pipeline._skill_runtime.execute_email_send = fake_email_send  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Sende per Mail alerts-mail "Backup erfolgreich abgeschlossen"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:email_send"]
    assert result.text == "Mail gesendet via `alerts-mail` an ops@example.org"
    assert result.detail_lines == [
        "Ausgeführt via SMTP-Profil `alerts-mail`",
    ]
    assert calls == [("alerts-mail", "Backup erfolgreich abgeschlossen")]
    assert llm.calls == 0


def test_pipeline_capability_router_sends_email_via_metadata_title_alias() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "email": {
                    "alerts-mail": {
                        "smtp_host": "smtp.example.org",
                        "user": "alerts@example.org",
                        "from_email": "alerts@example.org",
                        "to_email": "ops@example.org",
                        "title": "Alerts",
                        "tags": ["notifications"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_email_send(connection_ref: str, content: str) -> str:
        calls.append((connection_ref, content))
        return "Mail gesendet via `alerts-mail`"

    pipeline._skill_runtime.execute_email_send = fake_email_send  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Schick das an alerts "Backup erfolgreich abgeschlossen"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:email_send"]
    assert result.text == "Mail gesendet via `alerts-mail`"
    assert result.detail_lines == [
        "Ausgeführt via SMTP-Profil `alerts-mail`",
    ]
    assert calls == [("alerts-mail", "Backup erfolgreich abgeschlossen")]
    assert llm.calls == 0


def test_pipeline_capability_router_reads_mailbox_via_explicit_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "imap": {
                    "ops-inbox": {
                        "host": "imap.example.org",
                        "user": "ops@example.org",
                        "mailbox": "INBOX",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[str] = []

    def fake_imap_read(connection_ref: str) -> str:
        calls.append(connection_ref)
        return "Neueste Mails aus INBOX:\n1. Backup ok"

    pipeline._skill_runtime.execute_imap_read = fake_imap_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Zeige mir die neuesten Mails im Postfach ops-inbox",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:mail_read"]
    assert result.text == "Neueste Mails aus INBOX:\n1. Backup ok"
    assert result.detail_lines == [
        "Ausgeführt via IMAP-Profil `ops-inbox`",
    ]
    assert calls == ["ops-inbox"]
    assert llm.calls == 0


def test_pipeline_capability_router_reads_mailbox_via_metadata_title_alias() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "imap": {
                    "ops-inbox": {
                        "host": "imap.example.org",
                        "user": "ops@example.org",
                        "mailbox": "INBOX",
                        "title": "Ops",
                        "tags": ["inbox"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[str] = []

    def fake_imap_read(connection_ref: str) -> str:
        calls.append(connection_ref)
        return "Neueste Mails aus INBOX:\n1. Backup ok"

    pipeline._skill_runtime.execute_imap_read = fake_imap_read  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            "Zeige mir die neuesten Mails in der ops inbox",
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:mail_read"]
    assert result.text == "Neueste Mails aus INBOX:\n1. Backup ok"
    assert result.detail_lines == [
        "Ausgeführt via IMAP-Profil `ops-inbox`",
    ]
    assert calls == ["ops-inbox"]
    assert llm.calls == 0


def test_pipeline_capability_router_searches_mailbox_via_explicit_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "imap": {
                    "ops-inbox": {
                        "host": "imap.example.org",
                        "user": "ops@example.org",
                        "mailbox": "INBOX",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str]] = []

    def fake_imap_search(connection_ref: str, query: str) -> str:
        calls.append((connection_ref, query))
        return "Treffer in INBOX für „Backup“:\n1. Backup Report"

    pipeline._skill_runtime.execute_imap_search = fake_imap_search  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Suche Mails in ops-inbox nach "Backup"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:mail_search"]
    assert result.text == "Treffer in INBOX für „Backup“:\n1. Backup Report"
    assert result.detail_lines == [
        "Ausgeführt via IMAP-Profil `ops-inbox`",
        "Suche: Backup",
    ]
    assert calls == [("ops-inbox", "Backup")]
    assert llm.calls == 0


def test_pipeline_capability_router_publishes_mqtt_via_explicit_profile() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "mqtt": {
                    "event-bus": {
                        "host": "mqtt.example.org",
                        "user": "aria",
                        "topic": "aria/events",
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str, str]] = []

    def fake_mqtt_publish(connection_ref: str, topic: str, content: str) -> str:
        calls.append((connection_ref, topic, content))
        return "MQTT gesendet via `event-bus` auf Topic `aria/events`"

    pipeline._skill_runtime.execute_mqtt_publish = fake_mqtt_publish  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Sende per MQTT event-bus auf topic aria/events "Backup fertig"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:mqtt_publish"]
    assert result.text == "MQTT gesendet via `event-bus` auf Topic `aria/events`"
    assert result.detail_lines == [
        "Ausgeführt via MQTT-Profil `event-bus`",
        "Topic: aria/events",
    ]
    assert calls == [("event-bus", "aria/events", "Backup fertig")]
    assert llm.calls == 0


def test_pipeline_capability_router_publishes_mqtt_via_metadata_title_alias() -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": False},
            "connections": {
                "mqtt": {
                    "event-bus": {
                        "host": "mqtt.example.org",
                        "user": "aria",
                        "topic": "aria/events",
                        "title": "Event",
                        "tags": ["bus"],
                    }
                }
            },
            "token_tracking": {"enabled": False, "log_file": "data/logs/test_tokens.jsonl"},
        }
    )
    llm = FakeLLMClient()
    pipeline = Pipeline(settings=settings, prompt_loader=FakePromptLoader(), llm_client=llm)

    calls: list[tuple[str, str, str]] = []

    def fake_mqtt_publish(connection_ref: str, topic: str, content: str) -> str:
        calls.append((connection_ref, topic, content))
        return "MQTT gesendet via `event-bus` auf Topic `aria/events`"

    pipeline._skill_runtime.execute_mqtt_publish = fake_mqtt_publish  # type: ignore[method-assign]

    result = asyncio.run(
        pipeline.process(
            'Schick das an den event bus "Backup fertig"',
            user_id="u1",
            source="test",
        )
    )

    assert result.intents == ["capability:mqtt_publish"]
    assert result.text == "MQTT gesendet via `event-bus` auf Topic `aria/events`"
    assert result.detail_lines == [
        "Ausgeführt via MQTT-Profil `event-bus`",
        "Topic: aria/events",
    ]
    assert calls == [("event-bus", "aria/events", "Backup fertig")]
    assert llm.calls == 0
