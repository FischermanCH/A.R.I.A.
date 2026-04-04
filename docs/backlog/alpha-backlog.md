# ARIA - Alpha Backlog

Stand: 2026-04-03

Zweck:
- harte Pre-Public-Alpha TODO-Liste
- nur Punkte, die vor einem sauberen GitHub/Docker-Hub-Release noch erledigt oder bewusst final entschieden werden sollen
- kein historischer Masterplan, sondern ein fokussierter Release-Backlog

## Must-Have vor Public Alpha

### Hilfe / Onboarding
- [x] mitgelieferte Help-Doku bereitstellen
  - `docs/help/help-system.md`
  - thematische Help-Seiten für Memory, Pricing, Security
- [x] Help-Seite im UI anbinden
- [x] First-Run- und Admin/User-Modus in der UI klarer erklären

### Statistiken / Betrieb
- [x] Statistik-Reset-Funktion definieren und umsetzen
  - Tokens/Kosten/Activities gezielt zurücksetzen
  - klare UI-Warnung, was dabei gelöscht wird und was nicht
- [ ] Qdrant-Größenanzeige im separaten Container-Setup final gegen echten Prod-Betrieb prüfen
- [ ] Preflight-/Statusanzeigen final auf Konsistenz und mobile Darstellung prüfen

### Memory
- [x] gewichtetes Multi-Collection-Recall über Facts, Preferences, Sessions und Knowledge produktiv nutzen
- [x] Memory-Export als JSON-Download für den aktuellen User und den aktuellen Filter/Suchkontext bereitstellen
- [ ] Memory-Export auf `prod` live gegen echte Qdrant-Daten testen

### Release / Git / Docker
- [ ] finale Git-Versionierungsstrategie aktiv anwenden
  - SemVer + Pre-Release-Tags wie `v0.1.0-alpha.N`
  - Release-Notes nach `Added / Changed / Fixed / Security / Known Limitations / Upgrade Notes`
- [ ] Docker-Image-Tags für Public Release festlegen
  - versionierter Tag
  - optional Alias-Tag `alpha`
- [x] Root-`CHANGELOG.md` anlegen und Release-Schema dokumentieren
- [x] Root-`CHANGELOG.md` pro Release konsequent pflegen
- [ ] Stack-/Compose-Beispiele auf public-taugliche Image-Tags vorbereiten

### README / Public Docs
- [x] Root-`README.md` auf Public-Alpha-Struktur final glätten
  - Quickstart
  - klare ALPHA-Grenzen
  - Setup-Links in `docs/`
  - Support-/Known-Limitations-Hinweise
- [x] `docs/product/*` und `docs/setup/*` strukturell konsolidieren
- [x] `docs/product/*` und `docs/setup/*` final sprachlich glätten
- [ ] Screenshots / UI-Bilder optional ergänzen, falls für Release sinnvoll

### Security / Repo Sweep
- [x] Lizenz final festlegen und im Repo ergänzen
- [x] Third-Party-Notices für Qdrant und wichtige Dependencies ergänzen
- [ ] Repo-/Privacy-Sweep vor Public Push
  - keine lokalen Secrets
  - keine internen IPs/Hosts in auszuliefernden Default-Dateien, sofern vermeidbar
  - keine rein privaten Notizen außerhalb `project.docu/`
- [x] `.gitignore` und Beispiel-Konfigs final gegenchecken
- [x] Security-Hinweis für LAN/VPN statt Public Internet im README und in `docs/` klar stehen lassen

### Qualität / Release Smoke Test
- [ ] frischen Host / frischen Container-Start einmal komplett durchspielen
  - Bootstrap-User
  - LLM + Embeddings
  - Qdrant / Memory
  - SSH/SFTP/SMB/RSS/Discord Beispielpfade
  - Skill Import + Skill Run
  - `/stats`, `/help`, mobile UI
- [ ] Upgrade-Test mit bestehenden Volumes
  - Config bleibt erhalten
  - Secrets bleiben erhalten
  - Skills bleiben erhalten
  - Memories bleiben erhalten

## Nice-to-Have, aber noch Alpha-nah

- Hilfe-Icons zuerst nur an den wichtigsten Seiten und später breit ausrollen
- Kontextsensitives Hilfe-System im UI umsetzen
  - Info-Icon an erklärungsbedürftigen Feldern und Boxen
  - kurze, zentral gepflegte Hilfetexte
  - Mehrsprachigkeit DE/EN
- kleines `aria --version` / Version-Check-Konzept ergänzen
- bessere Release-Hinweise bei harten Browser-Caches nach UI/CSS-Updates
- mehr Sample-Skills für typische Homelab-/RSS-/Admin-Flows

## Bewusst nicht mehr Blocker für Public Alpha

- Session-Rollup Tag -> Woche -> Monat weiter vertiefen
- Embedding-Modellwechsel / Reindex-Flow absichern
- volles Multi-User-/RBAC-Modell
- Memory Map / Graph-Visualisierung
- Home Assistant Integration
- Dokument-Ingest / Knowledge Base
- Websuche / Research-Flow
- Streaming/SSE für Live-Antworten
