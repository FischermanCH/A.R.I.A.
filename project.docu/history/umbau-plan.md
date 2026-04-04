ja gerne m# ARIA Umbau-Plan

Stand: 2026-03-26
Status: Phase 5 abgeschlossen

## Ziel

ARIA soll modularer, testbarer und später plugin-fähig werden, ohne die aktuelle Funktionalitaet zu gefährden.

Der Umbau ist kein Redesign des Produkts, sondern ein kontrollierter Architektur-Schnitt:

- weniger Logik in `aria/main.py`
- klarere Verantwortungen in `aria/core/pipeline.py`
- mehr wiederverwendbare Services
- kleinere, besser testbare Module

## Warum jetzt?

Jetzt ist der richtige Zeitpunkt:

- ARIA kann bereits genug, um zu wissen, welche Produktbereiche stabil und wichtig sind
- neue Features werden in der aktuellen Struktur teurer und riskanter
- die bisherigen Bugs zeigen, dass Monolith-Dateien die Fehlerwahrscheinlichkeit erhöhen
- wir wollen mittelfristig erweiterbar und plugin-fähig werden

## Umbau-Regeln

1. Kein Big-Bang-Refactor
2. Verhalten zuerst erhalten, nicht gleichzeitig Verhalten und Architektur ändern
3. Nach jedem Schritt:
   - `pytest`
   - ARIA Neustart
   - kurzer Smoke-Test
4. Doku nach jedem Schritt aktualisieren
5. Wenn ein Schritt zu viel Risiko erzeugt, wird er aufgeteilt

## Nicht-Ziele

Diese Punkte gehoeren **nicht** in den Umbau, solange nicht explizit beschlossen:

- neues UI-Design
- neues Skill-Konzept
- neue Memory-Architektur
- grosse Business-Logik-Änderungen
- Plugin-System final implementieren

## Hauptprobleme heute

### 1. `aria/main.py`

`_build_app()` ist aktuell faktisch eine ganze Anwendung in einer Funktion:

- App-Bootstrap
- Middleware
- Auth
- Chat
- Skills
- Memories
- Config
- Activities / Stats

Risiko:

- Seiteneffekte
- schweres Review
- schwer isoliert testbar
- hohe Wahrscheinlichkeit für stille Fehler bei späteren Erweiterungen

### 2. `aria/core/pipeline.py`

Die Pipeline enthält aktuell zu viele Verantwortungen:

- Routing
- Skill-Ausführung
- SSH-Runtime
- Safe-Fix
- Skill-Status
- Token-/Kosten-Logging

Risiko:

- zu viele Querverbindungen
- schwer wartbar
- Skill-Runtime und Orchestrierung sind nicht sauber getrennt

## Zielstruktur

Die Zielstruktur soll ungefähr so aussehen:

```text
aria/
├── main.py
├── web/
│   ├── auth_routes.py
│   ├── chat_routes.py
│   ├── stats_routes.py
│   ├── activities_routes.py
│   ├── skills_routes.py
│   ├── memories_routes.py
│   └── config_routes.py
├── core/
│   ├── custom_skills.py
│   ├── skill_wizard.py
│   ├── skill_runtime.py
│   ├── ssh_runtime.py
│   ├── safe_fix.py
│   └── pipeline.py
```

`main.py` soll am Ende nur noch enthalten:

- App-Erzeugung
- Middleware
- globale Helper
- Route-Registrierung
- gemeinsame Services / Context

## Technisches Leitmuster

Vor dem Route-Schnitt wird ein gemeinsamer App-Kontext eingefuehrt, z. B.:

- `settings`
- `pipeline`
- `prompt_loader`
- `llm_client`
- `auth_manager`

Danach werden Route-Gruppen registriert über:

- `register_auth_routes(app, ctx)`
- `register_skills_routes(app, ctx)`
- `register_memories_routes(app, ctx)`

Damit vermeiden wir:

- chaotische Closures
- versteckte Abhaengigkeiten
- mehrfachen Copy/Paste-Zustand

## Reihenfolge des Umbaus

### Phase 1: Skill-Basis aus `main.py` loesen

Ziel:

- Skill-Manifest-Logik aus `main.py` auslagern

Neue Datei:

- `aria/core/custom_skills.py`

Verschieben:

- Skill-Validator
- Laden/Speichern von Skill-Manifests
- Trigger-Index
- Skill-bezogene Hilfsfunktionen ohne HTTP-Bezug

Akzeptanz:

- Skill Wizard funktioniert unverändert
- Import/Export funktioniert unverändert
- bestehende Tests gruen

### Phase 2: Kleine Route-Module zuerst

Ziel:

- risikoarme Bereiche zuerst aus `main.py` loesen

Neue Dateien:

- `aria/web/stats_routes.py`
- `aria/web/activities_routes.py`

Akzeptanz:

- `/stats` unverändert
- `/activities` unverändert
- i18n / Filter / Preise weiterhin korrekt

### Phase 3: Skills-Routen modularisieren

Ziel:

- Skill-HTTP-Logik aus `main.py` loesen

Neue Datei:

- `aria/web/skills_routes.py`

Umfang:

- Skills-Seite
- Wizard
- Import / Export
- Save / Enable / Disable

Akzeptanz:

- Wizard funktioniert identisch
- Rename / Trigger / Schedule bleiben stabil

### Phase 4: Pipeline-Runtime trennen

Ziel:

- `aria/core/pipeline.py` auf Orchestrierung reduzieren

Neue Dateien:

- `aria/core/skill_runtime.py`
- `aria/core/ssh_runtime.py`
- `aria/core/safe_fix.py`

Akzeptanz:

- Custom Skills laufen unverändert
- SSH-Skills unverändert
- Safe-Fix unverändert
- Token-/Kosten-Logik unverändert

### Phase 5: Memories-Routen trennen

Neue Datei:

- `aria/web/memories_routes.py`

Akzeptanz:

- `/memories`
- `/memories/map`
- `/memories/config`
- Edit / Delete / Maintenance

bleiben funktional identisch

### Phase 6: Config-Routen modularisieren

Neue Datei:

- `aria/web/config_routes.py`

Optional später weiter aufteilen:

- `config_llm_routes.py`
- `config_memory_routes.py`
- `config_users_routes.py`

Akzeptanz:

- alle bestehenden Config-Seiten funktionieren unverändert

## Plugin-/Erweiterbarkeit

Der Umbau ist die Vorstufe für spätere Plugin-Fähigkeit.

Wichtig dafür:

- Skill-Manifest-Logik getrennt von HTTP
- Route-Registrierung modular
- Runtime-Komponenten klar getrennt
- später einfache Registrierung neuer Module/Skills

Das Plugin-System selbst ist **nicht** Teil dieses Umbaus, aber der Umbau soll es später leicht machen.

## Pro Schritt zu dokumentieren

Nach jeder Umbau-Phase festhalten:

1. Was wurde verschoben?
2. Was wurde nicht verändert?
3. Welche Tests liefen?
4. Welche Risiken bleiben?
5. Welche Folgephase ist als nächstes sinnvoll?

## Arbeitsprotokoll

### Phase 1

Status: abgeschlossen

Notizen:

- Backup vor Umbau erstellt: `/home/fischerman/ARIA_backup_2026-03-26`
- neues Modul `aria/core/custom_skills.py` angelegt
- Skill-Manifest-Logik wird aus `aria/main.py` ausgelagert
- verschoben:
  - `_sanitize_skill_id`
  - `_custom_skill_file`
  - `_normalize_skill_steps_manifest`
  - `_normalize_skill_schedule_manifest`
  - `_validate_custom_skill_manifest`
  - `_load_custom_skill_manifests`
  - `_save_custom_skill_manifest`
  - `_build_skill_trigger_index`
  - `_refresh_skill_trigger_index`
  - `_collect_skill_categories`
- `aria/main.py` nutzt die Funktionen jetzt nur noch per Import
- Verifikation:
  - `pytest`: `37 passed`
  - ARIA Neustart erfolgreich
  - `/health` antwortet mit `{\"status\":\"ok\"}`
  - manueller Check:
    - Skill bearbeiten/umbenennen: OK
    - `/config/skill-routing` sichtbar, LLM-Trigger-Vorschlag: OK
    - Skill-Export: OK
    - Skill-Import: noch offen, in Testliste aufgenommen
- Risiko nach Phase 1:
  - HTTP-Routen liegen weiterhin in `main.py`
  - Skill-Wizard- und Skills-Routen sind noch nicht modularisiert
- Nächster sinnvoller Schritt:
  - Phase 2: `stats` und `activities` als erste kleine Route-Module aus `main.py` loesen

### Phase 2

Status: abgeschlossen

Notizen:

- neue Module angelegt:
  - `aria/web/stats_routes.py`
  - `aria/web/activities_routes.py`
- `/stats` und `/activities` wurden aus `aria/main.py` in eigene Route-Registrierer verschoben
- `aria/main.py` registriert die beiden Seiten jetzt nur noch über:
  - `register_stats_routes(...)`
  - `register_activities_routes(...)`
- Verifikation:
  - `python -m py_compile`: OK
  - `pytest`: `37 passed`
  - ARIA Neustart erfolgreich
  - `/health` antwortet mit `{\"status\":\"ok\"}`
  - Smoke-Check:
    - `/stats` leitet korrekt auf `/login?next=%2Fstats`
    - `/activities?kind=skill&status=error` leitet korrekt auf Login mit `next` weiter
- Risiko nach Phase 2:
  - `skills`, `memories` und `config` liegen weiterhin in `aria/main.py`
  - ein gemeinsamer App-Kontext ist noch nicht eingefuehrt
- Nächster sinnvoller Schritt:
  - Phase 3: Skills-Routen modularisieren

### Phase 3

Status: abgeschlossen

Notizen:

- neues Modul angelegt:
  - `aria/web/skills_routes.py`
- folgende Routen wurden aus `aria/main.py` ausgelagert:
  - `/skills`
  - `/skills/save`
  - `/skills/wizard`
  - `/skills/wizard/save`
  - `/skills/import`
  - `/skills/export/{skill_id}`
- `aria/main.py` registriert die Skills-Seiten jetzt nur noch über `register_skills_routes(...)`
- Runtime-Schutz nachgezogen:
  - ausgelagerte Route-Module nutzen Getter für `settings`/`pipeline`, damit `reload_runtime()` weiterhin den aktuellen Zustand verwendet
- Verifikation:
  - `python -m py_compile`: OK
  - `pytest`: `37 passed`
  - ARIA Neustart erfolgreich
  - `/health` antwortet mit `{\"status\":\"ok\"}`
  - Smoke-Check:
    - `/skills` leitet korrekt auf `/login?next=%2Fskills`
    - `/skills/wizard?skill_id=server-update-2nodes` leitet korrekt auf Login mit `next` weiter
  - manueller Check:
    - Skill im Wizard geöffnet, Name geändert und gespeichert: OK
    - Skill-Export: OK
    - Toggle-Test auf `/skills` noch offen
- Risiko nach Phase 3:
  - `memories` und `config` liegen weiterhin in `aria/main.py`
  - Skill-Routing unter `/config/skill-routing` ist bewusst noch nicht mit umgezogen
- Nächster sinnvoller Schritt:
  - Phase 4: Pipeline-Runtime trennen

### Phase 4

Status: abgeschlossen

Notizen:

- neue Runtime-Module angelegt:
  - `aria/core/safe_fix.py`
  - `aria/core/ssh_runtime.py`
  - `aria/core/skill_runtime.py`
- aus `aria/core/pipeline.py` ausgelagert:
  - Safe-Fix-Logik
  - SSH-Command-Runtime
  - Custom-Skill-Runtime inkl. Step-Ausführung
  - Laden/Matchen von Custom-Skills
  - Skill-Status-Textaufbau
  - Auto-Memory-Skip-Regel für operative Skill-Runs
- `Pipeline` ist jetzt in diesem Bereich deutlich schlanker:
  - Runtime-Helfer delegieren an die neuen Module
  - `process()` bleibt Orchestrator
  - bestehende interne Methoden bleiben als Wrapper erhalten, damit Tests und Aufrufer stabil bleiben
- Verifikation:
  - `python -m py_compile`: OK
  - `pytest`: `37 passed`
  - ARIA Neustart erfolgreich
  - `/health` antwortet mit `{\"status\":\"ok\"}`
  - Smoke-Check:
    - `/skills` leitet korrekt auf `/login?next=%2Fskills`
    - `/activities?kind=skill&status=error` leitet korrekt auf Login mit `next` weiter
  - manueller Check:
    - Skill-Status-Intent antwortet korrekt und sehr schnell
    - Upgrade-Skill für beide `ubnsrv`-Server läuft erfolgreich
    - Hold-Detection + Safe-Fix-Vorschlag erscheinen korrekt
- nachtraeglicher Stabilitaets-Fix:
  - ein später isolierter Haenger in `tests/test_pipeline.py` war eine stale Referenz aus Phase 4
  - `CustomSkillRuntime` hielt die urspruengliche `memory_skill`, obwohl `pipeline.memory_skill` später ersetzt wurde
  - Loesung:
    - `CustomSkillRuntime` nutzt jetzt einen Getter auf `pipeline.memory_skill`
  - Verifikation:
    - `tests/test_pipeline.py::test_pipeline_custom_skill_does_not_persist_auto_memory_session_context`: `1 passed`
    - `tests/test_pipeline.py`: `11 passed`
    - Vollsuite: `37 passed`
- Risiko nach Phase 4:
  - `memories` und `config` liegen weiterhin in `aria/main.py`
  - `process()` ist noch relativ gross, auch wenn die Runtime-Bloecke jetzt ausgelagert sind
- Nächster sinnvoller Schritt:
  - Phase 5: Memories-Routen modularisieren

### Phase 5

Status: abgeschlossen

Notizen:

- neues Route-Modul angelegt:
  - `aria/web/memories_routes.py`
- folgende Routen wurden aus `aria/main.py` ausgelagert:
  - `/memories`
  - `/memories/map`
  - `/memories/delete`
  - `/memories/edit`
  - `/memories/maintenance`
  - `/memories/config`
  - `/config/memory`
  - zugehoerige POST-Aktionen für Select/Create/Auto-Save/Compress/Compression-Save
- `aria/main.py` registriert die Memory-Seiten jetzt nur noch über `register_memories_routes(...)`
- Getter-/Callback-Muster wie bei `skills` übernommen:
  - aktuelles `settings`/`pipeline` nach `reload_runtime()` bleibt erhalten
  - Qdrant-/Cookie-/Config-Helfer bleiben zentral, HTTP-Logik ist ausgelagert
- Verifikation:
  - `python -m py_compile`: OK
  - `pytest`: `37 passed`
  - ARIA Neustart erfolgreich
  - `/health` antwortet mit `{\"status\":\"ok\"}`
  - Smoke-Check:
    - `/memories` leitet korrekt auf `/login?next=%2Fmemories`
    - `/memories/map` leitet korrekt auf `/login?next=%2Fmemories%2Fmap`
    - `/memories/config` leitet korrekt auf `/login?next=%2Fmemories%2Fconfig`
    - `/config/memory` leitet korrekt auf `/login?next=%2Fconfig%2Fmemory`
- Risiko nach Phase 5:
  - `config` liegt weiterhin weitgehend in `aria/main.py`
  - Memory-Helfer liegen noch als Callbacks in `main.py`, nicht als eigener Service
- Nächster sinnvoller Schritt:
  - Phase 6: Config-Routen modularisieren

### Phase 6

Status: abgeschlossen

Notizen:

- neues Route-Modul:
  - `aria/web/config_routes.py`
- ausgelagert aus `aria/main.py`:
  - `/config`
  - `/config/language`
  - `/config/debug`
  - `/config/security`
  - `/config/logs`
  - `/config/connections`
  - `/config/users`
  - `/config/prompts`
  - `/config/routing`
  - `/config/skill-routing`
  - `/config/llm`
  - `/config/embeddings`
  - `/config/files`
  - `/config/error-interpreter`
- `main.py` registriert die Config-Seiten jetzt nur noch über `register_config_routes(...)`
- Getter-/Proxy-Muster auch für `config` umgesetzt:
  - aktuelle `settings`/`pipeline` bleiben nach `reload_runtime()` gültig
  - bestehende Helfer aus `main.py` werden als explizite Dependencies übergeben
- Verifikation:
  - `py_compile`: OK
  - `tests/test_router.py`: `8 passed`
  - `tests/test_memory.py`: `4 passed`
  - `tests/test_error_handling.py`: `4 passed`
  - ARIA Neustart erfolgreich
  - `/health` antwortet mit `{\"status\":\"ok\"}`
  - Route-Registry-Check: `50` `/config*`-Routen im FastAPI-App-Objekt vorhanden
- Nachtrag:
  - der zuvor offene `tests/test_pipeline.py`-Haenger wurde isoliert und behoben
  - Vollsuite ist wieder komplett gruen (`37 passed`)
- Nächster sinnvoller Schritt:
  - Feinschnitt der verbleibenden `main.py`-Helfer oder gezielter Test-/Cleanup-Durchlauf für den Umbau

## Entscheidung

Empfehlung:

- Umbau **jetzt** beginnen
- aber streng inkrementell
- Start mit **Phase 1**

Warum:

- aktueller Nutzen hoch
- Risiko noch kontrollierbar
- Basis für Stabilitaet und Erweiterbarkeit
