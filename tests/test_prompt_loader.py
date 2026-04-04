from pathlib import Path

from aria.core.prompt_loader import PromptLoader


def test_prompt_loader_extracts_persona_name(tmp_path: Path) -> None:
    persona = tmp_path / "persona.md"
    persona.write_text("# Persona\n\nName: NOVA\nSprache: Deutsch\n", encoding="utf-8")
    loader = PromptLoader(persona)
    assert loader.get_persona_name() == "NOVA"


def test_prompt_loader_falls_back_when_name_missing(tmp_path: Path) -> None:
    persona = tmp_path / "persona.md"
    persona.write_text("# Persona\n\nSprache: Deutsch\n", encoding="utf-8")
    loader = PromptLoader(persona)
    assert loader.get_persona_name(default="ARIA") == "ARIA"
