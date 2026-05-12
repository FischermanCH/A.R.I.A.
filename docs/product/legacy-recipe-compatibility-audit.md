# Legacy Recipe Compatibility Audit

Status: 2026-05-12

## Ziel

ARIA ist recipe-first. Alte Skill-Begriffe bleiben nur dort erhalten, wo sie alte Configs, Imports, URLs oder externe Erweiterungen absichern.

## Muss vorerst bleiben

- `skills:` in `config/config.yaml` und Backups: alte Installationen speichern Rezept-Toggles noch unter diesem Root.
- `/skills*` Redirect-/Wrapper-Surface: alte Bookmarks und Links sollen nicht hart brechen.
- `custom_skill:*`, `skill_status`, `custom_skill_confirmation`: alte Intents und Pending-Actions bleiben auswertbar.
- `aria.core.custom_skills`, `aria.core.skill_runtime`, `aria.core.action_planner_skill_candidates`, `aria.web.skills_routes`: reine Import-Wrapper fuer alte externe Imports.
- `samples/skills/`: Legacy-Referenz mit denselben Dateinamen wie `samples/recipes/`; die UI bevorzugt `samples/recipes/` und nutzt `samples/skills/` nur als Fallback.
- `skill_errors` im Token-/Activity-Log: historisches Feld bleibt neben `recipe_errors` fuer alte Logzeilen und UI-Kompatibilitaet.

## Darf nicht neu verwendet werden

- Neue UI-Texte, Hilfe, Wiki, Release Notes und Samples sollen `Recipe`/`Rezept` verwenden.
- Neue Importpfade sollen `aria.core.recipe_*` oder `aria.web.recipes_*` verwenden.
- Neue Sample-Manifeste gehoeren nach `samples/recipes/` und setzen `ui.config_path` auf `/recipes`.
- Neue Tests fuer Samples sollen recipe-first heissen und `samples/recipes/` pruefen.

## Entfernbare Bruecken spaeter

Erst nach einem expliziten Migrationsrelease entfernen:

- `samples/skills/`, wenn public docs und alte Release-Zweige lange genug auf `samples/recipes/` zeigen.
- `custom_skill_*` Aliase in `recipe_manifests.py` und `recipe_runtime.py`, wenn keine externen Imports/Backups mehr erwartet werden.
- `/skills*` Redirects, wenn alte Bookmarks nicht mehr relevant sind.
- `skills:` Config-Root, wenn ein automatischer Config-Migrator auf `recipes:` existiert und getestet ist.

## Aktuelle Absicherung

- `tests/test_recipe_samples.py` prueft, dass `samples/recipes/` recipe-first bleibt und nicht nach `/skills` zeigt.
- Derselbe Test stellt sicher, dass `samples/skills/` nur als paritaetische Legacy-Referenz existiert.
- Recipe-Routen-Tests pruefen, dass sichtbare Seiten keine alten Skill-Labels anzeigen.
- Backcompat-Wrapper enthalten kurze Modul-Docstrings mit Verweis auf die neuen Recipe-Module.

## Migration-Gate

Legacy-Bruecken werden nur entfernt, wenn alle Punkte erfuellt sind:

- Ein Release-Text nennt die Entfernung und den Migrationspfad explizit.
- Alte Config-/Backup-Daten werden automatisch oder per dokumentiertem Admin-Schritt auf `recipes` migriert.
- `/skills*`-URLs liefern mindestens einen Release-Zyklus lang klare Redirect-/Hinweis-Texte.
- Tests belegen, dass neue UI, Samples, Hilfe und Wiki recipe-first bleiben.
- Externe Imports fuer die alten Wrapper sind bewusst als Breaking Change akzeptiert.
