# ARIA - Alpha Backlog

Stand: 2026-05-16

Zweck:
- schlanker Arbeits-Backlog fuer die laufende Alpha-Linie
- offene Aufgaben und naechste Schritte stehen oben
- erledigte Produkt-/Architektur-Aenderungen stehen im `CHANGELOG.md`
- Build-Historie steht in `docs/internal/alpha-build-log.md`
- groessere Zukunftsthemen stehen in `docs/backlog/future-features.md`

## Offen

1. Discord-Eventbus und Startup-Host-Meldung schaerfen
- Status: in `alpha298` intern getestet und fuer Public Release nachgezogen.
- Ausloeser: Der Startup-Discord-Event meldete `Public URL nicht konfiguriert`, obwohl ARIA aktuell bewusst als LAN-/Enduser-Loesung betrieben wird und eine interne URL wie `http://aria.black.lan/` voellig gueltig ist.
- Umsetzung: Die Startup-Meldung nutzt jetzt dieselbe Runtime-URL-Ermittlung wie die Weboberflaeche: zuerst `ARIA_PUBLIC_URL`/`aria.public_url`, dann ein expliziter Host, sonst eine automatisch erkannte lokale Adresse. Damit steht im Discord-Event eine echte URL/IP statt einer Konfigurationswarnung.
- Discord-Eventbus-Check: Wenn Discord konfiguriert und die jeweilige Kategorie aktiviert ist, laufen aktuell relevante Eventklassen ueber den Eventbus: `system_events` fuer Startup, `recipe_errors`/`skill_errors` fuer echte Recipe-Fehler, `safe_fix` fuer Safe-Fix bereit/ausgefuehrt und `connection_changes` fuer Verbindungsstatuswechsel. Erwartete Guardrail-Blocks und erwartbare HTTP-Statusantworten bleiben bewusst keine Recipe-Error-Alerts.
- Naechster Schritt: im naechsten Build Live-Startup-Event pruefen und sicherstellen, dass die Meldung entweder `http://aria.black.lan` aus der Config oder eine automatisch erkannte lokale IP zeigt.

2. Usage-/Kostenmeter transparent machen
- Status: in `alpha295` fuer internen Build vorbereitet.
- Ausloeser: Die bisherige Anzeige von Claude-/LLM-Kosten wirkte zu absolut, obwohl ARIA nur lokale Usage-Logs mit aktuellen oder geloggten Modellpreisen schaetzen kann.
- Umsetzung: Die Stats-Kostenkarte erklaert Kosten explizit als Usage-Schaetzung und zeigt die Reset-Aktion direkt dort, wo der User die Kosten sieht. Der Reset startet eine neue lokale Abrechnungsperiode, archiviert aber den bisherigen Token-/Run-Log statt ihn kommentarlos zu loeschen.
- Hygiene-Nachzug: Standard-Retention ist 90 Tage. Startup und Maintenance bereinigen neben Token-/Kosten-/Activity-Logs auch den redigierten LLM-Debug-Log. Config-Backups sind Downloads und werden nicht dauerhaft in ARIA gesammelt.
- Label-Nachzug: Die Token-Karte zeigt bei Requests jetzt `aktuelle Periode` statt `7 Tage`, weil ein Reset eine neue lokale Periode startet und das feste Zeitfenster fuer User irrefuehrend wirkt.
- Nachzug: Der `Details`-Link auf der Kostenkarte oeffnet jetzt die eingeklappte `Costs & Pricing`-Kachel direkt und springt erst danach zum Ziel.
- Operator-Guardrail-Nachzug: Wenn der Gesamtstatus `Warnung` oder `Fehler` ist, listet die Karte jetzt die konkreten betroffenen Checks inklusive Detailtext und Sprunglink zur jeweiligen Sektion.
- Naechster Schritt: beim naechsten Build live pruefen, dass `/stats` die Erklaerung und `Abrechnungsperiode zuruecksetzen` sichtbar anbietet, `Details` die richtige Kachel oeffnet und nach `RESET` einen Archivnamen meldet.

3. Colloquial Multi-Server-Healthfragen haerten
- Status: in `alpha294` intern gebaut/exportiert; Live-Test bestanden.
- Ausloeser: `wie fit sind meine server ?` fiel wieder in normalen Chat/RAG zurueck, weil die Pre-RAG Action Gate-Schicht zwar `server` erkannte, aber `fit` nicht als Health-/Statuswort kannte.
- Umsetzung: Der bounded LLM-Capability-Draft kennt jetzt `target_intent=health_check|capacity_check` fuer frei formulierte Server-Fitness-/Health-/Kapazitaetsfragen. Die deterministische Schicht nutzt diesen Intent nur zur sicheren Multi-Target-Normalisierung, Guardrail-Pruefung und Preflight-Ausfuehrung. Der Prompt `wie fit sind meine server?` ist als Regressionstest abgesichert und wird auf `uptime -p && df -h && free -h` fuer alle SSH-Ziele gehoben, ohne `fit` als fest verdrahtetes Health-Wort zu benoetigen.
- Live-Test: `wie fit sind meine server?`, `sind meine server gesund?`, `haben alle meine server kein problem` und `fehlt meinen servern was` routen wieder in den SSH-Multi-Target-Healthpfad.

4. Connection-UX-Paritaet vor Multi-Guardrail
- Status: in `alpha293` intern gebaut/exportiert; Live-Test offen.
- Ziel: SSH ist der Master fuer die Connection-Detailseiten. Alle Verbindungstypen sollen gespeicherte Profile konsistent anzeigen, per Profilkarte und sichtbarer `Editieren`-Aktion in den Edit-Modus springen und Create/Edit/Delete-Bereiche gleich nachvollziehbar strukturieren.
- Programm-Logik: Edit-URLs, Statuskarten, Guardrail-Auswahl und Profil-Kontext duerfen nicht pro Template auseinanderlaufen. Gemeinsame Helfer/Partials haben Vorrang vor kopierten Spezialloesungen.
- Erste Umsetzung: gemeinsamer Connection-Status-Block nutzt einklappbare Profilkarten mit sichtbarer Editier-Aktion; SFTP bekommt denselben Edit-URL-Pfad wie die generischen Connection-Seiten.
- Zweite Umsetzung: die Connection-Detailseiten fuer SFTP, SMB, Webhook, HTTP API, Discord, SMTP, IMAP, MQTT, Google Calendar, SearXNG, RSS und Websites nutzen wie SSH einklappbare Arbeitsbereiche fuer bestehendes Profil und neue Verbindung.
- Dritte Umsetzung: Guardrail-Attachments der guardrail-faehigen Connection-Seiten (`ssh`, `sftp`, `smb`, `webhook`, `http_api`) laufen ueber gemeinsame Templates, gemeinsame Context-Keys und einen gemeinsamen Save-Validation-Helper. Aktuell bleibt es bewusst bei single `guardrail_ref`.
- Vierte Umsetzung: Guardrails koennen optional auf exakte Verbindungsklassen gescoped werden. Ein `file_access`-Guardrail fuer `sftp` wird dadurch nicht mehr auf `smb` angeboten und umgekehrt; alte Guardrails ohne Scope bleiben als kompatible Legacy-Profile sichtbar.
- UX-Nachzug: Security/Advanced-Bereiche auf guardrail-faehigen Connection-Formularen sind standardmaessig offen, damit Guardrail-Zuweisungen nicht versteckt wirken.
- Naechste Schritte: Runtime-/Dry-Run-Auswertung fuer Guardrail-Attachments ist nach Live-Ausreissern bei SFTP/SMB/Webhook/HTTP API in `alpha289` gebaut: Operationen wie `file_list`, `read`, `webhook_send`, `status` und `health` werden jetzt in die deterministische Guardrail-Auswertung eingespeist, und bestaetigte SSH/HTTP-`ask_user`-Aktionen reichen die User-Bestaetigung bis in die Runtime-Policy weiter. `alpha290` zieht den Webhook-/Datei-Schreibblock-Nachzug nach. `alpha291` klassifiziert HTTP-API-4xx/5xx-Antworten als externen Endpoint-Status statt als internen Rezeptfehler. `alpha292` formuliert Guardrail-Blocks als Sicherheitsentscheidung statt Profil-/Zugriffsfehler. `alpha293` ergaenzt direkte Guardrail-Review-Links und zieht den blocked-action Timeout-Fallback auf dieselbe Sicherheitsentscheidungs-Sprache. Naechster Schritt ist Live-Test von `alpha293`, danach Multi-Guardrail als gemeinsame UI-/Runtime-Schicht bauen.

5. Multi-Guardrail pro Verbindung
- Status: bewusst geparkt bis Connection-UX und Connection-Logik konsistent sind.
- Ziel: Verbindungen sollen spaeter mehrere kompatible Guardrails tragen koennen, z. B. eine allgemeine SSH-Sicherheitsregel plus eine profilspezifische Betriebsregel.
- Kompatibilitaet: bestehendes `guardrail_ref` bleibt Legacy-/Migrationspfad; neues Zielmodell ist eine geordnete Liste kompatibler Guardrail-Refs pro Verbindung.
- Sicherheitslogik: deterministische Auswertung bleibt konservativ. Jede Deny-Regel darf blockieren; Allow-Bedingungen muessen nachvollziehbar kombiniert werden; keine LLM-Entscheidung darf Guardrails aktivieren oder umgehen.
- Vorbedingung: gemeinsame UI-/Runtime-Schicht fuer Guardrail-Attachments, damit Multi-Guardrail nicht mehrfach pro Provider nachgebaut wird.

5. KI-gestuetzte Guardrail-Vorschlaege
- Status: gestartet nach `alpha282`.
- Ziel: Admin/User beschreibt in Alltagssprache eine Sicherheitsabsicht, z. B. `keine sudo-Befehle auf Ubuntu Linux`; ARIA erstellt daraus einen Guardrail-Vorschlag mit Ref, Typ, Beschreibung, Allow-/Deny-Wording, Scope-Hinweisen und Beispielen.
- Sicherheitsgrenze: LLM erstellt nur den Vorschlag. Aktiv wird nichts automatisch; der User prueft und speichert den Vorschlag bewusst. Die eigentliche Auswertung bleibt deterministisch ueber die bestehende Guardrail-Engine.
- Kontext: Vorschlag bekommt Guardrail-Typ, kompatible Verbindungsklassen, vorhandene Guardrails, passende Connection-Zusammenfassung und Connection Action Contract als begrenzten Kontext. Keine Secrets, Hosts oder Tokens werden erfunden oder in den Prompt geschrieben.
- Erste Umsetzung: `/config/security` bekommt `KI-Vorschlag fuer Guardrail erstellen`; der Entwurf wird als editierbare Review-Karte angezeigt und nutzt den bestehenden Guardrail-Speicherpfad.
- UX-Nachzug: Security-Guardrails-Seite ist in einklappbare Arbeitsbereiche aufgeteilt, damit riskante Aktionen wie Loeschen oder manuelles Bearbeiten nicht gleichzeitig mit KI-Vorschlag, Samples und Neuanlage offen herumliegen.
- UX-Nachzug: Der KI-Vorschlag-POST zeigt jetzt eine kleine Arbeitsanzeige mit groben Schritten wie Kontext pruefen, LLM kontaktieren und Review-Entwurf vorbereiten, damit laengere LLM-Latenz nicht wie ein eingefrorener Screen wirkt.
- Kosten-/Token-Nachweis: Guardrail-Draft-Aufrufe laufen ueber den zentralen `LLMClient.chat(...)` mit `source=guardrail_draft` und werden vom UsageMeter/Token-Tracking fuer Fakturierung erfasst.
- Testmodus: `/config/security` bekommt eine Guardrail-only Testbox. Gespeicherte Guardrails koennen mit Beispielanfragen gegen die deterministische Guardrail-Engine geprueft werden, bevor sie an echte Verbindungen gehaengt werden.
- UX-Nachzug fuer Anwendung: `/config/connections/ssh` ist in einklappbare Bereiche gegliedert; Profilkarten fuehren direkt in den Edit-Modus und zeigen eine explizite `Editieren`-Aktion, damit gespeicherte Guardrails einfacher an SSH-Profile gehaengt werden koennen.
- Naechster Schritt: Live mit SSH-Beispielen testen, danach optional Guardrail-Testmodus auf Policy/Confirmation-Dry-Run erweitern, damit auch `ask_user` sichtbar geprueft werden kann.

6. Google Calendar als erster Enduser-Connection-Pilot
- Status: `alpha280` zeigte live, dass der Device-Code/OAuth-Pfad fuer Google Calendar in Selfhosted-LAN-Setups nicht tragfaehig ist; Google Calendar Device Code kann den Calendar-Scope nicht sauber abdecken und Redirect-OAuth bleibt fuer Enduser ohne DNS/FQDN zu schwer.
- Entscheidung: sauberer Rueckbau des Calendar-OAuth-/Device-Code-Flows. Keine OAuth-Client-JSONs, keine Client-ID/Secrets, keine Refresh-Tokens und keine Browser-Redirect-Variante mehr fuer den aktuellen Enduser-Pfad.
- Neue Umsetzung: Google Calendar read-only nutzt die geheime iCal-Adresse aus Google Calendar > Einstellungen > Kalender integrieren. ARIA speichert den iCal-Link im Secure Store, testet den Feed und liest Termine aus `VEVENT`-Eintraegen.
- Ziel bleibt: Calendar als erster Enduser-Connection-Pilot, aber bewusst mit einem robusten, erklaerbaren read-only Setup statt Google-Cloud-Projekt-Komplexitaet.
- Produkt-, Hilfe- und Wiki-Doku sind auf den iCal-Enduser-Pfad nachgezogen; alte OAuth-/Device-Code-Hinweise bleiben nur in historischen Changelog-/Buildlog-Eintraegen.
- Live-Test nach `alpha281`: `heute` und `morgen` funktionieren; `nächster Termin` listete zu viele kommende Termine.
- Fix in `alpha282` gebaut/exportiert: Calendar-Range `next` liefert nur noch den einzelnen naechsten Termin, waehrend `upcoming`/Wochenbereiche Listen bleiben.
- Naechster Schritt: `alpha282` installieren und `wann ist mein nächster termin?` live erneut testen.

7. Chat-Arbeitsstatus fuer Enduser sichtbarer machen
- Status: kleine Variante mit Nachzug in `alpha272` intern gebaut/exportiert.
- Ziel: Wenn ARIA arbeitet, soll der User ohne Debug-Log sehen, was grob passiert: Server pruefen, Feeds lesen, Dateien/Shares durchsuchen, Nachricht vorbereiten, Web/Memory pruefen oder Ergebnis zusammenfassen.
- Umsetzung: lokaler, rein UI-seitiger Prompt-Klassifizierer im Chat-Frontend; keine neue Backend-Progress-API und keine Roh-Debugdaten im User-Flow.
- Nachzug: Lang laufende Requests behalten nach dem 8-Sekunden-Fallback den Arbeitstyp, z. B. `ARIA wartet auf Serverantworten...` statt generischem `ARIA arbeitet noch...`.
- Zusatz: Die Haupt-Chatansicht nutzt den verfuegbaren Viewport nun dynamischer aus; der Nachrichtenbereich waechst mit dem Screen, der Composer bleibt darunter.
- Naechster Schritt: nach internem Update live mit SSH-, RSS-, SMB/File-, Memory- und normalen Chat-Prompts sowie Desktop/iPhone-Viewport gegenpruefen.

8. Provider-/E-Mail-Fundament fuer modulare Enduser-Verbindungen vorbereiten
- Status: gestartet nach `alpha269`.
- Ziel: ARIA soll neue Provider wie E-Mail, Tickets, Notizen, Kalender, Dateien und weitere Community-Verbindungen ueber deklarierte Capabilities einhaengen koennen, ohne neue Provider-Branches in `pipeline.py`.
- Leitbild: read/search zuerst, draft/review danach, side-effect execution nur bestaetigt und policy-/guardrail-geprueft.
- Erste Umsetzung: Connection Action Contract und Provider Manifest bekommen planner-level Rollen, sensitive-content-Flag, confirmation-required-Flag und optionale Draft-Capability.
- Zweite Umsetzung: generisches `AgenticContentAccessRequest` / `AgenticContentAccessResult` Modell und `AgenticContentAccessRegistry` fuer Read/Search/List-Provider vorbereitet; `email_send` und andere Side-Effects koennen dort bewusst nicht hineinfallen.
- Dritte Umsetzung: Content-Access-Registry ist optional in den Pipeline-Orchestrator eingehaengt; ohne passenden Handler bleibt der bestehende Executor-/IMAP-Pfad aktiv.
- E-Mail-Referenzmodell:
  - `mail_search`: Mails anhand Sender, Betreff, Inhalt, Datum oder Mailbox-Scope finden.
  - `mail_read`: begrenzte Mailinhalte lesen und zusammenfassen.
  - `email_send`: neue Mail erst als Draft/Review vorbereiten und nur nach Bestaetigung senden.
  - spaeter `email_reply`: Thread-/Originalnachricht als Pflichtkontext plus Bestaetigung.
  - spaeter Mutationen wie Archive/Label/Delete als eigene Capabilities mit strengeren Policies.
- Naechste Schritte: ersten echten IMAP-Content-Access-Handler ueber die Registry ziehen, generischen Confirmation-/Draft-Flow fuer Send/Write/Publish vereinheitlichen, danach E-Mail Provider als erster echter Pilot.

9. GitHub Release-Objekt fuer `0.1.0-alpha298` anlegen
- Status: Public-Release-Push laeuft.
- Quelle fuer Release-Text: `docs/release/github-release-v0.1.0-alpha.298.md`.
- Kein API-Release ohne bewusst bereitgestellte GitHub-Auth.

10. Public `0.1.0-alpha298` live pruefen
- `/health`
- `/stats` mit Release-Metadaten, Operator Guardrail, Kosten-/Resetstatus und Log-Hygiene
- `/config/security` Guardrail-KI-Vorschlag und Testmodus
- Connection-Edit/Guardrail-Attachments fuer SSH/SFTP/SMB/Webhook/HTTP API
- Google Calendar iCal: `was steht heute in meinem kalender?`
- Server-Health: `wie fit sind meine server?`
- Webhook-/HTTP-API-Guardrail-Block
- Discord-Startup-Event mit echter Host-/IP-Zeile

11. Update-Reconnect-Shell beobachten
- Nach vorherigem Seitenbesuch beim naechsten Update pruefen.
- Erwartung: Navigation waehrend kurzem ARIA-Recreate zeigt Warteseite statt Browser-Fehler und kehrt nach `/health` zur Zielseite zurueck.

12. Learned-Recipe-Live-Dossier weiter auswerten
- Echte Fehl-Learnings weiter als Kontext-, Resolver-, Policy-/Guardrail-, Runtime-/Summary- oder Observability-/Kostenluecke klassifizieren.
- Keine schnellen Spezialfaelle bauen, nur weil ein einzelner Prompt ausreisst.

13. Kurz formulierte Multi-Server-Healthfragen live nachtesten
- Status: Fix in `alpha274` intern gebaut/exportiert.
- Ausloeser: `sind meine server ok` fiel trotz korrektem Server-/Statussignal in Chat/RAG zurueck.
- Umsetzung: Capability-Router erkennt generisch `SSH-Zielwort` plus Health-Statuswort wie `ok`, `okay`, `gesund`, `in Ordnung` oder `healthy` als SSH-Health-Intent; konkrete Befehlswahl bleibt im bestehenden Agentic-/Guardrail-Pfad.
- Nachzug in `alpha274`: Formulierungen wie `sind meine server in ordnung` und `are my servers healthy` werden auch in der Multi-Target-Health-Adaption auf den breiten erlaubten Statuscheck gehoben, statt bei blockierbarem `uptime` zu bleiben.
- Naechster Schritt: nach internem Update live mit `sind meine server ok`, `sind meine server gesund`, `sind meine server in ordnung` und `are my servers healthy` testen.

## Naechster Entwicklungsblock: Kontrollierter Agentic-Enduser-Helfer

Ziel:
- ARIA soll sich weniger wie ein Bot mit Tools und mehr wie ein verlaesslicher persoenlicher Operator anfuehlen.
- LLMs duerfen Bedeutung, Zusammenfassung, freie Formulierungen und Review-Metadaten liefern.
- Deterministische Schichten bleiben fuer Sicherheit, Normalisierung, Preflight, Policy/Guardrail, Runtime, Validierung und Fallbacks verantwortlich.
- Enduser sollen erkennen koennen, was ARIA verstanden hat, was ARIA tun will, was blockiert wurde und was als naechstes sinnvoll ist.

Aufgaben:

1. Agentic Flow als durchgehenden Pfad haerten
- Pre-RAG Action Gate, bounded Planner, Resolver, Policy/Guardrail, Runtime und Summary als einheitlichen Ablauf sichtbar halten.
- Debug-Boundaries fuer Kontext, Draft, Policy und Runtime in neuen/regressiven Pfaden konsequent mitschreiben.
- Live-Dossier-Ausreisser zuerst einem Architekturtyp zuordnen: Kontext, Resolver, Policy/Guardrail, Runtime/Summary, Observability/Kosten.
- Keine neuen starren Prompt-Spezialfaelle einfuehren, wenn ein bounded LLM-Schritt die flexiblere Loesung ist.

2. Learned-Recipe-Noise und Promotion-Gates verbessern
- Status: begonnen in `alpha267`; deterministische Promotion-Gates fuer Multi-Target-Scope und Side-Effects sind umgesetzt und getestet.
- Multi-Target-SSH-Learnings duerfen keine einzelnen Ziel-Rezepte polluten. Umsetzung: `target_scope=multi_target` / `learning_origin=plural_target_scope` bleibt context-only.
- Side-Effect-Aktionen wie Discord/Webhook/E-Mail/MQTT duerfen nicht allein durch Wiederholung zu schnell promotable wirken. Umsetzung: Side-Effects werden hoechstens review-ready und duerfen nicht direkt als gespeichertes Rezept promoted werden.
- Fehl-Learnings wie RSS-Kandidat aus SSH-Frage als Curator-/Resolver-/Policy-Luecke klassifizieren und gezielt testen. Umsetzung: Learned-Reentry prueft `connection_kind` + `capability` gegen den Connection Action Contract, bevor ein gelernter Kandidat in den bounded Planner kommt.
- Promotion-Reife staerker an Scope, Side-Effect-Risiko, Zielklarheit, Action-Fingerprint und negativer Evidenz ausrichten.
- Learned Recipes bleiben Review-/Context-only, bis Admin-Promotion bewusst erfolgt.

3. Pipeline weiter modularisieren
- Status: begonnen in `alpha267`; generischer Agentic Execution Handler Contract, Handler-Registry, Learning-Service, SSH-Multi-Target-Pilot und RSS-Feed-Adapter sind umgesetzt.
- `pipeline.py` bleibt Orchestrator, Provider-/Runtime-Logik soll schrittweise in domainnahe Module wandern.
- Erste Kandidaten: SSH-Agentic-Ausfuehrung und RSS-Digest/Group-Handling laufen ueber Handler; naechste Kandidaten sind Learning-Followups, Confirmation-/Blocked-Action-Flows und danach weitere Provider-Familien.
- Neue Provider sollen ueber `AgenticExecutionHandler` / `AgenticExecutionRequest` / `AgenticExecutionResult` und die Handler-Registry einhaengen, statt eigene Branches direkt in `pipeline.py` zu schreiben.
- Erfolgreiche Provider-Ausfuehrungen sollen ueber `AgenticExecutionLearningService` lernen, damit Store, Curator und Memory nicht pro Provider dupliziert werden.
- Refactors zuerst als reine Verschiebung mit bestehenden Tests; danach Verhalten verbessern.
- Keine lokalen Provider-Listen in neuen Modulen; Connection Action Contract bleibt Quelle fuer Provider-/Capability-Boundaries.

3a. Provider-Manifest-Schicht vorbereiten
- Status: begonnen in `alpha267`, erweitert nach `alpha269`; internes `ConnectionProviderManifest`-Modell, Export und Validator sind umgesetzt.
- Bestehende Connection Action Contracts werden provider-orientiert nach `connection_kind` gespiegelt.
- Capability-Zeilen tragen jetzt `planner_role`, `confirmation_required`, `sensitive_content` und `draft_capability`, damit E-Mail-/Ticket-/Notizen-Provider nicht pro Runtime neu verdrahtet werden muessen.
- Noch kein Community-Import und keine UI: zuerst Contract, Validator, Auth-/Runtime-Grenzen stabilisieren.
- Naechste Schritte: Runtime-Adapter-IDs gegen Agentic Execution Registry pruefen, Secret/Auth-Boundaries fuer externe Provider definieren, generische Read/Search-Registry und Draft/Confirm-Flows stabilisieren, danach Import-/Editor-Konzept.

4. Enduser-Operator-UX schaerfen
- Antworten sollen klar zeigen: verstandenes Ziel, geplante Aktion, Sicherheitsentscheidung, Ergebnis und naechster Schritt.
- Side-Effect-Confirmations muessen knapp, konkret und auditierbar bleiben.
- Blockierte Aktionen sollen den real erkannten Wunsch zeigen, nicht in harmlose Ersatzaktionen umgebogen werden.
- Fehlertexte sollen handlungsorientiert sein und nicht nur technische Exceptions wiedergeben.
- `/stats` und Operator Guardrail bleiben Vertrauenszentrale fuer Release-/Kosten-/Runtime-/Learning-Status.

5. Testanker und Live-Dossier ausbauen
- Neue Agentic-Regressions zuerst im Dossier dokumentieren, dann als fokussierte Tests absichern.
- Testdateien bei neuen Faellen nach Domaene aufteilen, statt `tests/test_pipeline.py` weiter ungebremst wachsen zu lassen.
- Relevante Checks vor internem Build: fokussierte Agentic-/Learning-Tests, Release-/Package-Hygiene, i18n strict und `git diff --check`.

## Aktueller Release-Stand

- aktuell gebaut: `0.1.0-alpha298` intern
- public veroeffentlicht: `0.1.0-alpha298`
- Git Commit: Public-Release-Commit fuer `alpha298`
- Git Tag: `v0.1.0-alpha.298`
- Public Docker Tags: `fischermanch/aria:0.1.0-alpha.298` und `fischermanch/aria:alpha`
- Public Docker Digest: `sha256:7f5a55506d087e0479d0087bb1d9bdfab7706055ba1d21f08d8f6f30ae7db0ad`
- interner Docker Build: `fischermanch/aria:0.1.0-alpha.298` / `aria:alpha-local`
- internes TAR: `/mnt/NAS/aria-images/aria-alpha298-local.tar`
- internes TAR-SHA256: `5d8e55db537cb8320b428385a73d6eacc7620de4eda8b9803007566c05ef02d8`
- interner Image-Digest: `sha256:7f5a55506d087e0479d0087bb1d9bdfab7706055ba1d21f08d8f6f30ae7db0ad`
- GitHub Release URL: `https://github.com/FischermanCH/A.R.I.A./releases/tag/v0.1.0-alpha.298`
- GitHub Wiki-Quellen und lokale Hilfe sind fuer `0.1.0-alpha298` nachgezogen.
- `0.1.0-alpha298` ist fuer Public Commit/Tag/Docker Push freigegeben.
- Naechster interner Build nach Abschluss waere voraussichtlich `0.1.0-alpha299`, aber nur nach expliziter Anforderung.

## Dauer-Guardrails

- Packaging-/Release-Hygiene aktiv halten.
- Kein generiertes `*.egg-info/`, `build/`, `dist/` oder `*.whl` im Workspace oder Commit.
- Neue Runtime-Assets muessen von `tests/test_package_data_contract.py` oder `tests/test_release_hygiene.py` abgedeckt bleiben.
- `CHANGELOG.md` fuer alle sichtbaren Produkt-/Architektur-Aenderungen fortschreiben.
- Agentic Live-Ausreisser zuerst in `docs/product/agentic-live-regression-dossier.md` klassifizieren.
- Keine neuen Agentic-Spezialfaelle auf Verdacht bauen.
- Flexibilitaet ist LLM-first; deterministische Logik bleibt fuer Sicherheit, Normalisierung, Preflight, Policy/Guardrail, Runtime, Validierung und Fallbacks.
- Recipes UX nur anhand echter neuer Recipe-Ausgaben/Live-Ausreisser weiter schaerfen.
- Connection-Modularisierung ueber `docs/product/connection-action-contract.md` und `docs/product/connection-provider-manifest-checklist.md` contract-backed halten.
- Agentic Runtime-Modularisierung ueber `docs/product/agentic-execution-handler-contract-alpha267.md` halten.
- Neue Provider-/Capability-Familien muessen Runtime, Policy, Guardrail und Direct-Gate im Connection Action Contract deklarieren.
- Provider-Manifeste muessen `validate_connection_provider_manifest()` bestehen, bevor Import/UI daran gebaut wird.
- Keine lokalen Provider-Listen in Pipeline, Web-Routen oder Resolvern nachziehen.
- Operator Guardrail nach `docs/product/operator-observability-guardrails.md` pflegen.
- Kosten-/Token-Tracking-Ausfaelle bleiben Release-Fehler.
- Legacy-Skill-Bruecken nur nach dem Migration-Gate in `docs/product/legacy-recipe-compatibility-audit.md` entfernen.
- i18n strict vor groesseren Releases laufen lassen: `scripts/audit_i18n_code_literals.py --strict`.
- Deutsche UI-/Runtime-Texte gehoeren in `aria/i18n/*.json`.
- Deutsche Eingabe-/Routing-Lexika gehoeren in `aria/lexicons/*.json`.
- Managed Update-Pfad schuetzen: normale Updates sollen nur `aria` recreaten; Qdrant/SearXNG/Valkey nur bewusst via `repair`/`update-all`.

## Recipe-First Zielbild

- `Recipe Memory`: was ARIA aus Nutzung gelernt hat
- `Recipe Candidate`: was fuer eine Anfrage relevant sein koennte
- `Executable Plan`: was jetzt konkret ausgefuehrt wird
- `Policy / Guardrails`: was erlaubt, bestaetigungspflichtig oder blockiert ist
- `Runtime Adapter`: wie technisch ausgefuehrt wird
- neue Intelligenz entsteht bevorzugt aus Dossier + Planner + Policy + Summary + Learning, nicht aus starren Skills

## Spaeter

- Scheduler/Cron fuer kontrollierte Recipe-Automation weiter vorbereiten.
- OAuth2-Connection-Foundation fuer Enduser-Integrationen ausbauen.
- Google-Integrationen nach Calendar schrittweise erweitern (`Tasks`, spaeter `Drive`, `Sheets`).
- Apple bewusst spaeter und selektiv angehen (`Calendar` zuerst).
- `recipe_runtime.py` nach Executor-Domaenen weiter schneiden.
- `pipeline.py` als Orchestrator weiter verschlanken.

## Referenzen

- Release-Details: `CHANGELOG.md`
- Alpha-Build-Historie: `docs/internal/alpha-build-log.md`
- Public-Release-Text: `docs/release/github-release-v0.1.0-alpha.298.md`
- Public-Rollup-Hintergrund: `docs/release/public-alpha-rollup-alpha167-to-next.md`
- Agentic Flow Map: `docs/product/agentic-flow-map-alpha267.md`
- Agentic Live Regression Dossier: `docs/product/agentic-live-regression-dossier.md`
- Connection-Manifeste: `docs/product/connection-provider-manifest-checklist.md`
- Codebase-Modularitaetscheck: `docs/product/codebase-modularity-audit-alpha257.md`
- Operator Guardrail: `docs/product/operator-observability-guardrails.md`
- Legacy Recipe Compatibility: `docs/product/legacy-recipe-compatibility-audit.md`
- Zukunftsthemen: `docs/backlog/future-features.md`
