# ARIA — Alpha Build Log

Stand: 2026-05-21

Zweck:
- nachvollziehen, **was bereits in Alpha-Builds gelandet ist**
- festhalten, **was auf `dev` schon vorbereitet ist**
- Build-Versionen und inhaltliche Aenderungen zusammen sichtbar machen

## Vorbereitet fuer naechsten Build

- `alpha298` ist intern gebaut/exportiert, aber nicht public gepusht, nicht getaggt und nicht als GitHub Release angelegt.
- Nach GitHub-/Live-Release pruefen:
  - `/stats`: Release-Metadaten muessen den installierten Stand zeigen und Operator Guardrail darf keinen Release-Fehler melden.
  - `/stats`: Kostenkarte muss klar als Schaetzung formuliert sein; Abrechnungsperiode-Reset muss Tokenlog archivieren statt loeschen.
  - `/config/logs`: Log-Hygiene muss 90 Tage Retention fuer Token-/Kosten-/Aktivitaetslogs und LLM-Debug-Logs ausweisen.
  - `/config/llm/debug`: Debug-Log muss 90-Tage-Retention und manuelles Loeschen korrekt erklaeren.
  - Stats-Details-Link-Test: Kostenkarte `Details` muss die `Costs & Pricing`-Kachel oeffnen und dorthin springen.
  - Stats-Tokenkarten-Test: Nach Reset muss die Anfrage-Karte `Anfragen · aktuelle Periode` anzeigen, nicht mehr `7 Tage`.
  - Discord-Startup-Test: Startup-Event darf nicht mehr `Public URL nicht konfiguriert` melden; ohne Basis-URL nennt es die optionale Basis-URL, mit `ARIA_PUBLIC_URL=http://aria.black.lan/` diese interne LAN-URL.
  - Operator-Guardrail-Warnung-Test: Bei `Warnung`/`Fehler` muss die Karte die konkreten betroffenen Checks mit Detailtext und Link anzeigen.
  - Guardrail-Live-Test: SFTP-/SMB-Read-only-Guardrails sollen `list/read` erlauben, `write/create/delete` blockieren.
  - Webhook-Live-Test: Status-/Benachrichtigungs-Payload erlauben, `delete user record` als Webhook-Payload behandeln und durch Guardrail blockieren, nicht als Connection-Delete.
  - HTTP-API-Live-Test: generische Formulierungen wie `meine http api` sollen bei Single-Profil sauber auf das Profil fallen.
  - HTTP-API-Status-Test: Ziel-HTTP-Status wie 404 sollen als externe Endpoint-Antwort erklaert werden und keinen Discord-Recipe-Error erzeugen.
  - Guardrail-Block-UX-Test: erwartete Policy-Blocks sollen als Sicherheitsentscheidung erklaert werden und keinen generischen Profil-/Zugriffsrechte-Hinweis zeigen.
  - Pending-Action-Test: bestaetigte SSH-`ask_user`-Aktionen muessen nach Klick wirklich in die Runtime laufen.
  - Server-Fitness-Test: `wie fit sind meine server?` muss in `capability:ssh_command` laufen und `plural_target_scope health_command_adapted command=uptime -p && df -h && free -h` zeigen.

## Bereits gebaut

### alpha298

- Interner Build nach `alpha297` mit Discord-Startup-Host-Nachzug:
  - Startup-Discord-Events nutzen jetzt die zentrale Runtime-URL-Ermittlung.
  - Wenn `ARIA_PUBLIC_URL`/`aria.public_url` gesetzt ist, wird diese Basis-URL angezeigt.
  - Wenn keine Basis-URL gesetzt ist, faellt ARIA auf eine automatisch erkannte lokale Adresse mit Port zurueck statt eine Konfigurationswarnung zu senden.
- Verifikation vor Build:
  - Discord-/Release-/Package-Hygiene: `15 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha298`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha298-local.tar`
  - TAR-SHA256: `5d8e55db537cb8320b428385a73d6eacc7620de4eda8b9803007566c05ef02d8`
  - TAR-Size: `235M` (`ls -lh`)
- Image:
  - `fischermanch/aria:0.1.0-alpha.298`
  - `aria:alpha-local`
  - Image-Digest: `sha256:7f5a55506d087e0479d0087bb1d9bdfab7706055ba1d21f08d8f6f30ae7db0ad`
  - Image-Size: `245498292` bytes
  - Created: `2026-05-21T14:27:55.648243956+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha291` entfernt; interne TARs `alpha292` bis `alpha298` bleiben als letzte sieben Builds erhalten.
  - Lokaler Root-Speicher nach Build/Export/Smoke: ca. `20G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - Public Docker Tags `fischermanch/aria:0.1.0-alpha.298` und `fischermanch/aria:alpha` wurden mit Digest `sha256:7f5a55506d087e0479d0087bb1d9bdfab7706055ba1d21f08d8f6f30ae7db0ad` gepusht.
  - Git Commit, Git Tag und GitHub Release werden im Public-Release-Schritt erstellt.

### alpha297

- Interner Build nach `alpha296` mit Stats-/Discord-Nachzug:
  - Die Stats-Anfragekarte spricht nach einem Kosten-/Aktivitaetsreset von `aktueller Periode` statt von einem starren 7-Tage-Fenster.
  - Discord-Startup-Events nennen eine optionale Basis-URL statt `Public URL nicht konfiguriert`; interne LAN-URLs wie `http://aria.black.lan/` sind ausdruecklich ok.
  - Der Discord-Eventbus-Test deckt die relevanten konfigurierbaren Kategorien ab: Recipe Errors, Skill Errors, Safe Fix, Connection Changes und System Events.
- Verifikation vor Build:
  - Stats-/Token-/Discord-/Chat-Tooling-/Release-/Package-Hygiene: `65 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha297`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha297-local.tar`
  - TAR-SHA256: `08b680104a20e3002c747d3e097d53e88bc64122f45600a512bab9dc655ec7c4`
  - TAR-Size: `235M` (`ls -lh`)
- Image:
  - `fischermanch/aria:0.1.0-alpha.297`
  - `aria:alpha-local`
  - Image-Digest: `sha256:978db8ec570f2ab551d9bcf9dd9f43e20f7bccde40c4e18d7beaca35ba3ee694`
  - Image-Size: `245498989` bytes
  - Created: `2026-05-21T13:56:32.123447618+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha290` entfernt; interne TARs `alpha291` bis `alpha297` bleiben als letzte sieben Builds erhalten.
  - Lokaler Root-Speicher nach Build/Export/Smoke: ca. `21G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha297`

### alpha296

- Interner Build nach `alpha295` mit Stats-UX-Nachzug:
  - Der `Details`-Link auf der Kostenkarte oeffnet die eingeklappte `Costs & Pricing`-Kachel direkt und springt zum Ziel.
  - Die Operator-Guardrail-Karte listet bei Warnungen/Fehlern die konkreten betroffenen Checks inklusive Detailtext und Link zur passenden Sektion.
  - `Startup-Preflight` und `Runtime-Health` haben eigene Sprungziele fuer diese Review-Links.
- Verifikation vor Build:
  - Stats-/Release-/Package-Hygiene: `50 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha296`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha296-local.tar`
  - TAR-SHA256: `e3b5ba9667092c14584888cad0f3b56128f10ce7547a68fe7266f86468afb239`
  - TAR-Size: `235M` (`ls -lh`)
- Image:
  - `fischermanch/aria:0.1.0-alpha.296`
  - `aria:alpha-local`
  - Image-Digest: `sha256:3ea610b061dbe311963ab7df7e010b8c238d896664e28be9ada7d5257548b7bc`
  - Image-Size: `245497255` bytes
  - Created: `2026-05-21T11:01:53.29749486+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha289` entfernt; interne TARs `alpha290` bis `alpha296` bleiben als letzte sieben Builds erhalten.
  - Lokaler Root-Speicher nach Build/Export/Smoke: ca. `23G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha296`

### alpha295

- Interner Build nach `alpha294` mit Kosten-/Log-Hygiene:
  - `/stats` kennzeichnet Provider-Kosten als lokale Schaetzung, nicht als Rechnung.
  - Abrechnungsperioden koennen ueber `/stats` und `/config/logs` zurueckgesetzt werden; der bisherige Token-/Kostenlog wird vorher archiviert.
  - Token-/Kosten-/Aktivitaetslogs und LLM-Debug-Audit werden standardmaessig 90 Tage gehalten und beim App-Start sowie in der Maintenance bereinigt.
  - Hilfe, Wiki, Pricing- und Architektur-Doku beschreiben die 90-Tage-Retention und den Reset-Pfad.
- Verifikation vor Build:
  - Token-/Stats-/LLM-Audit-Fokus: `59 passed`
  - Recipes-/Learned-Views: `22 passed`
  - Release-/Package-Hygiene: `11 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha295`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha295-local.tar`
  - TAR-SHA256: `366842b932fbad72a9f41ae64a9b7c78a9ac17396be44654dc037d12fa652282`
  - TAR-Size: `235M` (`ls -lh`)
- Image:
  - `fischermanch/aria:0.1.0-alpha.295`
  - `aria:alpha-local`
  - Image-Digest: `sha256:d1a641e96b59e3bf27f50f0e3fa4ab47aa1ca2d82ff0499d5f75585b08731908`
  - Image-Size: `245494926` bytes
  - Created: `2026-05-21T09:51:11.484121101+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha288` entfernt; interne TARs `alpha289` bis `alpha295` bleiben als letzte sieben Builds erhalten.
  - Lokaler Root-Speicher nach Build/Export/Smoke: ca. `24G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha295`

### alpha294

- Interner Build nach `alpha293` mit colloquial Server-Health-Nachzug:
  - Der bounded LLM-Capability-Draft kann fuer frei formulierte Server-Fitness-/Health-/Kapazitaetsfragen `target_intent=health_check` oder `target_intent=capacity_check` liefern.
  - Die deterministische SSH-Multi-Target-Schicht nutzt diesen Intent nur zur sicheren Normalisierung auf den breitesten erlaubten Read-only-Statuscheck und prueft weiterhin Guardrails/Preflight vor Runtime.
  - Der Live-Ausreisser `wie fit sind meine server?` ist als Regressionstest abgesichert, ohne `fit` als hartes Health-Wort in den deterministischen Lexika zu verdrahten.
- Verifikation vor Build:
  - Fokusblock Capability/Pipeline/Error/Blocked-Action: `106 passed`
  - Release-/Package-Hygiene: `11 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha294`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha294-local.tar`
  - TAR-SHA256: `30932eaad007296d0ef7321bf9d2a1677fac74f04218ec9b1e2ffa5aac0c825e`
  - TAR-Size: `245498880` bytes
- Image:
  - `fischermanch/aria:0.1.0-alpha.294`
  - `aria:alpha-local`
  - Image-Digest: `sha256:793ba137d78e3b00149b5c003f61aae04833f9c31c274ab9e2a10d0d6c6e04da`
  - Image-Size: `245471005` bytes
  - Created: `2026-05-20T23:48:25.923267018+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha287` entfernt; interne TARs `alpha288` bis `alpha294` bleiben als letzte sieben Builds erhalten.
  - Lokales ARIA-Image `alpha292` entfernt; `alpha293` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `25G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha294`

### alpha293

- Interner Build nach `alpha292` mit Guardrail-Link-/Fallback-Nachzug:
  - Runtime-Guardrail-Blocktexte enthalten wieder direkte Review-Links zur passenden Guardrail.
  - Der blocked-action Timeout-Fallback nutzt dieselbe Sicherheitsentscheidungs-Sprache wie der Runtime-Pfad, statt auf `ARIA kann diese Aktion nicht ausfuehren...` zurueckzufallen.
  - Geplante Aktion/Payload bleibt bei Blocks sichtbar, damit User den blockierten Wunsch nachvollziehen koennen.
- Verifikation vor Build:
  - Fokus + Release-/Package-Hygiene: `25 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha293`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha293-local.tar`
  - TAR-SHA256: `c0a58a986ccad5d5c552e39c63f2cafa02b34a74fea6214b727e6ccb43981a21`
- Image:
  - `fischermanch/aria:0.1.0-alpha.293`
  - `aria:alpha-local`
  - Image-Digest: `sha256:6a0786fa61b89d34b3130c0be4dae5df861950e7971f6f66acf764da27320c8e`
  - Image-Size: `245470075` bytes
  - Created: `2026-05-20T01:24:02.806597949+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha286` entfernt; interne TARs `alpha287` bis `alpha293` bleiben als letzte sieben Builds erhalten.
  - Lokales ARIA-Image `alpha291` entfernt; `alpha292` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `25G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha293`

### alpha292

- Interner Build nach `alpha291` mit Guardrail-Block-UX-Nachzug:
  - Runtime-Guardrail-Blocks erhalten eigene Capability-Fehlercodes wie `capability_api_request_guardrail_blocked`.
  - Chat-Antworten formulieren erwartete Guardrail-Blocks als aktive Sicherheitsentscheidung, nicht als defektes Profil, Ziel- oder Zugriffsrechteproblem.
  - Der generische Zusatzhinweis `Profil, Ziel und Zugriffsrechte pruefen` wird fuer erwartete Guardrail-Blocks unterdrueckt.
  - Discord-/Eventbus-Rezeptfehler-Alerts werden fuer erwartete Guardrail-Policy-Blocks unterdrueckt; echte Runtime-/Codefehler bleiben alertbar.
- Verifikation vor Build:
  - Fokus + Release-/Package-Hygiene: `20 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha292`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha292-local.tar`
  - TAR-SHA256: `040d6c6fa45c6f2093858711bc734b8314288f36399ea2aff1f28aba2b9981ed`
- Image:
  - `fischermanch/aria:0.1.0-alpha.292`
  - `aria:alpha-local`
  - Image-Digest: `sha256:660d403089fc8cacc8a7224931aa0f63010d3795acc77f225a6bb53adeea8331`
  - Image-Size: `245467051` bytes
  - Created: `2026-05-20T00:49:51.594944353+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha285` entfernt; interne TARs `alpha286` bis `alpha292` bleiben als letzte sieben Builds erhalten.
  - Lokales ARIA-Image `alpha290` entfernt; `alpha291` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `26G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha292`

### alpha291

- Interner Build nach `alpha290` mit HTTP-API-Statusklassifizierung:
  - HTTP-API-4xx/5xx-Antworten werden als externe Endpoint-Statusantworten behandelt, nicht als interner Rezeptfehler.
  - Die Chat-Antwort erklaert, dass das HTTP-API-Profil erreicht wurde, aber der Ziel-Endpunkt einen Statuscode wie `404` geliefert hat.
  - Health-Pfad und ein begrenzter Antwortauszug werden in die Fehlermeldung aufgenommen, damit Profile-/Pfadprobleme schneller erkennbar sind.
  - Discord-/Eventbus-Rezeptfehler-Alerts werden fuer erwartbare HTTP-Statusantworten unterdrueckt; echte Runtime-/Codefehler bleiben alertbar.
- Verifikation vor Build:
  - Fokus + Release-/Package-Hygiene: `19 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha291`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha291-local.tar`
  - TAR-SHA256: `836436dab2c2f6c854a7a0876a7cae1e0d8a239e17fd598772fd8365aa958d40`
- Image:
  - `fischermanch/aria:0.1.0-alpha.291`
  - `aria:alpha-local`
  - Image-Digest: `sha256:e5f395d897c481990b68d9a5a387ba7b534c7b9a82d024cc220f363d51974845`
  - Image-Size: `245463201` bytes
  - Created: `2026-05-19T23:24:35.395267358+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha284` entfernt; interne TARs `alpha285` bis `alpha291` bleiben als letzte sieben Builds erhalten.
  - Lokales ARIA-Image `alpha289` entfernt; `alpha290` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `27G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha291`

### alpha290

- Interner Build nach `alpha289` mit gezieltem Live-Ausreisser-Nachzug:
  - Webhook-/API-/Message-Payloads mit Woertern wie `delete` werden nicht mehr vom Memory-Forget-Router abgefangen, bevor Capability-Routing greifen kann.
  - Datei-Schreibaktionen, die durch Read-only-Guardrails blockiert werden, bekommen einen natuerlicheren deterministischen Fallback-Text, falls der LLM-Erklaerer nicht rechtzeitig liefert.
- Verifikation vor Build:
  - Fokus + Release-/Package-Hygiene: `66 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha290`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha290-local.tar`
  - TAR-SHA256: `471deac0fa6b2268b853f0bafda862e1a1bb83cc51664c8946bc1c1c77e0213b`
- Image:
  - `fischermanch/aria:0.1.0-alpha.290`
  - `aria:alpha-local`
  - Image-Digest: `sha256:dde907cce2e52d2cb67a1e5bd509c06262eec431ea578901732d062d9890d1ac`
  - Image-Size: `245461777` bytes
  - Created: `2026-05-19T22:22:53.111419654+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha283` entfernt; interne TARs `alpha284` bis `alpha290` bleiben als letzte sieben Builds erhalten.
  - Lokales ARIA-Image `alpha288` entfernt; `alpha289` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `28G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha290`

### alpha289

- Interner Build nach `alpha288` mit Guardrail-Runtime- und Pending-Confirmation-Fix:
  - Guardrail-Auswertung fuer SFTP/SMB speist Operation-Aliasse wie `file_list`, `read`, `list`, `file_write`, `write`, `create` und `delete` in Dry-Run und Runtime ein.
  - Webhook-/HTTP-API-Guardrails bekommen strukturierte Payload-/Method-/Pfad-Aliasse, damit Status-/Health-Guardrails nicht nur auf freie Textfragmente angewiesen sind.
  - Webhook-Payloads wie `delete user record` werden nicht mehr als Connection-Delete-Adminaktion fehlinterpretiert.
  - Bestaetigte SSH-`ask_user`-Aktionen reichen die User-Bestaetigung bis in die Runtime-Policy weiter.
  - Generische HTTP-API-Zielworte wie `http api` gelten als weicher Hint; bei genau einem HTTP-API-Profil wird dieses Profil genutzt.
- Verifikation vor Build:
  - Agentic-/Guardrail-/Release-Fokus: `376 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha289`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha289-local.tar`
  - TAR-SHA256: `1a57d76f6dfc5a35d3c4426d212e87e162dd7f66d3e8b0267b915ae1e556529d`
- Image:
  - `fischermanch/aria:0.1.0-alpha.289`
  - `aria:alpha-local`
  - Image-Digest: `sha256:4d6571e034d334e7748620ff9457aefd887382c8d3fdf13fcce9da934df77e6e`
  - Image-Size: `245460462` bytes
  - Created: `2026-05-19T15:15:28.280508139+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha282` entfernt; interne TARs `alpha283` bis `alpha289` bleiben als letzte sieben Builds erhalten.
  - Lokales ARIA-Image `alpha287` entfernt; `alpha288` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `29G` frei; NAS: ca. `900G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha289`

### alpha288

- Interner Build nach `alpha287` mit Guardrail-Scope-Fix und sichtbarerem Guardrail-Selector:
  - Gespeicherte Guardrails koennen optional exakte `connection_kinds` tragen, z. B. nur `sftp` oder nur `smb`.
  - KI-Vorschlaege mit gewaehlter Verbindungsklasse speichern diesen Scope mit.
  - Guardrail-Selectoren auf Connection-Seiten filtern nun neben Guardrail-Typ auch nach konkretem Verbindungsklassen-Scope.
  - Save-Validation prueft denselben Scope serverseitig; eine SFTP-only Guardrail kann nicht an SMB gespeichert werden.
  - Alte Guardrails ohne Scope bleiben als Legacy-/Kompatibilitaetsprofile sichtbar.
  - Security/Advanced-Bereiche auf guardrail-faehigen Connection-Formularen sind standardmaessig offen, damit Guardrail-Zuweisungen nicht versteckt wirken.
- Verifikation vor Build:
  - Guardrail-/Connection-/Release-Fokus: `28 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha288`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha288-local.tar`
  - TAR-SHA256: `5ac9065a7d63c9e5b58ad9a25cd2c82bf38abe1b5dc635fdc6e6aedbdf17e8f5`
- Image:
  - `fischermanch/aria:0.1.0-alpha.288`
  - `aria:alpha-local`
  - Image-Digest: `sha256:4d0a5917f1d0f8c4f20bba22acdb48ae4b62129b0e4b7641795666ab02d76fcd`
  - Image-Size: `245455093` bytes
  - Created: `2026-05-18T21:52:26.248492036+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `alpha281` entfernt; interne TARs `alpha282` bis `alpha288` bleiben als letzte sieben Builds erhalten.
  - Lokales ARIA-Image `alpha286` entfernt; `alpha287` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `29G` frei; NAS: ca. `899G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha288`

### alpha287

- Interner Build nach `alpha286` mit Connection-UX-Paritaet und gemeinsamen Guardrail-Attachments:
  - Connection-Detailseiten nutzen wie SSH einklappbare Arbeitsbereiche fuer gespeicherte Profile, bestehendes Profil bearbeiten und neue Verbindung.
  - Profilkarten sind auf allen gemeinsamen Statusbloecken klickbar und zeigen eine sichtbare `Editieren`-Aktion.
  - SSH landet beim Editieren nicht mehr optisch im Bereich `Neue Verbindung erfassen`; Hash-/Mode-Sync oeffnet den passenden Arbeitsbereich.
  - Guardrail-Auswahl und Guardrail-Zusammenfassung der guardrail-faehigen Verbindungstypen (`ssh`, `sftp`, `smb`, `webhook`, `http_api`) laufen ueber gemeinsame Templates und gemeinsame Context-Keys.
  - Guardrail-Ref-Validierung beim Speichern laeuft ueber einen gemeinsamen Save-Helper; aktuell bleibt es bewusst bei single `guardrail_ref`.
  - SFTP-Statuskarten bekommen denselben Edit-URL-Pfad wie die generischen Connection-Seiten.
- Verifikation vor Build:
  - Vollsuite: `1140 passed`, danach erwarteter Release-Metadaten-Nachzug fuer `alpha287`
  - Release-/Package-Hygiene nach Metadaten-Nachzug: `11 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha287`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha287-local.tar`
  - TAR-SHA256: `db49cd4b75b71d5875d00766505c562093bdf8acbfb66378ad3877408eada020`
- Image:
  - `fischermanch/aria:0.1.0-alpha.287`
  - `aria:alpha-local`
  - Image-Digest: `sha256:4c10b77df6a42fea6bbdd356947ee18eca86307693b7e2f7e616738ea5c17b65`
  - Image-Size: `245446055` bytes
  - Created: `2026-05-17T23:11:23.821301591+02:00`
- Update-/Export-Hinweis:
  - Alte interne TARs `alpha278` bis `alpha280` entfernt; interne TARs `alpha281` bis `alpha287` bleiben als letzte sieben Builds erhalten.
  - Lokales ARIA-Image `alpha285` entfernt; `alpha286` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `30G` frei; NAS: ca. `899G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha287`

### alpha286

- Interner Build nach `alpha285` mit Guardrail-Testmodus und SSH-Verbindungs-UX:
  - `/config/security` hat einen Guardrail-only Testmodus fuer gespeicherte Guardrails.
  - Beispielanfragen koennen gegen die deterministische Guardrail-Engine geprueft werden, bevor ein Profil an echte Verbindungen gehaengt wird.
  - `/config/connections/ssh` ist in einklappbare Bereiche fuer Profile, bestehendes Profil bearbeiten, neue Verbindung und Tools aufgeteilt.
  - SSH-Profilkarten sind direkt klickbar und haben zusaetzlich eine sichtbare `Editieren`-Aktion.
  - Der Guardrail-Selector ist im SSH-Edit-Modus klarer unter `Security & advanced options` auffindbar.
- Verifikation vor Build:
  - Fokus + Release-/Package-Hygiene: `15 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha286`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha286-local.tar`
  - TAR-SHA256: `fa2564b04c90e3c04382fae4989940637084b2ff47e33178811da264a7256f16`
- Image:
  - `fischermanch/aria:0.1.0-alpha.286`
  - `aria:alpha-local`
  - Image-Digest: `sha256:f56a0462de1a4dc5e876209cc3094bf7bceb95bf963a43abf875013729de8e83`
  - Image-Size: `245431676` bytes
  - Created: `2026-05-17T21:35:18.027739094+02:00`
- Update-/Export-Hinweis:
  - Lokales ARIA-Image `alpha284` entfernt; `alpha285` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `31G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha286`

### alpha285

- Interner Build nach `alpha284` mit Guardrail-KI-Working-Status:
  - Das Formular `KI-Vorschlag fuer Guardrail erstellen` zeigt waehrend laengerer LLM-Draft-Erstellung eine kleine Arbeitsanzeige.
  - Die Anzeige nennt grobe Enduser-Schritte wie Kontext pruefen, Verbindungstypen/Profile beruecksichtigen, LLM-Vorschlag anfragen und Review-Entwurf vorbereiten.
  - Keine Debugdaten oder Rohlogs werden im User-Flow angezeigt; die bestehende Serverlogik und UsageMeter-Fakturierung bleiben unveraendert.
- Verifikation vor Build:
  - Fokus + Release-/Package-Hygiene: `19 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha285`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha285-local.tar`
  - TAR-SHA256: `b7d6b2636e5f0ac16d21d96a9f174754d893df3dfbfe7e92d2bc98bd4169449e`
- Image:
  - `fischermanch/aria:0.1.0-alpha.285`
  - `aria:alpha-local`
  - Image-Digest: `sha256:05fd0d5ffd79b4879902ac2af0738ffd284d7df0955043e44599a5e803e1cf55`
  - Image-Size: `245417047` bytes
  - Created: `2026-05-17T15:03:34.32304587+02:00`
- Update-/Export-Hinweis:
  - Lokales ARIA-Image `alpha283` entfernt; `alpha284` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `31G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha285`

### alpha284

- Interner Build nach `alpha283` mit Security-Guardrail-UX-Nachzug:
  - `/config/security` ist in einklappbare Arbeitsbereiche fuer KI-Vorschlag, bestehendes Guardrail, Loeschen, manuelles Erfassen und Samples aufgeteilt.
  - Der KI-Bereich oeffnet automatisch, wenn ein Vorschlag vorhanden ist; riskante Bereiche bleiben getrennt.
  - Guardrail-Draft-LLM-Aufrufe sind explizit gegen UsageMeter/Token-Tracking abgesichert: `source=guardrail_draft`, Intent `llm:draft_ssh_command`.
- Verifikation vor Build:
  - Fokus + Release-/Package-Hygiene: `73 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha284`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha284-local.tar`
  - TAR-SHA256: `c20caa77dca61cf1bd022d6bd1c513f6176dc84599dbc542eab77857258acea6`
- Image:
  - `fischermanch/aria:0.1.0-alpha.284`
  - `aria:alpha-local`
  - Image-Digest: `sha256:909491513ed242f79af463bb6776e4c4eb8f0e2c9417acfc1b3b9d5b6504b743`
  - Image-Size: `245414260` bytes
  - Created: `2026-05-17T13:32:54.077311372+02:00`
- Update-/Export-Hinweis:
  - Lokales ARIA-Image `alpha282` entfernt; `alpha283` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `33G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha284`

### alpha283

- Interner Build nach `alpha282` mit KI-gestuetztem Guardrail-Vorschlagsflow:
  - `/config/security` kann aus natuerlicher Sprache einen Guardrail-Entwurf erzeugen.
  - Der Entwurf nutzt Guardrail-Typ, kompatible Connection-Klassen, vorhandene Guardrails und Connection Action Contract als begrenzten Kontext.
  - Die KI speichert nichts automatisch; der Vorschlag erscheint als editierbare Review-Karte und wird erst durch den bestehenden Guardrail-Speicherpfad aktiv.
  - Deterministische Guardrail-Auswertung bleibt unveraendert.
- Verifikation vor Build:
  - Vollsuite: `1134 passed`
  - Fokus + Release-/Package-Hygiene nach Release-Bump: `66 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha283`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha283-local.tar`
  - TAR-SHA256: `027a211d1b51c84d33c73af8eba64bd432ed3eec6a1bec99770487dd61007764`
- Image:
  - `fischermanch/aria:0.1.0-alpha.283`
  - `aria:alpha-local`
  - Image-Digest: `sha256:61615cd4e4a6af97343060df4a0827fa66fbd9413cbb82c19c08f116f37cf6ff`
  - Image-Size: `245414117` bytes
  - Created: `2026-05-17T13:06:25.079983779+02:00`
- Update-/Export-Hinweis:
  - Lokales ARIA-Image `alpha281` entfernt; `alpha282` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `33G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha283`

### alpha282

- Interner Build nach `alpha281` mit Calendar-Live-Test-Fix:
  - `next` / `nächster Termin` gibt jetzt nur noch den einzelnen naechsten Termin zurueck.
  - `upcoming`, `today`, `tomorrow`, `this_week` und `next_week` bleiben Listen.
- Verifikation vor Build:
  - Vollsuite: `1130 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha282`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha282-local.tar`
  - TAR-SHA256: `a9110d6fa2484b63ddebd9342b9733086115bf541a25aa9425ec2e38277aad17`
- Image:
  - `fischermanch/aria:0.1.0-alpha.282`
  - `aria:alpha-local`
  - Image-Digest: `sha256:8dd1ea9cea54ddca071877f2cb7fe277e4a054c610d6875d31595ffe0167682a`
  - Image-Size: `245386404` bytes
  - Created: `2026-05-17T02:43:28.146272833+02:00`
- Update-/Export-Hinweis:
  - Lokales ARIA-Image `alpha280` entfernt; `alpha281` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `33G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha282`

### alpha281

- Interner Build nach `alpha280` mit Rueckbau des nicht tragfaehigen Google-Calendar-OAuth-/Device-Code-Pfads:
  - Google Calendar nutzt im aktuellen Enduser-Pfad die geheime iCal-Adresse aus Google Calendar.
  - OAuth-Client-JSON, Client-ID, Client-Secret, Refresh-Token, Device-Code und Browser-Redirect wurden aus der aktuellen Calendar-UI und den Calendar-Routes entfernt.
  - ARIA speichert die iCal-URL serverseitig im Secure Store, testet den Feed auf `VCALENDAR` und liest Termine aus `VEVENT`-Eintraegen.
  - Produkt-, Hilfe- und Wiki-Doku zeigen den iCal-read-only-Pfad statt alter Google-Cloud-/OAuth-Anleitungen.
- Verifikation vor Build:
  - Vollsuite vor Release-Bump: `1128 passed`
  - Nach Release-Bump: Vollsuite stoppte nur am erwarteten Release-Hygiene-Abgleich, danach Backlog auf `alpha281` synchronisiert
  - Release-/Package-Hygiene: `11 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - Release-Metadaten im Container: `0.1.0-alpha281`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha281-local.tar`
  - TAR-SHA256: `5255796b2ee3a98c6aa6dec050556cde21744131506da8e99f9c7d729b1e10c9`
- Image:
  - `fischermanch/aria:0.1.0-alpha.281`
  - `aria:alpha-local`
  - Image-Digest: `sha256:34e4922e8d67e10a50a3eea3562fd6f7c3504c59d8cb14b18fd69293dcaacc73`
  - Image-Size: `245386853` bytes
  - Created: `2026-05-17T01:20:59.274808839+02:00`
- Update-/Export-Hinweis:
  - Alte lokale interne ARIA-Images `alpha275` bis `alpha279` entfernt; `alpha280` bleibt als Rollback erhalten.
  - Lokaler Root-Speicher nach Build/Export/Cleanup: ca. `34G` frei.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha281`

### alpha280

- Interner Build nach `alpha279` mit Google-Calendar-Device-Code-Safari-Fallback:
  - OAuth-JSON-Autofill schreibt Client-ID und ein optional vorhandenes Client-Secret weiterhin in die sichtbaren Felder.
  - Zusaetzlich werden dieselben Werte in versteckte Fallback-Felder geschrieben, damit Safari/Form-Submit-Edge-Cases nicht wieder mit `OAuth Client-ID fehlt` enden.
  - Der Backend-Handler akzeptiert diese Fallback-Felder beim Device-Code-Start.
- Verifikation vor Build:
  - Google-Calendar-Fokusblock: `12 passed`
  - Release-/Package-Hygiene: `11 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha280`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha280-local.tar`
  - TAR-SHA256: `cc5c1927a46ec4cf016cf15fd59301048150da172740977f9349a0e817b1dc4f`
- Image:
  - `fischermanch/aria:0.1.0-alpha.280`
  - `aria:alpha-local`
  - Image-Digest: `sha256:85a7a3f7184d686c263c125fbb4aa319de13bc841fb0114a58a4f440d5cb22a4`
  - Image-Size: `245426801` bytes
  - Created: `2026-05-16T23:25:34.070690749+02:00`
- Update-/Export-Hinweis:
  - Alte interne TARs `alpha273` bis `alpha277` entfernt; lokales ARIA-Image `alpha274` entfernt.
  - Lokaler Root-Speicher nach Build/Export: ca. `32G` frei
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha280`

### alpha279

- Interner Build nach `alpha278` mit Google-Calendar-Device-Code-Backend-Fallback:
  - Device-Code-Start liest bei leer injizierter Client-ID die Form nochmal direkt und nutzt den letzten nicht-leeren `client_id`-Wert.
  - Ziel ist der Live-Fall, in dem die Client-ID sichtbar im Feld steht, FastAPI aber trotzdem einen leeren Handler-Parameter liefert.
- Verifikation vor Build:
  - Google-Calendar-Fokusblock: `11 passed`
  - Release-/Package-Hygiene: `11 passed`
  - i18n strict: gruen
  - JSON-i18n-Validierung: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha279`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha279-local.tar`
  - TAR-SHA256: `8d125efc85e7e4f61e149e8129beef99d4a6d095199cef384c261f4ac3ba34ed`
- Image:
  - `fischermanch/aria:0.1.0-alpha.279`
  - `aria:alpha-local`
  - Image-Digest: `sha256:988e26f3b3d1ee340b20f467dbd761ff5682eff6e804d56bc2ec3010f0e82f4b`
  - Image-Size: `245425352` bytes
  - Created: `2026-05-16T17:32:40.896463001+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `/mnt/NAS/aria-images/aria-alpha272-local.tar` entfernt; lokales ARIA-Image `alpha272` entfernt.
  - Lokaler Root-Speicher nach Build/Export: ca. `33G` frei
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha279`

### alpha278

- Interner Build nach `alpha277` mit Google-Calendar-UI-Nachzug:
  - Beim Auswaehlen einer Google OAuth-Client-JSON liest die Setup-Seite die Datei im Browser und fuellt Client-ID sowie ein optional vorhandenes Client-Secret sichtbar in die Formularfelder.
  - Damit ist vor dem Klick auf `Mit Google per Code verbinden` sichtbar, ob ARIA die JSON erkannt hat.
- Verifikation vor Build:
  - Google-Calendar-Fokusblock: `11 passed`
  - Release-/Package-Hygiene: `11 passed`
  - i18n strict: gruen
  - JSON-i18n-Validierung: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha278`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha278-local.tar`
  - TAR-SHA256: `e60ad21e99d497c53cef0b598ecfe3b0845461698de3b79e8cc07adef9469d17`
- Image:
  - `fischermanch/aria:0.1.0-alpha.278`
  - `aria:alpha-local`
  - Image-Digest: `sha256:dd540dfa41a3766f1817422ba3368e230c678e34737ec8a29b8f1b4bf0cc9f69`
  - Image-Size: `245419042` bytes
  - Created: `2026-05-16T15:20:24.530221637+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `/mnt/NAS/aria-images/aria-alpha271-local.tar` entfernt; lokales ARIA-Image `alpha271` entfernt.
  - Lokaler Root-Speicher nach Build/Export: ca. `33G` frei
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha278`

### alpha277

- Interner Build nach `alpha276` mit Google-Calendar-Device-Code-Nachzug:
  - OAuth-Client-JSONs vom Typ `TVs and Limited Input devices` duerfen ohne Client-Secret verwendet werden, solange sie eine Client-ID enthalten.
  - Device-Code-Token-Tausch und Calendar-Refresh senden das Client-Secret nur, wenn es im Profil vorhanden ist.
  - Die Google-Calendar-UI markiert das Client-Secret fuer den Default-Code-Flow als optional und grenzt den Advanced-Browser-Redirect-Pfad klarer ab.
- Verifikation vor Build:
  - Volltest: `1136 passed`
  - Google-Calendar-Fokusblock: `11 passed`
  - Calendar-Runtime-/Connection-Runtime-Fokusblock: `7 passed`
  - Release-/Package-Hygiene: `11 passed`
  - i18n strict: gruen
  - JSON-i18n-Validierung: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha277`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha277-local.tar`
  - TAR-SHA256: `2faa0f4f585172f0ea350ff9fa9a16545aaea5a00109e0c7e0f21b30e186ee8f`
- Image:
  - `fischermanch/aria:0.1.0-alpha.277`
  - `aria:alpha-local`
  - Image-Digest: `sha256:fd17fb73d6d3128000ea23e2e31ea19d789927854933beab6406750b6a5af3d9`
  - Image-Size: `245414965` bytes
  - Created: `2026-05-16T14:54:30.018565209+02:00`
- Update-/Export-Hinweis:
  - Altes internes TAR `/mnt/NAS/aria-images/aria-alpha270-local.tar` entfernt; lokale ARIA-Images `alpha269` und `alpha270` entfernt.
  - Lokaler Root-Speicher nach Build/Export: ca. `34G` frei
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha277`

### alpha276

- Interner Build nach `alpha275` mit Google-Calendar-Setup-Nachzug:
  - Google-Calendar-Setup-Hilfe nennt jetzt explizit den Download der OAuth-Client-JSON aus der Google OAuth-Client-Liste.
  - Neue Google-Calendar-Profile sind mit `primary-calendar` als Connection-Ref vorausgefuellt.
  - Save-, Browser-OAuth- und Device-Code-Handler nutzen serverseitig `primary-calendar`, falls der Browser einen leeren Ref abschickt.
  - Regressionstest deckt den Live-Ausreisser ab: Device-Code-Start mit leerem `connection_ref` darf nicht mehr mit `invalid_ref` abbrechen.
- Verifikation vor Build:
  - Google-Calendar-/Release-/Package-Hygieneblock: `16 passed`
  - i18n strict: gruen
  - JSON-i18n-Validierung: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha276`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha276-local.tar`
  - TAR-SHA256: `80e19744e8c89d79846fae4506ecb0d01683fbd57bcf6979438895e7bf8b78a5`
- Image:
  - `fischermanch/aria:0.1.0-alpha.276`
  - `aria:alpha-local`
  - Image-Digest: `sha256:3005177b3a98780e857f19a9c7ecc49e836373fe3b54534290b88c9b0748222a`
  - Image-Size: `245414510` bytes
  - Created: `2026-05-16T14:34:48.391406338+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha269-local.tar` entfernt
  - Lokaler Root-Speicher nach Build/Export: ca. `34G` frei
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha276`

### alpha275

- Interner Build nach `alpha274` mit Google-Calendar-Device-Code-Flow:
  - `Mit Google per Code verbinden` ist der Default-Selfhosted-Pfad fuer LAN/IP-Installationen ohne Redirect-URI.
  - ARIA ruft Googles Device-Code-Endpunkt auf, zeigt Verification-URL und User-Code, tauscht nach User-Bestaetigung den Device-Code gegen ein Refresh-Token und speichert dieses im Secure Store.
  - Der bestehende Web-Redirect-OAuth-Pfad bleibt als `Advanced: Browser-Redirect` erhalten.
  - Bei zu fruehem Klick auf `Verbindung abschliessen` bleiben Code und Google-URL sichtbar, solange Google noch `authorization_pending` oder `slow_down` meldet.
- Verifikation vor Build:
  - Google-Calendar-/Release-/Package-Hygieneblock: `17 passed`
  - i18n strict: gruen
  - JSON-i18n-Validierung: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha275`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha275-local.tar`
  - TAR-SHA256: `d6e3cc06d5460d90465b40635c283b1d6064a0f50c0e7f9e6c3d852feec45595`
- Image:
  - `fischermanch/aria:0.1.0-alpha.275`
  - `aria:alpha-local`
  - Image-Digest: `sha256:3f37dea85ca848e4f1e974d133a9fdb0e76ea7e15f363a4fe5993d1492b8609a`
  - Image-Size: `245411042` bytes
  - Created: `2026-05-16T12:18:27.23689935+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha268-local.tar` entfernt
  - Lokaler Docker-Build-Cache wurde vor dem Build bereinigt; alte lokale ARIA-Images vor `alpha269` wurden entfernt, Public-Stand `alpha266` und interne `alpha269`-`alpha275` bleiben lokal erhalten.
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha275`

### alpha274

- Interner Build nach `alpha273` mit Multi-Server-Health-Adaptionsnachzug:
  - Formulierungen wie `sind meine server in ordnung` und `are my servers healthy` werden auf den breiten erlaubten Statuscheck gehoben, statt bei blockierbarem `uptime` zu bleiben.
  - Betroffene Variantenfamilie: `server/servern in ordnung`, `server/servern gesund`, `server/servern okay`, `servers healthy`, `servers ok`, `servers okay`, `servers alright`, `servers all good`.
- Verifikation vor Build:
  - Capability-/Pipeline-/Release-/Package-Hygieneblock: `76 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha274`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha274-local.tar`
  - TAR-SHA256: `49aa3a4449b6521a9b76985b5592d9b43e0c44f1bb4a008e41bca8ec3b9ac023`
- Image:
  - `fischermanch/aria:0.1.0-alpha.274`
  - `aria:alpha-local`
  - Image-Digest: `sha256:81649b33f7cf1afb80604c35a3dcc9fd3422ff8d4a21cf5257b5fb93e62acdfa`
  - Image-Size: `245372805` bytes
  - Created: `2026-05-16T03:21:12.134488697+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha267-local.tar` entfernt
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha274`

### alpha273

- Interner Build nach `alpha272` mit Multi-Server-Health-Nachzug:
  - Kurzfragen wie `sind meine server ok` routen wieder in den SSH-Multi-Target-Healthpfad statt in Chat/RAG.
  - Der Router erkennt generisch SSH-Zielwoerter plus Health-Statuswoerter wie `ok`, `okay`, `gesund`, `in Ordnung` oder `healthy`; konkrete Befehlswahl bleibt im bestehenden Agentic-/Guardrail-Pfad.
- Verifikation vor Build:
  - Capability-/Pipeline-/Release-/Package-Hygieneblock: `76 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha273`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha273-local.tar`
  - TAR-SHA256: `a4dfe87cce7d132db2cd8029df762c12af891bf093a32a04f98010013c3220f4`
- Image:
  - `fischermanch/aria:0.1.0-alpha.273`
  - `aria:alpha-local`
  - Image-Digest: `sha256:fdf0497a1527d02c2a0466a940cd0b6f412208a596bcc66503a96b3ad0b09f87`
  - Image-Size: `245371646` bytes
  - Created: `2026-05-16T03:11:36.573814482+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha266-local.tar` entfernt
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha273`

### alpha272

- Interner Build nach `alpha271` mit Chat-Arbeitsstatus-Nachzug:
  - Lang laufende Requests behalten nach dem 8-Sekunden-Fallback den Arbeitstyp, z. B. Serverantworten statt generischem Arbeiten.
  - Fuer Multi-Server-Checks soll die UI nach laengerer Laufzeit `ARIA wartet auf Serverantworten...` statt einer generischen Arbeitsmeldung zeigen.
- Verifikation vor Build:
  - Chat-/Release-/Package-Hygieneblock: `12 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha272`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha272-local.tar`
  - TAR-SHA256: `aa68404dd74849df22a7e6f60709bf14ac68dfdccc62369dcc7ed22b724ecc48`
- Image:
  - `fischermanch/aria:0.1.0-alpha.272`
  - `aria:alpha-local`
  - Image-Digest: `sha256:b568e7b1b0c11904ca34d6fa67b246a1908a918fb54ae5fe946bb274aa051c39`
  - Image-Size: `245372712` bytes
  - Created: `2026-05-16T02:51:44.655553589+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha265-local.tar` entfernt
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha272`

### alpha271

- Interner Build nach `alpha270` mit Chat-UX-Nachzug:
  - Chat-Frontend zeigt waehrend laufender Requests grobe, enduser-taugliche Arbeitsmeldungen wie Server pruefen, Feeds lesen, Dateien/Shares durchsuchen, Nachricht vorbereiten oder Ergebnis zusammenfassen
  - Haupt-Chatansicht nutzt den verfuegbaren Viewport dynamischer aus; der Nachrichtenbereich waechst mit dem Screen, der Composer bleibt darunter
- Verifikation vor Build:
  - Chat-/Release-/Package-Hygieneblock: `12 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - CSS-Brace-Check: gruen
  - JSON-i18n-Validierung: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha271`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha271-local.tar`
  - TAR-SHA256: `b7de4594b91c2c18af147ce0f9d22407d07eda369cfa3cb724cdeee33189a434`
- Image:
  - `fischermanch/aria:0.1.0-alpha.271`
  - `aria:alpha-local`
  - Image-Digest: `sha256:0acaf5e07318b815a0572a3192d04ca3710e6c61e3ac9b8f8503e078272fbd66`
  - Image-Size: `245372189` bytes
  - Created: `2026-05-16T02:12:26.647924401+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha264-local.tar` entfernt
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha271`

### alpha270

- Interner Build nach `alpha269` mit Agentic-/Provider-Fundament, Healthcheck- und Mobile-Nachzug:
  - Connection Action Contract und Provider Manifest tragen planner roles, confirmation/sensitive-content/draft metadata und optionale Draft-Capability
  - generisches Agentic Content Access Request/Result Modell plus Registry fuer Read/Search/List-Provider vorbereitet und optional in den Pipeline-Orchestrator eingehaengt
  - breite Multi-Server-Healthfragen wie `wie geht es meinen servern` werden auf den staerksten ueber alle SSH-Ziele erlaubten Read-only-Statuscheck gehoben, bevorzugt `uptime -p && df -h && free -h`
  - iPhone-/Mobile-UI-Fix: offener CSS-Block im 640px-Bereich geschlossen, iOS Safe-Area-Viewport aktiviert und mobile Formularfelder gegen Safari-Zoom stabilisiert
  - Dokumentation unter `docs/` konsolidiert; lokale Handoff-/History-Dateien liegen ignoriert unter `docs/local/`
- Verifikation vor Build:
  - Multi-Server-Health-/Guardrail-Regressionsblock: `4 passed`
  - Content-Access-/Provider-/Release-/Package-Hygieneblock: `33 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
  - Release-Metadaten im Container: `0.1.0-alpha270`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha270-local.tar`
  - TAR-SHA256: `ca4205ad99fbb49b9caddfb691e8bbc75d507e6ed4e95f4dacb2c3e0cbc029d3`
- Image:
  - `fischermanch/aria:0.1.0-alpha.270`
  - `aria:alpha-local`
  - Image-Digest: `sha256:e8faf0a9f02e78b64e0c758570e023bc3f55cb5d0452bb520851f931dcbed82d`
  - Image-Size: `245369167` bytes
  - Created: `2026-05-16T01:48:53.322511477+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha263-local.tar` entfernt
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha270`

### alpha269

- Interner Build nach `alpha268` mit Kapazitaetscheck- und UI-Badge-Nachzug:
  - vage Multi-Server-Kapazitaetsfragen werden vom generischen `uptime` auf den staerksten ueber alle SSH-Ziele erlaubten Read-only-Kapazitaetscheck gehoben
  - bevorzugter Multi-Target-Read-only-Check ist `uptime -p && df -h && free -h`, mit deterministischem Fallback auf schmalere erlaubte Checks
  - teilweise blockierte SSH-Aktionen werden in der Chat-UI nicht mehr als `memory_error` gelabelt
- Verifikation vor Build:
  - fokussierter Vorbuild-Regressions-/Releaseblock: `11 passed`
  - vorheriger breiter Pipeline-Block fuer den Fix: `186 passed`
  - Router-/Error-Block: `116 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - `py_compile`: gruen
  - Release-Metadaten im Container: `0.1.0-alpha269`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}` und Docker-Health ist `healthy`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha269-local.tar`
  - TAR-SHA256: `76332a3997fa35ec1c750b884120cef82ea0a8ae8d843e790fbbaa725364bd1a`
- Image:
  - `fischermanch/aria:0.1.0-alpha.269`
  - `aria:alpha-local`
  - Image-Digest: `sha256:6d0bac4a3c2bb958b6ea7287d7bd45d6f46115c052dcae5366faa291f118d391`
  - Image-Size: `245281003` bytes
  - Created: `2026-05-16T00:26:33.122570003+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha262-local.tar` entfernt
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha269`

### alpha268

- Interner Build nach `alpha267` mit SSH-Disk-Prompt-Regressionsfix und LLM-first Capability-Draft-Hardening:
  - gemischtsprachige Formulierungen wie `all meinen server` werden als pluraler SSH-Ziel-Scope erkannt
  - `harddisk` und `speicher frei` zaehlen als natuerliche SSH-Disk-Signale
  - ein bounded LLM-Capability-Draft-Fallback faengt operative Remote-Formulierungen ab, die deterministisch kein Capability-Draft erzeugen
  - der Pre-RAG-Gate kann falsche `memory_store`-Keyword-Treffer durch bounded LLM-Capability-Klassifikation ueberstimmen
  - Policy, Guardrails, Auth, Runtime und Validierung bleiben deterministisch
- Verifikation vor Build:
  - voller Regressionslauf: `1119 passed`, 4 bekannte aiohttp/Python-Deprecation-Warnings
  - fokussierter Release-/Package-/Agentic-/Provider-Hygieneblock: `18 passed`
  - Release-/Package-Metadaten nach Version-Bump: `9 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Release-Metadaten im Container: `0.1.0-alpha268`
  - Container-Smoke-Test: Docker-Health prueft `/health` mit HTTP 200
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha268-local.tar`
  - TAR-SHA256: `980e8116529ffdbc32597748a9725748efe643f21f0bd04abe1edfad2c798bb0`
- Image:
  - `fischermanch/aria:0.1.0-alpha.268`
  - `aria:alpha-local`
  - Image-Digest: `sha256:9287ab82bf5a8c444322da6001178b75c6567c2a4d43edd7822a4fb8525a9e74`
  - Image-Size: `245266081` bytes
  - Created: `2026-05-15T23:48:23.219254369+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha261-local.tar` entfernt
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha268`

### alpha267

- Interner Build nach `alpha266` mit dem ersten kontrollierten Agentic-Enduser-Helfer-Hardening:
  - Agentic Flow Map und Debug-Boundaries fuer Kontext-Enrichment, bounded Draft und Runtime-Execution nachgezogen
  - Learned-Recipe-Promotion-Gates fuer Multi-Target-Scope, Side-Effects und Contract-Mismatch gehaertet
  - generischer Agentic Execution Handler Contract mit Registry, Learning-Service, SSH-Multi-Target-Adapter und RSS-Feed-Adapter eingefuehrt
  - internes Connection Provider Manifest Modell mit Export/Validator und Contract-Tests vorbereitet
- Verifikation vor Build:
  - voller Regressionslauf: `1116 passed`, 4 bekannte aiohttp/Python-Deprecation-Warnings
  - fokussierter Release-/Package-/Agentic-/Provider-Hygieneblock: `18 passed`
  - `py_compile` fuer neue Agentic-/Provider-Module: gruen
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Runtime-Constraints im Container entsprechen `constraints/runtime.txt`
  - Release-Metadaten im Container: `0.1.0-alpha267`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha267-local.tar`
  - TAR-SHA256: `adf506d083b1bc422975208011d0d92968e22a0af15fd9062ca724ce91c51f7b`
- Image:
  - `fischermanch/aria:0.1.0-alpha.267`
  - `aria:alpha-local`
  - Image-Digest: `sha256:d9ad21e15827ec9ead4382459def8e38c908c7c6d18442149ced55daed456d45`
  - Image-Size: `245264614` bytes
  - Created: `2026-05-15T21:19:16.323653011+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha260-local.tar` entfernt
- Public-Hinweis:
  - kein Git Commit, kein Git Tag, kein Public Docker Push und kein GitHub Release fuer `alpha267`

### alpha266

- Public-Release-Kandidat nach `alpha265` mit finalem Learned-Recipes-Layout-Polish:
  - `/recipes/learned` rendert Review-Karten einspaltig/layout-stabil
  - lange LLM-Curator-Felder werden in strukturierte Details, Trigger-Chips und Limit-Listen verpackt
  - alte `file_list`-Learnings werden als `SMB List Files` / `SFTP List Files` statt `Read File` angezeigt
  - Public-Dokus, Help/Wiki-Quellen, Docker-Hub-Text und Release Notes sind auf `0.1.0-alpha266` nachgezogen
- Verifikation vor Build/Publish:
  - voller Regressionslauf: `1098 passed`, 4 bekannte aiohttp/Python-Deprecation-Warnings
  - i18n strict: gruen
  - `git diff --check`: gruen
  - normalisierter Dependency-Check: `85` Constraints, `85` installierte Pakete, keine Missing/Extra
  - CLI-Version im Container: `0.1.0-alpha266`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha266-local.tar`
  - TAR-SHA256: `bebe761da8470f6851788d75d4dda0cb770151d181ee7237ab4aac0e48792dcd`
- Image:
  - `fischermanch/aria:0.1.0-alpha.266`
  - `fischermanch/aria:alpha`
  - `aria:alpha-local`
  - Image-Digest: `sha256:528ea0ef93eb346811542e85b46f671461a0d9b49e32385f48c52b7056c7a45d`
  - Image-Size: `245139758` bytes
  - Created: `2026-05-15T13:59:46.616539877+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha259-local.tar` entfernt


### alpha265

- enthaelt den Dependency-Pinning-/Locking-Nachzug nach `alpha264`:
  - Docker-Release-Builds pinnen Python- und Docker-CLI-Base-Images per Digest
  - Runtime-Dependencies werden ueber `constraints/runtime.txt` aus dem getesteten `alpha264`-Container fixiert
  - Docker installiert mit gepinntem `pip==25.0.1`, `setuptools==80.9.0`, `wheel==0.45.1` und `--no-build-isolation`
  - `pip freeze --all` im fertigen Image matched `constraints/runtime.txt` fuer `85` Pakete
- Verifikation:
  - voller Vorbuild-Regressionslauf vor Version-Bump: `1097 passed`, 4 bekannte aiohttp/Python-Deprecation-Warnings
  - Release-/Update-/Stats-Regressionsblock nach Version-Bump: `66 passed`, 4 bekannte aiohttp/Python-Deprecation-Warnings
  - i18n strict: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha265`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha265-local.tar`
  - TAR-SHA256: `88151e0d05eb8f11466c76bb759aa632208a64162a715d08c3d546d90fc97182`
- Image:
  - `fischermanch/aria:0.1.0-alpha.265`
  - `aria:alpha-local`
  - Image-Digest: `sha256:e1e0d5f4f172edaddb5266f7a7189c6a06e242c3d473dc24612f49fd072c3a39`
  - Image-Size: `245137172` bytes
  - Created: `2026-05-15T00:36:37.57545884+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha258-local.tar` entfernt
- Beobachtung:
  - Python-Dependencies und Base-Image-Digests sind jetzt reproduzierbar fixiert; Debian-`apt`-Pakete kommen weiterhin aus den normalen Debian-Repos und waeren erst mit Snapshot-Repos voll eingefroren.

### alpha264

- enthaelt den Antwortqualitaets-Nachzug nach dem `alpha263`-Live-Test:
  - RSS-Runtime-Transportlimit skaliert jetzt mit dem angefragten Digest-Count, damit `10 News` nicht vor der Chat-Zusammenfassung auf 8 sichtbare Eintraege abgeschnitten wird
  - Chat-Markdown rendert Link-Labels mit eckigen Klammern, z.B. Exploit-DB `[[webapps] ...](...)`
  - Guardrail-Review-Hinweise behalten neben dem klickbaren Markdown-Link auch den sichtbaren `/config/security?guardrail_ref=...`-Pfad
- Verifikation:
  - Vorbuild-Regressionsblock: `114 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha264`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha264-local.tar`
  - TAR-SHA256: `a5118690a2b909272e1f0e22e8d2b32b546a2d80ecff06b864821d264f09a6f0`
- Image:
  - `fischermanch/aria:0.1.0-alpha.264`
  - `aria:alpha-local`
  - Image-Digest: `sha256:5c3d4d832b99d4a5908566cfc9a95c7e7fdb942a9666fd590ac997107a53bc27`
  - Image-Size: `243495940` bytes
  - Created: `2026-05-14T15:40:46.618634695+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha257-local.tar` entfernt
- Beobachtung:
  - Dependency-Drift bleibt wie bei `alpha263`: Docker zieht neuere nicht gepinnte transitive Model-Gateway-Abhaengigkeiten (`litellm`, `openai`, `aiohttp`, `pydantic`). Vor Public weiter als Release-Hygiene-Punkt behandeln.

### alpha263

- enthaelt den Performance-/Antwortqualitaets-Nachzug nach `alpha262`:
  - Learned-Recipe-Curator und Recipe-Experience-Memory laufen nach erfolgreicher Antwort im Hintergrund, damit Chat-Antworten nicht auf Curation-LLM oder Memory-Embedding warten
  - RSS-Gruppenfeeds werden bounded parallel gelesen statt seriell, sodass einzelne langsame Feeds/Timeouts nicht mehr additiv die gesamte Digest-Antwort blockieren
  - RSS-Link-Parsing erhaelt `Link:`-Zeilen auch fuer Titel mit bracketed Markdown-Labels wie Exploit-DB `[webapps]`
  - Guardrail-Review-Referenzen werden als Markdown-Link auf `/config/security?guardrail_ref=...` gerendert
  - File-Listen trennen Ordner von Datei-Beispielen, damit SMB/SFTP-Folder-Listings lesbarer werden
- Verifikation:
  - Vorbuild-Regressionsblock: `254 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha263`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha263-local.tar`
  - TAR-SHA256: `7ea7f28b2adc13f55376d17fb9a4d17fe523a5652c315f5e8b4765d3b5d55d20`
- Image:
  - `fischermanch/aria:0.1.0-alpha.263`
  - `aria:alpha-local`
  - Image-Digest: `sha256:26e945926d41670008cd6f3a8ddd77d8ef47cff07805e3a218cbb8ff3e2f007d`
  - Image-Size: `243490656` bytes
  - Created: `2026-05-14T11:11:10.222342563+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha256-local.tar` entfernt
- Beobachtung:
  - Docker zog beim Build neuere nicht gepinnte transitive Model-Gateway-Abhaengigkeiten als bei `alpha262` (`litellm`, `openai`, `aiohttp`, `pydantic`); vor Public sollte Dependency-Pinning/Locking als eigener Release-Hygiene-Punkt bewertet werden.

### alpha262

- enthaelt die Update-Downtime-Reconnect-Shell nach `alpha261`:
  - ARIA registriert einen Service Worker mit Scope `/`
  - Navigation waehrend der kurzen ARIA-Container-Recreate-Downtime bekommt eine kleine mehrsprachige Warteseite statt einer harten Browser-Fehlerseite
  - die Warteseite pollt `/health` und laedt die urspruengliche Zielseite wieder, sobald ARIA erreichbar ist
  - der Effekt greift erst ab dem Update nach der ersten erfolgreichen `alpha262`-Seitenladung, weil der Browser den Service Worker vorher noch nicht registriert haben kann
- Verifikation:
  - Vorbuild-Regressionsblock: `232 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha262`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha262-local.tar`
  - TAR-SHA256: `e0056ae2046138b95414ff98a00ea7ae7d520d286ffe1b76171fe8fdcccaea7e`
- Image:
  - `fischermanch/aria:0.1.0-alpha.262`
  - `aria:alpha-local`
  - Image-Digest: `sha256:47cb1a81cb7e9f6a3771c639d9f4c12f3871950e14a727877ad1181db78d861f`
  - Image-Size: `242651151` bytes
  - Created: `2026-05-14T01:56:53.694720543+02:00`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha255-local.tar` entfernt

### alpha261

- enthaelt den SSH-Policy-Block-Fast-Path nach `alpha260`:
  - die LLM erkennt weiter die beabsichtigte SSH-Aktion
  - sobald Policy/Guardrail blockiert, baut ARIA die finale Safety-Antwort deterministisch und schnell
  - fehlende Guardrail-Review-Links werden aus der selektierten Connection nachgezogen
  - der Debug-Pfad zeigt `blocked_action_explanation agentic_source=deterministic_fallback reason=ssh_policy_block_fast_path`
- Verifikation:
  - Vorbuild-Regressionsblock: `204 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha261`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha261-local.tar`
  - TAR-SHA256: `565cc20a98658c7b82f00566d97a79ca856962edba75af061e5c30d80df2383b`
- Image:
  - `fischermanch/aria:0.1.0-alpha.261`
  - `aria:alpha-local`
  - Image-Digest: `sha256:2eff4eb101e80a74e47492dd24fef3a8e266bbd8045c4432fd9af67305911c92`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha254-local.tar` entfernt

### alpha260

- enthaelt den Block-Erklaerungs-Performance-Fix nach `alpha259`:
  - Block-Erklaerungs-LLM hat ein kurzes Timeout mit deterministischem Fallback
  - klar mutierende SSH-Blocks ueberspringen `ssh_guardrail_intent`, sobald Policy bereits blockiert hat
  - Guardrail-Review wird als sichtbare Plain-URL ausgegeben
- Verifikation:
  - Vorbuild-Regressionsblock: `230 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha260`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha260-local.tar`
  - TAR-SHA256: `2217fd9339b74db45fcd4f9555a06bb69516fd9996024772fddfed59273a8637`
- Image:
  - `fischermanch/aria:0.1.0-alpha.260`
  - `aria:alpha-local`
  - Image-Digest: `sha256:3e20513b27e622c3f476f27f6e5913a6de91e861320dfb2e31c6c35200aa3abf`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha253-local.tar` entfernt

### alpha259

- enthaelt den Block-Erklaerungs-Polish nach `alpha258`:
  - live formulierte geplante Aktionen werden nicht mehr doppelt angehaengt
  - schwache Guardrail-Referenzen wie `Guardrail pruefen/anpassen: ssh-healtcheck` werden durch den kanonischen `/config/security?guardrail_ref=...`-Link ersetzt
  - Regressionstest pinnt den DNS-Restart-Live-Ausreisser
- Verifikation:
  - Vorbuild-Regressionsblock: `194 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha259`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha259-local.tar`
  - TAR-SHA256: `dc2a6fad0c870ef61b933f5f4853fd5de8ecf5c9d52360f18aca89a5f8f77d2c`
- Image:
  - `fischermanch/aria:0.1.0-alpha.259`
  - `aria:alpha-local`
  - Image-Digest: `sha256:e6dc82f3584ca5faf0fc7c9e4b8fe65aede37a86b20e6f0b055e0ac24e12ea2a`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha252-local.tar` entfernt

### alpha258

- enthaelt den Block-Erklaerungs-Nachzug nach `alpha257`:
  - geblockte Policy-/Guardrail-Aktionen behalten die deterministische Block-Entscheidung
  - die User-Antwort wird danach ueber einen bounded LLM-Schritt erklaert, statt nur statisch `wuerde blockieren` zu formulieren
  - geplante Aktion/Command bleibt sichtbar
  - bei aktivem Guardrail-Profil wird direkt auf `/config/security?guardrail_ref=...` verlinkt
  - LLM-/Fallback-Pfad ist in Debug als `blocked_action_explanation` sichtbar
- Verifikation:
  - Vorbuild-Regressionsblock: `193 passed`
  - Pipeline-Regression komplett: `185 passed`
  - Block-/Guardrail-/Agentic-Regressionen: `37 passed`
  - i18n strict: gruen
  - `py_compile`: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha258`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha258-local.tar`
  - TAR-SHA256: `6da0fbcc45626de2d6366a6ec500b2bbaf8464973e817601c90b6285768f9b5e`
- Image:
  - `fischermanch/aria:0.1.0-alpha.258`
  - `aria:alpha-local`
  - Image-Digest: `sha256:041925547a62e8c8b1011071f24c28f773aef2bfd72a13928b26d485485a3420`
- Update-/Export-Hinweis:
  - Export-Script hat wegen `KEEP_TARS=7` das alte interne TAR `/mnt/NAS/aria-images/aria-alpha251-local.tar` entfernt

### alpha257

- enthaelt den Modularitaets-/Memory-/Recipes-Nachzug nach `alpha256`:
  - `/recipes/learned` rendert die Flow-Erklaertexte dezenter, damit die leere Learned-Recipe-Ansicht ruhiger wirkt
  - `/memories`, `/memories/map` und `/stats` nutzen einen zentralen Qdrant-Collection-Classifier
  - `aria_recipe_experience_*` und zukuenftige unbekannte `aria_*`-System-Collections bleiben automatisch sichtbar
  - codebase-weiter Modularitaetscheck zentralisiert Routing-Workbench-Optionen, Pending-Route-Kinds, Qdrant-Routing-Kinds, Pipeline-Capability-Gate, Guardrail-Kind-Mapping sowie Agentic Read/Message-Familien auf Connection Catalog / Connection Action Contract
  - Audit-Dokument: `docs/product/codebase-modularity-audit-alpha257.md`
- Verifikation:
  - gezielter Vorbuild-Regressionsblock: `376 passed`
  - i18n strict: gruen
  - `py_compile` fuer geaenderte Runtime-/Web-Module: gruen
  - `git diff --check`: gruen
  - CLI-Version im Container: `0.1.0-alpha257`
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha257-local.tar`
  - TAR-SHA256: `ef67d1d9c4c5c155a3cb5beafc9bbd94a6d1a53aa3ab48e77b28e06314f04463`
- Image:
  - `fischermanch/aria:0.1.0-alpha.257`
  - `aria:alpha-local`
  - Image-Digest: `sha256:960921f81fe8537ae738a1ff34361694eff0969fef2b0c4d98f649cc6e7c1bb0`
  - Image-Size: `242617896` bytes
  - Created: `2026-05-13T23:34:02.600357358+02:00`
- Release-Label:
  - `0.1.0-alpha257`

### alpha256

- enthaelt den Self-Learning-/RSS-Nachzug nach `alpha255`:
  - Learned-Recipe-Delete entfernt jetzt den lokalen Review-Kandidaten und passende Recipe-Experience-Memory-Punkte in Qdrant fuer den aktuellen User
  - Delete bleibt best-effort fuer Qdrant: der lokale Admin-Delete wird nicht zurueckgerollt, aber ein Purge-Fehler bleibt sichtbar/debugbar
  - RSS-Digest-Planung extrahiert explizite Count-/Detail-Wuensche bounded LLM-first und uebergibt sie an die read-only RSS-Runtime
  - RSS-Gruppenreads sammeln mehrere Eintraege pro Feed bis zur sicheren Obergrenze, statt immer nur einen Eintrag pro Feed zu zeigen
  - RSS-Antworten erklaeren Anfrage-/Ergebnisluecken wie angefragt, angezeigt, gefunden/lesbar und ausgelassen
- Verifikation:
  - gezielter Regressionsblock: `232 passed`
  - kompletter Testlauf: `1077 passed, 4 warnings`
  - i18n strict: gruen
  - `py_compile` fuer geaenderte Runtime-Module: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `{"status":"ok"}`
  - CLI-Version: `0.1.0-alpha256`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha256-local.tar`
  - TAR-SHA256: `2f3c6688a2501f8ba7fa12e3caa6e3c2f892afab27a2ecda044ee20bd28a9f1d`
- Image:
  - `fischermanch/aria:0.1.0-alpha.256`
  - `aria:alpha-local`
  - Image-Digest: `sha256:8474da472da22fddca88ccde7152b7a8d1a8593e046c80493b3185f7a9d0939b`
  - Image-Size: `242578057` bytes
  - Created: `2026-05-13T22:50:02.221231124+02:00`
- Release-Label:
  - `0.1.0-alpha256`

### alpha255

- enthaelt den Self-Learning-/Recipes-Nachzug nach `alpha254`:
  - Learned Recipes zeigen Curator-Debug mit Quelle, Policy, Status, Zeitpunkt und Skip-/Fehlergrund
  - gelernte Erfolgslaeufe bekommen qualitative Lernsignale: neues Muster, Wiederholung, Formulierungsvariante, Scope-Variante, Aktionsvariante und riskante Abweichung
  - Review-Reife nutzt gewichtete Lern-Evidenz statt nur rohe Run-Anzahl
  - Recipe Experience Memory transportiert Lernsignal und Evidenz als context-only Planner-Kontext
  - riskante Aktionsabweichungen ueberschreiben nicht automatisch die bisher gelernte Aktion
- Verifikation:
  - Vorbuild-Regressionsblock: `55 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` 200
  - CLI-Version: `0.1.0-alpha255`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha255-local.tar`
  - TAR-SHA256: `2bdf7997b1c94511545a4f2a904b5ae398a3245b584a591415c847483a3e35e2`
- Image:
  - `fischermanch/aria:0.1.0-alpha.255`
  - `aria:alpha-local`
  - Image-Digest: `sha256:38213cd916f0708c9fa8c545534d91b9dec03df1b7ab397e73f21d46461d377b`
  - Image-Size: `242536838` bytes
  - Created: `2026-05-13T13:42:51.648344968+02:00`
- Release-Label:
  - `0.1.0-alpha255`

### alpha254

- repariert den `alpha253`-Nachzug:
  - Multi-Target-SSH LLM-Summaries nutzen jetzt den zentralen `LLMClient` ohne unsupported per-call `temperature`-Argument
  - wenn der Summary-Call ausfaellt, bleibt ein Debug-Hinweis sichtbar statt still auf die alte deterministische Summary zurueckzufallen
  - erwartet im Live-Test: Tokens/Kosten > 0 und Debug-Zeile `multi_target_ssh_summary agentic_source=llm_decision`
- Verifikation:
  - Vorbuild-Regressionsblock: `11 passed`
  - i18n strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` 200
  - CLI-Version: `0.1.0-alpha254`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha254-local.tar`
  - TAR-SHA256: `fa84f8f06fbf516860b66798def546f126eaca523e5270f2321ab19afeda421f`
- Image:
  - `fischermanch/aria:0.1.0-alpha.254`
  - `aria:alpha-local`
  - Image-Digest: `sha256:677cd3f044cbb913e1abf470819832b8c17e3f897d41be0b1c16c1fcac62a06e`
  - Image-Size: `242470698` bytes
  - Created: `2026-05-13T00:54:20.480574858+02:00`
- Release-Label:
  - `0.1.0-alpha254`

### alpha253

- enthaelt den LLM-backed Multi-SSH-Operator-Summary-Nachzug:
  - Multi-Target-SSH fuehrt weiter nur erlaubte Read-only-Kommandos aus
  - danach fasst ein bounded LLM-Schritt die echten Runtime-Resultate gegen die Userfrage zusammen
  - deterministische freie-Festplatten-Schwellen bleiben nur als Fallback/Guardrail erhalten
  - Architektur-Leitplanke dokumentiert: Flexibilitaet ist LLM-first; deterministisch bleibt fuer Sicherheit, Normalisierung, Preflight, Policy/Guardrail und Fallbacks
- Verifikation:
  - Vorbuild-Regressionsblock: `11 passed`
  - i18n-Code-Literal-Audit strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha253`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha253-local.tar`
  - TAR-SHA256: `1104500a59c900f1ab8a75cd6a5d7a2d12709fa880e22cf11ec8c18de7181251`
- Image:
  - `fischermanch/aria:0.1.0-alpha.253`
  - `aria:alpha-local`
  - `sha256:024838b1e509eb3e4286d0c8d9898805b7b9b0210fbb627a9c86cf334c9f5c96`
- Release-Label:
  - `0.1.0-alpha253`

### alpha252

- enthaelt den Backlog-Abschluss nach `alpha251`:
  - Agentic-/Recipe-/Connection-/Observability-Guardrails sind im Backlog nur noch als Dauerleitplanken gefuehrt
  - Recipe-UX-Metadaten, Review-Reife und Recipe-Result-Zaehler sind enthalten
  - Connection Action Contracts exportieren Manifest-Zeilen fuer spaetere deklarative Provider-Manifeste
  - `/stats` Operator Guardrail hat stabile Row-Keys
  - Legacy-/Recipe-Kompatibilitaet hat ein explizites Migration-Gate
- Verifikation:
  - Vorbuild-Regressionen: `81 passed`
  - i18n-Code-Literal-Audit strict: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha252`
  - Live-Smoke-Test nach internem Update: gruen
    - Multi-Target SSH-Festplattencheck: `13/13` unauffaellig, kompakte Operator-Zusammenfassung
    - RSS-Security-News: Eintraege mit Link, Quelle, Zeit und Kurztext sichtbar
    - SSH-Guardrail: DNS-Restart korrekt blockiert
    - HTTP-API-Check: `n8n-test-http-api` ok
    - Discord-One-Click: Bestaetigung per Button sendet erfolgreich
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha252-local.tar`
  - TAR-SHA256: `a87cd56401dc8d7dc670de4e64c25e484bce7563577628cdc2effede2555c6e7`
- Image:
  - `fischermanch/aria:0.1.0-alpha.252`
  - `aria:alpha-local`
  - `sha256:266fe7c0d712af0ae74f5b57b77fc9acc8088288235213f1cbe2bd49a7388b83`
- Release-Label:
  - `0.1.0-alpha252`

### alpha251

- enthaelt den letzten Public-Update-Safety-Nachzug:
  - `docker/aria-host-update.sh` prueft veroeffentlichte Compose-Host-Ports vor dem Service-Recreate
  - wenn der neue Compose-Plan z.B. Port `8800` nutzen will, dieser Port aber von einem anderen Prozess belegt ist, bricht der Helper vor Veraenderungen am ARIA-Service ab
  - isolierter Managed-Stack-Test auf Port `18831`: nur `aria` wurde recreated; Qdrant, SearXNG und Valkey behielten ihre Container-IDs
- Verifikation:
  - kompletter Testlauf: `1023 passed`
  - i18n-Code-Literal-Audit strict: gruen
  - `python -m compileall aria`: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha251`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha251-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.251`
  - `aria:alpha-local`
  - `sha256:3aacbe8145da283dddaeb9c8cdef0b56961b05119770df1871570f0e26388321`
- Release-Label:
  - `0.1.0-alpha251`

### alpha250

- enthaelt die kleinen Nachzuege aus dem `alpha249`-Live-Test:
  - RSS-Digests zeigen den Link jetzt zusaetzlich als eigene `Link:`-Zeile, damit kopierter Chat-Text die URL sicher enthaelt
  - pluraler SSH-Zielparser entfernt Artikelreste wie `requested_ref=n server`
- Verifikation:
  - RSS-/Router-/Pipeline-/Release-Hygiene-Vorbuild: `256 passed`
  - `python -m compileall aria`: gruen
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha250`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha250-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.250`
  - `aria:alpha-local`
  - `sha256:6169fdcfff5a2d0f39de4d073c7455a34db77b87ea654cf7116553974792a6ad`
- Release-Label:
  - `0.1.0-alpha250`
- Live-Testplan nach Deployment:
  - RSS-Security-News: Hauptantwort muss pro Eintrag `Link: https://...` enthalten
  - Multi-Target SSH: Debug soll kein `requested_ref=n server` mehr zeigen

### alpha249

- enthaelt die Nachzuege aus dem `alpha248`-Live-Test
- RSS-Digest-Praesentation:
  - Kategorie-/Gruppenfeeds behalten jetzt klickbare Links, Quelle, Zeitstempel und Kurztext im Chat-Haupttext
  - die alte Ein-Zeilen-Zusammenfassung bleibt nicht mehr der einzige sichtbare Nutzen fuer den User
- Public-Update-Safety:
  - der generierte Managed-Stack-Helper `aria-stack.sh update` pullt/recreatet jetzt nur noch den `aria` Service
  - stateful Sidecars wie Qdrant/SearXNG werden im normalen Update-Pfad nicht mehr recreated
  - `repair` und `update-all` bleiben die bewussten Full-Stack-Pfade
  - der Host-Update-Helper kann per `--target-image` alte Fixed-Tag-Installs gezielt auf ein neues Image heben, ohne den alten in-stack Helper auszufuehren
  - Managed-Stack-Dateien werden dabei aus dem Ziel-Image refreshed und danach wieder auf die urspruengliche Datei-Owner-ID gesetzt
  - echte Alt-zu-Neu-Probe vor Build mit temporaerem `alpha167`-Managed-Stack: nur `aria` wurde recreated; Qdrant, SearXNG und Valkey blieben mit gleicher Container-ID laufen
- Verifikation:
  - RSS-/Pipeline-/Release-Hygiene-Vorbuild: `203 passed`
  - Update-Helper-/Host-Update-/Managed-Setup-/Update-UI-/Release-Hygiene-Tests: `36 passed`
  - `python -m compileall aria`: gruen
  - `git diff --check`: gruen
  - Docker-Skript-Syntax: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha249`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha249-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.249`
  - `aria:alpha-local`
  - `sha256:7c9a875daba4991020b09961641ddeb11b8d553ec3f20be0719073bf5cc19173`
- Release-Label:
  - `0.1.0-alpha249`
- Live-Testplan nach Deployment:
  - RSS-Security-News: Hauptantwort muss mehrere Eintraege mit klickbarem Link, Quelle, Zeit/Kurztext zeigen
  - Update-Button: interner Update-Pfad soll `aria-alpha249-local.tar` nutzen und nur `aria` ersetzen
  - Regression: Multi-Target SSH, DNS-Restart-Block, Management-HD, DNS-Health, API-Check, Discord-One-Click, SMB-Root-Listing

### alpha248

- enthaelt den Operator-Summary-Nachzug aus dem `alpha247`-Live-Test
- Multi-Target SSH:
  - all-ok Flottenchecks geben im Chat nur noch ein kompaktes Operator-Fazit aus, z. B. `Gesamt: 13/13 SSH-Ziele unauffaellig. Kein Handlungsbedarf.`
  - gemischte Multi-Target-Ergebnisse zeigen im Chat nur noch Auffaelligkeiten, blockierte Ziele und Fehler
  - OK-Hostdetails bleiben in der technischen Detailspur erhalten
  - Regression nutzt das Live-Wording: `check mal die festplatten von meinen server und melde mir falls handlungsbedarf besteht`
- Verifikation:
  - finaler Vor-Build-Regressionsblock: `317 passed`
  - `python -m compileall aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha248`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha248-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.248`
  - `aria:alpha-local`
  - `sha256:5c8643293a062dbbb009fa4a293df689ca9c9a6688504d94e1825fe33142f9a3`
- Release-Label:
  - `0.1.0-alpha248`
- Live-Testplan nach Deployment:
  - `check mal die festplatten von meinen server und melde mir falls handlungsbedarf besteht`: kompakte all-ok Antwort mit `Kein Handlungsbedarf`
  - Details pruefen: alle SSH-Ziele sollen weiterhin in der technischen Spur sichtbar bleiben
- Live-Test nach Deployment:
  - `check mal die festplatten von meinen server und melde mir falls handlungsbedarf besteht`: `13/13` SSH-Ziele geprueft, kompakte all-ok Antwort mit `Kein Handlungsbedarf`
  - Details enthalten weiterhin alle 13 SSH-Runtime-Ausfuehrungen
  - Plural-Scope gewinnt korrekt gegen einen einzelnen semantischen LLM-Zielvorschlag
  - Nachzuege fuer spaeter: `requested_ref=n server` Parser-Artefakt und Guardrail-ID `ssh-healtcheck`

### alpha247

- enthaelt den Live-Test-Nachzug aus `alpha246`
- Multi-Target SSH:
  - Live-Test-Befund: `check mal ob meine server noch genug festplatten platz haben` blieb in `alpha246` weiterhin in der SSH-Profil-Rueckfrage haengen
  - Ursache: der plurale SSH-Scope wurde zwar erkannt, aber nach Bounded Planner/Template-Normalisierung blieb wieder ein stale `connection_ref`-Missing-Input als finale Action-Struktur uebrig
  - Fix: plurale SSH-Multi-Target-Actions werden jetzt nach Bounded Planner und Template-Normalisierung nochmals finalisiert
  - Fix: wenn der Command-Draft dann noch leer ist, wird der Agentic SSH Resolver spaet erneut gefragt und das Ergebnis als Multi-Target-Payload mit `connection_refs` gesetzt
- Model-Gateway / Pricing:
  - LiteLLM ist keine harte ARIA-Basisdependency mehr; das Python-Paket definiert ein optionales `model-gateway`-Extra
  - Docker installiert dieses Extra explizit, und LLM/Embedding-Clients laden LiteLLM erst beim konkreten Gateway-Call
  - Pricing bleibt damit von einem installierten LiteLLM-Python-Paket entkoppelt; LiteLLM GitHub Pricing JSON bleibt nur Preislistenquelle
- Backlog:
  - der aktive Alpha-Backlog ist komprimiert; alte Build-Historie liegt im Buildlog/Changelog, waehrend `docs/backlog/alpha-backlog.md` nur aktuelle Blocker, Live-Test-Fokus und naechste Cleanup-Schritte zeigt
- Verifikation:
  - gezielte Mehrzahl-/Live-Sequenz-Regressions: `7 passed`
  - breiter Pipeline/Planner/Dry-Run/Agentic/i18n-Core-Block: `267 passed`
  - Gateway-/Kosten-/Stats-Regressionen: `46 passed`
  - finaler Vor-Build-Regressionsblock: `313 passed`
  - `python -m compileall aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha247`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha247-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.247`
  - `aria:alpha-local`
  - `sha256:78108f7d9c48f70e28ea929de3b2708b99319e03a6687d326fa24bb842c0f741`
- Release-Label:
  - `0.1.0-alpha247`
- Live-Testplan nach Deployment:
  - `check mal ob meine server noch genug festplatten platz haben`: SSH Multi-Target, keine Ziel-Rueckfrage, kein RSS/Stored-Recipe/Single-Host-Memory-Hint
  - `starte meinen dns server neu`: mutierender Restart-Draft sichtbar, Policy blockiert, keine Healthcheck-Ausfuehrung
  - `wie sieht die hd auf meinem management server aus`: `ssh/ubnsrv-mgmt-master`, LLM-Draft `df -h`, Tokens/Kosten sichtbar
  - `ist mein dns server ok`: Guardrail-Healthcheck-Bundle auf `ssh/pihole1`
  - `pruef ob die api erreichbar ist`: `http_api/n8n-test-http-api`, Pfad `/`, allow
  - `schick eine testnachricht an discord: alpha247 laeuft`: One-Click-Confirm und Versand via Discord-Profil
  - `zeige mir die folder auf dem share Ronny Fischer`: SMB-Root-Listing `.` ohne Rueckfrage
- Live-Test nach Deployment:
  - `check mal ob meine server noch genug festplatten platz haben`: `13/13` SSH-Ziele geprueft, alle unauffaellig, Multi-Target-Payload korrekt
  - `starte meinen dns server neu`: mutierender `sudo systemctl restart pihole-FTL`-Draft sichtbar und policyseitig blockiert
  - `wie sieht die hd auf meinem management server aus`: `ssh/ubnsrv-mgmt-master`, `df -h`, Tokens/Kosten sichtbar
  - `ist mein dns server ok`: `ssh/pihole1`, Guardrail-Healthcheck-Bundle und Health-Zusammenfassung
  - `pruef ob die api erreichbar ist`: `http_api/n8n-test-http-api`, Pfad `/`, allow
  - `schick eine testnachricht an discord: alpha247 laeuft`: One-Click-Confirm und Versand erfolgreich
  - `zeige mir die folder auf dem share Ronny Fischer`: `smb/fischer_ronny`, Root-Listing `.`

### alpha246

- enthaelt den Live-Test-Nachzug aus `alpha245`
- Multi-Target SSH:
  - Live-Test-Befund: `check mal ob meine server noch genug festplatten platz haben` erkannte zwar pluralen SSH-Scope, blieb aber ohne Command-Draft in der Ziel-Rueckfrage haengen
  - Fix: plurale SSH-Zielwuensche mit leerem Command-Draft holen jetzt einen bounded read-only SSH-Command ueber den Agentic SSH Resolver, bevor Multi-Target-Ausfuehrung entschieden wird
  - Fix: Multi-Target-Actions setzen die alte Single-Target-Action-Decision auf ready, damit kein stale `connection_ref`-Missing-Input mehr im Chat auftaucht
- Restart-Safety:
  - Live-Test-Befund: `starte meinen dns server neu` wurde faelschlich in einen erlaubten Healthcheck-Fallback umgebogen
  - Fix: mutierende SSH-Wuensche blockieren Guardrail-Healthcheck-Fallbacks hart; ARIA zeigt den mutierenden Draft und laesst Policy/Guardrail blockieren
- Regression:
  - Live-Test-Sequenz als Regression vorbereitet: Multi-Target-SSH, Management-HD, DNS-Health, Restart-Block, API-Reachability, Discord-Pending/Confirm, SMB-Root-Listing
- Verifikation:
  - gezielte Ausreisser-/Live-Sequenz-Regressions: `6 passed`
  - breiter Pipeline/Planner/Dry-Run/Agentic/i18n-Core-Block: `266 passed`
  - `python -m compileall aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha246`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha246-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.246`
  - `aria:alpha-local`
  - `sha256:9089de7625bf800aad3854b686ac2d1bb839bb062e336078c02f9e75427a09a8`
- Release-Label:
  - `0.1.0-alpha246`
- Live-Testplan nach Deployment:
  - `check mal ob meine server noch genug festplatten platz haben`: SSH Multi-Target, kein RSS/Stored-Recipe/Single-Host-Memory-Hint, keine Ziel-Rueckfrage
  - `wie sieht die hd auf meinem management server aus`: `ssh/ubnsrv-mgmt-master`, LLM-Draft `df -h`, Policy allow, Tokens/Kosten sichtbar
  - `ist mein dns server ok`: Guardrail-Healthcheck-Bundle auf `ssh/pihole1`
  - `starte meinen dns server neu`: mutierender Restart-Draft sichtbar, Policy blockiert, keine Healthcheck-Ausfuehrung
  - `pruef ob die api erreichbar ist`: `http_api/n8n-test-http-api`, Pfad `/`, allow
  - `schick eine testnachricht an discord: alpha246 laeuft`: One-Click-Confirm und Versand via Discord-Profil
  - `zeige mir die folder auf dem share Ronny Fischer`: SMB-Root-Listing `.` ohne Rueckfrage

### alpha245

- enthaelt den Multi-Target-/Agentic-Contract-Nachzug aus dem `alpha244`-Live-Test
- Multi-Target SSH:
  - plurale SSH-Zielwuensche wie `check mal ob meine server noch genug festplatten platz haben` werden bei sicheren Read-only-Commands als bounded Multi-Target-Action vorbereitet
  - ARIA fuehrt dabei den Command nicht ueber ein altes Fleet-Recipe aus und waehlt keinen alten Single-Host-Memory-Hint, sondern laesst jedes SSH-Profil einzeln durch die normale SSH-Runtime/Policy laufen
  - vor der Ausfuehrung wird jedes SSH-Ziel einzeln gegen Profil-Allowlist, Guardrail-Allowterms und SSH-Readonly-Policy geprueft
  - gemischte Zielmengen laufen partiell: erlaubte Ziele werden ausgefuehrt, blockierte Ziele erscheinen als Teilfehler in der lokalisierten Zusammenfassung
  - die Antwort bekommt eine lokalisierte Multi-Target-Zusammenfassung, damit im Chat klar ist, dass mehrere Ziele bewusst geprueft wurden
  - Multi-Target-Antworten bekommen vor den Hostdetails eine kompakte Operator-Lage mit ok/auffaellig/blockiert/Fehler-Zaehlern
- Agentic Contract:
  - SSH, HTTP API, File, Messaging und Read nutzen jetzt denselben LLM-Systemprompt-Vertrag: Kontext-Dossier anreichern, LLM nur bounded Action-Draft bauen lassen, Policy/Guardrail entscheidet danach
- Verifikation:
  - Pipeline/Agentic-Fokus: `201 passed`
  - breiter Pipeline/Planner/Dry-Run/Agentic/i18n-Core-Block: `263 passed`
  - `python -m compileall aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha245`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha245-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.245`
  - `aria:alpha-local`
  - `sha256:e05be41b4f9af4b346971d98949451bc23d8ae24442e4e96b2aaaa3103b70fbe`
- Release-Label:
  - `0.1.0-alpha245`
- Live-Testplan nach Deployment:
  - `check mal ob meine server noch genug festplatten platz haben`: SSH Multi-Target, Operator-Zusammenfassung, kein RSS/Stored-Recipe/Single-Host-Memory-Hint
  - `wie sieht die hd auf meinem management server aus`: `ssh/ubnsrv-mgmt-master`, LLM-Draft `df -h`, Policy allow, Tokens/Kosten sichtbar
  - `ist mein dns server ok`: Guardrail-Healthcheck-Bundle auf `ssh/pihole1`
  - `starte meinen dns server neu`: mutierender Restart-Draft sichtbar, Policy blockiert, keine Ausfuehrung
  - `pruef ob die api erreichbar ist`: `http_api/n8n-test-http-api`, Pfad `/`, allow
  - `schick eine testnachricht an discord: alpha245 laeuft`: One-Click-Confirm und Versand via Discord-Profil
  - `zeige mir die folder auf dem share Ronny Fischer`: SMB-Root-Listing `.` ohne Rueckfrage

### alpha244

- enthaelt den UX-/Kontext-Nachzug aus dem `alpha243`-Live-Test
- Chat Confirm:
  - One-Click-Buttons senden intern weiter den signierten Confirm-Command, zeigen im Chat aber nur noch den geklickten Buttontext statt `bestaetige aktion ...`
  - die manuelle Token-Eingabe bleibt als Compatibility-Fallback erhalten
- Recent File Context:
  - `im gleichen Ordner` unterscheidet jetzt zwischen zuletzt gelistetem Ordner und zuletzt geoeffneter Datei
  - nach einem Listing von `/tmp` bleibt der Follow-up daher in `/tmp`, statt auf `/` zurueckzufallen
- Verifikation:
  - gezielte Chat-/Same-Ordner-Regression: `3 passed`
  - breiter Chat/Pipeline/Planner/Dry-Run/i18n/Release-Block: `258 passed`
  - `python -m compileall aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha244`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha244-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.244`
  - `aria:alpha-local`
  - `sha256:05d55038e76d505a0589d3370d625c62fbd6c8a433c83eb9bfec3c0620c6a759`
- Release-Label:
  - `0.1.0-alpha244`

### alpha243

- enthaelt den Live-Test-Nachzug fuer Chat-Confirm, SSH-Block-Preview und Recent-File-Kontext
- Chat Confirm:
  - One-Click-Buttons fuer pending Chat-Actions senden jetzt neben dem sichtbaren Confirm-Text auch den signierten Pending-Action-Payload an `/chat`
  - damit funktioniert der Klick auch dann, wenn der Browser den Pending-Cookie aus der vorherigen AJAX-Antwort noch nicht persistiert hat
  - der Server prueft weiter Signatur, User, Alter und Token; die manuelle Token-Eingabe bleibt als Compatibility-Fallback erhalten
- Agentic SSH:
  - blockierte SSH-Previews werden neu aufgebaut, wenn der Agentic Resolver einen alten generischen Probe-Command durch den tatsaechlich gemeinten Command ersetzt
  - `starte meinen dns server neu` soll dadurch den mutierenden Restart-Command zeigen, den die Policy blockiert, statt wieder `uptime`
- Recent File Context:
  - `im gleichen Ordner` ueberschreibt jetzt auch Default-Pfadhalter wie `.` in expliziten oder Single-Profile SFTP/SMB-Pfaden
- Verifikation:
  - `tests/test_chat_tooling.py`: `18 passed`
  - `tests/test_pipeline.py`: `173 passed`
  - `tests/test_action_planner.py tests/test_execution_dry_run.py tests/test_i18n_core_surfaces.py`: `62 passed`
  - breiter Fix-Block: `253 passed`
  - `python -m compileall aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha243`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha243-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.243`
  - `aria:alpha-local`
  - `sha256:7badb7447e66122e3a948eefedbbfa0de20c16077055760dbc8b66efc33cd7e9`
- Release-Label:
  - `0.1.0-alpha243`

### alpha242

- enthaelt den Closure-Fix fuer plurale SSH-Zielwuensche und die Build-Vorbereitung nach `alpha241`
- Agentic Routing:
  - plurale SSH-Zielwuensche wie `meine Server` unterdruecken Stored-Recipe-Kandidaten jetzt auch dann, wenn der Capability-Draft noch keinen konkreten Command enthaelt
  - ARIA bleibt bounded und fragt nach dem SSH-Ziel, statt ein altes Fleet-Recipe oder einen Single-Host-Memory-Hint auszufuehren
- Verifikation:
  - fokussierter Closure-Regressionsblock: `190 passed`
  - Nachpruefung Regression + Release-Hygiene: `5 passed`
  - `python -m compileall aria tests`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha242`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha242-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.242`
  - `aria:alpha-local`
  - `sha256:ba47bf0fa3a7656973362cad942d808d51cc704c396cd7b59f06b4485d0875e4`
- Release-Label:
  - `0.1.0-alpha242`

### alpha241

- enthaelt den Token-/Kosten-Tracking-Fix fuer Agentic Action-Pfade
- Token-/Kosten-Tracking:
  - Agentic Pre-RAG Action-Pfade laufen jetzt in einem Request-Usage-Scope
  - LLM-Entscheidungen fuer SSH/HTTP/File/Messaging/Read werden dadurch im sichtbaren `PipelineResult`, Chat-Badge und Token-Log mitgezaehlt
  - fruehe Action-Antworten zeigen nicht mehr irrefuehrend `0 tokens`, wenn vorher ein LLM fuer die Action-Entscheidung genutzt wurde
- Verifikation:
  - gezielte Pipeline-/Usage-/Gateway-/Stats-Regression: `58 passed`
  - `python -m compileall -q aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha241`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha241-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.241`
  - `aria:alpha-local`
  - `sha256:325b27a1c3808f01eba659e358a003b35894d5b36e3dfbfdb166c10be8b9a8a5`
- Release-Label:
  - `0.1.0-alpha241`

### alpha240

- enthaelt den One-Click-Confirm-Fix fuer pending Chat-Actions
- Chat-Pending-Actions:
  - ausgehende Aktionen wie Discord-Send zeigen im Chat jetzt einen One-Click-Button `Aktion ausführen`
  - der Button sendet intern weiter den signierten Confirm-Befehl ueber den bestehenden `/chat`-Flow; Guardrails, Pending-Cookie, CSRF und Token-Ablauf bleiben aktiv
  - die manuelle Token-Eingabe bleibt als Fallback/Compatibility erhalten, wird aber nicht mehr als primaerer UX-Pfad angezeigt
- Chat-Frontend:
  - das bestehende Fetch-Submit-Handling kann nun auch Button-Aktionen absenden, ohne einen eventuell vorhandenen Composer-Draft zu loeschen
  - ein kleiner Pending-Status-JS-Bug wurde dabei bereinigt (`likelyRecipe` statt altem `likelySkill`-Variablennamen)
- Verifikation:
  - gezielte Chat-/i18n-/Release-Regression: `22 passed`
  - `python -m compileall -q aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha240`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha240-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.240`
  - `aria:alpha-local`
  - `sha256:074b1be4e02f364a90b2ab40ffc1699648944423ca0d64a2146824a5c4a61ee4`
- Release-Label:
  - `0.1.0-alpha240`

### alpha239

- enthaelt die Nachzuege aus dem ersten `alpha238`-Live-Test
- Agentic Routing:
  - generische HTTP-API-Erreichbarkeitsfragen wie `pruef ob die api erreichbar ist` behandeln Statuswoerter nicht mehr als Profilnamen und koennen bei genau einem HTTP-API-Profil direkt den Health-/Root-Pfad nutzen
  - SMB-/SFTP-Listenfragen ohne Pfad werden fuer `file_list` als Root-Listing `.` normalisiert, statt erneut nach einem Dateipfad zu fragen
  - frische Discord-Sendeanfragen werden nicht mehr als Antwort auf ein altes pending SMB-Pfadfeld verbraucht
  - natuerliche SSH-Uptime-/Disk-Begriffe bleiben im Router Intent-/Ziel-Hinweise; der konkrete Command wird danach vom Agentic SSH Resolver vorgeschlagen und weiterhin durch Guardrails entschieden
- Verifikation:
  - fokussierte Routing-/Pending-/Package-/Release-/i18n-Regressionen: `73 passed` plus `8 passed`
  - `python -m compileall -q aria`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha239`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha239-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.239`
  - `aria:alpha-local`
  - `sha256:c2e5b1f5d4db86cb6a9e23cc3e5e7fc0d4c4081074cfac7045fedfccad7c0f9e`
- Release-Label:
  - `0.1.0-alpha239`

### alpha235

- enthaelt die Admin-Debug-Sicht fuer echte LLM-Gateway-Prompts
- LLM Debugging:
  - `/config/llm/debug` zeigt die letzten zentralen `LLMClient`-Calls mit Prompt-Messages, Response, Source, Operation, Modell, Dauer und Token-Nutzung
  - der Audit-Log ist ein begrenzter In-Memory-Ringbuffer und schreibt keine Prompt-Daten auf Disk
  - API Keys, Tokens, Passwoerter und Discord-Webhook-URLs werden vor Anzeige maskiert
  - der Log kann per Admin-Button geleert werden
- Verifikation:
  - gezielte LLM-Audit-/Gateway-/Package-/i18n-Regression: `5 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha235`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha235-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.235`
  - `aria:alpha-local`
  - `sha256:6c61a2257a403cc505c58012a7e6a06ad209113ef789b9f419d9e3e84d1d21f1`
- Release-Label:
  - `0.1.0-alpha235`

### alpha234

- enthaelt den Hotfix fuer das `alpha233`-Live-Feedback
- Agentic Routing / SSH:
  - weiche/ordinale Zielhinweise wie `zweiten dns server` werden per semantischem LLM ueber alle verfuegbaren Profile disambiguiert
  - alias-basierte Ersttreffer wie `dns server -> pihole1` bleiben dadurch Kandidaten, aber nicht mehr automatisch Wahrheit
  - mutierende SSH-Wuensche bekommen eine zweite LLM-Mutating-Intent-Runde, wenn das erste Proposal die Absicht durch `uptime` oder eine andere generische Statusprobe maskiert
  - die Policy blockiert danach die tatsaechlich gemeinte mutierende Operation
- Verifikation:
  - gezielte Live-Feedback-Regression: `5 passed`
  - Agentic-/Planner-Regressionsblock: `31 passed`
  - Semantic-/Action-Planner-/Dry-Run-Regressionsblock: `73 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha234`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha234-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.234`
  - `aria:alpha-local`
  - `sha256:4dbc7036c74de4ed5df9bc779cfc4d7ede3697e961d8f854e72edbff30a479ce`
- Release-Label:
  - `0.1.0-alpha234`

### alpha233

- enthaelt den Hotfix fuer das `alpha232`-Live-Feedback
- Agentic Routing / SSH:
  - explizite User-Commands wie `uptime` bleiben explizite Commands und werden nicht mehr zu einem kompletten Healthcheck-Bundle erweitert
  - natuerliche Health-/Statusfragen duerfen weiterhin das erlaubte Guardrail-Healthcheck-Bundle nutzen
  - mutierende SSH-Wuensche werden vom LLM-Resolver als die tatsaechlich gemeinte Operation modelliert, damit die SSH-Policy den echten Command blockiert
  - plurale Server-Wuensche wie `meine Server` duerfen nicht mehr durch semantische LLM-Verbindungswahl auf einen einzelnen Host reduziert werden
- Verifikation:
  - gezielte Live-Feedback-Regression: `5 passed`
  - Agentic-/Planner-Regressionsblock: `31 passed`
  - Action-Planner-/Dry-Run-Regressionsblock: `61 passed`
  - Connection-Semantic-/Pipeline-Regressionsblock: `14 passed`
  - Release-/Package-/i18n-Hygiene: `10 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha233`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha233-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.233`
  - `aria:alpha-local`
  - `sha256:ba5dc0c325ae6781f5e31afa7d9c6153149c466c8ee571a1d7a5c49010e6d91d`
- Release-Label:
  - `0.1.0-alpha233`

### alpha232

- enthaelt den Agentic-Architektur-Nachzug nach `alpha231`
- Agentic Routing / Planner:
  - Bounded Planner promptet jetzt explizit mit dem Vertrag `context_enrichment -> llm_action_proposal -> policy_guardrail_decision -> runtime_execution`
  - deterministische Kandidaten, Dossiers, Session Context und Experience Memory sind damit klar Kontext, nicht finale Produktentscheidung
  - Planner-Result und Routing-Debug geben den Agentic-Flow zurueck
  - natuerliche SSH-Statusfragen mit generischem `uptime`-Draft fragen zuerst den bounded SSH-LLM-Command-Resolver nach einem konkreten Vorschlag
  - explizite User-Commands wie `uptime` bleiben explizite Commands; Guardrails entscheiden weiter `allow|ask_user|block`
- Verifikation:
  - gezielte Agentic-/Planner-/Release-Regression: `35 passed`
  - Action-Planner-/Dry-Run-Regressionsblock: `61 passed`
  - Release-Hygiene: `4 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha232`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha232-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.232`
  - `aria:alpha-local`
  - `sha256:bc53eefcb1b4fab37602750c9b1798753c5636059b49b318c2a2ffbdc0389bfd`
- Release-Label:
  - `0.1.0-alpha232`

### alpha231

- enthaelt den Hotfix fuer das `alpha230`-Live-Routing-Feedback
- Agentic Routing / Memory Assist:
  - Plural-/Fleet-Zielwuensche wie `meine Server` duerfen nicht mehr durch alte Memory-Hints auf ein einzelnes vorheriges SSH-Profil gezwungen werden
  - Memory Assist erkennt pluralen Zielscope ueber ein deklaratives Lexikon in `aria/lexicons/memory_assist.json`
  - der bounded SSH-Draft bleibt erhalten; bei mehreren SSH-Profilen fragt ARIA nach dem Ziel, bis ein sicherer Multi-Target-Pfad existiert
- Verifikation:
  - gezielte Memory-/Pipeline-Regression: `3 passed`
  - Package-Data-Regression: `2 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha231`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha231-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.231`
  - `aria:alpha-local`
  - `sha256:6680ae4b5253a037d617363839c078266036eaa06abfde75c4dd27cccbc9636c`
- Release-Label:
  - `0.1.0-alpha231`

### alpha230

- enthaelt den Hotfix fuer das `alpha229`-Live-Routing-Feedback
- Agentic Routing / Guardrails:
  - konkrete SSH-Diskspace-Drafts (`ssh_command` + `df -h`) unterdruecken widersprechende Stored-Recipe-Kandidaten
  - einfache Diskspace-Fragen koennen dadurch nicht mehr als altes Fleet-Recipe enden oder `recipe_manifest_missing` ausloesen
  - der normale `ssh_run_command`-Template-/Policy-Pfad bleibt aktiv und fragt bei mehreren SSH-Profilen nach dem Ziel
  - die Regel ist bewusst eng auf `df -h` begrenzt, damit legitime Health-Recipes weiter funktionieren
- Verifikation:
  - breiter Routing-/Planner-/Dry-Run-Regressionsblock: `221 passed`
  - Release-Hygiene: `4 passed`
  - `python3 -m compileall aria tests`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha230`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha230-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.230`
  - `aria:alpha-local`
  - `sha256:e6bf66a5d03461ddea1666b31c8d83917355b7801e0c2a55b0906661e874f850`
- Release-Label:
  - `0.1.0-alpha230`

### alpha229

- enthaelt den Hotfix fuer das `alpha228`-Live-Routing-Feedback
- Agentic Routing / Guardrails:
  - Unified Routing uebergibt die vom Capability-Draft gesetzte Connection-Familie an die Live-Routing-Chain
  - SSH-Diskspace-Drafts wie `df -h` koennen dadurch nicht mehr durch RSS-/Qdrant-Routing-Kandidaten ueberschrieben werden
  - natuerliche Pluralfragen ueber Server-Festplattenplatz bleiben bei SSH und fragen nach dem Ziel, statt RSS-Feeds zu lesen
  - mutierende SSH-Anfragen behandeln generische Template-Kommandos wie `uptime` nicht mehr als echten User-Command
  - dadurch kann der bounded SSH-Resolver gefaehrliche Aktionen erkennen und die Policy blockiert sie weiter sauber
- Verifikation:
  - breiter Routing-/Planner-/Dry-Run-Regressionsblock: `217 passed`
  - Release-Hygiene: `4 passed`
  - `python3 -m compileall aria tests`: gruen
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha229`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha229-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.229`
  - `aria:alpha-local`
  - `sha256:db3986ecc5259dfc7a2eda2a3dc853329e7c59a2678739757e26a1847285173d`
- Release-Label:
  - `0.1.0-alpha229`

### alpha228

- enthaelt die Testfeedback-Nachzuege nach `alpha227`
- Agentic Routing / Guardrails:
  - SSH-Health-/Statusfragen ersetzen ein geblocktes nacktes `uptime` wieder durch das konfigurierte erlaubte Healthcheck-Guardrail-Bundle
  - natuerliche SSH-Diskspace-Fragen erzeugen jetzt einen bounded `df -h`-Draft
  - Pluralfragen ueber Server-Festplattenplatz fragen bei mehreren SSH-Profilen nach dem Ziel, statt ein altes Fleet-Health-Recipe oder einen generischen Server-Alias zu nehmen
  - sehr kurze Connection-Refs/Aliase wie `a`/`b` matchen nicht mehr auf beliebige Buchstaben innerhalb normaler Woerter
  - SFTP-/SMB-List nutzt `.` als gueltigen Root-/Share-Default statt unnoetig nach einem Pfad zu fragen
  - klare Discord-/Messaging-Anfragen fallen ohne passendes Messaging-Profil nicht mehr auf alten SMB-/File-Kontext zurueck
  - `/connections/types` rendert ohne Live-Probes; Statuschecks bleiben auf `/connections/status`
- Verifikation:
  - fokussierter Buildblock: `42 passed`
  - breiter Routing-/Planner-/Dry-Run-Regressionsblock: `257 passed`
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha228`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha228-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.228`
  - `aria:alpha-local`
  - `sha256:943576073a5e9c71d369f6a356948ecdedc94eb6589c4eaef8e730fa709eeb54`
- Release-Label:
  - `0.1.0-alpha228`

### alpha227

- enthaelt den Agentic-Intelligence-Schnitt nach `alpha226`
- Agentic Intelligence:
  - gemeinsamer `AgenticActionDraft`-/`AgenticPolicyResult`-Contract eingefuehrt
  - SSH- und HTTP-API-Agentic-Pfade nutzen gemeinsame Draft-, Policy- und Debug-Helfer
  - Debug markiert jetzt explizit LLM-Draft, Quelle/Operation und Policy-Entscheid in einem gemeinsamen Format
  - File-Operationen haben einen generischen `file_operation`-Draft fuer SFTP/SMB list/read/write und ein secret-freies Dossier als Vorbereitung fuer modulare Connections
  - ein bounded File-LLM-Resolver ergaenzt fehlende Pfade/Inhalte fuer unvollstaendige SFTP-/SMB-Drafts, ohne klare bestehende Drafts erneut durch ein LLM zu schicken
  - Messaging-Operationen haben einen generischen Draft fuer Discord/Webhook/Email/MQTT und ein secret-freies Message-Dossier
  - ein bounded Messaging-LLM-Resolver ergaenzt nur fehlende Inhalte/Topics; vollstaendige Outbound-Drafts bleiben ohne LLM und laufen weiter durch Confirm/Guardrails
  - Read-Operationen haben einen generischen read-only Draft fuer RSS, Google Calendar, IMAP Mail/Search und beobachtete Websites sowie ein secret-freies Read-Dossier
  - ein bounded Read-LLM-Resolver ergaenzt nur fehlende Selector-/Query-Felder; vollstaendige Read-Drafts bleiben ohne LLM und behalten normale Routing-/Candidate-Debugdaten
  - Policy-Actions werden im Agentic-Core kanonisch auf `allow`, `ask_user` oder `block` normalisiert
  - Dry-Run-Debug fuer SSH, HTTP API, File, Messaging und Read zeigt jetzt denselben Draft-vs-Policy-Vertrag
  - deterministische Helfer sind als Routing-Hint, Normalizer, Policy, Runtime, Summary oder Compatibility klassifiziert; Product-Logic-Hardcodes sind nicht als Boundary-Rolle erlaubt
  - Agentic-Debugzeilen markieren Draft/Policy-Boundaries explizit, und die Runtime-Grenze wird bei aktivem Debug als `agentic_runtime` sichtbar
  - aktive POC-Namen im bounded Planner wurden bereinigt; `bounded_planner_poc` bleibt nur als Legacy-Fallback fuer alte Config-Daten lesbar
  - freie Agentic-Formulierungen sind per Regression fuer File, Messaging, Read/Mail und HTTP-Status abgesichert; mutierende SSH-/HTTP-Drafts bleiben trotz LLM-Flexibilitaet in der Policy-Grenze
  - Ziel: LLMs schlagen Actions vor, Guardrails/Policies entscheiden, Runtime fuehrt nur erlaubte normalisierte Plaene aus
- Verifikation:
  - `python3 -m compileall aria tests`: gruen
  - buildnaher Regressionsblock: `116 passed`
  - Volltest: `987 passed`, 4 warnings
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha227`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha227-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.227`
  - `aria:alpha-local`
  - `sha256:d4df84bf5946fa3073dfebd2d2e5f4c6f3eb2938a1d102b4b649bbb8cdd16852`
- Release-Label:
  - `0.1.0-alpha227`

### alpha226

- enthaelt die Backlog-Closure-Nachzuege nach `alpha225`
- Recipe / Experience Memory:
  - Recipe Experience Memory kann aus `/stats` bewusst in den Learned-Recipe-Review uebernommen werden
  - Web/Search-Ergebnisse nutzen denselben Core-Vertrag als Context-only Review-Kandidaten
  - nicht-promotable Capabilities zeigen im Learned-Recipe-Review keinen Stored-Recipe-Promote-Button mehr
  - Learned-Recipe-Store-Previews bleiben sprachneutral/stabil, UI-Lokalisierung bleibt getrennt
- Recipe-First Cleanup / Guardrails:
  - Recipe-Legacy intern weiter reduziert
  - Experience Memory Recall/Fingerprints, Monolithen-Schnitt, I18N-/Package-Guardrails und Pricing-Admin-Nachzuege sind enthalten
- Verifikation:
  - `python3 -m compileall aria tests`: gruen
  - buildnaher Regressionsblock: `312 passed`
  - Release-/Stats-/Recipes-/Experience-Regressionen: `58 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha226`
  - Container-Pricing-Check: `source LiteLLM GitHub pricing JSON`
  - Container-Pricing-Check: `chat 3312`, `embedding 189`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha226-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.226`
  - `aria:alpha-local`
  - `sha256:bc2ec6e25023784223dedc2b25dd3d35c3a1bd7cc4dfa8005b48b03740d60eed`
- Release-Label:
  - `0.1.0-alpha226`

### alpha225

- enthaelt den Stats-Diagnose-Layout-Nachzug nach `alpha224`
- Stats / UI:
  - Model Gateway Audit und Recipe Experience Memory werden jetzt als volle Diagnose-Zeilen untereinander gerendert
  - dadurch entsteht neben den langen Karten keine leere dritte Spalte mehr
  - die internen LED-Felder der Diagnose-Karten bleiben auf Desktop mehrspaltig lesbar
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Stats-/i18n-Regressionen: `29 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha225`
  - Container-Pricing-Check: `source LiteLLM GitHub pricing JSON`
  - Container-Pricing-Check: `chat 3310`, `embedding 189`, `second_used_cache True`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha225-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.225`
  - `aria:alpha-local`
  - `sha256:533c19770c460e81346e1d14a9acf980c5fc6f3475fe28b92e49486e616a4cec`
- Release-Label:
  - `0.1.0-alpha225`

### alpha224

- enthaelt den Stats-UI-Korrektur-Nachzug nach `alpha223`
- Stats / Pricing:
  - Kosten-Kachel nutzt jetzt eine stabile LED-Matrix statt gemischter Label-/Wert-Zeilen
  - geschaetzte USD, geloggte USD, Durchschnitt und bepreiste Anfragen bleiben jeweils in eigenen Mini-Panels zusammen
  - Pricing-Status zeigt weiterhin die aktive LiteLLM-GitHub-Preisquelle und den lokalen Cache explizit
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Stats-/i18n-Regressionen: `29 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha224`
  - Container-Pricing-Check: `source LiteLLM GitHub pricing JSON`
  - Container-Pricing-Check: `chat 3310`, `embedding 189`, `second_used_cache True`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha224-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.224`
  - `aria:alpha-local`
  - `sha256:7922bb959b0fb236ceb82350b43e0c2098dc59bd0b31d574ef96e140db6af970`
- Release-Label:
  - `0.1.0-alpha224`

### alpha223

- enthaelt den Stats-UI-Nachzug nach `alpha222`
- Stats / Pricing:
  - Pricing-Status zeigt die aktive LiteLLM-GitHub-Preisquelle und den lokalen Cache explizit
  - Kosten-Kachel nutzt eine kompakte Hero/List-Darstellung, damit geschaetzte USD, geloggte USD, Durchschnitt und bepreiste Anfragen die Header-Reihe nicht mehr strecken
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Stats-/Pricing-/i18n-Regressionen: `41 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha223`
  - Container-Pricing-Check: `source LiteLLM GitHub pricing JSON`
  - Container-Pricing-Check: `chat 3310`, `embedding 189`, `second_used_cache True`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha223-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.223`
  - `aria:alpha-local`
  - `sha256:aaab54d2d13d4bc8f48867720229576bfd20fffa80d9e3028a2c53192cfe6b6c`
- Release-Label:
  - `0.1.0-alpha223`

### alpha222

- enthaelt den LiteLLM-GitHub-Pricing-Cache-Nachzug nach `alpha221`
- Stats / Pricing:
  - LiteLLM `model_prices_and_context_window.json` ist jetzt die primaere Preisquelle fuer Modellpreise
  - ARIA cached die letzte gute Kopie lokal unter `data/pricing/litellm_model_prices.json`
  - Startup aktualisiert den Cache nur, wenn er aelter als 7 Tage ist
  - `/stats -> Preise aktualisieren` erzwingt einen frischen Remote-Download
  - bei GitHub-Ausfall nutzt ARIA den lokalen Cache weiter; ohne Cache bleibt ein kleiner ARIA-Notfallseed
  - lokale/custom Preise und markierte manuelle Overrides bleiben beim Refresh erhalten
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Pricing-/Stats-/Usage-/Gateway-/i18n-/Config-Regressionen: `25 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha222`
  - Container-Pricing-Check: `source LiteLLM GitHub pricing JSON`
  - Container-Pricing-Check: `chat 3306`, `embedding 189`, `second_used_cache True`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha222-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.222`
  - `aria:alpha-local`
  - `sha256:a82c121730b58d287a970f68c18758998896a043963a567f5ec3aa6e14415016`
- Release-Label:
  - `0.1.0-alpha222`

### alpha221

- enthaelt den Pricing-Alias-Fix fuer OpenAI-compatible/LiteLLM-Deployment-Namen nach `alpha220`
- Stats / Pricing:
  - `pricing.model_aliases` ist jetzt Teil der Pricing-Konfiguration
  - `embed-small` und `openai/embed-small` werden standardmaessig auf `openai/text-embedding-3-small` gemappt
  - UsageMeter, Stats-Coverage und historische Kostenschaetzung nutzen dieselbe Alias-Aufloesung
  - unbepreiste Embedding-Tokens fuer `openai/embed-small` sollen dadurch nicht mehr als False Positive erscheinen
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Pricing-/Stats-/Usage-/Pipeline-/Gateway-/i18n-/Config-Regressionen: `50 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha221`
  - Container-Pricing-Check: `openai/embed-small priced: True 0.02`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha221-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.221`
  - `aria:alpha-local`
  - `sha256:7f2e4a7b302f958ab9e529bff7b0ac566a47fad4340a6af1cac60de2b36dcdfa`
- Release-Label:
  - `0.1.0-alpha221`

### alpha220

- enthaelt die Pricing-Entkopplung von der LiteLLM-Paket-Preisliste nach `alpha219`
- Stats / Pricing:
  - `aria/core/pricing_catalog.py` importiert kein `litellm` mehr
  - Pricing liest kein `litellm.model_cost` mehr
  - die Kostenlogik nutzt einen expliziten ARIA-bundled Pricing Seed fuer gaengige OpenAI-/Anthropic-Modelle
  - OpenRouter bleibt als optionale Live-Anreicherung mit kurzem Timeout aktiv
  - LiteLLM bleibt in diesem Build noch Runtime-Adapter fuer Modellaufrufe in `LLMClient` und `EmbeddingClient`, aber nicht mehr Preisquelle
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Pricing-/Stats-/Usage-/Pipeline-/Gateway-/i18n-Regressionen: `43 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha220`
  - Container-Pricing-Check: `pricing imports litellm: False`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha220-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.220`
  - `aria:alpha-local`
  - `sha256:bf17f9b27cd1021c1da9845aaccce9377f6d9edace9c10e278644f6139f8e985`
- Release-Label:
  - `0.1.0-alpha220`

### alpha219

- enthaelt den Pricing-Refresh-UX-/Timeout-Nachzug nach `alpha218`
- Stats / Pricing:
  - Pricing-Refresh nutzt den ARIA-bundled Pricing Seed als primaere Offline-Quelle
  - OpenRouter bleibt als optionale Zusatzquelle aktiv, hat aber nur noch einen kurzen Timeout, damit `/stats` nicht lange auf eine externe API wartet
  - Refresh-Button zeigt waehrend des HTMX-Requests einen sichtbaren Inline-Indikator
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Pricing-/Stats-/Usage-/i18n-Regressionen: `41 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha219`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha219-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.219`
  - `aria:alpha-local`
  - `sha256:a92b7b641b1d5357b10592474fb9da63b41f7c7614a0e304b4e7e3fc68bb8c12`
- Release-Label:
  - `0.1.0-alpha219`

### alpha218

- enthaelt den sichtbaren `/stats` Pricing-Nachzug nach `alpha217`
- Stats / Pricing:
  - Pricing-Refresh zeigt nach dem Klick ein sichtbares Ergebnis im Details-Panel
  - Refresh-Ergebnis enthaelt Chat-/Embedding-Modellanzahl, Aktualisierungsdatum und eventuelle Fehler
  - Pricing-Details listen jetzt exakt die unbepreisten Modellnamen samt Tokenzahl, damit Custom-Deployment-Aliase gezielt gemappt werden koennen
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Pricing-/Stats-/Usage-/Gateway-/i18n-/Package-Regressionen: `41 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha218`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha218-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.218`
  - `aria:alpha-local`
  - `sha256:cd459c89002d174aa519b466ca80887bd912c192a12b292c8c3ce7a84485f9fd`
- Release-Label:
  - `0.1.0-alpha218`

### alpha217

- enthaelt den Pricing-/Stats-Nachzug nach `alpha216`
- Stats / Pricing:
  - Pricing-Aufloesung nutzt jetzt die volle bepreiste LiteLLM-Provider-Matrix statt nur OpenAI/Anthropic
  - erkennbare Azure-, AWS-Bedrock-, OpenRouter-, Gemini-, Mistral-, Cohere-, Ollama- und weitere LiteLLM-Modellnamen koennen dadurch ohne manuelle Preislistenpflege bepreist werden
  - OpenRouter-Live-API bleibt als zusaetzliche Refresh-Quelle erhalten
  - LLMs bleiben bewusst nicht die Preis-Wahrheit; sie koennen spaeter hoechstens bei unklaren Deployment-Namen als Mapping-Hilfe dienen
  - Unpriced-Warnung in `/stats` ist jetzt eine kompakte Statuszeile mit Details-Link statt layoutsprengendem Langtext
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - Pricing-/Stats-/Usage-/Gateway-/i18n-/Package-Regressionen: `41 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha217`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha217-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.217`
  - `aria:alpha-local`
  - `sha256:af8165d500c85d5d1de7e02197ba2f6a9cf0ad4d1f39161134fde47da6abe42a`
- Release-Label:
  - `0.1.0-alpha217`

### alpha216

- enthaelt den Cleanup-/Buildnachzug nach `alpha215`
- i18n / Packaging:
  - i18n-Code-Literal-Audit ist jetzt als strikte Guardrail abgesichert
  - Runtime-Assets wie i18n-Dateien, Lexicons, Templates und Static Assets sind als Package-Data deklariert
- Model Gateway / Kosten:
  - Contract-Test blockiert direkte OpenAI-/Anthropic-SDK-Nutzung und direkte LiteLLM-Bypaesse ausserhalb von `LLMClient` / `EmbeddingClient`
  - `UsageMeter` bepreist bekannte Claude-Chat-Modelle und OpenAI-Embedding-Modelle ueber den zentralen LiteLLM-Pricing-Fallback mit non-zero USD
  - `/stats` trennt geloggte USD von geschaetzten USD und zeigt den Model-Gateway-Audit fuer Live-Pruefung
- Experience Memory / Learned Recipes:
  - Planner-Debug zeigt Recipe-Experience-Treffer mit Score, Ziel, Success-Count und zuvor funktionierender Aktion
  - Learned-Recipe-Review zeigt User-Formulierung, Ziel, zuvor funktionierende Aktion und Safety-Status sichtbarer
  - Healthcheck-Experience-End-to-End-Pfad ist per Regression abgesichert
- Recipe-first UI / Runtime:
  - Learned-Recipe-Admin-UI und Recipes-Hub/Wizard nutzen recipe-first i18n-Keys statt sichtbarer Legacy-Skill-Keys
  - `recipes_routes.py` wurde entlang klarer UI-/Wizard-/Learned-/Import-Helfer geschnitten
  - `recipe_runtime.py` wurde entlang Runtime-Adaptern, Step-Executor und RSS-Gruppenlogik weiter entkernt
  - Runtime-Datei reduziert: 2384 -> 819 Zeilen
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - buildnaher Regression-Block: `285 passed`
  - Model-Gateway-/Usage-/Stats-/i18n-/Packaging-Block: `36 passed`
  - `scripts/audit_i18n_code_literals.py --strict`: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha216`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha216-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.216`
  - `aria:alpha-local`
  - `sha256:bd47428b02fa961daced3a0c2ba312aece039363f830ae71d6f57c67ef0ad87d`
- Release-Label:
  - `0.1.0-alpha216`

### alpha215

- enthaelt den Self-Learning-/Experience-Memory-Schnitt nach `alpha214`
- Stats / Model Gateway Audit:
  - Token-Nutzung wird in `/stats` als kompakte vertikale Token-Karte dargestellt, damit Chat-/Embedding-/Gesamtwerte die Symmetrie von Tokens/Kosten/Ressourcen nicht mehr sprengen
  - `/stats` zeigt eine neue `Model Gateway Audit`-Kachel mit aktivem Chat-Modell, aktivem Embedding-Modell, gemeinsamem `UsageMeter`-Status, Memory-Embedding-Wiring, Token-Log-Status und unbepreisten Tokens
  - die Kostenkarte warnt sichtbar, wenn Modell-Tokens gemessen wurden, aber fuer mindestens ein verwendetes Modell kein USD-Preis aufgeloest werden kann
  - Pricing-Coverage zeigt jetzt `bepreist / gesehen` statt die bisher missverstaendliche Gesamtzahl konfigurierter Preislistenmodelle
- Metering-Architektur:
  - Memory-Embedding-Fallbacks und Memory-Maintenance nutzen jetzt ebenfalls den gemeinsamen `UsageMeter`
  - ein neuer Contract-Test verhindert direkte `litellm`-Runtime-Calls ausserhalb von `LLMClient` und `EmbeddingClient`
- Connection-UX:
  - leere Connection-Detailseiten, die aus `/connections/types` geoeffnet werden, fallen jetzt automatisch in den Create-Modus statt beide Hauptbereiche zu verstecken
  - Discord-Connection-Seite bekommt den Toggle-Section-Builder wieder sauber ueber die Helper-Dependencies und rendert dadurch unter `/config/connections/discord?return_to=/connections/types` korrekt
- SSH-Healthcheck / Guardrails:
  - natuerliche Statusfragen wie `wie geht es meinem dns server` gelten jetzt fuer den Guardrail-Fallback als Health-/Statusanfrage
  - wenn der Planner daraus nur `uptime` ableitet, kann ARIA auf das erlaubte Healthcheck-Bundle aus der Guardrail wechseln statt wegen `ssh_command_not_in_allow_list` zu blockieren
  - volle SSH-Healthcheck-Antworten enden mit einem lesbaren Fazit wie `Fazit: unauffaellig` oder `Fazit: Handlungsbedarf`
- Self-Learning:
  - erfolgreiche Template-Ausfuehrungen werden als Learned-Recipe-Kandidaten aufgezeichnet
  - erfolgreiche Recipe-/Guardrail-Laeufe werden zusaetzlich als `Recipe Experience Memory` semantisch in Qdrant indiziert
  - passende Experience-Treffer gehen nur als Kontext in den bounded Planner, nicht als direkter Executor
  - `/stats` zeigt Experience-Memory-Collections/-Punkte
  - die Learned-Recipe-Review-UI zeigt User-Formulierung sowie Lernquelle
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - fokussierter Stats-/i18n-/Usage-/Gateway-/Memory-Block: `42 passed`
  - Config-/Connection-Regressionen: `132 passed`
  - Planner-/Dry-run-/SSH-/Learning-Regressionen: `82 passed`
  - Recipe-Experience-/Stats-/Result-Summary-Regressionen: `131 passed`
  - voller Testlauf: `922 passed`, 4 Warnungen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha215`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha215-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.215`
  - `aria:alpha-local`
  - `sha256:1cf919a623da3439e83a34e3de4752dcecc492572d703f673d44af130dc73742`
- Release-Label:
  - `0.1.0-alpha215`

### alpha214

- enthaelt den Backlog-/Hardening-Schnitt nach `alpha213`
- Backlog / Betrieb:
  - oberer Alpha-Backlog wurde entdupliziert und auf echte Build-Blocker reduziert
  - Learning Loop / Self-Learning bleibt als Roadmap-Thema in `docs/backlog/future-features.md`, nicht als aktueller Build-Blocker
  - Qdrant-Diagnose warnt jetzt auch, wenn lokaler Storage vorhanden ist, aber kein lesbares Collection-Layout gefunden wird
- Sicherheit:
  - Login-Rate-Limit fuer wiederholte fehlgeschlagene Passwortversuche
  - Runtime-Signing-Secrets werden nicht mehr leer initialisiert
  - Pending-Action-Signing und Memory-Forget-Signing sind getrennt
- UI / Recipe-first:
  - Connection-Profile werden auf allen Connection-Seiten direkt sichtbar gerendert; altes Count-/Collapse-Verhalten entfernt
  - sichtbare Recipe-/Skill-Wording-Reste in Templates, i18n und Sample-Rezepten weiter bereinigt
  - Recipe-Routen nutzen intern lesbarere `core_recipe_rows` / `sample_recipe_rows` statt produktiv falscher Skill-Row-Namen
- Update-Helper:
  - FastAPI lifespan statt `on_event`
  - timezone-aware UTC-Timestamps statt `datetime.utcnow()`
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - fokussierte Vor-Build-Regression: `201 passed`, 4 Warnungen
  - voller Testlauf: `907 passed`, 4 Warnungen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha214`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha214-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.214`
  - `aria:alpha-local`
  - `sha256:6da179cdf3736c7a7025c12a6b13649bc8896959d35f637843dedee472514273`
- Release-Label:
  - `0.1.0-alpha214`

### alpha213

- enthaelt die Politur nach dem `pihole1` Healthcheck-Live-Test und dem Recipe-Wording-Cleanup
- SSH-Healthcheck / Antwortqualitaet:
  - Journal-Rohzeilen werden nicht mehr direkt als Nutzerantwort ausgegeben
  - Journal-Funde werden nach Risiko/Kategorie zusammengefasst, z. B. sudo-/Login-Geraeusche statt `pam_unix`-Rohtext
  - kritische Muster wie Storage-/Dateisystem-/OOM-/Crash-Fehler bleiben als echte Risiken sichtbar
  - doppelte `ssh_command_guardrail_fallback`-Debugzeile aus dem Existing-Command-Pfad entfernt
- Recipe-UI / Legacy-Wording:
  - Start-/Mine-/Templates-Seiten vermeiden neue `Skill`-Produktbegriffe
  - mitgelieferte `samples/recipes` sprechen von Rezepten statt Beispielskills und verweisen auf `/recipes`
  - sichtbare Admin-/Stats-/Memory-Texte wie `Skill-Prompts`, `Skill Routing` und `Memory Skill nicht aktiv` wurden auf Rezept-/Memory-Wording gezogen
  - alte `/skills*`-Redirects und `prompts/skills`-Normalisierung bleiben als technische Legacy-Bruecken erhalten
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - `./.venv/bin/pytest -q`: `897 passed`, 23 Warnungen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
  - CLI-Version im Container: `0.1.0-alpha213`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha213-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.213`
  - `aria:alpha-local`
  - `sha256:5c0f6c7b384c85c40103f8a7d2c2f42971b42f0cbd3204581967325a63bbe8d3`
- Release-Label:
  - `0.1.0-alpha213`

### alpha212

- enthaelt den Fix fuer den Legacy-`uptime`-Template-Pfad beim Guardrail-first SSH-Healthcheck
- Planner / Guardrails:
  - vorhandene Template-Kommandos wie `uptime` beenden die SSH-Aufloesung nicht mehr zu frueh
  - bei Healthcheck-Anfragen wird auch dieser bestehende Template-Content gegen die Guardrail-Allow-Liste geprueft
  - wenn `uptime` nicht exakt erlaubt ist, aber ein Guardrail-Healthcheck-Bundle existiert, ersetzt ARIA `uptime` durch das vollstaendige Bundle
  - verhindert den Live-Fall: `ARIA wuerde ... blockieren: SSH command: uptime`
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - `./.venv/bin/pytest -q`: `896 passed`, 23 Warnungen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha212-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.212`
  - `aria:alpha-local`
  - `sha256:ed138b6318bbfe9ef166faf5a5e70b2afbb4558a097cf87d88d28b31940b1bcc`
- Release-Label:
  - `0.1.0-alpha212`

### alpha211

- enthaelt den Healthcheck-aware SSH-Result-Summarizer nach dem `pihole1` Live-Test
- Result-Summarizer:
  - Full-Healthcheck-Bundles werden als `Server-Healthcheck` statt als reiner Festplattencheck zusammengefasst
  - `uptime -p` wird erkannt und als Laufzeit ausgegeben
  - `systemctl --failed --no-pager` wird als Anzahl fehlgeschlagener systemd-Units zusammengefasst
  - `journalctl -p 3 -xb --no-pager -n 40` wird als Fehlerausschnitt ausgewertet bzw. als leerer Fehlerausschnitt gemeldet
  - bestehende Disk-/Kurzcheck-/Docker-Zusammenfassungen bleiben unveraendert
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - `./.venv/bin/pytest -q`: `895 passed`, 23 Warnungen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha211-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.211`
  - `aria:alpha-local`
  - `sha256:0a15a348cfa47de99b9f2a93df18cbf6213d523d455367618785df206128ff99`
- Release-Label:
  - `0.1.0-alpha211`

### alpha210

- enthaelt die Nachschaerfung fuer Guardrail-first SSH-Healthchecks nach dem Live-Test mit `pihole1`
- Planner / Guardrails:
  - bei echten Health-/Healthcheck-Anfragen nutzt ARIA das komplette Guardrail-Healthcheck-Bundle deterministisch
  - wenn das LLM nur eine Teilmenge der erlaubten Healthcheck-Kommandos auswaehlt, wird diese Teilmenge durch das vollstaendige Guardrail-Bundle ersetzt
  - Disk-only- und Spezialchecks bleiben davon getrennt und werden nicht blind zum Full-Healthcheck erweitert
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - `./.venv/bin/pytest -q`: `893 passed`, 23 Warnungen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha210-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.210`
  - `aria:alpha-local`
  - `sha256:1dcf2d191aaa4bf9c38fbf286b4da50024ef65ef3d9855b778b3d9de48f74803`
- Release-Label:
  - `0.1.0-alpha210`

### alpha209

- enthaelt den Guardrail-first SSH-Healthcheck fuer den Live-Test ohne manuell erstelltes Rezept
- Planner / Guardrails:
  - SSH-Zieldossiers geben `guardrail_allow_terms` an den agentischen SSH-Planer weiter
  - Health-/Status-Anfragen fallen auf exakt erlaubte Guardrail-Kommandos zurueck, wenn das LLM einen unbekannten Probe-Befehl wie `pihole status` vorschlaegt
  - mutierende SSH-Kommandos bleiben weiterhin blockiert; Pipes und Fallback-Ketten bleiben bestaetigungspflichtig
- Policy / Runtime:
  - `systemctl --failed --no-pager` ist als read-only Statusform erlaubt
  - exakt allowlist-gedeckte Healthcheck-Bundles duerfen als direkte SSH-Ausfuehrung laufen
  - Dry-run und Runtime nutzen dieselbe kombinierte Allow-Liste aus Connection und Guardrail
- Verifikation:
  - `python3 -m compileall aria`: gruen
  - `./.venv/bin/pytest -q`: `892 passed`, 23 Warnungen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha209-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.209`
  - `aria:alpha-local`
  - `sha256:35875ed322ea469c19ec297e82b9fa13f94a8085198bd9cfa168fc67a73ecb3d`
- Release-Label:
  - `0.1.0-alpha209`

### alpha208

- enthaelt den stabilisierten Recipe-first Stand nach dem letzten Cleanup vor dem Live-Test
- Stabilisierung / Cleanup:
  - `/recipes`-Templates wurden von `skills_*` / `_skills_*` auf `recipes_*` / `_recipes_*` umbenannt
  - `recipes_routes.py` nutzt intern sichtbarere Recipe-Namen fuer lokale Helper, Render-Funktionen und Page-Handler
  - sichtbare Hilfe-/Produkt-/i18n-Texte wurden weiter von `Skill` auf `Rezept` gezogen
  - bewusste Legacy-Bruecken sind im Backlog dokumentiert: `skills:` Config-Root, `/skills*` Redirects, `skills.*` i18n-Keys, CSS-Altklassen und lesende `data/skills`-/`prompts/skills`-Fallbacks
- Verifikation:
  - `python3 -m compileall -q aria`: gruen
  - `./.venv/bin/pytest -q`: `887 passed`, 23 Warnungen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha208-local.tar`
- Image:
  - `fischermanch/aria:0.1.0-alpha.208`
  - `aria:alpha-local`
  - `sha256:a8a64df23e59927515f63de073c823ad5905b73ca474ee8f16a975bc3119e1fa`
- Release-Label:
  - `0.1.0-alpha208`

### alpha207

- enthaelt den recipe-first Migrationsstand nach Phase 7 vor dem naechsten Live-Test
- Migration / Produktpfad:
  - aktive Produktpfade, Planner-Contracts, Pipeline- und Web-Dependencies sprechen jetzt deutlich staerker `recipe` statt `skill`
  - `/recipes*` ist die klare Hauptoberflaeche; sichtbare Hilfe-/Architekturtexte wurden weiter auf Rezepte gezogen
  - Learned Recipes bleiben konservativ: nur `promoted` + `stored_recipe_id` werden als ausfuehrbare Kandidaten geladen
- Cleanup:
  - produktive Web-/Config-Vertraege wurden auf `stored_recipe_*` / `format_recipe_*` umgestellt
  - Pipeline- und Runtime-Restnamen wie `runtime_custom_skills` wurden auf `runtime_recipes` bereinigt
  - `recipe_manifests.py` haengt nicht mehr an `_custom_skill_*`-Importnamen
- Verifikation:
  - `tests/test_action_planner.py tests/test_pipeline.py tests/test_skill_runtime_matching.py tests/test_skills_routes.py tests/test_config_routes.py tests/test_chat_tooling.py tests/test_router.py tests/test_token_tracker.py tests/test_error_handling.py tests/test_execution_dry_run.py`: `351 passed`
  - `tests/test_router.py tests/test_token_tracker.py tests/test_error_handling.py tests/test_execution_dry_run.py`: `79 passed`
  - `tests/test_skills_routes.py tests/test_config_routes.py`: `64 passed`
  - `tests/test_config_backup.py`: `6 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha207-local.tar`
- Release-Label:
  - `0.1.0-alpha207`

### alpha206

- enthaelt den bereinigten Learned-Recipe-/Admin-Stand vor der naechsten Live-Runde
- Learned Recipes / Promotion:
  - Learned Candidates werden im normalen Planner jetzt nur noch dann als ausfuehrbare Kandidaten geladen, wenn sie `promoted` sind und bereits ein echtes `stored_recipe_id` haben
  - damit bleibt `review_ready` / `eligible` Admin-/Review-Material und kippt nicht in den bestehenden Stored-Recipe-Runtime-Pfad
  - `promote` auf `/skills/learned` uebernimmt jetzt ein Learned Recipe als echtes gespeichertes Rezept-Manifest
- Admin-GUI:
  - neue Learned-Recipe-Seite mit
    - Promotion-Statusfiltern
    - Connection-Kind-Filtern
    - Sortierung nach letztem Erfolg / Erfahrung / Titel
    - Admin-Aktionen `promote`, `dismiss`, `delete`
    - Direktlink ins erzeugte gespeicherte Rezept mit Rueckweg in die gefilterte Learned-Ansicht
- Verifikation:
  - `tests/test_learned_recipe_store_contract.py tests/test_action_planner.py tests/test_bounded_planner.py tests/test_learned_recipe_promotion.py`: `44 passed`
  - `tests/test_skills_routes.py`: `15 passed`
  - `tests/test_chat_tooling.py tests/test_router.py tests/test_pipeline.py tests/test_error_handling.py`: `216 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha206-local.tar`
- Release-Label:
  - `0.1.0-alpha206`

### alpha205

- enthaelt den kompletten Fixstand nach dem Recipe-/Experience-Contract-Cleanup vor dem spaeteren echten Learned-Recipe-Umbau
- Core / Cleanup:
  - neuer gemeinsamer Vertrag in `aria/core/recipe_candidate_contract.py`
  - `recipe_candidate_view.py`, `stored_recipe_manifest_view.py` und `execution_dry_run_payloads.py` nutzen jetzt denselben Recipe-/Experience-Boden
  - `execution_dry_run_payloads.py` haelt keine eigenen Experience-Defaultreste fuer gespeicherte Rezepte mehr
- Verifikation:
  - `tests/test_recipe_candidate_contract.py tests/test_stored_recipe_manifest_view.py tests/test_execution_dry_run.py tests/test_action_planner.py tests/test_bounded_planner.py`: `66 passed`
  - `tests/test_pipeline.py tests/test_capability_router.py tests/test_chat_tooling.py tests/test_execution_dry_run.py tests/test_action_planner.py tests/test_bounded_planner.py tests/test_stored_recipe_manifest_view.py tests/test_recipe_candidate_contract.py`: `296 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha205-local.tar`
- Release-Label:
  - `0.1.0-alpha205`

### alpha204

- enthaelt den kompletten Fixstand nach dem aktuellen Cleanup-Block vor dem naechsten groesseren Recipe-/Skill-Umbau
- Core / Cleanup:
  - `pipeline.py` weiter entkernt; Qdrant-/Routing-Helfer liegen jetzt in `aria/core/pipeline_qdrant_helpers.py`
  - `execution_dry_run_payloads.py` family-naeher geschnitten; Template-Draft-/Payload-Helfer liegen jetzt in `aria/core/execution_dry_run_template_payloads.py`
  - kleine Lesbarkeitsnachpflege in `aria/core/behavior_families.py`
- Verifikation:
  - `tests/test_pipeline.py tests/test_capability_router.py tests/test_chat_tooling.py tests/test_router.py tests/test_http_guardrails.py`: `251 passed`
  - `tests/test_action_planner.py tests/test_pipeline.py tests/test_behavior_families.py tests/test_execution_dry_run.py`: `216 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha204-local.tar`
- Release-Label:
  - `0.1.0-alpha204`

### alpha181

- enthaelt den kompletten Fixstand bis einschliesslich `alpha180`
- Routing / SSH:
  - `semantic_llm` darf bei gesetzter `requested_connection_ref` nur noch dann ein SSH-Ziel erzwingen, wenn der gewaehlte Host diese Zielphrase auch wirklich stuetzt
  - dadurch bleibt `backup server` bei fehlender starker Stuetze offen, statt kreativ auf `syncthing` zu springen
  - gleichzeitig bleibt `monitoring server` weiter erlaubt, wenn Titel/Beschreibung/Aliase den Monitoring-Bezug klar tragen
- Verifikation:
  - `tests/test_pipeline.py` + `tests/test_capability_router.py`: `154 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha181-local.tar`
- Release-Label:
  - `0.1.0-alpha181`

### alpha180

- enthaelt den kompletten Fixstand bis einschliesslich `alpha179`
- Routing / SSH:
  - der `CapabilityRouter` behandelt generische SSH-Aliase wie `server` bei Hostrollen jetzt strenger
  - wenn eine aktuelle Zielphrase wie `backup server` oder `monitoring server` vorliegt, darf ein schwacher frueher Alias-Treffer nicht mehr still als `explicit_ref` stehen bleiben
  - `management server` bleibt dabei weiterhin als valider expliziter Treffer erhalten
- Verifikation:
  - `tests/test_capability_router.py` + `tests/test_pipeline.py`: `152 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha180-local.tar`
- Release-Label:
  - `0.1.0-alpha180`

### alpha179

- enthaelt den kompletten Fixstand bis einschliesslich `alpha178`
- Routing / Planner / SSH:
  - der aktive Unified-Routing-Pfad zeigt jetzt sichtbare Debug-Spuren fuer
    - `capability_draft`
    - `candidate_pool`
    - `memory_hint`
    - `memory_hint blocked`
  - Prozess-Level-Regressionen sichern jetzt explizit ab, dass stale `memory_hint`-Treffer aktuelle Zielphrasen wie `backup server` nicht mehr still auf den Management-Host zwingen
  - explizite SSH-Ziele werden im Unified-Pfad vor spaeteren Memory-Hinweisen festgezogen und dadurch nicht mehr von altem Kontext ueberfahren
- Verifikation:
  - `tests/test_pipeline.py`: `103 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha179-local.tar`
- Release-Label:
  - `0.1.0-alpha179`

### alpha167

- enthaelt den kompletten Fixstand bis einschliesslich `alpha166`
- Refresh 2026-04-25:
  - sichtbare Release-Kennung und Public-Release-Linie sind jetzt bewusst wieder auf denselben `alpha167`-Stand gezogen
  - der `Updates`-Menueintrag erscheint nur noch, wenn wirklich ein neuer Release verfuegbar ist
- Memory Map / Notes:
  - die `aria_notes_<user>`-Collection aus Qdrant erscheint jetzt sichtbar in der `Memory Map`
  - Notes bekommen dort einen eigenen Block `Notes-Collections` statt still unsichtbar im Backend zu bleiben
  - der Memory-Graph zeigt `Notizen` jetzt als eigenen Wissenszweig und verlinkt direkt zur Notizverwaltung `/notes`
- Users / Admin mode:
  - der kaputte Save-Pfad `/config/users/debug-save` ist korrigiert und funktioniert wieder
  - Hinweise wie `Admin mode off` fuehren jetzt direkt zum passenden Toggle auf `/config/users#admin-mode`
- Google Calendar:
  - die Schritt-Karten im Setup sind kompakter zusammengerueckt und visuell klarer als einzelne Schritte gerahmt
- Verifikation:
  - voller Testlauf: `643 passed, 23 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha167-local.tar`
- Release-Label:
  - `0.1.0-alpha167`

### alpha166

- enthaelt den kompletten Fixstand bis einschliesslich `alpha165`
- Notes / Notizen:
  - `/notes` startet jetzt standardmaessig im Board-Modus ohne sofort offenen Editor
  - Klick auf eine Notiz oder `Neu` oeffnet den Editor direkt im rechten Arbeitsbereich statt den User wieder nach unten scrollen zu lassen
  - frisch angelegte Ordner landen sichtbar im aktiven Ordnerkontext und wirken dadurch nicht mehr wie "verschwunden"
- Verifikation:
  - voller Testlauf: `631 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha166-local.tar`
- Release-Label:
  - `0.1.0-alpha166`

### alpha165

- enthaelt den kompletten Fixstand bis einschliesslich `alpha164`
- Notes / Notizen:
  - eigentliche Ursache fuer den weiterhin sichtbaren Editor-Overflow war nicht nur das Input-Sizing, sondern die Seitenbreite selbst
  - `notes-app-shell` orientiert sich jetzt sauber an der umgebenden `app-shell` statt mit einer eigenen Viewport-Breite nach rechts auszubrechen
  - `notes-explorer-shell` ist zusaetzlich auf `min-width: 0` und `max-width: 100%` gehaertet
  - dadurch sollte der rechte Notes-Arbeitsbereich in Safari und Firefox nicht mehr ueber den Rand hinausgedrueckt werden
- Verifikation:
  - voller Testlauf: `629 passed, 36 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha165-local.tar`
- Release-Label:
  - `0.1.0-alpha165`

### alpha164

- enthaelt den kompletten Fixstand bis einschliesslich `alpha163`
- Connection-Edit-Flow fuehlt sich auf `Beobachtete Webseiten` und den uebrigen Connection-Seiten jetzt deutlich direkter an:
  - `Neu` springt nicht mehr nur auf dieselbe Seite, sondern direkt in den Create-Bereich `#create-new`
  - Klicks auf bestehende Connection-Karten springen direkt in den Edit-Bereich `#manage-existing`
  - gerade auf schmaleren Screens muss man dadurch nicht mehr erst nach unten zum eigentlichen Formular suchen
- Notes / Notizen:
  - der rechte Editorbereich wurde fuer Safari und Firefox nochmals haerter gegen Layout-Overflow abgesichert
  - Titel-, Tag- und Inhaltsfelder erzwingen jetzt konsequenter `min-width: 0`, `max-width: 100%` und block-level Sizing innerhalb des Editor-Layouts
- Doku-Sweep:
  - die nutzernahe Produkt-/Wiki-/Help-Doku wurde fuer `Notizen`, `Beobachtete Webseiten` und `Google Calendar` nachgezogen
  - besonders die Trennung zwischen `Memory` und `Notizen` ist jetzt in den Help- und Wiki-Seiten klarer beschrieben
- Verifikation:
  - voller Testlauf: `629 passed, 35 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha164-local.tar`
- Release-Label:
  - `0.1.0-alpha164`

### alpha163

- enthaelt den kompletten Fixstand bis einschliesslich `alpha162`
- kleiner, aber wichtiger Notes-UI-Fix:
  - der rechte Arbeitsbereich der neuen Notes-Oberflaeche laeuft nicht mehr ueber den Rand hinaus
  - Editorrahmen und Eingabefelder bleiben jetzt geschlossen innerhalb des Panels, statt horizontal aus dem Layout zu kippen
  - dafuer wurden Breite, `min-width`, `box-sizing` und Overflow-Verhalten im Notes-Workspace gezielt gehaertet
- Verifikation:
  - voller Testlauf: `628 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha163-local.tar`
- Release-Label:
  - `0.1.0-alpha163`

### alpha162

- enthaelt den kompletten Fixstand bis einschliesslich `alpha161`
- Notes / Notizen wurden in diesem Build deutlich staerker zu einem eigenen Arbeitsbereich statt zu einem Memory-Anhaengsel:
  - die Notes-Seite haengt nicht mehr in der Memory-Subnavigation, sondern steht produktisch auf eigenen Fuessen
  - die alten oberen Health-/Qdrant-Kacheln sind verschwunden; Qdrant-Status gehoert fuer Notes nicht mehr prominent auf diese Seite
  - die Oberflaeche arbeitet jetzt eher wie ein kleiner Datei-Explorer mit linker Ordnernavigation, einem Zettel-Board aus Vorschaukarten und einem separaten Editorbereich auf der Arbeitsseite
  - Suchtreffer aus dem Notes-Index werden robuster auf echte lokale Notizen zurueckgemappt, auch wenn ein technischer Treffer stale IDs liefert
- zusaetzlich ist ein echter Skills-Regression-Fix drin:
  - `Core / System` und `Meine Skills` schalten sich beim Speichern nicht mehr gegenseitig aus, nur weil jeweils die andere Checkbox-Gruppe nicht im aktuellen Formular vorhanden war
- Verifikation:
  - voller Testlauf: `628 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha162-local.tar`
- Release-Label:
  - `0.1.0-alpha162`

### alpha161

- enthaelt den kompletten Fixstand bis einschliesslich `alpha160`
- Notes wachsen in diesem Build von einem ersten MVP zu einem deutlich nuetzlicheren Alltagswerkzeug:
  - normale Websuche kann jetzt passende Notes automatisch als Zusatzkontext mitziehen, statt Notes nur auf expliziten Notes-Pfaden zu verwenden
  - Notizen lassen sich im Chat natuerlicher anlegen, etwa ueber freie Formulierungen wie `halte fest ...` oder `notiere ...`
  - Webquellen bzw. einzelne URLs koennen direkt aus dem Chat als Notiz uebernommen werden; Titel, Kurzbeschreibung, Ordnerhinweise und Tags werden dabei automatisch vorgeschlagen bzw. mitgespeichert
  - Notes bleiben dabei bewusst `Markdown-first` und werden nur als abgeleiteter Suchindex in Qdrant gehalten; bei Aenderungen wird die betroffene Notiz vollstaendig neu gechunkt und reindexiert
- Verifikation:
  - voller Testlauf: `626 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha161-local.tar`
- Release-Label:
  - `0.1.0-alpha161`

### alpha160

- enthaelt den kompletten Fixstand bis einschliesslich `alpha159`
- Google-Calendar-Setup weiter geschaerft:
  - die Einrichtung ist jetzt als 6 klare Kacheln mit knappen, konkreten Arbeitsschritten aufgebaut
  - `Audience / Testnutzer` ist als eigener Schritt sichtbar statt in einem unklaren Verweis auf einen zweiten Link zu verschwinden
  - der OAuth-Playground-Teil beschreibt jetzt die genaue Reihenfolge fuer Scope, Authorize APIs und das Kopieren des Refresh-Tokens
- Verifikation:
  - voller Testlauf: `610 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha160-local.tar`
- Release-Label:
  - `0.1.0-alpha160`

### alpha159

- enthaelt den kompletten Fixstand bis einschliesslich `alpha158`
- Google-Calendar-Setup weiter auf echte Checklisten-Schritte verdichtet:
  - die Seite nutzt jetzt 5 knappe Kacheln statt laengerer Erklaertexte
  - pro Kachel steht nur noch, was konkret zu tun ist und welcher Link geoeffnet werden soll
  - der OAuth-/Refresh-Token-Flow ist dadurch deutlich scanbarer und naeher an einer echten Einrichtungs-Checkliste
- Verifikation:
  - voller Testlauf: `610 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha159-local.tar`
- Release-Label:
  - `0.1.0-alpha159`

### alpha158

- enthaelt den kompletten Fixstand bis einschliesslich `alpha157`
- Google-Calendar-Setup und Routing-Feinschliff fuer den naechsten Live-Test:
  - die Google-Calendar-Einrichtung fuehrt jetzt pro Karte klarer durch den naechsten konkreten Schritt (`Jetzt tun`) und erklaert direkt, wann zum folgenden Schritt gewechselt werden soll
  - die Links zu Google Cloud, OAuth Playground und Google Calendar bleiben am jeweils passenden Schritt statt als separate Linksammlung
  - natuerliche SSH-Disk-Checks wie `check mal die festplatte auf meinen dns server` werden jetzt auf `df -h` normalisiert, statt den ganzen Satz als Command auszufuehren
  - `df -h` gilt im Dry-Run-/Confirm-Pfad jetzt als sicherer Standard-Read-Only-Command
- Verifikation:
  - voller Testlauf: `610 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha158-local.tar`
- Release-Label:
  - `0.1.0-alpha158`

### alpha157

- enthaelt den kompletten Fixstand bis einschliesslich `alpha156`
- letzter UI-Feinschliff vor dem Google-Livetest:
  - `/config/operations` zeigt `Updates` jetzt als ersten Block ganz oben
  - die wenig hilfreiche Leerlauf-Zeile `Aktueller Schritt` ist dort entfernt; auf den echten Update-Live-Seiten bleibt sie weiter sichtbar
  - die Google-Calendar-Setup-Seite nutzt jetzt die Schritt-Kacheln selbst als Linktraeger, statt dieselben Google-Links noch einmal als separate Liste ueber dem Flow zu wiederholen
- Verifikation:
  - voller Testlauf: `605 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha157-local.tar`
- Release-Label:
  - `0.1.0-alpha157`

### alpha156

- enthaelt den kompletten Fixstand bis einschliesslich `alpha155`
- weiterer Public-Release-Readiness-Schnitt vor dem naechsten oeffentlichen Stand:
  - `aria/web/config_routes.py` liegt jetzt unter `1000` Zeilen; der verbleibende Profil-/Embedding-/Sample-Helper-Block lebt in `aria/web/config_profile_helpers.py`
  - `aria/main.py` bleibt auf dem schlankeren Bootstrapping-Kurs unter `1200` Zeilen
  - die alte Moduloberflaeche fuer Tests und Monkeypatches blieb dabei bewusst stabil
- Google-Calendar-Readiness und der produktnahe Public-Smoke-Stand sind mit in diesem Build
- Verifikation:
  - voller Testlauf: `605 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha156-local.tar`
- Release-Label:
  - `0.1.0-alpha156`

### alpha153

- enthaelt den kompletten Fixstand bis einschliesslich `alpha152`
- weiterer sauberer Architektur-Schnitt rund um Routing-/Web-/Connection-Helfer:
  - die verbleibenden Connection-Reader und die per-Typ-Connection-Context-Builder leben jetzt in
    - `aria/web/connection_reader_helpers.py`
    - `aria/web/connection_context_helpers.py`
    statt weiter in `aria/web/config_routes.py`
  - `aria/web/config_routes.py` verliert damit nochmals spuerbar fachliche Helper-Masse und bleibt staerker bei Route-/Wiring-Verantwortung
  - die bereits gezogenen Chat-/Session-/Runtime-/Connection-Slices bilden jetzt deutlich konsistenter denselben Web-Layer statt weiterer Inline-Cluster in `main.py` und `config_routes.py`
- Routing-/Planner-/Resolver-Cleanup aus der laufenden Alpha-Linie ist mit in diesem Stand:
  - Chat und Workbench teilen sich denselben Produktpfad fuer Routing, Planner, Payload und Guardrails
  - stale Qdrant-Routing-Indizes werden fuer Nutzer selbstheilender behandelt
  - bestaetigungspflichtige Outbound-Aktionen bleiben kontrolliert ueber `ask_user`
  - `CapabilityRouter` und Routing-Lexikon wurden weiter auf gemeinsame Quellen zusammengezogen
- Verifikation:
  - voller Testlauf: `577 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha153-local.tar`
- Release-Label:
  - `0.1.0-alpha153`

### alpha152

- enthaelt den kompletten Fixstand bis einschliesslich `alpha151`
- Routing-/Planner-/Guardrail-Konsistenz jetzt wirklich als gemeinsamer Produktpfad:
  - der Live-Chat benutzt nicht mehr die alten separaten Live-Ausfuehrungspfade fuer `ssh` und generische Capability-Aktionen
  - Chat und Workbench teilen sich jetzt fuer unterstuetzte Verbindungsarten dieselbe Kette aus:
    - Routing
    - Action-Planer
    - Payload-Bau
    - Guardrail / Confirm
    - Execution Preview
  - die fruehere Inkonsistenz zwischen Routing-Testbench und echtem Chat-Verhalten wird dadurch deutlich reduziert
  - bestaetigungspflichtige Outbound-Aktionen wie `discord`, `webhook`, `email` und `mqtt` laufen jetzt konsistent ueber `ask_user` statt ueber uneinheitliche Altpfade
  - Qdrant-Routing im Live-Chat respektiert wieder Feature-Flag, Stale-Index-Checks und die gleichen Debug-/Detailhinweise wie der neue Resolver
  - Kontextfaelle wie `im gleichen Ordner` und Single-Profile-Faelle wurden auf der neuen Kette wieder sauber hergestellt
- Verifikation:
  - Routing-/Planner-/Pipeline-/Chat-Regressionssuite gruen
  - voller Testlauf: `570 passed, 11 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha152-local.tar`
- Release-Label:
  - `0.1.0-alpha152`

### alpha151

- enthaelt den kompletten Fixstand bis einschliesslich `alpha150`
- Routing-/Planner-Integration ist jetzt nicht mehr nur Workbench-Dry-run, sondern sauber bis in den Live-Chat zusammengezogen:
  - Chat und Workbench teilen sich jetzt fuer unterstuetzte Verbindungstypen dieselbe Routing-/Action-/Payload-/Guardrail-Kette
  - `allow`, `ask_user` und `block` gelten damit nicht mehr nur in der Testbench, sondern auch im echten Chat-Verhalten
  - bestaetigungspflichtige Aktionen koennen im Chat kontrolliert ueber `bestaetige aktion <token>` freigegeben werden
  - regelbasierte Custom-Skills behalten bewusst Vorrang, waehrend der neue gemeinsame Resolver Templates und verbindungsgebundene Skills konsistenter zusammenfuehrt
- Verifikation:
  - Routing-/Pipeline-/Chat-Regressionssuite gruen
  - breiter UI-/Session-/Update-Sanity-Block gruen
  - voller Testlauf: `562 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha151-local.tar`
- Release-Label:
  - `0.1.0-alpha151`

### alpha150

- enthaelt den kompletten Fixstand bis einschliesslich `alpha149`
- letzte Konsistenz- und Theme-Politur vor dem naechsten groesseren Produktblock:
  - Bereichstitel auf den grossen Domain-/Config-Seiten laufen jetzt wieder konsistent mit Icon, statt gemischt mit und ohne Symbol aufzutreten
  - `Aussehen & Theme` nutzt Hintergruende jetzt komplett dateibasiert:
    - alle Optionen kommen direkt aus `background-*`-Dateien in `aria/static/`
    - keine fest verdrahteten Sprachdatei-Eintraege mehr fuer Background-Namen
    - neue Bilder tauchen damit automatisch in der UI auf, solange sie der Naming-Convention folgen
  - die Label-Generierung fuer dynamische Hintergruende ist lesbarer geworden:
    - `8-Bit Arcade`
    - `AI Lobby`
    - `ARIA Thinking`
  - doppelte Background-Eintraege wurden beseitigt, indem die bisherige Mischlogik aus festen und dynamischen Optionen durch eine einheitliche Datei-Quelle ersetzt wurde
- Verifikation:
  - Error-/Config-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha150-local.tar`
- Release-Label:
  - `0.1.0-alpha150`

### alpha149

- enthaelt den kompletten Fixstand bis einschliesslich `alpha148`
- letzte Konsistenz- und Produktfluss-Politur vor dem naechsten groesseren Themenblock:
  - `Gedächtnis`-Karten wurden mikrotypografisch sauberer ausgerichtet:
    - `Eigene Memory erfassen`
    - `Dokumente importieren`
    - `Nächste Schritte`
    nutzen jetzt dasselbe stabile Icon-/Titel-/Badge-Raster
  - auffaellige Icon-Unstimmigkeiten wurden bereinigt:
    - `Gedächtnis-Explorer` zeigt wieder das passende `Gedächtnis`-Icon statt eines fachfremden Symbols
    - Dokument-Importe nutzen konsistent ein `Upload`-Icon
  - die Dev-/Produktlinie bleibt damit auch im kleinen Detail deutlich ruhiger und konsistenter
- Verifikation:
  - Gedächtnis-/Config-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha149-local.tar`
- Release-Label:
  - `0.1.0-alpha149`

### alpha148

- enthaelt den kompletten Fixstand bis einschliesslich `alpha147`
- letzte Konsistenz- und Mobil-Politur vor dem naechsten groesseren Produktblock:
  - `/updates` haengt jetzt sichtbar unter `Einstellungen > Betrieb & Transfer` und nutzt denselben Settings-Kopf wie die restlichen Config-Unterseiten
  - `Benutzer` bleibt nur noch unter `Einstellungen > Zugriff & Sicherheit`; das App-Menue selbst bleibt dadurch schlanker
  - `Hilfe`, `Produkt-Info`, `Updates` und `Lizenz` teilen sich jetzt denselben ruhigen Doku-Rahmen mit konsistentem Header-/Pill-Menue und dunklerem Inhalts-Akzent fuer bessere Lesbarkeit
  - Primary Actions auf Config-Seiten wurden vereinheitlicht: zentrale Speichern-/Ausfuehren-Aktionen wirken ruhiger, sind besser lesbar gruppiert und stehen klarer getrennt von destruktiven Aktionen
  - der globale Zurueck-Pfeil wurde aus der UI entfernt; die Navigation ist inzwischen stark genug und der wartungsintensive Sonderpfad faellt damit weg
  - die Chat-Arbeitsflaeche ist auf kleinen Screens jetzt dynamischer:
    - leerer/frischer Chat startet kompakter, damit Composer und Tool-Box auf dem iPhone frueher sichtbar bleiben
    - mit echtem Verlauf waechst die Flaeche wieder in eine komfortable Scroll-Hoehe hinein
- Verifikation:
  - Help-/Update-/Config-/Session-/Chat-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha148-local.tar`
- Release-Label:
  - `0.1.0-alpha148`

### alpha147

- enthaelt den kompletten Fixstand bis einschliesslich `alpha146`
- die neue UI-Linie ist jetzt auch visuell ueber die Hauptbereiche zusammengezogen:
  - eine gemeinsame dunkelgruene Buehne umrahmt jetzt die eigentlichen Seitenbereiche, waehrend die funktionalen Elemente weiterhin frei und leicht wirken
  - `Gedächtnis` war die Referenz, danach wurde derselbe Rahmen konsequent auf `Fähigkeiten`, `Verbindungen`, `Einstellungen`, `Statistiken` und den Doku-Bereich ausgerollt
- dadurch wirkt die Oberflaeche jetzt deutlich konsistenter:
  - weniger Flickwerk zwischen den Bereichen
  - mehr klare Seitenbuehne ohne Rueckfall in schwere Kachel-in-Kachel-Optik
- Verifikation:
  - Memory-/Skill-/Config-/Help-/Stats-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha147-local.tar`
- Release-Label:
  - `0.1.0-alpha147`

### alpha146

- enthaelt den kompletten Fixstand bis einschliesslich `alpha145`
- GUI-Re-Thinking jetzt als zusammenhaengender Hauptschnitt gebaut:
  - `Gedächtnis`, `Fähigkeiten`, `Verbindungen` und `Einstellungen` sind jetzt klarer als ruhige Hubs und Unterseiten organisiert
  - der neue Clean-Look reduziert schwere Trägerflächen und laesst die eigentlichen Funktionselemente bewusster stehen
  - `Statistiken` wurde optisch beruhigt, ohne die bestehende Einzelseiten-Logik zu zerlegen
- Doku-/Hilfebereich deutlich sauberer und konsistenter:
  - `Hilfe` ist schlanker aufgebaut und zeigt die eigentlichen Hilfetexte schneller
  - neue Seite `Lizenz` mit ARIA-, Qdrant- und SearXNG-Lizenzhinweisen
  - Qdrant und SearXNG sind als sichtbare Help-Themen praesent, ohne das obere Help-Menü zu überladen
- weitere UI-Details nachgezogen:
  - `/config/users` im Clean-Design
  - `/memories/config` mit klarer getrennten Abschluss-Aktionen
  - `/connections` wieder mit gemeinsam genutztem Live-Status-Block wie in `Statistiken`
- Verifikation:
  - Help-/Config-/Memory-/Skill-/Session-/Stats-/Update-Regressionen gruen
  - voller Testlauf: `554 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha146-local.tar`
- Release-Label:
  - `0.1.0-alpha146`

### alpha145

- enthaelt den kompletten Fixstand bis einschliesslich `alpha144`
- Gedächtnis-Übersicht weiter in die ruhigere Explorer-Richtung geschoben:
  - `Aktionen` und `Tools` stehen jetzt direkt unter der Übersichts-Kachel, noch vor dem Graphen
  - `/memories` nutzt dafür eine leichtere Flächenwirkung statt der schweren Vollflächen-Optik
  - der Stand ist bewusst als Sicht-Build gedacht, damit der neue Stil live gegen das Matrix-Theme beurteilt werden kann
- Verifikation:
  - Gedächtnis-Routen-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha145-local.tar`
- Release-Label:
  - `0.1.0-alpha145`

### alpha144

- enthaelt den kompletten Fixstand bis einschliesslich `alpha143`
- Connections-Hub wieder mit dem richtigen operativen Ueberblick:
  - der Live-Status aller konfigurierten Verbindungen ist jetzt wieder direkt auf `/connections` sichtbar
  - dafuer wird derselbe Status-Block wie auf `/stats` wiederverwendet, statt eine zweite Sonderdarstellung einzufuehren
  - die Verbindungs-Hauptseite fuehlt sich dadurch wieder vollstaendiger und nuetzlicher an
- Verifikation:
  - Config-/Update-/Session-Regressionen gruen
  - voller Testlauf: `steht nach Build-Lauf fest`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha144-local.tar`
- Release-Label:
  - `0.1.0-alpha144`

### alpha143

- enthaelt den kompletten Fixstand bis einschliesslich `alpha142`
- GUI-Feinschliff und Sprachkonsistenz weiter beruhigt:
  - die deutschen Hauptbegriffe sind jetzt in der sichtbaren UI klarer gezogen: `Gedächtnis`, `Fähigkeiten`, `Verbindungen`
  - `/help` ist deutlich schlanker aufgebaut und zeigt den eigentlichen Hilfetext schneller und klarer
  - das Inhaltsverzeichnis der Hilfe wirkt jetzt eher wie eine ruhige Dokumentnavigation statt wie eine zweite Landingpage
- Einordnung:
  - guter Zwischenstand fuer das bisherige GUI-Re-Thinking
  - die Hauptdomänen wirken jetzt deutlich konsistenter und weniger überladen
- Verifikation:
  - Help-/I18n-/Config-/Memory-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha143-local.tar`
- Release-Label:
  - `0.1.0-alpha143`

### alpha142

- enthaelt den kompletten Fixstand bis einschliesslich `alpha141`
- Feinschliff fuer die Hauptseiten-Informationsarchitektur:
  - `/connections` hat keine nutzlose Selbst-Referenz im Kopf mehr
  - die Uebersichtskarten auf `/connections` sind jetzt echte Einstiege zu Verbindungstypen, SearXNG und Samples
  - `/config` zeigt in den Statuskarten oben jetzt die eigentlichen Werte als primaere Zeile
  - die erklaerenden Beschreibungen auf `/config` sitzen dadurch ruhiger und konsistenter in der Meta-Zeile wie auf den anderen Hauptseiten
- Verifikation:
  - Config-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha142-local.tar`
- Release-Label:
  - `0.1.0-alpha142`

### alpha141

- enthaelt den kompletten Fixstand bis einschliesslich `alpha140`
- Hauptseiten visuell weiter harmonisiert:
  - `/skills` hat jetzt oben eine echte Uebersicht mit kompakten Statuskarten statt nur Titel und Fliesstext
  - `/connections` wirkt im Intro ruhiger und integriert sich besser in den restlichen Seitenstil
  - `/config` nutzt weiter denselben Header-Stil, aber die Navigation springt jetzt direkt in die jeweils geoeffnete Zielsektion
  - die nutzlose `Einstellungen`-Kachel in der Settings-Navigation ist entfernt
- Verifikation:
  - Config-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `steht nach Build-Lauf fest`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha141-local.tar`
- Release-Label:
  - `0.1.0-alpha141`

### alpha140

- enthaelt den kompletten Fixstand bis einschliesslich `alpha139`
- App-Menue und Settings-Hub weiter geschaerft:
  - `Einstellungen` steht im App-Menue jetzt bewusst vor `Statistiken`
  - `/config` hat nun dieselbe klare Kopf-/Anchor-Struktur wie `Memories`, `Skills` und `Connections`
  - die Bereiche `Uebersicht`, `Intelligenz`, `Persoenlichkeit & Stil`, `Zugriff & Sicherheit`, `Betrieb & Transfer` und `Workbench` sind direkt oben anspringbar
- Verifikation:
  - Config-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha140-local.tar`
- Release-Label:
  - `0.1.0-alpha140`

### alpha139

- enthaelt den kompletten Fixstand bis einschliesslich `alpha138`
- Navigation weiter vereinfacht:
  - `Chat` ist nicht mehr als eigener Punkt im App-Menue sichtbar
  - das ARIA-Logo bleibt der direkte Rueckweg zur Startseite
- Connections-Hub an die Informationsarchitektur von `Memories` und `Skills` angeglichen:
  - `/connections` hat jetzt oben dieselbe kompakte Navigation im Kachel-/Pill-Stil
  - die Navigation springt auf Anchors innerhalb derselben Seite
  - damit fuehlen sich die drei Hauptdomänen `Memories`, `Skills` und `Connections` nun deutlich einheitlicher an
- Verifikation:
  - Config-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha139-local.tar`
- Release-Label:
  - `0.1.0-alpha139`

### alpha138

- enthaelt den kompletten Fixstand bis einschliesslich `alpha137`
- Update-Seite weiter geschaerft:
  - `Kontrolliertes Update` ist jetzt die primaere Funktion auf `/updates`
  - der Bereich ist nicht mehr als eingeklapptes Detail versteckt, sondern als offene Primärkarte direkt oben sichtbar
  - Status, Start-Button und Log sind dadurch sofort im Fokus
- Skill-Seite weiter an die Memory-Informationsarchitektur angeglichen:
  - `/skills` hat jetzt oben eine Navigation im selben Stil wie `Memories`
  - die Navigation springt auf Anchors innerhalb derselben Seite
  - Reihenfolge jetzt bewusst: `Skill starten`, `Meine Skills`, `Core / System`, `Vorlagen`
  - `Core / System` steht im Hauptfluss vor den Sample-Skills
  - `Mitgelieferte Sample-Skills` bleiben standardmaessig eingeklappt
- Verifikation:
  - Update-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha138-local.tar`
- Release-Label:
  - `0.1.0-alpha138`

### alpha137

- enthaelt den kompletten Fixstand bis einschliesslich `alpha136`
- Skill-Bereich als klarerer Hub ueberarbeitet:
  - `/skills` ist jetzt staerker entlang der eigentlichen Nutzerarbeit geschnitten
  - `Meine Skills` stehen zuerst
  - ein eigener Block `Skill starten` macht Wizard und JSON-Import sofort sichtbar
  - `Mitgelieferte Sample-Skills` leben klar getrennt als Vorlagen-Bibliothek
  - `Core / System` ist weiter unten einsortiert und ueberdeckt den eigentlichen Nutzerfluss nicht mehr
- Sample-Skills verhalten sich jetzt robust eingeklappt:
  - die Karten basieren weiter auf `<details>`
  - der Inhaltsbereich wird aber zusaetzlich explizit verborgen, solange die Karte nicht geoeffnet ist
  - damit bleibt das Einklappen auch dann konsistent, wenn ein Browser `<details>` eigenwillig rendert
- Memory-Graph nachgezogen:
  - Detail-Knoten uebernehmen jetzt ihr echtes Typ-Icon statt pauschal nur das Memory-Symbol zu zeigen
- Verifikation:
  - Skill-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha137-local.tar`
- Release-Label:
  - `0.1.0-alpha137`

### alpha136

- enthaelt den kompletten Fixstand bis einschliesslich `alpha135`
- Qdrant-Zugriff im Memory-Setup weiter verbessert:
  - der Dashboard-Einstieg kann jetzt in einer Benutzeraktion gleichzeitig das Qdrant-Dashboard oeffnen und den API-Key in die Zwischenablage legen
  - wenn kein API-Key vorhanden ist, oeffnet derselbe Einstieg einfach nur das Dashboard
  - der Clipboard-Fallback fuer lokale/insecure Browser-Kontexte bleibt dabei aktiv
- Verifikation:
  - fokussierte Memory-/Config-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha136-local.tar`
- Release-Label:
  - `0.1.0-alpha136`

### alpha135

- enthaelt den kompletten Fixstand bis einschliesslich `alpha134`
- Memory-Bereich in der Bedienlogik weiter entschaerft:
  - auf `/memories/config#qdrant-access` ist der `Qdrant API Key` jetzt standardmaessig verborgen
  - der Copy-Button fuer URL und API-Key nutzt jetzt neben der Clipboard-API auch einen robusten Fallback fuer lokale/insecure Browser-Kontexte
  - auf `/memories/explorer` liegen keine Erfassungs-/Import-Aktionen mehr zwischen Suche und Browse-Flow
  - `Eigene Memory erfassen` und `Dokumente importieren` leben jetzt passend auf der `Memory-Uebersicht`
  - Create-/Upload-Aktionen springen von dort nach erfolgreicher Ausfuehrung auch wieder sauber auf die Uebersicht zurueck
- Verifikation:
  - fokussierte Memory-/Config-/Session-Regressionen gruen
  - voller Testlauf: `548 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha135-local.tar`
- Release-Label:
  - `0.1.0-alpha135`

### alpha134

- enthaelt den kompletten Fixstand bis einschliesslich `alpha133`
- Menue-Trigger weiter verbessert:
  - statt der drei Punkte nutzt das kompakte App-Menue jetzt ein Gear-/Settings-Icon
  - der Trigger signalisiert damit klarer, dass dort Bereiche, Optionen und Systemaktionen liegen
- Memory-Uebersicht weiter beruhigt und nuetzlicher gemacht:
  - auf `/memories` wird unten nicht mehr die Unterseiten-Navigation wiederholt
  - stattdessen zeigt die Seite jetzt direkt eine integrierte `Memory-Graph`-Vorschau
  - im `Tools`-Block gibt es neben dem Export jetzt auch einen klaren Einstieg zu `Qdrant-Zugriff`
  - dieser Einstieg fuehrt direkt auf `/memories/config#qdrant-access`, wo URL, API-Key und Dashboard-Link an einer Stelle fuer Copy/Paste liegen
- Verifikation:
  - fokussierte Memory-/Config-/Session-Regressionen gruen
  - voller Testlauf: `547 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha134-local.tar`
- Release-Label:
  - `0.1.0-alpha134`

### alpha133

- enthaelt den kompletten Fixstand bis einschliesslich `alpha132`
- Hauptnavigation wieder bewusst beruhigt:
  - die sichtbare Desktop-Leiste mit allen Hauptbereichen wurde wieder entfernt
  - stattdessen nutzt ARIA jetzt wieder ein einzelnes kompaktes App-Menue oben rechts
  - der Chat bleibt dadurch oben ruhiger und wird nicht von einer breiten Navigationsleiste ueberlagert
- dabei bleibt die verbesserte Informationsarchitektur erhalten:
  - `Chat`, `Memories`, `Skills`, `Connections`, `Statistiken`, `Einstellungen` und `Hilfe` leben weiter in einer klareren Reihenfolge innerhalb des Menues
  - aktive Bereiche werden im Menue hervorgehoben
  - Benutzer-/Admin-/Logout-Aktionen bleiben sauber von den eigentlichen App-Bereichen getrennt
- Verifikation:
  - fokussierte Config-/Memory-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `547 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha133-local.tar`
- Release-Label:
  - `0.1.0-alpha133`

### alpha132

- enthaelt den kompletten Fixstand bis einschliesslich `alpha131`
- Hauptnavigation als klarere Produktnavigation umgebaut:
  - auf Desktop sind jetzt die Kernbereiche sichtbar statt hinter einem generischen Menue zu verschwinden
  - primaere Navigation: `Chat`, `Memories`, `Skills`, `Connections`
  - sekundaere Navigation: `Statistiken`, `Einstellungen`, `Hilfe`
  - Benutzer-/Admin-/Logout-Aktionen leben separat im Account-Menue
  - auf Mobile bleibt ARIA bewusst kompakt ueber das Account-/Menue-Dropdown bedienbar
- Domainen und Hubs weiter geschaerft:
  - `Connections` hat jetzt eine echte Hauptseite unter `/connections` statt nur als Anker in `Einstellungen`
  - `Einstellungen` ist als System-/Admin-Hub neu geordnet und zeigt Connections nicht mehr doppelt
  - `Updates` bleibt eine einzige Seite unter `/updates`, ist aber jetzt sinnvoll von `Hilfe` und `Einstellungen` aus erreichbar
- weitere UI-Beruhigung in den Kernbereichen:
  - `Memory-Setup` zeigt Qdrant-Zugriff, URL, API-Key und Dashboard-Link jetzt nur noch an einer zentralen Stelle
  - die mitgelieferten Sample-Skills auf `/skills` sind standardmaessig eingeklappt und erschlagen die Seite nicht mehr
- Verifikation:
  - fokussierte Config-/Memory-/Skill-/Session-Regressionen gruen
  - voller Testlauf: `547 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha132-local.tar`
- Release-Label:
  - `0.1.0-alpha132`

### alpha131

- enthaelt den kompletten Fixstand bis einschliesslich `alpha130`
- Memory-IA und Memory-UI weiter beruhigt:
  - `Memories` ist jetzt der echte Hub unter `/memories`
  - der eigentliche Explorer lebt auf `/memories/explorer`
  - alte Explorer-Links mit `/memories?type=...` werden sauber auf den neuen Explorer-Pfad umgeleitet
  - alle Memory-Seiten nutzen jetzt eine gemeinsame lokale Navigation fuer `Uebersicht`, `Explorer`, `Map` und `Setup`
  - Qdrant-Dashboard-/API-Key-Kram ist aus Uebersicht und Map entfernt und lebt nur noch im `Memory-Setup`
- Memory-Uebersicht und Memory-Map optisch nachgeschaerft:
  - Uebersicht zeigt jetzt klare Status-Laempchen fuer Qdrant, aktive Collection, User-Memory, Dokumente und Auto-Memory
  - Explorer hat einen ruhigeren Kopfbereich mit Fokus-/Treffer-Zusammenfassung
  - Memory-Map hat jetzt einen klareren Hero-Bereich, konsolidierte Health-Karten und wertigere Abschnitts-Header
  - Collection- und Routing-Karten wirken kompakter und bewusster gestaltet
- Verifikation:
  - fokussierte Memory-/Config-/Session-Regressionen gruen
  - voller Testlauf: `544 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha131-local.tar`
- Release-Label:
  - `0.1.0-alpha131`

### alpha130

- enthaelt den kompletten Fixstand bis einschliesslich `alpha129`
- Routing-Testbench sauber ausgelagert:
  - die komplette Dry-run-Testbench lebt jetzt als eigene Workbench-Seite unter `/config/workbench/routing`
  - `/config/routing` konzentriert sich wieder auf Routing-Index, Live-Qdrant-Settings und Routing-/Memory-Regeln
  - alte Deep-Links mit `routing_query=...` auf `/config/routing` werden sauber auf die neue Workbench umgeleitet
- Memory-Navigation vereinheitlicht:
  - neuer zentraler Hub unter `/memories/overview`
  - Hauptmenue `Memories` fuehrt jetzt auf diese Uebersichtsseite
  - Memory-Map, Memory-Setup sowie routingnahe Memory-/Skill-Trigger liegen dort jetzt gesammelt an einem Ort
  - doppelte Memory-Einstiegspunkte unter `Einstellungen` wurden entfernt
- kleine UI-Nachschaerfung:
  - `Memory Map` und `Memory-Setup` auf `/memories` nutzen jetzt ebenfalls Icons
- Verifikation:
  - fokussierte Config-/Memory-/Skill-/Session-Regressionen gruen
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha130-local.tar`
- Release-Label:
  - `0.1.0-alpha130`

### alpha129

- enthaelt den kompletten Fixstand bis einschliesslich `alpha128`
- Routing-Dry-run robuster gemacht:
  - der bounded `Action / Skill`-Planner faellt bei leicht abweichenden LLM-Kandidatennamen nicht mehr mit `Kein Treffer` aus
  - stattdessen wird die LLM-Auswahl innerhalb der bounded Menge normalisiert oder kontrolliert auf den klaren heuristischen Kandidaten zurueckgefuehrt
  - dadurch laufen `Payload dry-run`, `Guardrail / Confirm dry-run` und `Final execution preview` bei natuerlichen SSH-Health-Fragen wieder sauber durch
- Memory-Map visuell nachgeschaerft:
  - Root-, Typ- und Collection-Knoten sind kompakter
  - Collections/Memory-Knoten nutzen jetzt ikonischere Darstellungen statt schwerer Rahmen
  - die Map braucht weniger Breite und wirkt ruhiger/lesbarer
- Verifikation:
  - fokussierte Planner-/Routing-/Memory-Regressionen gruen
  - voller Testlauf: `538 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha129-local.tar`
- Release-Label:
  - `0.1.0-alpha129`

### alpha128

- enthaelt den kompletten Fixstand bis einschliesslich `alpha127`
- Dry-run-Pfad in der Routing-Testbench jetzt end-to-end sichtbar:
  - `Action / Skill dry-run` waehlt zwischen sicheren Templates und passenden Custom Skills
  - `Payload dry-run` zeigt konkrete Eingaben wie SSH-Command, Dateipfad oder Nachrichtenvorschau
  - `Guardrail / Confirm dry-run` zeigt, ob ARIA direkt ausfuehren, nachfragen oder blocken wuerde
  - `Final execution preview` fasst Ziel, Capability und den naechsten sicheren Schritt zusammen
- Sicherheits-/Zugriffsgrenzen nachgezogen:
  - geschuetzte HTML-Seiten leiten ohne Session weiter korrekt auf `/login`
  - `/updates` bleibt absichtlich oeffentlich sichtbar
  - Managed-Update-Aktionen bleiben ohne Login/Admin weiter gesperrt
- Verifikation:
  - fokussierte Dry-run- und Auth-Regressionen gruen
  - voller Testlauf: `537 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha128-local.tar`
- Release-Label:
  - `0.1.0-alpha128`

### alpha127

- enthaelt den kompletten Fixstand bis einschliesslich `alpha126`
- UI-/Icon-Welle weitergezogen:
  - `Skills`, `Memories`, `Memory Map`, `Stats`, `RSS Connections`, `Import / Export`, Connection-Navigation und Kontext-Hilfe nutzen jetzt deutlich mehr ikonische Aktionen statt schwerer Textbuttons
  - betroffen sind vor allem Back-, Edit-, Delete-, Refresh-, Import-/Export- und Routing-Aktionen
  - im Skill-Wizard sind auch `Verbindungen verwalten`, Speichern/Loeschen und der Ruecksprung kompakter und konsistenter
- Mobile-/Scanbarkeit verbessert:
  - zentrale Actions auf dichten Admin-Seiten sind schneller erfassbar
  - Memories-Suche, Kontext-Rollup und `Mehr dazu` auf Help-Karten sind jetzt ebenfalls iconisiert
  - die Routing-/Pricing-Admin-Shortcuts in `Stats` folgen jetzt derselben Aktionssprache
- Verifikation:
  - fokussierte Template-/UI-Regressionen gruen
  - voller Testlauf: `532 passed`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha127-local.tar`
- Release-Label:
  - `0.1.0-alpha127`

### alpha126

- enthaelt den kompletten Fixstand bis einschliesslich `alpha125`
- Routing-/Planner-Dry-run weiter verfeinert:
  - finale Action-Entscheidungen und Kandidaten zeigen jetzt eine kompakte Summary-Zeile in menschlicherer Satzform
  - Beispiele:
    - `Template: Gesundheitscheck via SSH-Befehl auf ssh/pihole1`
    - `Template: Datei lesen auf sftp/mgmt`
  - die Summary unterdrueckt doppelte Begriffe wie `Datei lesen`, wenn Intent und Capability ohnehin dasselbe meinen
- Routing-Testbench kompakter gemacht:
  - die finale Action-Karte und die Kandidatenliste zeigen weniger redundante Detailzeilen
  - Candidate type und Capability werden nicht mehr doppelt separat wiederholt, wenn die Summary sie schon traegt
  - uebrig bleiben die relevanten Review-Daten wie Score, State, Preview, Inputs, Rueckfrage und Beispiel-Prompt
- Review-/Qualitaetsstand:
  - fokussierte Planner-/Routing-Regressionen gruen
  - voller Testlauf: `531 passed`
  - kurzer Diff-/Selbstreview vor dem Build: keine blockierenden Findings
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha126-local.tar`
- Release-Label:
  - `0.1.0-alpha126`

### alpha125

- enthaelt den kompletten Fixstand bis einschliesslich `alpha124`
- Routing-Hints / Connection-Metadaten:
  - gemeinsamer Helfer `aria/core/routing_hints.py` fuehrt Skill-Keyword- und Connection-Metadaten-Hints jetzt zusammen
  - SSH- und SFTP-Profile koennen Routing-Metadaten beim Speichern jetzt automatisch aus `service_url` ergaenzen, wenn Titel/Beschreibung/Aliase/Tags noch leer oder duenn sind
  - vorhandene Nutzerwerte bleiben fuehrend und werden nicht blind ueberschrieben
- Skill-Wizard weiter entschaerft:
  - `Skill type` mit gefuehrten Defaults fuer `Health Check`, `Monitor`, `Notify`, `Fetch`, `Sync`
  - Simple-Mode setzt Kategorie, Beschreibung und erste Step-Defaults jetzt serverseitig, nicht nur per UI
  - Simple-Mode zeigt je Skill-Typ nur noch sinnvolle Step-Typen
  - passende Folge-Schritte koennen im Simple-Mode direkt per Klick hinzugefuegt werden
  - Hauptverbindung wird im Simple-Mode jetzt ebenfalls gefuehrt und kann aus vorhandenen Connections direkt in den ersten Step uebernommen werden
- Scope bewusst klein gehalten:
  - kein Umbau des Skill-Manifests
  - keine Runtime-/Executor-Aenderung
  - keine Live-Aktivierung neuer Planner-/Intent-Logik
- Tests:
  - fokussierte Regressionen fuer Config-Routen sowie Skill-Wizard / Custom-Skills / Sample-Skills gruen
  - voller Testlauf: `510 passed`
- Release-Label:
  - `0.1.0-alpha125`

### alpha124

- enthaelt den kompletten Fixstand bis einschliesslich `alpha123`
- Skill-Wizard erster Entschlackungs-Schnitt:
  - neuer `Simple Skill` / `Advanced Skill`-Modus
  - `Simple` ist jetzt der gefuehrte Standardpfad
  - `Advanced` blendet Rohschritte, Metadaten und Feintuning wieder ein
  - pro Step werden nur noch die zum gewaehlten Step-Typ passenden Felder gezeigt
  - der Wizard-Modus bleibt nach dem Speichern erhalten
- Scope bewusst klein gehalten:
  - keine Aenderung am Skill-Manifest-Format
  - keine Runtime-/Executor-Umstellung
  - vorhandene komplexe Skills sollen weiter funktionieren
- Tests:
  - Skill-Wizard-, Custom-Skill- und Sample-Skill-Regressionen gruen
  - voller Testlauf: `507 passed`
- Release-Label:
  - `0.1.0-alpha124`

### alpha123

- enthaelt den kompletten Fixstand bis einschliesslich `alpha122`
- Routing-Testbench erweitert:
  - neuer Debug-Schalter, um den `LLM router dry-run` ohne deterministischen Hint zu testen
  - dadurch ist `Qdrant + LLM` isoliert beurteilbar, ohne das Live-Routing zu veraendern
- Routing-/Admin-Integration:
  - `/config/routing`
  - `/config/routing-index/test`
  - unterstuetzen jetzt den Debug-Modus fuer `Qdrant + LLM only`
- Tests:
  - Routing-Admin, Config-Routing und Pipeline-Regressions fuer den neuen Debug-Schalter gruen
- Release-Label:
  - `0.1.0-alpha123`

### alpha122

- enthaelt den kompletten Fixstand bis einschliesslich `alpha121`
- LLM-Routing erster sicherer Schnitt:
  - die Routing-Testbench unter `/config/routing` zeigt jetzt zusaetzlich eine `LLM router dry-run`-Entscheidung
  - die LLM-Schicht sieht nur den begrenzten Kandidatenraum aus deterministischem Treffer plus akzeptierten Qdrant-Kandidaten
  - Ausgabe bleibt bewusst rein beobachtend/adminseitig; noch keine Live-Ausfuehrung im Chat-Routing
- Routing-/Admin-Integration:
  - `/config/routing`
  - `/config/routing-index/test`
  - geben die LLM-Dry-run-Entscheidung jetzt mit aus
- Tests:
  - Routing-Admin, Config-Routing und Pipeline-Regressions fuer den neuen Dry-run-Schnitt gruen
- Release-Label:
  - `0.1.0-alpha122`

### alpha121

- enthaelt den kompletten Fixstand bis einschliesslich `alpha120`
- Routing-/SSH-Uptime-Fix:
  - natuerliche Fragen wie `Wie lange ist mein DNS Server schon online?` werden jetzt ebenfalls als SSH-`uptime` erkannt
  - dieselbe Formulierung stuetzt jetzt auch die Preferred-Kind-Inferenz fuer das Qdrant-Routing
  - dadurch faellt diese Phrase nicht mehr in generische LLM-/Memory-Antworten zurueck
- Tests:
  - gezielte Regressionen fuer Capability-Router, Pipeline und Routing-Resolver gruen
- intern verifiziert auf der echten internen ARIA:
  - GUI-Update-Button zog `aria-alpha121-local.tar` sauber vom NAS und aktualisierte erfolgreich
  - Config / Profile / Memory / Theme blieben nach dem Update erhalten
  - `Wie lange ist mein DNS Server schon online?` fuehrte korrekt `uptime` auf dem SSH-Profil `pihole1` aus
- Release-Label:
  - `0.1.0-alpha121`

### alpha120

- enthaelt den kompletten Fixstand bis einschliesslich `alpha119`
- Runtime-Reload-Hardening:
  - `_reload_runtime()` baut jetzt ein frisches Runtime-Bundle fuer `settings`, `prompt_loader`, `usage_meter`, `llm_client` und `pipeline`
  - der Swap auf die neue Runtime erfolgt atomar unter `threading.RLock`, statt die einzelnen Objekte nacheinander zu ueberschreiben
  - Startup-/Preflight-Diagnostics greifen konsistent auf den aktuellen Runtime-Stand zu
  - Stats-, Activities-, Skills-, Memories- und Config-Routen lesen Runtime-Objekte ueber Live-Getter statt eingefrorene Referenzen
- Config-/Session-Konsistenz:
  - `ConfigRouteDeps` nutzt fuer `auth_session_max_age_seconds` jetzt ebenfalls einen Getter
  - Session-Cookies bleiben damit nach Runtime-Reloads auf dem aktuellen Security-Stand
- Tests:
  - app-nahe Regressionen fuer Config-Routen, Chat-/Session-Pfade, Update-UI, Stats und den neuen Dynamic-Proxy gruen
  - voller Testlauf: `501 passed`
- Release-Label:
  - `0.1.0-alpha120`

### alpha119

- enthaelt den kompletten Fixstand bis einschliesslich `alpha118`
- Memory-Map / Routing-Graph:
  - Routing-Collections erscheinen jetzt nicht nur als Textblock, sondern auch sichtbar im Memory-Graph
  - Routing haengt als eigener System-Zweig in der Grafik und verlinkt auf `/config/routing`
- Routing / SSH-Intent:
  - natuerliche Fragen wie `Wie lange laeuft mein DNS Server schon?` werden jetzt ebenfalls als SSH-`uptime` erkannt
  - dieselbe Formulierung stuetzt jetzt auch die Preferred-Kind-Inferenz fuer Qdrant-Routing
  - dadurch faellt diese Frage nicht mehr in eine generische LLM-Antwort zurueck
- Tests:
  - gezielte Regressionen fuer Memory-Graph, Capability-Router, Pipeline und Routing-Resolver gruen
- intern verifiziert auf der echten internen ARIA:
  - GUI-Update-Button zog `aria-alpha119-local.tar` sauber vom NAS und aktualisierte erfolgreich
  - Config / Profile / Memory blieben nach dem Update erhalten
  - Routing-Collection im Memory-Graph sichtbar
  - `Wie lange laeuft mein DNS Server schon?` fuehrte korrekt `uptime` auf dem SSH-Profil aus
- Release-Label:
  - `0.1.0-alpha119`

### alpha118

- enthaelt den kompletten Fixstand bis einschliesslich `alpha117`
- Managed-Update-Hardening v2:
  - `aria-stack.sh validate` prueft jetzt nicht mehr nur `config.yaml`, sondern auch die Bind-Mounts und Sync-Sicht fuer `config`, `prompts` und `data`
  - `/app/config`, `/app/prompts` und `/app/data` werden explizit gegen die erwarteten Host-Pfade validiert
  - `prompts/persona.md` und die Auth-DB werden Host-vs-Container geprueft; fuer leere frische Setups gibt es einen `data`-Fallback-Check auf die Kernverzeichnisse
  - der Managed-Update-Helper hebt die echte Validate-Ursache jetzt in `last_error`/UI hoch, statt nur generisch `exit code 1` zu melden
- Admin-/Memory-Map:
  - Routing-Qdrant-Collections erscheinen jetzt separat in der Memory Map als System-/Routing-Collections
  - semantisches User-Memory und Routing-Index bleiben in der Anzeige sauber getrennt
- SSH-UX:
  - harmlose `known hosts`-Warnungen beim ersten SSH-Kontakt werden nicht mehr als sichtbarer `STDERR`-Fehler gezeigt
- Tests:
  - gezielte Tests fuer Setup-/Update-Helfer, Update-UI, Memory-Map und SSH-Output gruen
- Release-Label:
  - `0.1.0-alpha118`

### alpha117

- enthaelt den kompletten Fixstand bis einschliesslich `alpha116`
- Routing-/Intent-Fix:
  - natuerliche Laufzeit-/Uptime-/Healthcheck-Fragen werden jetzt als SSH-Command geplant
  - Beispiel: "Zeig mir die Laufzeit vom primaeren DNS Server" wird zu `ssh_command` mit `uptime`
  - SFTP-`file_read` greift nicht mehr nur wegen "zeig/zeige", wenn eigentlich ein Server-Status gefragt ist
  - der SSH-Intent kann mit explizitem Alias direkt routen oder ohne Alias ueber den Qdrant-Routing-Index aufgeloest werden
- Tests:
  - Capability-Router-Regression fuer Laufzeitfragen via Alias
  - Capability-Router-Regression fuer Laufzeitfragen ohne Ziel, damit Qdrant anschliessend aufloesen kann
  - Pipeline-Regression mit SSH und SFTP parallel, damit Laufzeitfragen vor SFTP als SSH ausgefuehrt werden
- Release-Label:
  - `0.1.0-alpha117`

### alpha116

- enthaelt den kompletten Fixstand bis einschliesslich `alpha115`
- Routing-UI:
  - `/config/routing` hat jetzt einen direkten Schalter fuer Live-Qdrant-Routing im Chat
  - Threshold und Kandidatenlimit koennen direkt auf der Routing-Seite angepasst werden
  - Option "bei unsicherem Qdrant-Routing nachfragen statt ausweichen" ist direkt konfigurierbar
  - Speichern erfolgt ueber einen eigenen Endpoint, getrennt vom Editor fuer Memory-/Routing-Regeln
- Tests:
  - UI zeigt den neuen Live-Routing-Save-Block
  - Speichern persistiert Enable/Disable, Threshold, Limit und Ask-on-low-confidence sauber in `config.yaml`
- Release-Label:
  - `0.1.0-alpha116`

### alpha115

- enthaelt den kompletten Fixstand bis einschliesslich `alpha114`
- Qdrant-Routing-Testbench / Live-Routing:
  - Auto-Modus erkennt aus dem Prompt nun den bevorzugten Connection-Typ
  - Laufzeit, uptime, Healthcheck, Befehl, Kommando und aehnliche Aktionen werden als SSH-Intent gewertet
  - Datei, Pfad, Ordner, Verzeichnis, Upload/Download werden als SFTP-Intent gewertet
  - Discord-Nachrichten und RSS-/News-Fragen bekommen ebenfalls eigene Typ-Hints
  - bei erkanntem Typ werden Qdrant-Kandidaten anderer Connection-Typen verworfen statt als finale Route akzeptiert
  - Qdrant fragt bei gesetztem/erkanntem Typ mehr Kandidaten ab und filtert danach hart, damit ein semantisch passender SSH-Treffer nicht von SFTP-Kandidaten verdeckt wird
  - die Testbench zeigt erkannte Auto-Typen und verworfene Kandidaten nachvollziehbar an
- Tests:
  - Regression fuer deutsche DNS-/Laufzeit-Fragen, bei denen SFTP hoeher scort als SSH
  - Regression fuer Auto-Intent-Erkennung in Resolver und Routing-Testbench
- Release-Label:
  - `0.1.0-alpha115`

### alpha114

- enthaelt den kompletten Fixstand bis einschliesslich `alpha113`
- Qdrant-Routing-Index:
  - Connection-Profile werden als eigene Routing-Dokumente fuer SSH, SFTP, RSS, Discord und HTTP-API aufgebaut
  - Routing-Dokumente enthalten Titel, Beschreibung, Aliase, Tags und nicht-sensitive Verbindungsmetadaten
  - Secrets, Tokens, Webhooks und Passwoerter werden nicht in Routing-Texte geschrieben
- Admin-/Debug-Funktionen:
  - `/config/routing` zeigt Status, Collection, Dokumentanzahl, Fingerprint und Stale-Erkennung des Routing-Index
  - manueller Rebuild fuer den Routing-Index
  - Testbench fuer Routing-Fragen mit optional bevorzugtem Connection-Typ
  - `/stats` zeigt den Routing-Index-Zustand kompakt mit an
- Live-Routing:
  - Qdrant-Routing ist als Feature-Flag vorbereitet und standardmaessig aus
  - exakte Profilnamen, Aliase, Memory-Hints und deterministische Router gewinnen weiter vor Qdrant
  - bei veraltetem oder fehlendem Index fragt ARIA im Live-Modus nach statt unsicher auf falsche Tools zu fallen
- Tests:
  - neue Unit-/Integrationstests fuer Index-Building, Resolver, Admin-Status/Testbench und Pipeline-Fallbacks
- Release-Label:
  - `0.1.0-alpha114`

### alpha113

- enthaelt den kompletten Fixstand bis einschliesslich `alpha112`
- SFTP-Connections:
  - neues Feld `Service URL`
  - Metadaten-Hilfe ueber Web-Seite + LLM fuer Beschreibung, Aliase und Tags
  - `service_url` wird jetzt im Datenmodell, in der UI und beim Speichern sauber mitgefuehrt
- SSH-/Skill-Safety:
  - `{query}` und `{query:q}` in SSH-Custom-Command-Templates werden shell-gequotet gerendert
  - Backtick-/Newline-Blockade bleibt als zusaetzliche Sicherheitsgrenze aktiv
- Guardrails:
  - einfache Begriffe matchen token-/boundary-bewusst
  - Pfad-Guardrails behalten Prefix-/Substring-Matching fuer Unterpfade
- Skill-Runtime:
  - konstante Regexes vor-kompiliert
  - dynamische Condition-Regexes ueber kleinen LRU-Cache
- Release-Label:
  - `0.1.0-alpha113`

### alpha112

- enthaelt den kompletten Fixstand bis einschliesslich `alpha111`
- SSH- und RSS-Metadaten-Helfer respektieren jetzt die aktive ARIA-Sprache
  - bei `DE` werden Titel, Beschreibung, Aliase und Tags gezielt auf deutsche Routing-/Trigger-Begriffe ausgerichtet
  - bei `EN` entsprechend auf englische Begriffe
- Release-Label:
  - `0.1.0-alpha112`

### alpha111

- enthaelt den kompletten Fixstand bis einschliesslich `alpha110`
  - Managed-Update-Haertung
  - `aria-stack.sh repair`
  - Host-vs-Container-Config-Validierung nach Managed-Updates
- SSH-Connections:
  - neues Feld `Service URL`
  - Metadaten-Hilfe ueber Web-Seite + LLM fuer Beschreibung, Aliase und Tags
  - optionale Checkbox, beim Anlegen direkt ein passendes SFTP-Profil mitzuerzeugen
- Connection-UX:
  - `Create` auf den Connection-Seiten deutlich prominenter
- Release-Label:
  - `0.1.0-alpha111`

### alpha8

- Skill-Loeschen auf `/skills`
- Skill-Loeschen direkt im Wizard
- neue sauber benannte Background-Assets
- `Nodes Field` als zusaetzlicher Background
- Theme-/Background-Einbindung aktualisiert

### alpha9

- Logo-Fix im Build
- Skill-Wizard:
  - `Schritt duplizieren`
  - `Step ID` aus der sichtbaren UI entfernt
  - `SSH Command` als groesseres Feld mit hoeherem Limit
- neue Samples/Connections fuer:
  - `SMB`
  - `Discord`
  - `RSS`
- aktualisiertes Linux-Update-Sample

### alpha10

- Stats-Fix fuer `bepreiste Anfragen`
- `0.0`-Kosten zaehlen nicht mehr als bepreist
- fruehe Pipeline-Pfade loggen keine Fake-Preise mehr
- Release-Label:
  - `0.1.0-alpha10`

### alpha11

- Connection-UX auf den Connection-Seiten beruhigt:
  - bestehende Profile direkt anklickbar
  - `Bearbeiten` aus dem Kopfbereich entfernt
  - `Neu` als klarer Einstieg
  - im Create-Modus: `Zurueck zu Verbindungen`
- Skill-Wizard:
  - duplizierte Steps landen direkt unter dem aktuellen Step
  - Steps lassen sich nach oben/unten verschieben
  - Reihenfolge wird vor dem Speichern sauber neu nummeriert
- Custom-Skill-Prioritaet vor generischem Capability-Pfad
  - klar passende Skills gewinnen jetzt vor z. B. direktem Discord-Senden
- Release-Label:
  - `0.1.0-alpha11`

### alpha12

- Stats:
  - Qdrant-Groesse wird im separaten Docker-/Compose-Betrieb ueber Qdrant-Telemetrie/API ermittelt
  - `Startup Preflight` zeigt die vier Kernchecks auf Desktop als eine Reihe
- Release-Label:
  - `0.1.0-alpha12`

### alpha13

- Memory:
  - Chat-Forget raeumt leere Qdrant-Collections sofort auf
- Discord:
  - Skill-Error-Alerts werden gekuerzt/sanitized
  - Statuschips fuer `Testposts aktivieren` / `Skill-Ziel erlauben` sind klarer als Read-only-Anzeige gestaltet
- Connections:
  - SFTP `SSH-Daten uebernehmen` im Create-Modus speichert wieder korrekt ein neues Profil
  - RSS nutzt dieselbe `Neu` / Klick-auf-Karte-zum-Editieren-Logik wie die anderen Connection-Seiten
- UI:
  - Back-Pfeil sitzt sauber unter der Topbar und ist etwas sichtbarer
- Release-Label:
  - `0.1.0-alpha13`

### alpha14

- Stats / Statistics:
  - `Aktivitaeten & Runs` ist direkt in `/stats` integriert
  - der separate Menuepunkt `Aktivitaeten` ist aus dem User-Menue entfernt
  - Activity-KPIs stehen in einer kompakten 4er-Reihe mit Mobile-Fallback
- Pricing:
  - manueller Button `Preise aktualisieren` in `/stats`
  - OpenAI-/Anthropic-Preise werden aus dem ARIA-bundled Pricing Seed in die lokale ARIA-Preisliste uebernommen
  - OpenRouter-Preise werden ueber `https://openrouter.ai/api/v1/models` synchronisiert
  - aktualisierte Preise werden in `config/config.yaml` persistiert
- Connections:
  - Karten aus `Live-Status aller Profile` sind jetzt der direkte Einstieg in den Edit-Modus
  - Zusatzbloecke wie `Geladenes Profil` / separate Direkt-Links sind entfernt
  - `ARIA_PUBLIC_URL` / `aria.public_url` wird fuer Host-/Discord-Links genutzt statt Docker-Bridge-IP
  - RSS-Save-Redirect auf `Zurueck zu Verbindungen` korrigiert
- RSS / OPML:
  - OPML Import/Export auf der RSS-Connection-Seite
  - OPML-Import erzeugt pro Feed ein eigenes RSS-Profil
  - doppelte Feed-URLs werden beim Import uebersprungen
  - pro RSS-Profil gibt es `poll_interval_minutes`
  - RSS-Seite nutzt bei frischem Status den Cache statt jeden Feed bei jedem Seitenaufruf live zu pingen
  - OPML-Export schreibt die RSS-Sammlung als OPML 2.0
- UI / i18n:
  - `Stats` heisst in DE jetzt `Statistiken`, in EN `Statistics`
- Release-Label:
  - `0.1.0-alpha14`

### alpha15

- Stats:
  - `Aktivitaeten & Runs` auf `/stats` unter `Live-Status aller konfigurierten Verbindungen` verschoben
- RSS:
  - OPML-Import-Upload repariert (`opml_file missing` / Multipart-CSRF)
  - `OPML Import / Export` als einklappbarer Block
  - RSS-Kategorien als einklappbare Gruppen
  - nach Klick auf einen Feed zeigt der Edit-Modus nur noch diesen Feed + Formular + Loeschen
- Release-Label:
  - `0.1.0-alpha15`

### alpha16

- LLM:
  - leere Provider-Antworten werden als sauberer `LLMClientError` behandelt
  - ARIA faellt dadurch nicht mehr still auf `Ich habe gerade keine Antwort erzeugt.` zurueck
- RSS:
  - `Jetzt pingen` fuer den aktuell gewaehlten Feed im Edit-Modus
  - `Kategorien mit LLM aktualisieren` ist jetzt ein klarer Button statt ein dezenter Link
  - EN-Label: `Refresh categories with LLM`
- Release-Label:
  - `0.1.0-alpha16`

### alpha17

- LLM:
  - Default `max_tokens` fuer neue Setups/Profile auf `4096` erhoeht
  - reduziert `finish_reason=length` bei normalen Chat-Antworten
- Pricing:
  - Kostenberechnung nutzt jetzt eine LiteLLM-Fallback-Preisliste
  - bekannte Modelle wie `gpt-5.1` bekommen dadurch auch dann USD-Kosten, wenn `pricing.chat_models` in der Config noch leer ist
- Release-Label:
  - `0.1.0-alpha17`

### alpha18

- Custom-Skill-Routing:
  - Description-Match entschaerft
  - generische Admin-/Storage-Fragen wie LVM/ZFS/Btrfs triggern den Linux-Updates-Skill nicht mehr nur wegen `Ubuntu` + `Server`
  - echte Linux-Update-Fragen triggern den Skill weiter
- RSS:
  - RSS-Verbindungstests nutzen jetzt einen browserartigen `User-Agent`
  - RSS-Skill-Reads nutzen denselben robusteren Header
  - behebt Feeds, die im Browser funktionieren, aber vorher in ARIA mit `HTTP Error 403: Forbidden` gescheitert sind
- Release-Label:
  - `0.1.0-alpha18`

### alpha19

- Mobile/iPhone:
  - `Admin aktiv` sitzt auf kleinen Screens rechts in der Menu-Zeile statt neben dem A.R.I.A.-Titel
  - Desktop bleibt unveraendert
- RSS:
  - RSS-Statuskarten auf der RSS-Seite nutzen beim Seitenaufbau nur noch den letzten Cache-Stand
  - bei fehlendem/abgelaufenem Cache wird **kein synchroner Live-Ping** mehr gestartet
  - stattdessen zeigt ARIA einen Hinweis und `Jetzt pingen` bleibt die explizite Live-Aktion pro Feed
  - Feed-Loeschen/Editieren blockiert dadurch nicht mehr 20-40 Sekunden wegen eines langsamen RSS-Endpunkts
  - RSS-Verbindungstests lesen mehr als den alten 8-KB-Ausschnitt und akzeptieren auch RSS-1.0-Roots wie `<rdf:RDF>`
  - behebt valide Feeds wie NVD/Debian, die vorher faelschlich mit `ungueltiges XML` rot wurden
  - RSS-Profile haben jetzt `group_name` als manuell setzbare Gruppe/Kategorie
  - OPML-Import uebernimmt die erste OPML-Kategorie als Start-Gruppe
  - OPML-Export nutzt `group_name` als Outline-Gruppe
  - `Kategorien mit LLM aktualisieren` sortiert nur noch Feeds ohne manuell gesetzte Gruppe neu
- Release-Label:
  - `0.1.0-alpha19`

### alpha20

- RSS:
  - Feld `Gruppe / Kategorie` bietet jetzt Dropdown-Vorschlaege aus bestehenden Gruppen, bleibt aber frei editierbar fuer neue Kategorien
  - Feed-URL-Dedupe normalisiert URLs vor Vergleich/Speicherung
  - Varianten wie `/feed`, `/feed/`, Default-Port `:443`, Fragment-Hashes und Tracking-Parameter wie `utm_*`/`fbclid` werden zusammengefuehrt
  - JSON-URLs in RSS liefern jetzt eine klare Fehlermeldung mit Hinweis auf HTTP-API-Connections
  - auf RSS-Detailseiten geht `Zurueck zur RSS-Uebersicht` wieder direkt nach `/config/connections/rss`
  - lokale RSS-Suche nur ueber RSS-Titel, URL, Ref, Gruppe und Tags
  - passende RSS-Gruppen klappen bei aktiver Suche automatisch auf
  - RSS-Gruppen werden alphabetisch sortiert
  - RSS-Gruppenuebersicht nutzt ein dichteres responsives 2-3-Spalten-Grid mit Mobile-Fallback
- Release-Label:
  - `0.1.0-alpha20`

### alpha21

- RSS:
  - globales `Ping-Intervall` fuer alle RSS-Feeds statt pro Feed einzeln pflegen
  - alle bestehenden RSS-Profile werden beim Speichern des globalen Intervalls auf denselben Wert synchronisiert
  - RSS-Poll-Faelligkeit wird pro Feed stabil per Hash-Offset gestaffelt, damit nicht alle Feeds auf derselben Intervall-Kante faellig werden
  - lokale RSS-Suche blendet nicht passende Gruppen/Feeds wieder korrekt aus
  - das Suchfeld reagiert auch auf das kleine `x` zum Leeren
  - natuerlichere RSS-Fragen wie `was fuer news gibs auf heise` werden besser als RSS-Intent erkannt
  - RSS-Routing nutzt jetzt auch Titel, Kurzbeschreibung, Aliase und Tags der RSS-Profile
  - Button `Check mit LLM` im RSS-Metadatenblock fuellt Titel, Kurzbeschreibung, Aliase und Tags vor bzw. ergaenzt sie
- Statistiken:
  - `Startup Preflight` und `Systemzustand` zeigen Status jetzt nur noch als gruene/gelbe/rote Laempchen statt ausgeschriebener `OK/Warn/Error`-Labels
- Themes:
  - neue Themes `CyberPunk Pulse`, `8-Bit Arcade`, `Amber CRT` und `Deep Space`
- Release-Label:
  - `0.1.0-alpha21`

### alpha22

- Themes:
  - `CyberPunk Pulse` staerker Richtung Hot-Pink/Magenta gezogen, weniger violette Flaechen
- Docs / Release:
  - Doku-Struktur unter `docs/` und der damaligen lokalen History-Ablage aufgeraeumt
  - `Hilfe` und `Produkt-Info` als Read-only-Seiten im UI angebunden
  - `LICENSE` und `THIRD_PARTY_NOTICES.md` ergaenzt
  - `docs/product/roadmap.md` als GitHub-tauglicher Roadmap-Snapshot ergaenzt
  - `docs/release/github-release-notes-template.md` als Release-Notes-Vorlage ergaenzt
  - `CHANGELOG.md` `Unreleased`-Block mit dem aktuellen dev-Stand befuellt
  - `README.md` und zentrale Public-Docs sprachlich/funktional auf den aktuellen Public-Alpha-Stand geglaettet
  - neutrale Beispielwerte in `docker/aria-stack.env.example`, `docs/setup/portainer-deploy-checklist.md` und `docs/help/memory.md`
  - `.gitignore` um Python-/Build-Artefakte und lokale TARs erweitert
- Onboarding:
  - Bootstrap-/Admin-/User-Modus in Login-, Benutzer- und Security-UI klarer erklaert
- Statistiken:
  - Statistik-Reset mit `RESET`-Bestaetigung auf `/stats`
  - Qdrant-Groessenanzeige robuster fuer separates Compose-/Portainer-Qdrant-Volume vorbereitet
- Memory:
  - Auto-Memory filtert fluechtige Einmalfragen und reine Tool-/Action-Prompts beim automatischen Persistieren staerker heraus
  - echte Fakten/Preferences und deklarativer Nutzerkontext werden weiter gespeichert
  - Architekturentscheidung festgehalten: Capability-Ergebnisse werden bewusst **nicht** pauschal automatisch in Memory persistiert; spaeter nur ueber gezielte Summary-/State-Memory-Flows
  - Memory-Export als JSON-Download in `/memories`
  - gewichtetes Multi-Collection-Recall mit einem expliziten Regression-Test gegen Fact-vs-Session-Ranking abgesichert
- Mobile/iPhone:
  - Chat-Debug-Header bricht lange `Tages-Kontext`- und `Login-Session`-IDs jetzt sauber um, statt horizontalen Page-Overflow zu erzeugen
- Release-Label:
  - `0.1.0-alpha22`

### alpha23

- Themes:
  - `CyberPunk Pulse` nochmals pinker gezogen, waehrend Helper-/Meta-/Status-Texte und Chips im Theme gezielt auf neon-gruen `#00ff00` gehen
- Mobile/iPhone:
  - Chat-Scroller und Message-Bubbles auf vertikales Panning geklemmt
  - horizontale Drift/seitliches Mitschieben beim Scrollen weiter reduziert
  - lange Bubble-Inhalte, Meta-Badges und Details-Zeilen brechen jetzt konsequent innerhalb der Bubble um
- Packaging:
  - `docs/` wird jetzt ins Docker-Image kopiert, damit `/help` und `/product-info` im Container nicht mehr auf fehlende Markdown-/SVG-Dateien laufen
- UI / Doku-Navigation:
  - `Produkt-Info` aus dem Top-Menue entfernt und stattdessen als Kachel unter `/help` verlinkt
- Statistiken:
  - Qdrant-Groessenanzeige faellt bei `Telemetry · n Collections`, aber `0 B`, jetzt erst noch auf lokale Storage-Pfade zurueck
  - `0 B` aus Qdrant-Telemetrie blockiert dadurch nicht mehr den Volume-/Filesystem-Fallback
- Release-Label:
  - `0.1.0-alpha23`

### alpha24

- UI / Produkt-Info:
  - `Copy Pack`-Kachel aus `/product-info` entfernt; dort bleiben nur Overview, Feature-Liste und Architektur
- Themes:
  - `CyberPunk Pulse`: Buttons und Menu-Beschriftung neon-gruen, damit die Controls klarer gegen die pinken Flaechen stehen
  - `Deep Space`: dunklerer, violett-/nebula-lastiger Farbschnitt, damit das Theme weniger nach `Harbor Blue` aussieht
- Samples / Skills / Connections:
  - `samples/` wird jetzt ins Docker-Image kopiert, damit Sample-Skills, Sample-Connections und Guardrail-Beispiele im Container unter `/app/samples` verfuegbar sind
  - `/skills` zeigt mitgelieferte Sample-Skills aus `/app/samples/skills` direkt an und kann sie serverseitig per Klick importieren
  - `/config` zeigt mitgelieferte Sample-Connections aus `/app/samples/connections` direkt an und kann sie serverseitig in `config.yaml` importieren, ohne bestehende Refs zu ueberschreiben
  - neuer Sample-Skill `rss-morning-briefing-to-discord-template.json` fuer ein taegliches, per LLM kuratiertes Multi-RSS-Briefing nach Discord
  - Skill-Wizard erklaert bei `llm_transform` jetzt direkt die Platzhalter `{prev_output}` und `{s1_output}` / `{s2_output}` fuer Multi-Step-Aggregation
- Release-Label:
  - `0.1.0-alpha24`

## Auf `dev` vorbereitet fuer den naechsten Build

- Hilfe:
  - `docs/help/alpha-help-system.de.md` und `docs/help/alpha-help-system.en.md` als praktische, menschenlesbare Alpha-Kurzhilfe in DE/EN ergaenzt
  - `/help` zeigt jetzt je nach aktiver UI-Sprache diese Alpha-Hilfe statt den internen Help-System-Entwurf `docs/help/help-system.md` direkt zu rendern
- Chat-Toolbox:
  - Skill-Eintraege zeigen jetzt den eigentlichen Skill-Namen als Titel, einen kleinen `/skill`-Badge und darunter Beschreibung/Beispiel-Trigger
  - lange Skill-Titel und Hinweise koennen in der Toolbox sauber umbrechen statt unsichtbar abgeschnitten zu werden
- Menue:
  - `Hilfe` sitzt jetzt nach `Einstellungen` und vor `Benutzer`
- README:
  - Root-`README.md` klar in `English`- und `Deutsch`-Abschnitt getrennt, mit EN zuerst und DE als eigener, eindeutig markierter Block weiter unten
- `/stats` -> `Systemzustand`: ARIA Runtime, Model Stack, Memory / Qdrant, Security Store und Activities / Logs bekommen jetzt ebenfalls die normalen Status-Laempchen
- Repo-/Privacy-Sweep:
  - persoenliche Dev-Host-Defaults aus `docker/pull-from-dev.sh` entfernt
  - `config/secrets.env` neutralisiert
  - Root-Artefakte `=1.2` und `=2.1` entfernt
  - `docs/setup/portainer-deploy-checklist.md` von `/home/fischerman/ARIA` auf neutraleren Beispielpfad umgestellt

### alpha154

- Routing / Personal Integrations:
  - erster echter `Google Calendar`-Produktpfad als `read-only`-Faehigkeit integriert
  - natuerliche Kalender-Prompts wie `was steht heute an?`, `was habe ich morgen im kalender?` und `wann ist mein naechster termin?` laufen jetzt ueber denselben Routing-/Planner-/Payload-/Guardrail-Pfad wie die restlichen Aktionen
  - neuer Executor `calendar_read` mit Google-Token-Refresh und read-only Event-Abfrage
- Connections / Produktfluss:
  - `Google Calendar` als eigener Connection-Typ mit Secure-Store fuer `client_secret` und `refresh_token`
  - read-only Connection-Test gegen Google-Kalender-Metadaten
- Memory / UX:
  - redundanten `Naechste Schritte`-Block auf `/memories` entfernt
  - `Auto-Memory`-Kachel auf `/memories` fuehrt jetzt direkt zum passenden Setup-Block
  - `Memory backend enabled` als irrefuehrenden Kill-Switch aus `/memories/config` entfernt; Qdrant-Setup haelt Memory jetzt aktiv
  - Restart-Flaeche fuer `Qdrant` und `SearXNG` unter `/config/operations`
- Robustheit:
  - externe Connection-Fehler fuer Auth, Berechtigungen, TLS/SSL, Timeout und Erreichbarkeit produktfaehiger formuliert
  - Connection-Koepfe sprechen klarer ueber `verbunden`, `Anmeldung fehlt` und `optional`
- Tests:
  - voller Testlauf: `602 passed, 11 warnings`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha154-local.tar`
- Release-Label:
  - `0.1.0-alpha154`

### alpha155

- Google Calendar / Produktfluss:
  - Setup-Seite fuer `Google Calendar` bewusst auf denselben Clean-/Domain-Stil getrimmt; die innere Hilfeflaeche ist keine weitere schwere `config-card` mehr
  - Google-Setup jetzt als echter Enduser-Flow direkt auf der Seite:
    - API aktivieren
    - OAuth Branding / Audience / Client vorbereiten
    - Refresh-Token im OAuth Playground erzeugen
    - Werte in ARIA eintragen
  - alle benoetigten Google-Links sind direkt auf der Seite sichtbar, damit die Konfiguration ohne externe Nebensuche machbar bleibt
  - Feldreihenfolge und Feldhinweise fuer `Client ID`, `Calendar ID`, `Timeout`, `Client Secret` und `Refresh Token` logisch nach dem realen Setup-Ablauf geordnet
- Tests:
  - voller Testlauf: `602 passed, 11 warnings`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha155-local.tar`
- Release-Label:
  - `0.1.0-alpha155`

## Noch offen / weiter sammeln

- Docker-Hub-Hinweis auf neue Version statt In-App-Update
- Memory-Export auf `prod` live gegen echte Qdrant-Daten testen
- weitere Single-User-/Personalisierungs-Polishes

### Public release 0.1.0-alpha.122

- Oeffentliche Versionslinie von `0.1.0-alpha121` auf `0.1.0-alpha122` angehoben.
- Roll-up Release ueber die intern getesteten Staende `alpha122` bis `alpha167`.
- Git:
  - Commit: `bae8a94`
  - Tag: `v0.1.0-alpha.122`
- Docker Hub:
  - `fischermanch/aria:0.1.0-alpha.122`
  - `fischermanch/aria:alpha`
  - Digest: `sha256:f023bf58cd0d3e32007bb769ea0288beb4390644ea4662adf73cee99d77a35ae`
- Release-Schwerpunkte:
  - `Google Calendar` read-only als erster persoenlicher Enduser-Pfad
  - `Notizen` als eigener Markdown-first Bereich mit Qdrant-Indexierung
  - `Beobachtete Webseiten` als neue Quellen-Verbindung
  - vereinheitlichter Routing-/Planner-/Guardrail-Pfad
  - groesserer UI-, Doku- und Runtime-Cleanup
- Tests:
  - voller Testlauf: `634 passed, 11 warnings`
- Hinweis:
  - GitHub Release API-Eintrag konnte in dieser Shell nicht erzeugt werden, weil `GITHUB_TOKEN` hier nicht gesetzt ist.

### Public release 0.1.0-alpha.125

- Oeffentliche Versionslinie von `0.1.0-alpha124` auf `0.1.0-alpha125` angehoben.
- Fokus bewusst eng auf den Managed-Update-Pfad gelegt.
- Git:
  - Tag: `v0.1.0-alpha.125`
- Docker Hub:
  - `fischermanch/aria:0.1.0-alpha.125`
  - `fischermanch/aria:alpha`
- Release-Schwerpunkte:
  - fehlgeschlagene Managed-Updates fuehren nach einem kaputten `validate` jetzt automatisch genau einen `repair` aus
  - stale roter `/updates`-Status heilt sich automatisch, sobald `./aria-stack.sh validate` wieder sauber ist
  - `repair` / `restart` / `update` behandeln jetzt die komplette Runtime-Gruppe inklusive `qdrant`, `searxng-valkey` und `searxng`

### Public release 0.1.0-alpha.127

- Oeffentliche Versionslinie von `0.1.0-alpha126` auf `0.1.0-alpha127` angehoben.
- Fokus bewusst eng auf Discoverability fuer den Update-Pfad gelegt.
- Git:
  - Tag: `v0.1.0-alpha.127`
- Docker Hub:
  - `fischermanch/aria:0.1.0-alpha.127`
  - `fischermanch/aria:alpha`
  - Digest: `sha256:c12478e91fb52f75476df7a68ba07b8f2074ca0ec5969045b3149a7f18f380f5`
- Release-Schwerpunkte:
  - `Updates` ist im Hauptmenue jetzt ein eigener Zielpunkt statt nur implizit ueber das kleine Header-Laempchen auffindbar
  - wenn ein neuer Stand verfuegbar ist, markiert das Menue den Eintrag direkt mit `Update verfuegbar`
  - der reparierte Managed-Update-Pfad aus `alpha126` bleibt Basis und ist fuer Admins dadurch im Alltag schneller auffindbar
- Tests:
  - voller Testlauf: `643 passed, 23 warnings`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha127-local.tar`
- Release-Label:
  - `0.1.0-alpha127`

### alpha168

- Google Calendar:
  - freundlichere und praezisere Fehlertexte fuer typische Google-OAuth-/API-Probleme wie widerrufene Tokens, deaktivierte API, fehlende Berechtigungen und Rate Limits
  - natuerlichere Kalendersuche versteht auch einfache unquoted Formulierungen wie `nur Zahnarzttermine`
  - kurze Follow-ups wie `und morgen?` koennen den letzten Kalenderkontext weiterverwenden
  - Setup-Seite erklaert klarer, dass nach abgelaufenem Google-Login haeufig nur das Refresh-Token erneuert werden muss
- Notizen / beobachtete Webseiten im Chat:
  - Notiz-Ordner direkt im Chat auflisten
  - Notizen pro Ordner im Chat auflisten
  - Notizen ueber natuerliche Suchbegriffe direkt oeffnen
  - beobachtete Webseiten im Chat oeffnen und gruppiert anzeigen
  - Admin-Kurzbefehle fuer `beobachte https://...` und natuerlichere Website-Aenderungen wie Titel/Gruppe/URL
- Versionslinie:
  - interner Build auf `0.1.0-alpha168` angehoben
- Tests:
  - gezielte Regressionen fuer Calendar, Notes, Websites, Admin-Shortcuts und Pipeline: `217 passed`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha168-local.tar`
- Release-Label:
  - `0.1.0-alpha168`

### alpha169

- Google Calendar:
  - echter Google-Login-Flow direkt aus ARIA statt manuellem OAuth-Playground-Copy/Paste
  - neuer Button `Mit Google verbinden` auf der Google-Calendar-Verbindungsseite
  - ARIA speichert das Refresh-Token serverseitig nach dem Google-Callback selbst
  - Reconnect fuer abgelaufene oder widerrufene Tokens laeuft ueber denselben Login-Flow
- Notizen / beobachtete Webseiten / Calendar-Hardening aus `alpha168` bleiben Basis
- Versionslinie:
  - interner Build auf `0.1.0-alpha169` angehoben
- Tests:
  - gezielte Config-/Google-Calendar-Regressionen: `80 passed`
  - weitere Pipeline-/Router-Regressionen: `126 passed`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha169-local.tar`
- Release-Label:
  - `0.1.0-alpha169`

### alpha170

- Google Calendar:
  - die Verbindungsseite zeigt jetzt nur noch den neuen Google-Login-zentrierten Produktpfad statt den alten manuellen Refresh-Token-Leitfaden
  - der alte OAuth-Playground-/Handarbeitsweg ist aus der prominenten Setup-Anleitung entfernt
- Notizen:
  - Ordner koennen direkt in der Notes-Oberflaeche umbenannt werden
  - der Editor erklaert jetzt explizit, dass eine Titelaenderung die Notiz umbenennt
  - lange Notiztitel umbrechen im Board jetzt sauber und zerziehen das Layout nicht mehr
  - `oeffne notizen in ordner ...` bleibt jetzt im Notes-Produktpfad statt in generische Datei-/SFTP-Flows zu kippen
- Versionslinie:
  - interner Build auf `0.1.0-alpha170` angehoben
- Tests:
  - gezielte Google-Calendar-/Notes-Regressionen: `66 passed`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha170-local.tar`
- Release-Label:
  - `0.1.0-alpha170`

### alpha171

- Google Calendar:
  - Upload einer Google OAuth Client JSON direkt in ARIA moeglich
  - Client-ID und Client-Secret koennen dadurch automatisch aus der JSON uebernommen werden
  - `Mit Google verbinden` nutzt den hochgeladenen OAuth-Client jetzt direkt weiter
- Routing / RSS:
  - RSS-Profile ziehen `group_name` jetzt staerker in die semantische Alias-Bildung ein
  - bei mehreren RSS-Kandidaten darf ein bounded RSS-LLM-Resolver jetzt einen schwachen fruehen Alias-Treffer ueberstimmen
  - Ziel: weniger Keyword-Hardcoding und bessere Feedauswahl bei Formulierungen wie `rss news tech was gibts neues`
- Versionslinie:
  - interner Build auf `0.1.0-alpha171` angehoben
- Tests:
  - gezielte Config-/Routing-/Notes-Regressionen: `158 passed`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha171-local.tar`
- Release-Label:
  - `0.1.0-alpha171`

### alpha172

- Routing / Planner / Live-Chat:
  - gemeinsamer `candidate resolver` fuer Connection-Ziele weiter ausgebaut
  - gemeinsamer `routing decision record` eingefuehrt und in den aktiven Unified-Routing-Pfad gehaengt
  - Explain-/Debug-Spuren fuer Routing-Entscheidungen im Unified-Pfad ausgebaut
  - bounded LLM fuer die Connection-Auswahl jetzt auch fuer weitere produktische Connection-Kinds nutzbar
    - `discord`
    - `google_calendar`
    - `webhook`
    - `email`
  - starke Routing-Chain-/Qdrant-/Alias-Treffer bleiben weiterhin vorrangig und werden nicht spaeter nochmals weich ueberschrieben
- Versionslinie:
  - interner Build auf `0.1.0-alpha172` angehoben
- Tests:
  - gezielte Routing-Regressionen: `102 passed`
- Build-Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha172-local.tar`
- Release-Label:
  - `0.1.0-alpha172`

### alpha173

- Routing / RSS:
  - gleich starke Alias-Treffer werden nicht mehr still per Ref-Sortierung entschieden
  - mehrdeutige Alias-Matches enthalten sich jetzt deterministisch und geben an den bounded semantischen Re-Rank weiter
  - das behebt speziell RSS-Faelle wie `rss ... tech news ...`, bei denen bisher der falsche Feed wegen Alias-Tie zu frueh gewonnen hat
- Versionslinie:
  - interner Build auf `0.1.0-alpha173` angehoben
- Tests:
  - gezielte Routing-Regressionen: `100 passed`

### alpha174

- Retrieval-First Planner / SSH-POC:
  - gemeinsames `PlannerCandidate`-/`PlannerInputSet`-Schema jetzt aktiv fuer Connection- und Action-Kandidaten
  - erster bounded Planner als eigenes Modul eingefuehrt
  - Planner-POC haengt jetzt im aktiven Unified-Routing-/Execution-Pfad
  - bewusst nur fuer den SSH-Pilot und nur dann, wenn mehrere bounded Connection-Ziele vorliegen
  - klare Ein-Ziel-SSH-Faelle bleiben deterministisch und schnell
- Versionslinie:
  - interner Build auf `0.1.0-alpha174` angehoben
- Tests:
  - gezielte Planner-/Pipeline-Regressionen: `118 passed`

### alpha175

- SSH-/Infra-Routing:
  - natuerliche Infra-Phrasen wie `backup server` und `monitoring server` triggern jetzt frueher den SSH-/Infra-Pfad statt in generischen Chat/RAG zu kippen
  - explizite Zielphrasen wie `proxmox` werden nicht mehr still von alten `memory_hint`-Treffern auf andere Hosts umgebogen
  - natuerliche Formulierungen wie `wie geht es dem monitoring server` werden als `ssh_command` mit `uptime` erkannt
- Versionslinie:
  - interner Build auf `0.1.0-alpha175` angehoben
- Tests:
  - gezielte Capability-/Pipeline-Regressionen: `142 passed`

### alpha176

- SSH Planner POC:
  - der bounded SSH-POC sieht fuer generische Host-/Status-Faelle jetzt nur noch die passenden SSH-Templates
  - Custom Skills wie Fleet-/Discord-Healthchecks werden in diesem engen POC nicht mehr als Aktion fuer einzelne Host-Status-Fragen ausgewaehlt
  - damit kippen Prompts wie `wie geht es dem monitoring server` nicht mehr in einen unpassenden Fleet-Healthcheck
- Versionslinie:
  - interner Build auf `0.1.0-alpha176` angehoben
- Tests:
  - gezielte Pipeline-Regressionen: `97 passed`

### alpha177

- SSH-/Planner-/Routing-Nachzug:
  - Short-Term Session Context wird jetzt in den bounded Planner eingespeist
  - generische Ein-Wort-Labels wie `server`, `host`, `system` oder `node` duerfen keine harten Connection-Treffer mehr ausloesen
  - dadurch springen Phrasen wie `backup server` nicht mehr still auf einen beliebigen Management-Host
- Versionslinie:
  - interner Build auf `0.1.0-alpha177` angehoben
- Tests:
  - gezielte Resolver-/Pipeline-Regressionen: `110 passed`

### alpha178

- SSH-/Routing-Guard:
  - semantische Zielphrasen wie `backup server`, `monitoring server` oder `management server` werden nicht mehr als blosse Soft-Hints abgewertet
  - `memory_hint` darf kein Forced-Routing mehr ausloesen, wenn der User ein eigenes Server-Ziel nennt und der Memory-Treffer nicht dazu passt
  - weiche Zielphrasen wie `alerts channel`, `mailbox` oder `topic` bleiben fuer Discord-/Mail-/MQTT-Faelle bewusst weich
- Versionslinie:
  - interner Build auf `0.1.0-alpha178` angehoben
- Tests:
  - gezielte Pipeline-Regressionen: `101 passed`

### alpha179

- Unified-Routing-Debug / stale Memory:
  - Live-Debug-Zeilen fuer `capability_draft`, `candidate_pool`, `memory_hint` und geblockte Memory-Hints direkt im aktiven Unified-Routing-Pfad sichtbar gemacht
  - explizite SSH-Ziele werden im Prozesspfad jetzt vor stale `memory_hint` festgezogen
  - Prozess-Level-Regressionen gegen alte `memory_hint`-Uebersteuerung hinzugefuegt
- Versionslinie:
  - interner Build auf `0.1.0-alpha179` angehoben
- Tests:
  - gezielte Pipeline-Regressionen: `103 passed`

### alpha180

- Capability-Router / SSH-Zielphrasen:
  - generische SSH-Aliase wie `server` duerfen aktuelle Zielphrasen wie `backup server` oder `monitoring server` nicht mehr still in einen falschen `explicit_ref` uebersetzen
  - `management server` bleibt weiter ein gueltiger expliziter Treffer
- Versionslinie:
  - interner Build auf `0.1.0-alpha180` angehoben
- Tests:
  - gezielte Capability-/Pipeline-Regressionen: `152 passed`

### alpha181

- Semantic-LLM-Guard fuer SSH-Ziele:
  - `semantic_llm` darf bei gesetztem `requested_connection_ref` nur dann ein SSH-Ziel waehlen, wenn dieses Ziel die angefragte Rollenphrase auch wirklich stuetzt
  - dadurch springt `backup server` nicht mehr frei auf `ubnsrv-syncthing`
  - `monitoring server` kann weiter sinnvoll auf `ubnsrv-netalert` gehen
- Versionslinie:
  - interner Build auf `0.1.0-alpha181` angehoben
- Tests:
  - gezielte Pipeline-/Capability-Regressionen: `154 passed`

### alpha182

- SSH-Zielwahl / Pending-UX:
  - fuer Rollenphrasen mit fehlendem SSH-Ziel wird jetzt sauber nach einem Profil gefragt, statt zu frueh einen Confirm-Token anzubieten
  - fehlendes `connection_ref` kann in Pending-Follow-ups jetzt direkt mit einem Profilnamen gefuellt werden
  - der semantische LLM-Rerank darf bei gesetzter Rollenphrase frueher eingreifen, auch wenn ein schwacher generischer Kandidat schon hoch scored
  - die Fehlermeldung bei unbekannten Rollenprofilen wurde auf einen hilfreichen Klaerungspfad umgestellt
- Versionslinie:
  - interner Build auf `0.1.0-alpha182` angehoben
- Tests:
  - gezielte Pipeline-/Chat-Regressionen: `116 passed`

### alpha183

- Pending-Flow / SSH-Zielklaerung:
  - offene `connection_ref`-Rueckfragen konsumieren jetzt nur noch echte Profilnamen statt versehentlich eine komplett neue Anfrage als Zielprofil zu behandeln
  - dadurch kann nach einer offenen `backup server`-Rueckfrage ein neuer Prompt wie `wie geht es dem monitoring server` wieder normal neu geroutet werden
  - fehlende Zielprofile bleiben weiter sauber im Klaerungspfad statt in einen kaputten Confirm-/Execution-Pfad zu kippen
- Versionslinie:
  - interner Build auf `0.1.0-alpha183` angehoben
- Tests:
  - gezielte Pipeline-/Chat-Regressionen: `117 passed`

### alpha184

- SSH-Alias-Lernen / Pending-Chat:
  - wenn ein fehlendes SSH-Zielprofil im Chat manuell nachgereicht wird, kann ARIA jetzt direkt anbieten, sich die urspruengliche Rollenphrase als Alias fuer das gewaehlte Profil zu merken
  - offene `connection_ref`-Rueckfragen bleiben dabei weiter auf echte Profilnamen begrenzt und schlucken keine neue Anfrage
- SSH-Antwortqualitaet:
  - erfolgreiche `uptime`-Antworten werden fuer den Chat jetzt als kurze, menschlichere Statuszusammenfassung formatiert
  - Detailzeilen mit Profil und ausgefuehrtem Befehl bleiben unveraendert sichtbar
- Versionslinie:
  - interner Build auf `0.1.0-alpha184` angehoben
- Tests:
  - gezielte SSH-/Pipeline-/Chat-Regressionen: `120 passed`

### alpha185

- Versionslinien-Cleanup:
  - frischer interner Build auf eigener, sauber neuer Versionsnummer statt weiterer Wiederverwendung von `alpha184`
  - aktueller Code-Stand der SSH-Routing-/Pending-/Antwortverbesserungen wird damit eindeutig als `0.1.0-alpha185` ausgeliefert
- Versionslinie:
  - interner Build auf `0.1.0-alpha185` angehoben
- Tests:
  - gezielte SSH-/Pipeline-/Chat-Regressionen: `169 passed`

### alpha186

- Kosten-/Stats-Cleanup:
  - Notes-/Routing-Embedding-Pfade haengen jetzt konsistenter am gemeinsamen `usage_meter`
  - Routing-Index-Refreshes im aktiven Runtime-/Pipeline-Pfad geben ihre Embedding-Kosten nicht mehr still an den Stats vorbei
  - `/stats` zeigt oben jetzt getrennt `Chat Tokens`, `Embedding Tokens` und `All Model Tokens` statt nur einer zu flachen Gesamtanzeige
- Versionslinie:
  - interner Build auf `0.1.0-alpha186` angehoben
- Tests:
  - gezielte Token-/Stats-/Notes-/Pipeline-Regressionen: `151 passed`

### alpha187

- Routing-/Antwortqualitaet:
  - RSS-Themenphrasen wie `tech news` / `security news` werden nicht mehr zu frueh als expliziter Feedname festgezogen
  - Notes-Ordner werden jetzt case-insensitiv auf vorhandene Ordner wie `Area41` aufgeloest
  - SSH-Follow-ups wie `pruefe dort den status` und `beim monitoring server` bleiben besser im letzten SSH-Kontext
  - SSH-Healthchecks laufen als begrenzter Kurzcheck ueber `uptime`, `df -h` und `systemctl --failed --no-pager`
  - die Chat-Antworten fuer SSH-Kurzchecks und Alias-/Profilklaerungen sind knapper und hilfreicher formuliert
- Versionslinie:
  - interner Build auf `0.1.0-alpha187` angehoben
- Tests:
  - gezielte Capability-/Pipeline-/Chat-/Notes-Regressionen: `196 passed`

### alpha188

- Routing-Hierarchie weiter geschaerft:
  - frische SSH-Zielphrasen wie `backup server` oder `management server` werden nicht mehr vorschnell als blosse Follow-ups auf den letzten Host umgeschrieben
  - echte SSH-Follow-ups wie `pruefe dort den status` oder `und wie sieht es beim monitoring server aus` bleiben weiter im letzten SSH-Kontext
  - RSS-Themenwoerter erzeugen nicht mehr zu frueh ein kuenstliches `requested_connection_ref`
  - mehrdeutige direkte RSS-Kategoriematches werden im Memory-/Direktmatch-Pfad nicht mehr blind auf den ersten Feed festgezogen
- Versionslinie:
  - interner Build auf `0.1.0-alpha188` angehoben
- Tests:
  - gezielte Capability-/Pipeline-Regressionen: `167 passed`

### alpha189

- Routing-/Planner-Nachzug:
  - semantisch aufgeloeste SSH-Statusanfragen wie `wie geht es dem monitoring server` koennen jetzt denselben bounded `ssh_health_check`-Pfad wie explizite Health-Checks nutzen
  - RSS-Themenanfragen mit gleich starken Kandidaten wie `tech news` oder `security news` werden nicht mehr frueh auf den ersten Alias-Gewinner festgezogen, sondern fallen in den spaeteren RSS-Verfeinerungspfad
- Versionslinie:
  - interner Build auf `0.1.0-alpha189` angehoben
- Tests:
  - gezielte Capability-/Pipeline-Regressionen: `167 passed`

### alpha190

- Routing-/Antwort-Nachzug:
  - semantische SSH-Statusanfragen wie `wie geht es dem monitoring server` laufen jetzt im aktiven Pfad ebenfalls ueber den bounded Kurzcheck statt nur ueber `uptime`
  - RSS-Themenanfragen wie `tech news` oder `security news` fallen bei Kandidatengleichstand im Unified-Pfad nicht mehr direkt auf `kind_only`, sondern bekommen noch einen RSS-Refiner-Versuch
- Versionslinie:
  - interner Build auf `0.1.0-alpha190` angehoben
- Tests:
  - gezielte Capability-/Pipeline-Regressionen: `169 passed`

### alpha191

- RSS-Priorisierung verfeinert:
  - bei RSS-Themenanfragen mit Gleichstand werden eindeutige Gruppen-/Sammelprofile wie `alle-security-news` vor einzelnen Quellen bevorzugt
  - wenn kein eindeutiges Gruppenprofil erkennbar ist, bleibt die semantische RSS-Verfeinerung aktiv statt wieder hart zu verdrahten
- Versionslinie:
  - interner Build auf `0.1.0-alpha191` angehoben
- Tests:
  - gezielte Capability-/Pipeline-Regressionen: `170 passed`

### alpha192

- RSS-Kategorie-Digests:
  - RSS-Kategorieanfragen wie `security news` oder `tech news` koennen jetzt ueber mehrere Feeds derselben Kategorie als gemeinsame Zusammenfassung laufen statt wieder auf eine einzelne Quelle zu kippen
  - der Unified-Routing-Pfad markiert dafuer RSS-Gruppenplaene explizit, damit die Runtime eine Kategorieausgabe statt eines Einzel-Feed-Reads ausfuehrt
  - Detailzeilen koennen jetzt die ausgefuehrte RSS-Kategorie statt nur eines einzelnen RSS-Profils anzeigen
- Versionslinie:
  - interner Build auf `0.1.0-alpha192` angehoben
- Tests:
  - Pipeline-/Capability-/RSS-Regressionen: `178 passed`

### alpha193

- RSS-Kategorie-Digests weiter verstaerkt:
  - der Chat-/Routing-Pfad kann RSS-Kategorie-Zusammenfassungen jetzt auch dann bilden, wenn im Live-Setup nicht alle Feeds explizit ueber `group_name` gepflegt sind
  - als Fallback werden gleichartige RSS-Themenkandidaten aus dem Refiner zu einem Kategorie-Bundle zusammengezogen statt wieder auf einen Einzel-Feed zu kippen
  - damit sollen Anfragen wie `security news` oder `tech news` im Chat endlich an den sichtbaren Kategorien statt nur an einer Einzelquelle haengen
- Versionslinie:
  - interner Build auf `0.1.0-alpha193` angehoben
- Tests:
  - Pipeline-/Capability-/RSS-Regressionen: `179 passed`

### alpha194

- Web-Chat Stabilitaet:
  - RSS-/Skill-Fehler im Web-Chat crashen nicht mehr ueber einen veralteten Helper-Aufruf in `chat_execution_flow`
  - Discord-Alert-Zeilen fuer Skill-Fehler werden wieder ueber die zentrale UI-Helferfunktion aufbereitet
  - damit sollen Kategorieanfragen wie `security news` bei Fehlern sauber antworten statt mit einer ASGI-Exception zu enden
- Versionslinie:
  - interner Build auf `0.1.0-alpha194` angehoben
- Tests:
  - Chat-/Pipeline-/Capability-/RSS-Regressionen: `192 passed`

### alpha199

- Behavior-Family-Ausbau statt weiterer Connection-Einzelpfade:
  - `sftp` + `smb` teilen jetzt denselben `file_operation`-Contract fuer Planner + Dry-Run
  - `rss` + `website` teilen jetzt denselben `source_lookup`-Contract fuer Planner-Scoring + Preview + Input-Ableitung + Dry-Run
  - `imap` nutzt jetzt denselben `mailbox_access`-Contract fuer Read/Search statt separater Planner-/Dry-Run-Aeste
  - `http_api` nutzt jetzt denselben `request_target`-Contract fuer API-Requests statt separater Planner-/Dry-Run-Aeste
- Website-Produktpfad weiter vereinheitlicht:
  - beobachtete Webseiten laufen fuer Read/List/Gruppenfaelle jetzt staerker ueber den Unified-Routing-/Planner-/Executor-Pfad
  - der alte Chat-Sonderflow bleibt nur noch fuer leichte Config-/Navigationsfaelle
- Versionslinie:
  - interner Build auf `0.1.0-alpha199` angehoben
- Tests:
  - Behavior-/Planner-/Dry-Run-/Pipeline-/Website-/Capability-Regressionen: `249 passed`

### alpha200

- SSH-Operationsvertrag statt nur Prompt-/Review-Safety:
  - neue zentrale `ssh_policy` validiert agentische SSH-Kommandos maschinenlesbar als `allow`, `ask_user` oder `block`
  - mutierende Befehle, Redirects, Backgrounding und Shell-Injection-Konstrukte werden jetzt hart geblockt statt nur bestaetigt
  - komplexe, aber read-only wirkende Ketten werden weiter erlaubt vorzuschlagen, aber systematisch auf Bestätigung gesetzt
  - `allow_commands` wird jetzt strukturiert gematcht statt ueber unscharfe Substring-Treffer
- Enforcement jetzt konsistent in mehreren Schichten:
  - Guardrail-/Confirm-Dry-Run
  - agentische SSH-Decision in der Pipeline
  - direkte SSH-Runtime-Ausfuehrung
  - Partial-Salvage von read-only SSH-Ergebnissen
- Versionslinie:
  - interner Build auf `0.1.0-alpha200` angehoben
- Tests:
  - SSH-Policy-/Dry-Run-/Runtime-/Pipeline-Regressionen: `176 passed`
  - breiter Regression-Block: `131 passed`

### alpha201

- SSH-/API-Feinschliff nach echtem Live-Test:
  - kurze read-only-SSH-Kurzchecks mit `uptime`, `df -h /`, `free -h` und einem einfachen `systemctl is-active ...` laufen jetzt ohne unnötige Bestätigung
  - komplexere Shell-Ketten mit Fallbacks oder Pipes bleiben weiter bewusst im Bestätigungspfad
  - operative Löschanfragen wie `lösche /tmp/test auf dem management server` kippen nicht mehr fälschlich in `memory_forget`
  - generische Aliaswörter wie `server`, `host`, `api` oder `website` werden nicht mehr als harter Direkt-Match aus dem Memory-Pfad missbraucht
  - API-Statusfragen mit Wörtern wie `erreichbar` werden jetzt konsistenter als `api_request` erkannt und für die Status-Zusammenfassung vorbereitet
- Versionslinie:
  - interner Build auf `0.1.0-alpha201` angehoben
- Tests:
  - gezielter Live-Fix-Block: `162 passed`
  - breiter Regression-Block: `152 passed`

### alpha202

- Mehrere Verbindungstypen in einem Sammelblock aufgezogen statt Einzel-Builds:
  - `http_api` hat jetzt einen echten read-only Operationsvertrag mit `allow / ask / block`
  - API-Status-/Health-Antworten fassen jetzt Version, Services und Laufzeit knapper zusammen
  - `imap` liefert für Read/Search jetzt operator-taugliche Mailbox-Zusammenfassungen statt nur rohe Headerlisten
  - `rss`-Kategorie-/Bundle-Fälle liefern jetzt kurze RSS-Digests mit Top-Themen und Quellen
  - `website`-Read/List-Antworten zeigen Gruppe, Beschreibung und Tags sichtbarer statt nur Admin-Link-Dumps
- Versionslinie:
  - interner Build auf `0.1.0-alpha202` angehoben
- Tests:
  - fokussierte API-/IMAP-/RSS-/Website-Blöcke jeweils grün
  - breiter Regression-Block: `322 passed`
### alpha236

- LLM Prompt Debug nach Live-Test korrigiert:
  - redigierte LLM-Audit-Eintraege werden zusaetzlich workeruebergreifend unter `data/runtime/llm_audit.jsonl` gehalten
  - `/config/llm/debug` liest diese geteilten Eintraege, damit Chat-Worker und Debug-Seiten-Worker nicht auseinanderlaufen
  - finale Chat-/RAG-Antworten taggen ihren Gateway-Call als `final_chat_response` inklusive Source, User, Request-ID, Prompt-Messages und LLM-Antwort
  - Recipe-`llm_transform`-Schritte taggen ihre Calls als `recipe_runtime` / `llm_transform`
  - `/config/workbench` verlinkt den LLM Prompt Debug jetzt sichtbar in der Workbench-Kachelgruppe
- Versionslinie:
  - interner Build auf `0.1.0-alpha236` angehoben
- Tests:
  - LLM-Audit-/i18n-/Package-/Gateway-/Release-Regressionen: `10 passed`
  - i18n-Code-Literal-Audit strict: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha236-local.tar`
  - Image-ID: `sha256:8a9e92fe413f0fa71a5196a398dd5b18b3e565b3d452948b8ebe2e1b7146d892`
### alpha237

- Agentic Drift-Fix fuer Server-Diskfragen:
  - Natural-SSH-Diskbegriffe erkennen jetzt auch `HD`, `HDD`, `hard drive`, `platte`, `platten` und `festplattenplatz`
  - `wie sieht die hd auf meinem management server aus` wird vor dem allgemeinen RAG-Chat als bounded SSH-Diskcheck modelliert
  - Regression mit irrelevanten Arlo-Memory-Treffern stellt sicher, dass der Pfad trotzdem `ssh_command` / `df -h` auf `ubnsrv-mgmt-master` bleibt
- Workbench UI:
  - `/config/workbench` zeigt den `LLM Prompt Debug` Link direkt in der Workbench-Kachelgruppe
- Versionslinie:
  - interner Build auf `0.1.0-alpha237` angehoben
- Tests:
  - gezielte Pipeline-/Package-/Release-Regression: `10 passed`
  - i18n-Code-Literal-Audit strict: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha237-local.tar`
  - Image-ID: `sha256:ac49e3ede0618d49329c1a66e5a47e22d708c7ac15489d7461d91e5c876e3c3c`

### alpha238

- Agentic Core:
  - generisches Pre-RAG Action Gate als expliziten Pipeline-Baustein eingefuehrt
  - Chat-/Memory-Anfragen werden vor Dokumenten-RAG auf Capability-/Connection-Aktionen geprueft
  - Debug-Ausgabe zeigt jetzt `pre_rag_action_gate` mit Action-Pfad, Capability und Connection-Kind
  - bestehender Action-Pfad fuer SSH/HTTP/File/Messaging/Read bleibt bounded: LLM/Resolver duerfen vorschlagen, Policy/Runtime entscheiden
- Regressionen:
  - SSH-Diskfrage mit irrelevanten Arlo-Memory-Treffern bleibt `ssh_command` / `df -h`
  - HTTP API, SMB/File, Discord, RSS und Calendar Sanity-Familien bleiben gruen
- Versionslinie:
  - interner Build auf `0.1.0-alpha238` angehoben
- Tests:
  - gezielte Pipeline-Familien-/Package-/Release-Regression: `13 passed`
  - i18n-Code-Literal-Audit strict: gruen, 0 Findings
  - `git diff --check`: gruen
  - Container-Smoke-Test: `/health` liefert `200 {"status":"ok"}`
- Artefakt:
  - `/mnt/NAS/aria-images/aria-alpha238-local.tar`
  - Image-ID: `sha256:c2449242c6050c95074cf1e2c3b0e2eef8676377cc6115e3d12927ad6cf4582b`
