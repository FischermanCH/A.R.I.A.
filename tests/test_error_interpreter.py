from pathlib import Path
import tempfile

from aria.core.error_interpreter import ErrorInterpreter


def test_error_interpreter_matches_sudo_rule() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "error_interpreter.yaml"
        path.write_text(
            """
rules:
  - id: sudo
    patterns:
      - "sudo:"
    messages:
      de:
        title: "sudo Problem"
        cause: "Passwort oder sudoers."
        next_step: "sudo pruefen."
  - id: unknown_nonzero
    default: true
    patterns: []
    messages:
      de:
        title: "Unbekannt"
        cause: "Unklar."
        next_step: "Details ansehen."
""".strip()
            + "\n",
            encoding="utf-8",
        )
        interpreter = ErrorInterpreter(path)
        result = interpreter.interpret(
            language="de",
            error_code="custom_skill_ssh_nonzero_exit",
            stdout="",
            stderr="sudo: a password is required",
            exit_code=1,
            command="sudo apt update",
            connection_ref="srv1",
        )
        assert result is not None
        assert result.category == "sudo"
        assert result.title == "sudo Problem"


def test_error_interpreter_uses_default_rule_for_unknown_nonzero() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "error_interpreter.yaml"
        path.write_text(
            """
rules:
  - id: unknown_nonzero
    default: true
    patterns: []
    messages:
      de:
        title: "Unbekannt"
        cause: "Unklar."
        next_step: "Details ansehen."
""".strip()
            + "\n",
            encoding="utf-8",
        )
        interpreter = ErrorInterpreter(path)
        result = interpreter.interpret(
            language="de",
            error_code="custom_skill_ssh_nonzero_exit",
            stdout="",
            stderr="some opaque failure",
            exit_code=1,
            command="sudo apt update",
            connection_ref="srv1",
        )
        assert result is not None
        assert result.category == "unknown_nonzero"
        assert result.title == "Unbekannt"
