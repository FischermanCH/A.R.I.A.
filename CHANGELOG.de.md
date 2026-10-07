# Changelog

## 0.1.0-alpha983

### Behoben

- Den in `0.1.0-alpha982` eingefuehrten Dokumentinventar-Fallback repariert: Fragen wie „Welche Dokumente, PDFs oder Beipackzettel hast du?“ liefern wieder eine benannte, collection-gebundene Zeile pro importiertem Dokument, statt keine Dokumente oder eine unvollstaendige Liste aus Suchauszuegen zu melden.
- Das Inventar fordert jetzt explizit bis zu 200 Dokumenteintraege an und faellt nicht mehr still auf das MemorySkill-Defaultlimit 12 zurueck. Search- und Answer-Ergebnisse behalten bei vorhandenen Metadaten ebenfalls Dokumentname und Collection.
- **Es gingen keine Daten verloren.** Die importierten Dokumente waren durchgehend gespeichert; defekt war nur die vollstaendige Inventardarstellung des nativen Tools.

## 0.1.0-alpha982

> **Zu den Versionsnummern:** Die Versionsnummern von ARIA zaehlen bewusst die Entwicklungs-Iterationen. Alpha604 bis Alpha982 sind 378 Iterationen, in denen ARIA gemeinsam mit KI gebaut wurde – die Zahl bleibt absichtlich transparent und zaehlt weiter, notfalls auch ueber 1000.

### Highlights

1. **Eine modulare ARIA unter der vertrauten Oberflaeche.** Von aussen sieht eigentlich nur noch die GUI so aus wie beim Public-Release Alpha604; darunter wurde die Anwendung in eigenstaendige Module mit expliziten Vertraegen neu aufgebaut. Der fruehere monolithische Core ist keine zweite Wahrheit mehr, sodass Aenderungen an Connections, Gedaechtnis, Rezepten, Chat und Administration besser isoliert bleiben.
2. **Selbstlernen mit Entscheidung vor dem Speichern.** ARIA kann wiederkehrende persoenliche Praeferenzen erkennen und erst nach wiederholter Evidenz als nutzerbezogene Erinnerung anbieten. Beilaeufige Aussagen werden nicht still gespeichert; ueber die eigene Aktion entscheidet der Nutzer, ob daraus ein persoenlicher Claim wird.
3. **Selbstlernende Rezepte.** Wiederholte ausfuehrbare Ablaeufe koennen trotz semantischer Varianten zu einem inaktiven Rezeptvorschlag zusammengefuehrt und fuer unterstuetzte Connections kopiert werden. Vorschlaege bleiben pruefbar und inaktiv, bis der Nutzer sie ausdruecklich speichert; der stillgelegte Legacy-Learning-Stack ist daran nicht mehr beteiligt.
4. **Nativer Tool-Agent mit MCP und robusten Hintergrund-Jobs.** Der Agent kann ARIAs native Tools und aktivierte MCP-Server verwenden; lange Arbeiten laufen als Jobs mit Pause, Fortsetzen, Korrektur, Abbruch, Budgeterweiterung und Bestaetigung im Job weiter. Tool-Bilder koennen an unterstuetzte Claude-Familienmodelle gehen, waehrend Ausgabe-Guards erfundene Ressourceninhalte oder Aktionsbehauptungen ohne Tool-Evidenz ablehnen.
5. **Eine klarere Gedaechtnis-Datenbankgrenze.** Kern-Erinnerungen, Fakten, Praeferenzen, Dokumente und Recipe Experience bleiben erhalten; obsolete Legacy-Learning-Collections werden nicht mehr geschrieben. Nach dem Upgrade koennen Administratoren diese alten nutzerbezogenen Collections unter **Gedaechtnis → Wartung → Alte Lern-Collections aufraeumen** explizit entfernen, ohne persoenliche Erinnerungen, Fakten oder Praeferenzen zu loeschen.

### Hinzugefuegt

- MCP-Client fuer aktivierte HTTP/SSE-Server mit namespaced Tool-Erkennung, serverbezogenem Vertrauen und Call-Timeout, Admin-Status, Reconnect, begrenzten Ergebnissen und Bestaetigungs-Previews fuer mutierende Tools.
- Persistente, nutzerbezogene Agent-Jobs mit Fortschritt, Token-/Kostenanzeige, Abschlussmeldungen sowie Pause, Fortsetzen, Korrektur, Bestaetigung, Budgeterweiterung, Finalisierung, Abbruch und Aufbewahrung.
- Native Recurrence fuer persoenliche Erinnerungs- und inaktive Rezeptvorschlaege sowie eine explizite Wartungsaktion fuer alte Lern-Collections.
- Strikter isolierter Browser-E2E-Pruefstand fuer Agent, MCP, Jobs, Bestaetigungen und Vision; er ist Entwicklungswerkzeug und kein Produktionsdienst.

### Geaendert

- Die Runtime hat modulare Owner: Der Kernel behaelt Lifecycle, Auth, Policy, Confirmation und Observability; Fachmodule besitzen Vertraege, Routen, Runtime und UI-Beitraege.
- Webantworten nutzen konfigurierte provider-native Faehigkeiten; der fruehere Such-Sidecar gehoert nicht mehr zu frischen Installationen.
- Gedaechtnis-Erfassung, Personal Claims, Rezeptausfuehrung und Cross-Connection-Bindings verwenden explizite strukturierte Vertraege und stabile IDs.
- Provider-Kompatibilitaet unterstuetzt leere Modell-Temperatur, laengere begrenzte Agent-Turns, Prompt-Caching, rollende Tool-Bildfenster und ehrliche Retries fuer ausgewaehlte Provider-Limits.

### Entfernt

- SearXNG- und Valkey-Sidecars aus dem unterstuetzten Fresh-Install-Stack.
- Tote Legacy-Learning-Module, Worker-/Admin-Flaechen und automatische Learning-Writer, ersetzt durch native Memory- und Recipe-Recurrence.
- Obsolete monolithische Kompatibilitaetsmodule und inaktive Public-Samples, deren lebende Owner bereits in Module umgezogen waren.

### Behoben

- Confirmation-Turns behalten das Pending Tool trotz Relevanz-Selektor; MCP-Sessions erholen sich oder scheitern ehrlich, ohne normale Turns zu blockieren.
- Agent-Jobs duplizieren keine Budget-Pausen oder Abschlussmeldungen mehr, verlieren keine Confirmation, werden nach vier Tool-Bildern nicht blind und stoppen nicht still bei Provider-Ausgabelimits.
- Memory-Recurrence clustert stabile Themenwerte ueber Formulierungen hinweg; explizites Memory Capture wiederholt begrenzt transiente Store-Fehler und zeigt sichere Diagnosen.
- Release-, Setup-, Routing-, Chat-History- und Update-Grenzen wurden ueber die Alpha605–Alpha982-Iterationen gehaertet.

### Sicherheit

- Mutierende native und nicht vertrauenswuerdige MCP-Tools laufen mit eingefrorenen Argumenten und One-Shot-Ledger-Claim durch den Confirmation-Kernel; Server-Vertrauen ist eine explizite Admin-Entscheidung.
- Agent-Job-Steuerungen und Wartungsaktionen sind authentifiziert, CSRF-geschuetzt und nutzerbezogen.
- Output-Guards lehnen unbelegte Ressourceninhalte oder abgeschlossene Aktionen ab; MCP-Header, Logs, Job-Snapshots und Release-Artefakte enthalten keine Klartext-Secrets.
- Public-Repo-Hygiene schliesst lokale Konfiguration, Secrets, Runtime-Daten, interne Arbeitslogs und Browserzustand aus und scannt generisch auf Privatsphaere- und Credential-Muster.

### Upgrade-Hinweise

- Vor dem Upgrade von `0.1.0-alpha604` die ARIA-Config-/Data-Mounts oder Volumes sowie das Qdrant-Volume sichern.
- Der isolierte Alpha604→Alpha982-Test prueft, dass Auth, beide Nutzer, Konfiguration und Connections, Chat-History, persoenliche Fakten/Praeferenzen, Rezepte und Qdrant-Memories mit denselben Speichern erhalten bleiben. Legacy-Learning-Collections werden bewusst nicht automatisch entfernt.
- Nach dem Update einmal pro Nutzer **Gedaechtnis → Wartung → Alte Lern-Collections aufraeumen** ausfuehren. Nur obsolete Learning-Candidate/Eval/Event/Hint/Reflection-Collections dieses Nutzers werden entfernt; persoenliche Erinnerungen, Fakten, Praeferenzen, Dokumente und Recipe Experience bleiben unangetastet.
- Alte SearXNG- und Valkey-Container koennen nach Backup und erfolgreicher Upgrade-Pruefung manuell entfernt werden; ARIA loescht sie nie automatisch. Siehe `docs/release/alpha981-upgrade-note.md`.
- Modellbezogene `temperature` darf fuer ablehnende neue Modelle leer bleiben. Fuer lange Agent-/Blender-Jobs sind etwa `16000` maximale Ausgabetokens und `300` Sekunden Modell-Timeout ein Startwert; den MCP-Call-Timeout konfiguriert man pro Server.
- LiteLLM-Proxies erhalten kein `tool_choice=none` mehr. MCP- und Blender-Setup beschreibt `docs/setup/mcp-and-blender.md`.

### Bekannte Einschraenkungen

- Tool-Result-Bildvision wird derzeit nur mit Claude-Familienmodellen unterstuetzt.
- KI-3D-Generierung ueber ein Blender-MCP-Add-on benoetigt eigene kostenpflichtige Generator-Keys des Nutzers; ARIA stellt weder Dienst noch Credits bereit.
- Die Blender-MCP-Bridge laeuft auf dem Rechner des Nutzers und muss aus dem ARIA-Container erreichbar sein; sie ist kein gebuendelter Sidecar.
- Tokenverbrauch, Kosten und Job-Budgets haengen von Provider und Modell ab. Der E2E-Pruefstand ist nur ein Entwicklerwerkzeug.

## 0.1.0-alpha961 (intern)

- Worker-geteiltes SQLite-Fundament fuer Agent-Jobs ergaenzt: Lange Native-Agent-Turns loesen sich nach einem konfigurierbaren synchronen Budget von 25 Sekunden, laufen ohne Abbruch weiter, protokollieren abgeschlossene Tool-Schritte und sind nutzerbezogen read-only unter `/jobs` abrufbar.
- Kurze Turns und Confirmation-Token-Turns bleiben synchron und erzeugen keine sichtbaren Jobs; beim Start werden nur veraltete laufende Jobs als unterbrochen markiert.

## 0.1.0-alpha947 (intern)

- Adaptive Connection-Bindings gespeicherter Rezepte von SSH auf die von SFTP-, SMB-, Discord-, Webhook-, E-Mail-, MQTT- und HTTP-API-Schritten vorgegebenen Connection-Arten generalisiert; explizite Referenzen und nicht betroffene Schritte bleiben unveraendert.
- Den exakten SSH-Fleet-Fan-out-Vertrag erhalten, dessen 20-Ziel-Limit fuer SFTP/SMB wiederverwendet, begrenzte lokalisierte `recipe_connection_*`-Fehler ergaenzt und Confirmation-Previews weiterhin an konkret aufgeloeste konfigurierte Ziele gebunden.

## 0.1.0-alpha946 (intern)

- Die zwei nicht mehr referenzierten Legacy-Learning-POST-Routen fuer Active-Hint-Mutationen und den retirten Candidate-Action-Stub aus Memory-Admin-Routing und Manifest-Metadaten entfernt.
- Persoenliches-Modell-Claim-Aktionen, Memory-Loeschrouten, Legacy-Learning-Collection-Klassifizierung und -Cleanup, der geschuetzte Gedaechtnis-Browser sowie die Native Registry mit 37 Tools bleiben erhalten.

## 0.1.0-alpha945 (intern)

- Veraltete Auto-Memory-Begriffe aus beiden lokalisierten Memory-Setup-Beschreibungen und dem Maintenance-Fallback entfernt; die uebrigen Setup-Hinweise bleiben erhalten.
- Rollup-, Lernvorschlag-Reset- und Legacy-Learning-Cleanup-Feedback wird per deterministischem Focus-Query und Anchor in der ausloesenden Maintenance-Karte angezeigt; bei fehlendem oder unbekanntem Focus bleibt der Seitenanfang-Fallback erhalten.

## 0.1.0-alpha944 (intern)

- Eine explizite authentifizierte und CSRF-geschuetzte Memory-Wartungsaktion ergaenzt, die ausschliesslich retirierte Legacy-Learning-Qdrant-Collection-Arten mit dem exakten Suffix des aktuellen Nutzers entfernt.
- Eine bestaetigungspflichtige Wartungskarte und begrenzte lokalisierte Ergebnisanzeige ergaenzt; Core Memory, Dokumente, Notizen, Sessions, Recipe Experience, Routing, Backups, externe Collections und andere Nutzer bleiben geschuetzt.

## 0.1.0-alpha943 (intern)

- Einen begrenzten Store-Retry mit maximal drei Versuchen und 0,2/0,4 Sekunden Backoff fuer fehlgeschlagene Personal-Memory-Store-Ergebnisse ergaenzt; erfolgreiche oder deduplizierte Writes und die Claim-Lifecycle-Logik bleiben unveraendert.
- Den begrenzten autoritativen Store-Fehler in fehlgeschlagenen `memory_capture`-Diagnosen erhalten; freundlicher Nutzertext und Registry-Vertrag bleiben unveraendert.

## 0.1.0-alpha942 (intern)

- Die letzte Legacy-Auto-Memory-Konfigurationsautoritaet samt toter Cookie-, Status-, Recipe- und Runtime-Verdrahtung entfernt; alte Konfigurationsdateien mit einer ignorierten `auto_memory`-Sektion laden weiterhin fehlerfrei.
- Aus dem beibehaltenen Gedaechtnis-Browser nur den obsoleten Auto-Memory-Status und die Learning-Effect-Anzeige entfernt; Recall, Capture, Persoenliches Modell, Navigation, Graph, Statistik und Suche bleiben intakt.

## 0.1.0-alpha941 (intern)

- Die neun geschlossenen Legacy-Learning-Module samt exklusiven Tests und UI-Partial physisch entfernt; der registrierte Modulgraph sinkt von 118 auf 109, ohne `memory_learning_bridge` oder gespeicherte Learning-Daten zu loeschen.
- Ihre statischen Registry-Eintraege und verbleibenden Recipe-/Auto-Memory-Manifestkanten entfernt; Core Memory, `/memories`, Persoenliches Modell, Native Learning und Recipe Tools bleiben bei ihren beibehaltenen Ownern.

## 0.1.0-alpha940 (intern)

- Alle zehn Legacy-Learning-Kandidaten-Routen fuer Review, Apply, Regression, generiertes Pytest und Aktivierung samt Apply-Preview-Template aus Memory Admin entfernt; Gedaechtnis-Browser und Persoenliches Modell bleiben erhalten.
- Das beibehaltene Memory-Admin-Modul von `learning_candidates`, `learning_artifacts` und `prepared_artifacts` entkoppelt; der Learning-Ring bleibt als bewusst geschlossener toter Subgraph fuer die separat freizugebende Stufe 3c-2 registriert.

## 0.1.0-alpha939 (intern)

- Das obsolete Legacy-Auto-Memory-Status-Badge samt ungenutztem Styling aus dem Chat-Debug-Header entfernt; die uebrigen Chat-Diagnosen bleiben erhalten.
- Den Kosten-Pre-Filter des servereigenen Memory-Learning um deutsche und englische Fragewoerter am Nachrichtenanfang erweitert, ohne Extraktion, Recurrence oder Registry zu aendern.

## 0.1.0-alpha938 (intern)

- Legacy-Learning-Retention, Synthese-Status, Active-Hint-Recall und Inventar sowie alle Learning-Importe wurden aus der beibehaltenen Core-MemorySkill entfernt; persoenliche Claims, Recall, Capture, Dokumente, Cleanup und Gedaechtnis-Browser bleiben erhalten.
- Das Native Tool `learning_context_read` samt Integration Point wurde entfernt (Registry jetzt 37 Tools), die lernexklusive Procedure-Guidance geloescht und die generische Memory-Admin-Abfrage in das bleibende `memory`-Modul relocatet.

## 0.1.0-alpha937 (intern)

- Die bisherige Auto-Memory-Seite auf das beibehaltene Persoenliche Modell reduziert; Auto-Memory-Toggle, Extraction-/Retention-Steuerung, Legacy-Learning-Inventar und Synthese-Anzeige entfernt, waehrend Personal Claims und ihre Lifecycle-Aktionen erhalten bleiben.
- Die obsoleten POST-Routen fuer Auto-Memory-Speichern und Learning-Synthese entfernt und den Memory-Tab in Persoenliches Modell umbenannt; MemorySkill, AutoMemoryConfig und `/memories` bleiben unveraendert.

## 0.1.0-alpha936 (intern)

- Beibehaltene Runtime-Execution-Vertraege, Stats, Memory Admin und Personal-Feedback-Verlinkung vom Legacy Learning Runtime entkoppelt; normale Action-Ausfuehrung, `/memories`, Memory-Recall und explizites Capture bleiben erhalten.
- Den Startup-Aufruf der Learning-Retention samt Logging entfernt; Document-MetaCatalog-Rebuild und Empty-Collection-Cleanup bleiben erhalten. Die Learning-Module bleiben fuer spaetere B2-Stufen registriert.

## 0.1.0-alpha934 (intern)

- Den expliziten Chat-Lernmodus mit Start/Stop/Abbrechen aus Live-POST-Dispatch und passiver Chat-Darstellung retirert; fruehere Kommandos laufen nun durch den normalen Chat-Flow, waehrend `recipe_remember` und native Recurrence die unterstuetzten Lernpfade bleiben.
- Chat-Learn-Session-Reads, Observation-Writes, Statusanzeigen, Toolbox-Steuerung und zwei dadurch tote Chat-Execution-Manifest-Abhaengigkeiten entfernt, ohne das `recipe_learning`-Modul zu loeschen oder zu verschieben.

## 0.1.0-alpha933 (intern)

- Die toten Legacy-Learning-Worker- und Self-Learning-Sektionen samt Admin-Routen aus der Memory-Wartung entfernt; der user-gebundene native Reset fuer Lernvorschlaege bleibt erhalten.
- Pipeline vom ungenutzten Legacy-Learning-Helper-Mixin und seiner Handler-Registrierung entkoppelt sowie Learning-Governance-Event-Writes aus RecipeRuntime entfernt; alle Learning-Module bleiben fuer spaetere B2-Stufen registriert.

## 0.1.0-alpha932 (intern)

- Den Native-Memory-Prompt so klargestellt, dass direkte Merk-, Speicher- oder Notierbitten das bestehende bestaetigungspflichtige `memory_capture` aufrufen muessen, waehrend beiläufige Praeferenzen weiterhin nie ein textliches Speicherangebot erhalten.
- Fuer das servereigene Memory-Learning festgelegt, dass Topic-Values in der Sprache der User-Nachricht bleiben und nie uebersetzt werden; der bestehende kleingeschriebene singulare Bare-Topic-Vertrag bleibt erhalten.

## 0.1.0-alpha931 (intern)

- Die zwei Legacy-Learning-Eingaenge aus B2 Stufe 1 gekappt: Startup Maintenance reiht keine globale Synthese mehr ein und RecipeRuntime zeichnet keine Learning Candidates oder Evals mehr auf; Claim-Speicherung, Rezeptausfuehrung und Auto-Memory-Event-Handling bleiben erhalten.

## 0.1.0-alpha930 (intern)

- Die native Memory-Extraktion auf denselben kleingeschriebenen singularen nackten Themen-Value fuer unterschiedliche Formulierungen einer dauerhaften Praeferenz verschaerft; Predicate-Nuancen bleiben erhalten und Routing Debug zeigt den begrenzten extrahierten Value.

## 0.1.0-alpha929 (intern)

- Die Stores zum Zuruecksetzen nativer Lernvorschlaege werden jetzt aus den kanonischen Runtime-Dateien des Projekts statt aus Lazy-Attributen einer Pipeline-Instanz aufgeloest. Dadurch funktioniert die authentifizierte Wartungsaktion bereits vor einem Native-Turn dieses Workers und behaelt den bestehenden User-Scope bei.

## 0.1.0-alpha928 (intern)

- Memory-spezifische deutsche und englische Darstellung fuer native Lernvorschlaege ergaenzt, sodass die bestehende `memory_capture`-Aktion nicht mehr als Rezeptangebot erscheint; Rezept-Recurrence- und Cross-Host-Copy-Texte bleiben unveraendert.

## 0.1.0-alpha927 (intern)

- Native Memory-Recurrence-Embeddings auf den normalisierten Claim-Value begrenzt, sodass modellvariable Praedikate unterschiedliche Formulierungen desselben Themas nicht mehr trennen; Exact-Key-Abgleich, Subject-Buckets und die vollstaendigen gespeicherten Claims bleiben unveraendert.

## 0.1.0-alpha926 (intern)

- Die Native-Agent-Memory-Regel mit Begruendung, deutschen und englischen Negativbeispielen sowie positivem Antwortverhalten hervorgehoben, damit normale dauerhafte Aussagen kein modellgeschriebenes Merk-/Speicherangebot ausloesen; ausdrueckliche `memory_capture`-Bitten bleiben unveraendert.
- User-gebundene atomare Reset-Operationen fuer native Erinnerungs- und Rezeptvorschlags-Wiederholungen sowie eine authentifizierte, CSRF-geschuetzte und bestaetigungspflichtige Wartungsaktion ergaenzt, die keine gespeicherten Erinnerungen oder Rezepte loescht.

## 0.1.0-alpha925 (intern)

- Den Server-Memory-Pre-filter auf die bestehenden strukturellen Gates plus erweiterte deutsche und englische First-Person-Formen begrenzt; die Klassifikation als dauerhafter Claim bleibt ausschliesslich beim strukturierten Extraktionsmodell.
- Die hartkodierte Dauerwort-Pflicht entfernt, sodass Ich-Praeferenzen wie `ohne Chili schmeckt mir Essen nicht` die Extraktion und damit den unveraenderten Recurrence-/Bestaetigungs-Offer-Pfad erreichen koennen.

## 0.1.0-alpha924 (intern)

- Die modellgewaehlte `memory_note_candidate`-Beobachtung durch einen servereigenen, nebenlaeufigen strukturierten Extraktionsschritt ersetzt, der dauerhafte Ich-Fakten und -Praeferenzen unabhaengig von der nativen Tool-Auswahl erfasst.
- Memory-Recurrence an Subject, Claim-Art und normalisierten Value gebunden, den bestehenden bestaetigungspflichtigen Capture-Button beim zweiten Vorkommen angeboten und bereits gespeicherte Claims ueber eine begrenzte semantische Abfrage mit wiederverwendetem Kandidaten-Embedding geprueft.
- `memory_note_candidate` entfernt; die Native Tool Registry enthaelt wieder 38 Tools, waehrend ausdrueckliche `memory_capture`-Bitten ihren bisherigen Preview-/Bestaetigungsvertrag behalten.

## 0.1.0-alpha923 (intern)

- Die stille native `memory_note_candidate`-Beobachtung fehlertolerant gemacht: ungueltige Kandidaten sowie fehlende oder fehlernde Beobachtungs-Abhaengigkeiten degradieren nun zu einem nicht vorschlagenden `ignored`-Ergebnis, statt den Nutzer-Turn fail-closed zu beenden.

## 0.1.0-alpha922 (intern)

- Das native Personal-Memory-Wiederholungs-Gate im Agent-Prompt erzwungen: normal geaeusserte dauerhafte Fakten und Praeferenzen werden still ueber `memory_note_candidate` beobachtet; nur ausdrueckliche Speicherbitten nutzen das bestaetigungspflichtige `memory_capture`.

## 0.1.0-alpha921 (intern)

- Konservatives natives Beobachten dauerhafter persoenlicher Fakten und Praeferenzen mit semantischem Wiederholungs-Clustering und einmaligem Bestaetigungs-Button ueber die bestehende `memory_capture`-Autoritaet ergaenzt.

## 0.1.0-alpha920 (intern)

- Die ARIA-MIT-`LICENSE` wird nun im Runtime-Image gebuendelt, damit `/licenses` den vollstaendigen, theme-lesbaren Lizenztext auch nach dem Deployment rendert.

## 0.1.0-alpha919 (intern)

- Runtime-Hintergrundsuche nach der Modularisierung korrigiert, sodass gespeicherte Darstellungsoptionen den Reload ueberleben und ihr gewaehltes Bild statt Grid Signal laden.

## 0.1.0-alpha918 (intern)

- Jede unter Darstellung angebotene Hintergrundauswahl wieder mit ihrem passenden ausgelieferten Bild verknuepft; Theme-Overlays und strukturelle Theme-Farben bleiben erhalten.

## 0.1.0-alpha917 (intern)

- Strukturell fest verdrahtete Gruenflaechen in Admin-, Statistik-, Verbindungs- und geteilter Konfigurations-UI durch Theme-Tokens ersetzt; semantische Erfolgs- und Health-Farben bleiben erhalten.
- Den doppelten Updates-Eintrag aus der Hub-Gruppe Ueber entfernt und den leeren ARIA-Lizenzcontainer ausgeblendet, wenn die Lizenzdatei nicht gebuendelt ist.

## 0.1.0-alpha916 (intern)

- Die vollmagenta Konfigurations-Akkordeons des Cyberpunk-Themes durch dunkle ARIA-House-Style-Karten mit grüner Umrandung auf Guardrail- und Verbindungsseiten ersetzt.

## 0.1.0-alpha915 (intern)

- Aktivitäten in Ausführungs-Historie umbenannt und provider-native Websuchen in deren bestehende, einfach gezählte Usage-Projektion aufgenommen.
- Die Lizenzseite von der vollständigen Hilfe-Wiki-Navigation entkoppelt und Guardrail-Karten an den dunklen grünen ARIA-House-Style angeglichen.

## 0.1.0-alpha914 (intern)

- Die redundante Workbench-Uebersicht und die experimentellen Rollout-Schalter entfernt; Datei-Editor, Fehler-Interpreter und LLM-Debug bleiben direkt im Konfigurations-Hub erreichbar.

## 0.1.0-alpha913 (intern)

- Native Rezept-, Memory- und System-Tool-Laeufe werden jetzt in der bestehenden user-gebundenen Aktivitaetsprojektion mit Dauer, Fehlerstatus, Rezeptname und aufgeloesten Zielmetadaten angezeigt.

## 0.1.0-alpha912 (intern)

- Duenne Konfigurations-Hub-Gruppen um ihre echten Modell-, Zugriffs-, Backup-, Log-, Update- und Aktivitaets-Unterseiten ergaenzt; eine Landing-Karte bleibt erhalten, wenn ihre Entfernung die Gruppe leeren wuerde.

## 0.1.0-alpha911 (intern)

- Den gruppierten Konfigurations-Hub vereinfacht: Natuerliche Sektionsueberschriften verlinken jetzt die jeweilige Uebersicht; doppelte Landing-Karten und redundante Gruppen-Untertitel entfallen.

## 0.1.0-alpha910 (intern)

- Parallele Einstellungen-/Admin-Navigationsbaeume durch einen rollenabhaengigen, thematisch gruppierten `/config`-Hub ersetzt; alle Detailseiten bleiben erhalten.
- Die bestehenden Agentic-Loop-Rollout-Schalter in die System-/Entwicklungs-Workbench verlegt und redundante Admin-Gruppenseiten entfernt.
- Den sichtbaren Eintrag `/licenses` in Lizenzvereinbarungen umbenannt, ohne die Route zu aendern.

## 0.1.0-alpha908 (intern)

- Der UI-Audit nutzt statt Auto-Save ein gemeinsames CSRF-geschuetztes Formular zum Speichern aller Zeilen; der Seitentitel wird korrekt lokalisiert.

## 0.1.0-alpha907 (intern)

- Die formularbasierten Einzel-Saves des UI-Audits durch debounced Auto-Save ohne Seiten-Neuladen und mit Zeilenfeedback ersetzt.

## 0.1.0-alpha906 (intern)

- Admin-only UI-Routen-Audit mit automatischer Registry-/Navigations-Erkennung, persistenten keep/verify/cut/regroup-Entscheidungen und JSON-Export ergaenzt.

## 0.1.0-alpha905 (intern)

- Die Live-State-Regel des nativen Agenten verlangt nun auch bei jeder wiederholten Zustandsabfrage einen frischen Tool-Aufruf im aktuellen Turn statt einer Wiederverwendung aus dem Verlauf.

## 0.1.0-alpha904 (intern)

- Modellformulierte Rezept-Lernvorschlaege wurden durch deterministische, nicht blockierende Chat-Buttons mit serverseitig eingefrorenen One-Shot-Bestaetigungsdaten ersetzt.

## 0.1.0-alpha903 (intern)

- Optionales Embedding-basiertes Clustering fuer aehnliche Wiederholungen auf demselben Host und einmalige Vorschlaege fuer inaktive, host-angepasste Rezeptkopien; der exakte Pfad bleibt der robuste Fallback.

## 0.1.0-alpha902 (intern)

- SSH-Ziele werden deterministisch ueber konfigurierte Ref, eindeutigen Anzeigenamen oder eindeutigen Host aufgeloest; mehrdeutige Werte bleiben unaufgeloest.
- Die exakte Wiederholungserkennung nutzt kanonische SSH-Refs und ignoriert unaufgeloeste oder transportseitig fehlgeschlagene Aktionen; echte Policy-Blocks zaehlen weiterhin.

## 0.1.0-alpha901 (intern)

- Begrenzte, persistente und nutzergebundene Erkennung exakt wiederholter nativer Aktionsfolgen ergaenzt.
- Die dritte exakte Wiederholung kann einmalig ein inaktives Rezept anbieten; vorhandene Rezepte und fruehere Angebote unterdruecken Duplikate.
- Secret-freie Signatur-/Zaehler-Diagnose ergaenzt; die Native-Tool-Anzahl bleibt unveraendert.

## 0.1.0-alpha900 (intern)

- Anthropic-Ephemeral-Prompt-Caching fuer den unveraenderten statischen Native-Agent-Systemprompt und die angebotenen Tool-Schemas ergaenzt.
- Native LLM-Latenz und Cache-Token pro Turn werden ohne Credentials oder dynamische Inhalte in den bestehenden Routing-Details ausgewiesen.

## 0.1.0-alpha899 (intern)

- Interne Confirmation-Control-Echos werden vor Native-Agent-Modellaufrufen aus User-History entfernt, damit Action-Tokens nicht als Rezept-IDs wiederverwendet werden.

## 0.1.0-alpha898 (intern)

- `recipe_remember` speichert die letzte explizit ausgefuehrte oder geblockte Native-Tool-Sequenz nach Kernel-Bestaetigung als inaktiven Rezeptentwurf in "Meine Rezepte".
- Eine eng begrenzte, idempotente Boot-Migration leert einmalig den Legacy-Lernstore und entfernt nur die gepaarten Legacy-Learning-Collections.

## 0.1.0-alpha896 (intern)

- Mutierende Host-Wartungsabsichten pruefen modellseitig zuerst das angebotene Recipe-Inventar. Ein passendes aktives Rezept wird ueber seine exakte ID ausgefuehrt; nur wenn keines passt, bleibt ein vollstaendig geguardeter Ad-hoc-SSH-Befehl der letzte Ausweg.
- Woertlich diktierte Einzelbefehle und einmalige Leseabfragen, Tool-Schemas/-Beschreibungen, Confirmation, SSH-Policy, Guardrails, 37 native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha895 (intern)

- Der modellseitige Native-Tool-Vertrag gibt benannten oder beabsichtigten gespeicherten Rezepten Vorrang vor dem Nachbau ihrer Aktionen als Ad-hoc-SSH-Befehl. Wo noetig dienen Recipe-Inventar oder -Preview weiterhin nur der exakten ID-Aufloesung.
- Woertlich genannte einmalige SSH-Reads und -Commands, Confirmation, SSH-Policy, Guardrails, 37 native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha894 (intern)

- Der Recipe-Wizard bietet fuer `ssh_run` optional ein Timeout in Sekunden. Positive Werte werden gespeichert und beim erneuten Oeffnen vorbefuellt; leer, null oder ungueltig laesst den Key weg, sodass der Connection-Default gilt.
- Recipe-Ausfuehrung, SSH-Policy, Guardrails, 37 native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha893 (intern)

- Jede bearbeitbare Karte unter Meine Rezepte besitzt eine Duplizieren-Aktion. Kopien erhalten kollisionsfreie IDs, behalten ihre Schritte und werden stets inaktiv gespeichert, damit sie vor der Aktivierung geprueft und angepasst werden koennen.
- Rezept-Ausfuehrung, adaptives Binding, Guardrails, 37 native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha892 (intern)

- Der bestehende Chat-Warteindikator zeigt waehrend laufender Rezepte live den logischen Schritt, bei adaptivem SSH-Fan-out den aktuellen Host sowie kumulierte Erfolgs-/Fehlerzahlen. Ein user-gebundener In-Memory-TTL-Store und ein polling-basierter Read-Endpunkt liefern nur additive Anzeigeinformationen; ohne Fortschritt bleibt die bisherige Sekundenanzeige.
- Rezept-Ausfuehrung, Confirmation, Guardrails, 37 native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha891 (intern)

- SSH-Guardrail-Profile koennen exakte IDs aktivierter Rezepte ueber einen Admin-Multi-Select erlauben. Nur ein passendes, kernel-bestaetigtes Rezept darf die normalen Allow-/Deny-Woerter dieses Profils umgehen; Ad-hoc-SSH und nicht erlaubte Rezepte bleiben unveraendert geguardet.
- Ein nicht uebersteuerbarer Code-Hard-Floor blockiert weiterhin Root-/Home-Wipes, rohe Blockgeraete-Schreib-/Formatbefehle, Fork-Bomben und Shutdown/Reboot/Halt/Poweroff/Init 0/6. Registry bleibt bei 37 nativen Tools, Public bleibt alpha604.

## 0.1.0-alpha890 (intern)

- Bestaetigte Recipe-Ergebnisse werden als lesbarer Klartext statt als Tool-JSON-Huelle weitergereicht; eine vom Recipe erzeugte `direct_chat_text`-Uebersicht hat Vorrang vor dem technischen Ergebnistext.
- Adaptive Multi-Host-SSH-Ausgaben werden vor einem Folgeschritt nach exakter Connection-Ref beschriftet zusammengefuehrt, sodass `llm_transform` alle Host-Ergebnisse sieht. Einzel-Host-Rezepte, Zielaufloesung, Per-Host-Policy, Confirmation, 37 native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha889 (intern)

- Native Tools koennen explizit ihr bereits nutzerfertiges, begrenztes Ergebnis nach Kernel-Bestaetigung direkt weiterreichen. Nur `recipes_execute` aktiviert dies, sodass die Recipe-eigene Uebersicht nicht durch einen zweiten Modellaufruf kondensiert wird; alle anderen mutierenden Tools behalten ihre bisherige Ergebnisformulierung.
- Confirmation, Recipe-Ausfuehrung, 37 native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha888 (intern)

- Der nach dem Safe-Fix-Teardown absichtlich leere Held-Packages-Summary-Wert wird nun vor der Recipe-Step-Ausfuehrung definiert. Erfolgreiche `ssh_run`-Rezepte erreichen damit ihre Ergebniszusammenfassung ohne `NameError`; adaptives Binding, SSH-Policy, native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha887 (intern)

- Die 15 ausgelieferten Legacy-Demo-Rezepte mit fixen, typischerweise nicht existierenden Connection-Refs sowie ihre Kopien unter `samples/skills` wurden entfernt.
- Ausgeliefert werden nur noch drei adaptive SSH-Beispiele fuer Uptime, Festplattenbelegung und Update-Pruefung. Sie verwenden `connection_kind=ssh` plus `binding=all`; User-Runtime-Rezepte, Alpha886-Expansion/SSH-Policy, 37 native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha886 (intern)

- `ssh_run`-Recipe-Steps koennen additiv ueber `connection_kind=ssh` und `binding=all|one` an konfigurierte SSH-Profile gebunden werden; `all` expandiert vor Ausfuehrung in konkrete Per-Ref-Steps mit Cap 20, `one` verlangt exakt ein Profil.
- Fixe `connection_ref`-Rezepte bleiben unveraendert. Die Confirmation-Preview nennt die aufgeloesten Ziele; alle expandierten Steps laufen weiter durch dieselbe Per-Step-SSH-Policy und Output-Begrenzung. Native Toolzahl und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha885 (intern)

- Der native Web-Tool-Boundary setzt `search_context_size` unabhaengig von einem gespeicherten Config-/Env-Wert fest auf `high`; das bestehende Feld bleibt aus Kompatibilitaetsgruenden erhalten, ist fuer die native Suche aber nicht mehr autoritativ.
- Alpha884-Query-Framing, Reasoning-Effort, Output-Limit, Debugdetails, native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha884 (intern)

- Provider-native Websuchen werden nicht mehr an veraltete Jahreszahlen oder Modellhinweise gebunden: Das aktuelle Datum ist im Gateway autoritativ, alte Evidence-URLs werden nicht mehr in den Provider-Input injiziert und der fehlende/leere Context-Size-Fallback ist `high`.
- Der Native Agent muss `web_search_fetch` mit frische-neutralen latest/current-Queries ohne hartkodiertes vergangenes Jahr aufrufen. Reasoning-Effort, Output-Limit, native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha883 (intern)

- Der temporaere Alpha882-Dateidump ist vollstaendig entfernt.
- Ein neuer standardmaessig ausgeschalteter Admin-Schalter zeigt den exakt gesendeten nativen Web-Input, kompakte Request-Parameter und hoechstens acht Evidence-URLs in den Routing-Details genau des bedienenden Chat-Turns.
- Secrets und rohe Provider-Responses werden nicht in die Chat-Details uebernommen; Web-Logik, native Tools und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha882 (intern)

- Der native Web-Gateway ueberschreibt temporaer nach jedem erfolgreichen Provider-Call genau eine Debug-Datei mit dem exakt gesendeten Input, rekursiv redigierter Raw-Response und normalisierter Evidenz.
- Dump-Fehler beeinflussen den Turn nicht; es gibt bewusst keinen Config-/Env-Schalter. Public alpha604 bleibt unveraendert.

## 0.1.0-alpha881 (intern)

- Das wirkungslose Auto/Main/Web-Chatmodus-Menue samt Client-Submission und verworfenem Request-Threading wurde entfernt.
- Main/Web-Modellkonfiguration, native Ausfuehrung und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha880 (intern)

- Der Context-Size-Default der provider-nativen Websuche wurde von `low` auf `high` angehoben.
- `ARIA_WEB_LLM_SEARCH_CONTEXT_SIZE` erlaubt `low`, `medium` oder `high`; ungueltige Werte verwenden den kanonischen Default.
- Native Tools, Gateway-Payloads und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha879 (intern)

- Der Native-Agent-Systemprompt verlangt fuer neueste/aktuelle schnelllebige externe Fakten jetzt `web_search_fetch` statt einer Antwort aus veraltetem Modellwissen.
- Antworten muessen Datum oder Stand der gefundenen Evidenz nennen und aeltere Evidenz ehrlich als neuesten gefundenen Stand statt als aktuell bezeichnen.
- Native Tools, Confirmation-Kernel, Ausfuehrungsautoritaet und Public alpha604 bleiben unveraendert.

## 0.1.0-alpha877 (intern)

- Hygiene B entfernt 24 leere Modulhuellen sowie den verwaisten Modul-`__pycache__` aus den abgeschlossenen Legacy-Loeschwellen.
- Der seit dem Safe-Fix-Drop inerte Discord-Schalter `alert_safe_fix` ist aus Config, Katalog, Formularen, Profilprojektionen, UI, Alert-Mapping und I18N entfernt.
- Bestehende Konfigurationen mit dem alten Key laden weiterhin fehlerfrei; der unbekannte Altwert wird ignoriert.

## 0.1.0-alpha876 (intern)

- Hygiene A entfernt 14 nach dem Funnel-Teardown unerreichbare Legacy-Support-Module aus Entscheidungs-, Resolution- und Answer-Composition-Schichten.
- `ssh_resolution` und `agentic_content_access` bleiben erhalten, weil lebende Runtime-Module sie weiterhin importieren; der iterative Waisenscan fand keine weitere neu verwaiste Loeschkandidatin.
- Native Registry, Confirmation-Kernel, Recipe-Ausfuehrung und Public-Version bleiben unveraendert.

Alle wichtigen Aenderungen an ARIA sollten in dieser Datei dokumentiert werden.

Format: `Added` / `Changed` / `Fixed` / `Security` / `Known Limitations` / `Upgrade Notes`

## [Unreleased]

### Interner Alpha875-Codekandidat

- Der in Alpha874 vollstaendig vom lebenden Code getrennte zehnteilige
  Legacy-Funnel-Ring wurde physisch entfernt. Registry, Ownership-Evidence und
  obsolete Ring-Tests sind bereinigt; die weiterhin produktiv verwendeten
  Action-Template-/Result-State-Utilities bleiben erhalten. Native Tools,
  Confirmation-Kernel, Recipes und System-Inventory bleiben unveraendert.
  Public bleibt `0.1.0-alpha604`.

### Interner Alpha874-Codekandidat

- Lebende Pipeline-, Inventory-, Recipe-, Dry-Run-, Pending-Action- und
  Context-Verbraucher importieren keine Runtime-Implementierung des verbliebenen
  Legacy-Funnel-Rings mehr. Behavior-identische Utilities liegen nun bei
  behaltenen Ownern; die zehn Ring-Pakete bleiben fuer die separate Loeschung in
  Etappe 3e unveraendert vorhanden. Public bleibt `0.1.0-alpha604`.

### Interner Alpha873-Codekandidat

- Die vier nicht mehr erreichbaren Legacy-Pipeline-Orchestrierungs-Mixins und ihr
  registriertes Modul wurden entfernt. Die Pipeline behaelt nur technische Helfer,
  die Native Tools, Recipe-Ausfuehrung, SSH, Memory, Website und Result-Finalisierung
  weiterhin nachweislich benoetigen. Public bleibt `0.1.0-alpha604`.

### Interner Alpha872-Codekandidat

- Der weiterhin benoetigte Recipe-Executor und seine exakte Runtime-Recipe-Aufloesung
  gehoeren nun dem `recipe_runtime`-Pipeline-Helper statt dem toten Legacy-Action-Mixin.
  Native `recipes_execute`, Custom-Step-Ausfuehrung und alle Step-Guardrails bleiben
  unveraendert. Public bleibt `0.1.0-alpha604`.

### Interner Alpha831-Codekandidat

- Aktivierte Native-Agent-Web-Turns rufen den nativen Handler nun vor der
  teuren Pre-Pipeline-MetaCatalog-Arbitration auf. Pending-Kontexte und
  deaktivierte Flags behalten den Legacy-Pfad unveraendert; liefert der native
  Handler unerwartet `None`, werden Arbitration und Legacy-Pipeline sauber
  nachgeholt.
- Bewusster Rollout-Trade-off: modellgeroutete Admin-Aktionen pro Chat und
  `memory_forget` werden bei aktivem Native-Flag voruebergehend nicht
  verarbeitet, bis sie als native Tools vorliegen. Public bleibt
  `0.1.0-alpha604`.

### Interner Alpha830-Codekandidat

- Der eigenstaendige, standardmaessig deaktivierte native Agent bietet nun auch
  `list_connections` als read-only Anthropic-natives Tool an.
- Das vollstaendige Inventar kommt passiv aus der Connections-Profilautoritaet,
  nicht aus Arbitration oder MetaCatalog-Top-k; optional kann exakt nach
  `connection_kind` gefiltert werden.
- Die aktuelle Turn-User-ID wird vom Handler gebunden und kann nicht vom Modell
  gewaehlt werden. Memory- und Connections-Tool besitzen getrennte Admin-Flags;
  bei beiden Flags entscheidet das Modell aus dem angebotenen nativen Toolsatz.
- Keine Profile ergeben eine ehrliche leere Antwort. Public bleibt
  `0.1.0-alpha604`.

### Interner Alpha829-Codekandidat

- Ein eigenstaendiger nativer Agent kann bei explizit aktiviertem Rollout den
  gesamten Turn vor Runtime-Follow-up und MetaCatalog-Arbitration uebernehmen.
- Er nutzt ausschliesslich den Anthropic-nativen `tools`-Pfad und bietet ein
  read-only Personal-Memory-Tool aus der autoritativen Memory-Quelle an.
- Direkte Chat-Antworten benoetigen keinen Tool-Aufruf; Tool-Schritte und finaler
  Ausgang werden begrenzt unter `data/modules/native_agent/` protokolliert.
- Der neue Admin-Schalter ist standardmaessig AUS und wirkt nur zusammen mit
  dem ebenfalls standardmaessig ausgeschalteten Master-Schalter.

### Interner Alpha828-Codekandidat

- Der native Tool-Calling-Selftest uebergibt LiteLLM nun eine Anthropic-native
  Tool-Definition mit explizitem `input_schema.type="object"`, Properties und
  Required-Feldern. Provider-BadRequests zeigen im Admin-Diagnoseergebnis den
  rohen Fehlertext und exakt das gesendete Tool-Payload. Tool-Call-Parsing und
  der zweite Roundtrip-Schritt bleiben unveraendert.
- Kein Public Release; Public bleibt `0.1.0-alpha604`.

### Interner Alpha827-Codekandidat

- Ein eigenstaendiger Admin-Diagnosetest prueft natives LiteLLM-Tool-Calling
  ueber `tools` und `tool_choice="auto"` mit dem rein lokalen, deterministischen
  Dummy-Tool `add_numbers`. Er gibt das Tool-Ergebnis in einem zweiten
  Modellaufruf zurueck und zeigt die Transportdiagnose an. Der Test verwendet
  weder `response_format`/JSON Schema noch Qdrant, Turn-Pipeline, Agentic Loop
  oder Produktoperationen; das Laden der Seite ist inert, nur ein expliziter
  POST loest die zwei Provider-Aufrufe aus. Lokal gruene Fake-Tests sind kein
  Live-Beweis; erst der spaetere explizite Live-Trigger prueft den Provider.
- Kein Public Release; Public bleibt `0.1.0-alpha604`.

### Interner Alpha826-Codekandidat

- Der standardmaessig deaktivierte Agentic Loop besitzt mit Personal-Memory-
  Recall seine erste modellgetriebene Vertikale. Recall bleibt an MetaCatalog-
  und Claim-Autoritaet gebunden, schreibt pro Schritt einen Lern-Trace und darf
  fehlgeschlagene Executor-Resultate niemals als erfolgreiche Antwort verwenden.
  Admins koennen die standardmaessig deaktivierten read-only Rollout-Flags ueber
  den bestehenden Config-Speicherweg schalten.
  Die Alpha825-Korrektur zieht das Recall-Gate vor die alte Arbitration;
  ein kleiner Modellentscheid waehlt Personal Recall oder unveraendertes Legacy.
  Der Alpha825-Livefehler zeigte leeren Message-Content bei Anthropic Tool-Use.
  Alpha826 liest deshalb die strukturierten Argumente des ersten Tool-Calls;
  normaler Content, Usage, Audit, Kosten und echtes Empty-Response-Verhalten
  bleiben unveraendert.
- Kein Public Release; Public bleibt `0.1.0-alpha604`.

### Interner Alpha823-Codekandidat

- Stage-2-Compiler fuer Connections und Commands verwerfen unbekannte
  nicht-autoritative Felder konsistent. Connection-Kinds/-Refs, Capabilities,
  Effects, Berechtigungen, Confirmation und Action-Matches bleiben exakt und
  fail-closed. Personal Memory darf einen widerspruechlichen Answer-/Context-
  Vertrag genau einmal modellbasiert reparieren.
- Kein Public Release; Public bleibt `0.1.0-alpha604`.

### Interner Alpha822-Codekandidat

- Strukturierte Turn-Entscheidungen verhandeln Strict-JSON-Schema jetzt
  fehlertolerant. Lehnt ein Provider Strict ab, folgt einmal der validierte
  nicht-strikte Pfad; spaetere Turns vermeiden einen erneuten fehlgeschlagenen
  Strict-Probe. Ignorierte Strict-Vorgaben bleiben durch Validierung und genau
  einen modellbasierten Repair begrenzt.
- Kein Public Release; Public bleibt `0.1.0-alpha604`.

### Interner Alpha821-Codekandidat

- Makroblock G fuegt einen standardmaessig deaktivierten Agentic Execution Loop
  mit einer read-only Connections-Inventory-Vertikale hinzu. Operationsvertrag,
  Policy und Confirmation werden vor Ausfuehrung im Kernel erzwungen; Iteration,
  Budgets, Observations und maschinenlesbare Traces laufen fail-closed.
- Kein Public Release; Public bleibt `0.1.0-alpha604`.

### Interner Alpha820-Codekandidat

- Recipes, Chat, Connections und Commands verwenden nach dem MetaCatalog-
  Dispatch schmale owner-spezifische Operationspayloads.
- Commands koennen nur Action-IDs kompilieren, die aktuelle Qdrant-
  MetaCatalog-Kandidaten anbieten; stale Config ersetzt keine Routingquelle.
- Recipe Inventory, Modulsemantik-Diagnostics und der SSH-Confirmation-
  Debuggrund aus dem Alpha819-Live-Review wurden korrigiert.
- Kein Public Release; Public bleibt `0.1.0-alpha604`.

### Public-Release-Notes-Entwurf seit 0.1.0-alpha604 - Hauptaenderungen

- **ARIA wurde von einem Monolithen auf eine modulare Architektur umgebaut.** Die interne Struktur besteht nicht mehr aus einem grossen Chat-/Runtime-Block, sondern aus registrierten Modulen mit klareren Ownern, Manifesten, Readmodels, Boundaries, Importidentitaeten und Release-Hygiene. Fuer Nutzer soll ARIA dadurch stabiler wartbar, besser testbar und weniger anfaellig fuer verdeckte Seiteneffekte sein; fuer Betreiber bedeutet es aber, dass dieses Update deutlich groesser ist als ein normales Alpha-Upgrade.
- **Routing und Tool-Nutzung sind strenger agentisch getrennt.** MetaCatalog, Dokumente, Memory, Notes, Recipes, Web/Public Facts und Runtime Actions haben eigene Autoritaetsgrenzen bekommen. Natuerliche Sprache soll nicht mehr ueber Wortlisten-, Regex-, Substring-, Token-, Stem- oder Phrasentrigger entschieden werden; Modellentscheidungen liefern strukturierte Plaene, danach validiert ARIA mechanisch IDs, Quellen, Schemata, Confirmation und Berechtigungen.
- **SearXNG ist nicht mehr der mitgelieferte Public-WebSearch-Pfad.** Gespeicherte SearXNG-Profile werden nicht mehr als Betriebsmodell vorausgesetzt. Fuer aktuelle Webantworten braucht ARIA stattdessen ein geeignetes LLM/Provider-Setup mit Web-Tooling bzw. verwaltetem Websuchdienst. Ohne dieses Web-Tooling muss ARIA bei aktuellen Fakten und Webfragen fail-closed oder eingeschraenkt antworten, statt heimlich auf alte lokale Suchprofile auszuweichen.
- **Public-Facts/WebSearch wurde source-bound neu abgesichert.** Aktuelle Fakten wie Preise, Geraete, Softwareversionen oder Webinhalte duerfen nicht mehr aus Modellwissen geraten werden, wenn eine Quelle erforderlich ist. Web-/Public-Fact-Antworten muessen ihre Such-/Tool-Autoritaet und den Quellenumfang einhalten.
- **Recipes wurden fachlich neu aufgeteilt.** Die gespeicherten Recipe-Manifeste stammen aus demselben Katalogpfad wie die UI, Operationen wie `inventory`, `explain`, `preview`, `execute` und `none` gehoeren einem eigenen Recipe-Semantikowner, und Execute erzeugt eine Confirmation statt still auszufuehren. Unbekannte Recipe-IDs werden source-bound erklaert und nicht durch aehnliche IDs ersetzt.
- **Notes, Dokumente und Memory wurden nach der Modularisierung repariert.** Notes-Folder-Listen, Dokumentinventare, Dokument-vs-Memory-Source-Labels und persoenlicher Recall wurden in mehreren internen Alphas wieder source-bound gemacht, damit ARIA nicht mehr zwischen aehnlich klingenden Speicher-, Notiz- und Dokumentquellen springt.
- **Runtime Actions sind konservativer geworden.** Action-Auswahl, Action-Input, Target-Scope und Confirmation sind staerker eingefroren. ARIA soll keine Runtime-Aktion ausfuehren, bevor die exakte strukturierte Aktion, das Ziel, die Berechtigung und die Nutzerbestaetigung zusammenpassen.
- **Release- und Artifact-Hygiene wurde deutlich verschaerft.** Interne Builds pruefen CLI/Release-Meta, Package-Daten, Registry, JSON/Compileall/Diff-Hygiene, Source-Bytecode, Layer-Privacy und passive HTTP-Routen. Private Daten, Secrets, produktive Connections, Qdrant-Daten und Live-Runtime-Aktionen gehoeren nicht in Public-Artefakte.

### Upgrade Notes

- Betreiber sollten dieses Update wie einen Architekturwechsel behandeln: Konfiguration, Provider, Web-Tooling, Recipes, Notes, Dokumente, Memory und Actions nach dem Upgrade gezielt testen.
- Wer bisher SearXNG als lokalen Suchdienst genutzt hat, muss auf das neue Provider-/Web-Tooling-Modell migrieren. Alte SearXNG-Profile sind keine verlaessliche Public-Upgrade-Basis mehr.
- Public bleibt bis zur separaten Public-RC-Freigabe auf `0.1.0-alpha604`; die folgenden Alpha-Eintraege dokumentieren interne Review-Builds und Live-Review-Fixes seitdem.

### Smooth Upgrade / Kein CLI-Recovery-Ziel

- **Der Public-Upgrade-Pfad muss zuerst ueber Browser/Managed Update funktionieren.** Normale Nutzer sollen nicht nach dem Update Docker-Container per Hand suchen, Compose-Dateien flicken oder unklare CLI-Recovery-Schritte ausfuehren muessen. `/updates`, `aria-setup upgrade` und `./aria-stack.sh update` sind die vorgesehenen Wege; rohe Docker-Kommandos gehoeren nur in Admin-/Recovery-Doku.
- **Keine stillen Daten- oder Volume-Loeschungen.** Config, Prompts, Notes, Recipes, Auth-Daten, Memory, Dokumentdaten und Qdrant-Collections duerfen beim Public-Sprung nicht geloescht, verschoben oder neu initialisiert werden, ohne dass ein eigener Migrationsschritt das vorher klar anzeigt und bestaetigen laesst.
- **SearXNG ist eine bewusste Stack-Migrationsentscheidung.** Die Anwendung verlaesst den alten SearXNG-Profilpfad, aber vorhandene Public-Stacks koennen noch `searxng` und `searxng-valkey` enthalten. Empfehlung fuer den ersten Public-Architektursprung: diese Sidecars nicht automatisch loeschen, sondern als Legacy/inert stehen lassen und ARIA auf Provider-Web-Tooling ausrichten. Eine spaetere Entfernung sollte ein eigener opt-in Helper mit Dry-run, Healthcheck und Rollback-Hinweis sein.
- **Wenn ein Script etwas stoppt, loescht oder neu erstellt, muss es das vorher sagen.** Fuer einen spaeteren SearXNG-Cleanup oder Compose-Layoutwechsel muss der Helper transparent ausgeben: betroffene Services, betroffene Volumes, was erhalten bleibt, was entfernt wird, welche Backups/Hashes existieren und wie der Abbruch vor Datenmutation funktioniert.
- **Provider-/Web-Tooling-Readiness muss sichtbar sein.** Vor einem Public-RC braucht ARIA eine klare UI-/Dokumentationsspur, ob ein LLM mit Web-Tooling bzw. verwalteter Websuche konfiguriert ist. Fehlt diese Faehigkeit, muessen Current-Fact/Web-Fragen ehrlich eingeschraenkt oder fail-closed sein, statt Nutzer in SearXNG-Debugging zu schicken.
- **Offene Public-RC-Gates vor einem Release.** Vor dem naechsten Public muss ein Upgrade-Pack mindestens Managed-Setup-Upgrade, Host-Update-Dry-run, Compose-Config, passive HTTP-Routen, Config-Backup/Restore-Readpoints, Provider/Web-Tooling-Hinweise, SearXNG-Legacy-Verhalten und No-Data-Deletion pruefen. Matrix: `.codex/aria_acceptance/public-alpha604-to-alpha807-upgrade-transition.json`.

### Detaillierter interner Alpha-Changelog

### alpha807 candidate - Changed

- **MetaCatalog transportiert Actions nur noch aus strukturierter Autoritaet und ist intern gebaut.** Der MetaCatalog-Payload nimmt Action-Zeilen nicht mehr pauschal aus dem globalen Runtime-Menue, sondern aus exakten `action_candidates`, `managed_action`-Refs, strukturierten Connection-Kinds und dem bestehenden Memory-Capture/Forget-Vertrag. Recipe-Domain-Handoffs koennen dadurch ohne unrelated Runtime-Actions an den Recipe-Semantikowner gehen; `aria_recipe_catalog_routing` bleibt alleiniger Owner fuer `inventory|explain|preview|execute|none` und exakte angebotene Recipe-IDs. Unknown-Recipe-ID antwortet jetzt source-bound mit angefragter ID und den exakt angebotenen IDs statt generischem Aktionsvertragstext. Ordinary Same-Hop-Chat ist mit leerem Action-Transport eingefroren; Routing Debug zeigt `action_transport_available/candidates/pruned`. Keine Wortlisten-, Regex-, Substring-, Token-, Stem- oder Phrasensemantik wurde hinzugefuegt. Red-first `3` rot; danach Fokus `4`, MetaCatalog `111`, Meta/Pipeline `115`, Pipeline/Source `344`, Arbitration/TurnDecision `132`, Arbitration/i18n/Release `124`, Release/Registry/UI `353`, i18n `4`, JSON, Compileall und Vollsuite `2643 passed` mit 5 bekannten aiohttp-Warnungen gruen. Image `sha256:b235c7f7cee4722735ce588ac0346f2fed6ccfe759cf607aae0641c9c4b1065f`; TAR/Alias SHA256 `fb77bfe1704c7efdb89bebca4a2139b0729972043d01188ccd62b56146a6422a`, `256740352` Bytes, Modus `0600`. Isolierte Smokes belegen CLI/Release-Meta Alpha807, `source_bytecode=0`, Layer-Privacy ohne private Dateien und passive HTTP-Routen `8x200`. Acceptance `.codex/aria_acceptance/meta-catalog-action-transport-alpha807.json`; Build-Evidence `.codex/aria_acceptance/meta-catalog-action-transport-alpha807-review-build.json`. Public Alpha604 bleibt unveraendert.

### alpha806 candidate - Changed

- **MetaCatalog fuer gespeicherte Recipes entmachtet und intern gebaut.** MetaCatalog sieht keine gespeicherten Recipe-Details mehr und darf nur noch die breite Recipe-Domain waehlen; die konkrete Operation `inventory`, `explain`, `preview`, `execute` oder `none` gehoert einem eigenen bounded Recipe-Semantikowner mit striktem JSON-Schema, exakten angebotenen IDs, Confidence-Gate und fail-closed Validierung. Fehlende oder ungueltige Recipe-Discriminatoren degradieren nicht zu Plain Chat und loesen weder Repair noch Final Composer aus. Keine Wortlisten-, Regex-, Substring-, Token-, Stem- oder Phrasensemantik wurde hinzugefuegt. CODE-Gates: fokussierter Recipe-Owner `9`, Meta/Source/Pipeline `453`, Web/Notes/Recipe-Nachbarschaft `150`, isolierter Pipeline-Smoke und Vollsuite `2641 passed` mit 5 bekannten aiohttp-Warnungen; BUILD-Preflight `108` plus Recipe/Meta-Fokus `5`; JSON, Compileall und Diff-Hygiene gruen. Image `sha256:acd1f37fd74f83a0ef1d9b11f105840cc251d4ef802bbcce6fcea6a70cba385d`; TAR/Alias SHA256 `9567b5850a457929cda69fc51d1c7ca638ef76113a3f7e62819affec4f846904`, `256688640` Bytes, Modus `0600`. Isolierte Smokes belegen CLI/Release-Meta Alpha806, `source_bytecode=0`, Layer-Privacy ohne private Dateien und passive HTTP-Routen `8x200`. Acceptance `.codex/aria_acceptance/recipe-semantic-owner-alpha806.json`; Build-Evidence `.codex/aria_acceptance/recipe-semantic-owner-alpha806-review-build.json`. Public Alpha604 bleibt unveraendert.

### alpha805 candidate - Changed

- **Public-Release-Vorfilter lokal gebuendelt und intern gebaut.** Alpha803 friert Public-Current-Facts/WebSearch mit Apple Watch, iPhone, n8n, Home Assistant und Qdrant source-bound/fail-closed ein; Alpha804 blockiert private/interne Artefakte in Public-Tree, Docker-Kontext und Package-Data; Alpha805 buendelt diese P0s mit Actions/Confirmation, Ordinary Chat/Error, Recipes und Memory/Notes/Docs als Build-Sparfilter. Keine Produktsemantik, keine Wortlisten-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik wurde hinzugefuegt. CODE-Gates: Release/Registry/Artifact `108`, Actions/Confirmation `79`, Memory/Notes/Docs `116`, WebSearch/Public Facts `230`, Recipes/Arbitration `148`, Ordinary Chat/Error/Tooling `185`, Vollsuite `2633 passed` mit 5 bekannten aiohttp-Warnungen; BUILD-Preflight `108`; JSON, Compileall und Diff-Hygiene gruen. Image `sha256:ed946db198a236718d7fb4154a80c4e4c37fbe79db4a56137b32cdb2278c6bda`; TAR/Alias SHA256 `754718acf363981bdf18209b2ab0c5ebfb5e75be6545563873ca99d70c71e30f`, `256655360` Bytes, Modus `0600`. Isolierte Smokes belegen CLI/Release-Meta Alpha805, `source_bytecode=0`, Layer-Privacy ohne private Pfade und passive HTTP-Routen `8x200`. Acceptance `.codex/aria_acceptance/public-release-regression-pack-alpha805.json`; Build-Evidence `.codex/aria_acceptance/public-release-regression-pack-alpha805-review-build.json`. Public Alpha604 bleibt unveraendert.

### alpha796 candidate - Fixed

- **Ordinary Chat bleibt auf dem kurzen Same-Hop-Pfad.** Ein validierter MetaCatalog-Plan fuer normalen, nicht source-bound Chat mit `decision_kind=answer`, `needs_context=false`, keinen Surfaces/Actions/Requests, `contract answer/allow_general` und vorhandenem `response_text` ueberspringt jetzt Action/Recipe-Handling sowie Context Loading und geht direkt zur Antwort. Final Composer, Recipe-Turn-Contract, Context-Packet, Runtime-Ausfuehrung und Pending State bleiben aus.
- **Source-bound und Handoff-Pfade bleiben geschuetzt.** Der Action/Recipe-Skip greift weiterhin fuer confident non-action contracts und schuetzt damit alte sichere Chat-Vertraege vor unseeded Pre-RAG-Actions. Der Context-Skip ist enger: nur echte Same-Hop-Antworten mit `response_text`, und nicht wenn ein lokaler Dokumententscheid seine Handoff-Usage/Evidence erhalten muss. Dokumente, Personal Recall, Web/Public Facts, Recipe Inventory und Runtime Actions behalten ihre eigenen source-bound/confirmation-Vertraege.
- **Keine Wortlisten-Semantik; intern gebaut und exportiert.** MetaCatalog bleibt alleiniger Natural-Language-Semantikowner; der Patch liest nur strukturierte Planfelder, Diagnosen und vorhandene Contract-Booleans. Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik wurde hinzugefuegt. Red-first zeigte erst `recipe_turn_contract`, danach `context_packet` auf Ordinary Same-Hop; danach Fokus `5`, gezielte Regressionen `4`, MetaCatalog/Pipeline `319`, Arbitration/TurnDecision/Context `165` und CODE-Vollsuite `2617 passed` mit 5 bekannten aiohttp-Warnungen gruen. BUILD-Gates: Prebuild Release/Updates `76`, Recipe/MetaCatalog/Pipeline `375`; Post-Bump Release/Updates `76`, Post-Bump-Vollsuite `2617 passed`; finales Post-Export-Gate `2617 passed` mit 5 bekannten aiohttp-Warnungen. Pyflakes, strict i18n, externes Compileall, `431` Acceptance-JSONs, Diff-Hygiene und Source-Bytecode0 gruen. Image `sha256:7805f3f6d84658cc9c2281b0517445963c01f07c0ec1825e809de1b411642b69`; TAR/Alias SHA256 `7c13af0c3aacd109a459bd3baf5c88f8f02a05fe21659fd5dc6b68ef9d105b78`, `254125056` Bytes, Modus `0600`, Retention alpha792-alpha796. Isolierte no-network Smokes belegen CLI Alpha796, `/app/aria` Source-Bytecode0, Ordinary-Same-Hop ohne Recipe/Context/Composer/Pending Action, passive HTTP `5x200/3x303`; nur das Python-Base-Image-`GPG_KEY` ist als oeffentlicher Signing-Key im Env sichtbar, kein ARIA-Secret. Acceptance `.codex/aria_acceptance/general-chat-ordinary-closure-alpha796.json`; Build-Evidence `.codex/aria_acceptance/general-chat-ordinary-closure-alpha796-review-build.json`. Kein Live-/produktiver Daten-/Connection-/Secret-/Qdrant-/Provider-/Runtimezugriff; Workspace/CLI/Build Alpha796, Public Alpha604.

### alpha794 candidate - Fixed

- **Recipe-Inventory nutzt dieselbe gespeicherte Katalog-Autoritaet wie `/recipes/mine`.** Der Alpha793-Livetest war routenseitig korrekt (`recipe_operation=inventory`, kein Final Composer), aber unvollstaendig: Chat sah nur `ssh_run_command`, waehrend die UI mindestens fuenf aktive gespeicherte Recipes zeigte. Die Runtime laedt nun kanonische `data/recipes` und legacy-kompatible `data/skills`-Manifeste in derselben Reihenfolge wie die UI; kanonische IDs gewinnen genau einmal.
- **Toggles und Cache sind source-bound.** `skills.custom.<id>.enabled` gilt auch fuer legacy-kompatible Rows, deaktivierte Recipes werden nicht MetaCatalog angeboten und nicht in Inventory/Explain/Preview gerendert. Die Runtime-Cache-Signatur enthaelt Manifest- und Config-State, sodass reine Toggle-Aenderungen ohne Manifest-Mtime-Wechsel greifen.
- **Keine neue Sprachsemantik; intern gebaut und exportiert.** MetaCatalog bleibt alleiniger Natural-Language-Semantikowner; keine Usertext-Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik wurde hinzugefuegt. Red-first Runtime zeigte vor Fix `2 failed,1 passed`; danach Fokus6, Rezept/UI64, Routing/Pipeline533, CODE-Vollsuite2615/5, Release/Updates76, Post-Bump-Vollsuite2615/5 und finales Post-Export-Gate2615/5 bekannte aiohttp-Warnungen gruen. Pyflakes, externes Compileall, strict i18n, 425 Acceptance-JSONs, Source-Bytecode0 und Diff-Hygiene gruen. Image `sha256:af7737bd48aa617011c03cb68d919c118bd76dcec73a7c8f90c9ec030a6a9937`; TAR/Alias SHA256 `ee64f2d6c4e196d2f048207cfca718f0066f4d17c0e864fc5d89daf7b13a2520`, `256650240` Bytes, Modus `0600`, Retention alpha790-alpha794. Isolierte no-network Smokes belegen CLI Alpha794, Privacy leer, Runtime Recipe catalog canonical+legacy, disabled toggle excluded und HTTP `5x200/3x303`. Kein Live-/produktiver Daten-/Connection-/Secret-/Qdrant-/Provider-/Runtimezugriff; Workspace/CLI/Build Alpha794, Public Alpha604.
- **User-Live-Review akzeptiert und eingefroren.** Der Alpha794-Export `[redigierter lokaler Anhang]` listet auf `Welche gespeicherten Rezepte hast du?` alle fuenf aktiven gespeicherten Recipes, mit `recipe_operation=inventory`, `manifests=5`, `downstream_model_calls=0`, Recipe-Stage `2ms` und ohne Ausfuehrung. Closure `.codex/aria_acceptance/recipe-runtime-catalog-authority-alpha794-live-closure.json`. Die beobachteten `6892` Tokens und `14.688s` Browserzeit bleiben als separate Alpha795-Latenzbaustelle offen.

### alpha795 candidate - Changed

- **Recipe-Transport zum MetaCatalog wird kompakter.** `stored_recipes` transportiert fuer die Entscheidung weiter exact IDs, Namen, Beschreibungen, Connection-Kinds und Step-IDs/Namen/Typen, aber keine freien Step-Parameterwerte mehr. Preview, Explain und Execute rendern unveraendert aus dem vollen Runtime-Manifest nach exakter ID-Validierung.
- **Keine neue Semantik oder Call-Stufe; intern gebaut und exportiert.** MetaCatalog bleibt alleiniger Natural-Language-Semantikowner fuer `inventory|explain|preview|execute|none`; kein Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenpfad, kein Zusatzcall, kein Repair und kein Final Composer. Matrix `.codex/aria_acceptance/meta-catalog-recipe-transport-efficiency-alpha795.json`; Postmortem `docs/internal/meta-catalog-recipe-inventory-latency-alpha794-postmortem-2026-09-10.md`. Red-first Transporttest rot wegen `uptime` im MetaCatalog-Payload; danach MetaCatalog106, Recipe/UI71, Pipeline211, CODE-Vollsuite2615/5 bekannte aiohttp-Warnungen, Prebuild Release/Updates76, Recipe/MetaCatalog/Pipeline369, Post-Bump445/3 und finales Post-Export-Gate2615/5 gruen. Pyflakes, strict-i18n, externes Compileall, 428 Acceptance-JSONs, Diff-Hygiene und Source-Bytecode0 gruen. Image `sha256:88396c75511a40368307b49cd0a5c8474d7cf2eeba4ca5917f583b836f579f4c`; TAR/Alias SHA256 `2d273af786e152768cf1065399c90fcc481b1e483ea8babbae1a91f03aa61279`, `254125056` Bytes, Modus `0600`, Retention alpha791-alpha795. Isolierte no-network Smokes belegen CLI Alpha795, `/app/aria` Source-Bytecode0, kompakten Recipe-Transport ohne `uptime`, keine sensitiven Env-Keys und passive HTTP `5x200/3x303`. Kein Live-/produktiver Daten-/Connection-/Secret-/Qdrant-/Provider-/Runtimezugriff; Workspace/CLI/Build Alpha795, Public Alpha604.
- **User-Live-Review akzeptiert mit Latenz-Restschuld.** Der Alpha795-Export `[redigierter lokaler Anhang]` listet alle fuenf Recipes mit `operation=inventory`, `manifests=5`, `downstream_model_calls=0`, Recipe-Stage `2ms` und ohne Ausfuehrung. Tokens sanken gegen Alpha794 von `6892` auf `5911` (-14,2 Prozent). Browser `18.803s` und `pre_meta_catalog_ms=12820` bleiben ungelöste Provider-/MetaCatalog-Walltime. Closure `.codex/aria_acceptance/meta-catalog-recipe-transport-efficiency-alpha795-live-closure.json`.

### alpha793 candidate - Fixed

- **Recipe-Discriminator ist jetzt total, sobald gespeicherte Recipes angeboten werden.** Der MetaCatalog-Prompt und das angeforderte Schema verlangen `recipe_operation=inventory|explain|preview|execute|none` bei jedem nichtleeren enabled `stored_recipes`-Katalog. `none` ist der explizite Nicht-Recipe-Ausgang; fehlend oder ungueltig stoppt vor Repair, Plain-Chat-Degradation und Final Composer.
- **Alpha792-Liveauslassung red-first reproduziert.** Der live-geformte Payload `answer/direct_answer/chat` mit angebotenem `ssh_run_command`, aber ohne `recipe_operation`, war vor dem Fix rot, weil ein Repair-Hop startete. Jetzt endet er nach genau einem MetaCatalog-Call fail-closed ohne Absence-Claim, Pending State, Execution oder Composer.
- **Ordinary Chat bleibt erlaubt, Unknown-ID bleibt fail-closed.** `recipe_operation=none` mit validiertem `response_text` laeuft als normaler same-hop Chat weiter; `none` wird nur dann als Recipe-Not-found gerendert, wenn die Routerdiagnose eine abgelehnte Recipe-Auswahl markiert. Inventory, Paraphrase, Explain, Preview und Execute-Confirmation bleiben manifest-/ID-bound; Preview fuehrt nichts aus, Execute erzeugt nur die bestehende Confirmation.
- **Keine Wortlisten-Semantik; intern gebaut und exportiert.** Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik fuer natuerliche Sprache wurde hinzugefuegt. Fokus `14`, Source-Execution-Nachbarschaft `120`, MetaCatalog/TurnDecision `142`, Pipeline/Recipe `226`, Post-Bump-Recipe/Pipeline `332`, Post-Bump- und finales Post-Export-Gate jeweils `2609 passed` mit 5 bekannten aiohttp-Warnungen. Pyflakes, strict i18n, Acceptance-JSON, null Source-Bytecode und Diff-Hygiene gruen. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `ef5996239773e06e9281696fa54bce0bf01dcbcc492dbb1912eda8825c77ec87`, CLI Alpha793, Privacy, Registry `135/583/66/0/0`, 294 Owner, 53 Integrationspunkte, Missing-Discriminator-Fail-closed und explizites `none` fuer Ordinary Chat; passives HTTP `4x200/4x303` ist separat netzlos gruen. Image `sha256:62cc2e1b55f4c69c2ebe447fa39e6f9ef372cfc8e83d2aea58ba00f1ba622796`; TAR/Alias SHA256 `fc19eabe39690bfb5b9e778b810c2f9f463ecbc70cc2eb25f5091d68b9e136d5`, `254125568` Bytes, Modus `0600`, Retention alpha789-alpha793. Kein Live-/produktiver Daten-/Connection-/Secret-/Qdrant-/Provider-/Runtimezugriff; Workspace/CLI/Build Alpha793, Public Alpha604.

### alpha792 candidate - Fixed

- **Recipe-Semantik hat nur noch einen Owner.** Die aktivierten gespeicherten Recipe-Manifeste erreichen den ersten MetaCatalog-Turnentscheid. Dieser waehlt `inventory`, `explain`, `preview`, `execute` oder `none` und bindet fuer Einzeloperationen exakt eine angebotene ID; unbekannte oder deaktivierte IDs werden nicht durch ein aehnliches Recipe ersetzt.
- **Read- und Preview-Turns enden ohne zweiten Modellhop.** Inventory, Explain, Preview und Not-found werden kanonisch aus dem validierten Manifest gerendert. Der generische AnswerComposer und der Alpha791-Recipe-Zweitrouter entfallen. Preview fuehrt nichts aus und erzeugt keinen Pending State; Execute erzeugt ausschliesslich die bestehende Recipe-Confirmation fuer die exakte ID.
- **Promptkosten bleiben auf Recipe-Turns begrenzt.** Recipe-Schema und -Instruktion werden nur transportiert, wenn aktivierte Recipes angeboten werden. Normale MetaCatalog-Turns bleiben unter dem bestehenden Systemprompt-Budget von 3400 Zeichen; Recipe-Turns bleiben mit Manifestvertrag unter 3800 Zeichen.
- **Alte Matching-Schicht sauber entfernt; Gates gruen.** `recipe_runtime/matching.py`, seine Pipeline-Wrapper, die tote Arbitration-Stage und ihre Alt-Tests wurden entfernt; der Authority-Audit verlangt, dass der Pfad geloescht bleibt. Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik fuer natuerliche Sprache. Red-first `8`, Fokus/Registry `13`, Hochrisikonachbarschaft `461`; Post-Bump- und finaler Post-Export-Lauf jeweils `2604 passed` mit 5 bekannten Warnungen. Compileall, Pyflakes, strict i18n, `422` Acceptance-JSONs und Diff-Hygiene gruen. Registry `135/583/66/0/0`, 294 Python-Owner, 53 Integrationspunkte, 3 dauerhafte Aliase.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.792` und `aria:alpha-local`, Image `sha256:0d22948fc10d86684fe7d66d7f80ee8153e7890d69ccf1635f6d2968830625a3`; TAR/Alias SHA256 `d4f2127db16a018c94d270027f4c36b9fb542f3368b1f200642e3e5ff6a19e7d`, `254292992` Bytes, Modus `0600`, Retention alpha788-alpha792. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `9353186b3e94f3d7e294f791ac37b0b11534b857e1befeb589a74d5573b6c95e`, null Source-Bytecode, CLI Alpha792, Privacy, Registry, die erforderlichen Recipe-Ownerpfade, den entfernten Matching-Pfad und passive HTTP-Routen `4x200/4x303`. Kein Provider-, Live-, produktiver Daten-, Connection-, Qdrant- oder Runtime-Zugriff; Public Alpha604 bleibt unveraendert.
- **Erster Recipe-Livetest abgelehnt.** Beim Inventory-Prompt erkannte die Modellbegruendung das angebotene `ssh_run_command`, liess aber die gesamte Recipe-Route und `recipe_operation` aus. Der generische Turn-Validator akzeptierte den Answer-Header; ein Final Composer behauptete danach falsch, es gebe keine Recipes. `10130` Tokens, `$0.043579`, MetaCatalog `14959ms`, Final Composer `3513ms`, Browser `24575ms`. Die Alpha792-Fakes hatten den Recipe-Discriminator stets fertig geliefert und diesen Totalauslassungsfall nicht abgedeckt. Alpha792 bleibt nur strukturell akzeptiert; fachliche Route, Source Authority, Call-Count und Latenz sind rot. Postmortem `docs/internal/recipes-alpha792-live-postmortem-2026-09-10.md`; Alpha793-Matrix `.codex/aria_acceptance/recipe-operation-total-contract-alpha793.json`, noch nicht buildfreigegeben.

### alpha791 candidate - Changed

- **Rezeptauswahl und Erklaerung brauchen nur noch einen semantischen Aufruf.** Ein bounded Modellentscheid waehlt `execute`, `explain` oder `none` ueber die angebotenen enabled Recipe-Manifeste. Explain liefert den source-bound Text direkt; Execute geht unveraendert durch Recipe Runtime, Policy, Inputs und Confirmation. Exakte IDs, Confidence und Ausgabeschema werden fail-closed validiert; unangebotene IDs oder erfundene Erklaerungen werden verworfen.
- **Learned-Recipe-Follow-ups unterstehen dem Learning Worker.** Erfolgreiche Beobachtungen werden als persistente, idempotente und budgetreservierte Jobs eingeplant. Curator- und Embedding-Usage fliessen in den Worker-Verbrauch; Ablehnung, Retry, Status und Audit bleiben sichtbar. Learned Entries bleiben bis zur expliziten Admin-Promotion review-only, bestehende Multi-Target-/Side-Effect-Blocker bleiben erhalten.
- **Keine Wortlisten-Semantik; CODE-Gates vor dem Build gruen.** Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik fuer natuerliche Sprache wurde hinzugefuegt. Red-first collection rot, danach `11` Kernvertraege (`13` inklusive i18n) und Recipe-/Learning-Nachbarschaft `552`. Ein erneuerter gemischter Build-Preflight fand genau einen veralteten Test, der noch den entfernten direkten Memory-Write statt der persistenten Worker-Uebergabe erwartete; der reine Testvertrag wurde korrigiert. Danach Fokus `4`, kombinierter Preflight `664` und Vollsuite `2602 passed` in `214.95s` mit 5 bekannten Warnungen; Pyflakes, externes Compileall, strict i18n, `418` Acceptance-JSONs, null Source-Bytecode, Diff und Registry `135/583/66/0/0` mit 295 Ownern und 53 Integrationspunkten gruen. Der bereits fertige Logo-Busy-Lifecycle-Fix wurde im selben Alpha791-Build gebuendelt.
- **Intern gebaut und exportiert.** Post-Bump-Fokus `44`; Post-Bump- und finales Post-Export-Gate jeweils `2602 passed` mit 5 bekannten Warnungen. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `717/717` Source-/Wheel-Dateien, Tree-SHA256 `fa731d809890d43287844b7d1325f6b0a145e7d98aa87cc634a040abb37083ca`, null Source-Bytecode, CLI Alpha791, Example-only Privacy, Registry, Alpha791-Paketpfade und HTTP `4x200/4x303`. Image `sha256:124ff01e11ba06fb68309b0168be2536fbe4e32b20621c63d09a2d3b834621da`; TAR/Alias SHA256 `bb258fa185152e0eb04ca3bde08a5e7c3cc56f921dd9c20f749216a4c468cebb`, `254118400` Bytes, `0600`, Retention alpha787-alpha791. Workspace/CLI/Build Alpha791, Public Alpha604; User-Livereview steht aus.

### alpha790 candidate - Changed

- **Dokumentinventare bleiben scanbar.** Der modellgestuetzte Dokument-Owner wird bei `inventory` um eine reine Praesentationsanforderung erweitert: kurze Einleitung, jedes distinct angebotene Artefakt in einer eigenen Bullet-Zeile und eine kurze Anschlussfrage. Wortwahl und Gruppierung bleiben beim Modell; der Transport bewahrt Zeilen und kompaktifiziert nur Whitespace innerhalb einer Zeile.
- **Keine neue Semantik und kein Zusatzcall; intern gebaut und exportiert.** Route, exakte angebotene IDs, Source Authority, Confirmation, Runtime-Reihenfolge und Ein-Call-Vertrag bleiben unveraendert. Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik, kein Formatter-Call und keine hart codierten Dokumentnamen. Red-first `2`, Fokus `15`, Hochrisikonachbarschaft `582`, BUILD-Preflight `732`; Post-Bump- und finaler Post-Export-Lauf jeweils `2591 passed` mit 5 bekannten Warnungen. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `928c6d36ee9a3c05534e117fcbdbda9833a2d4afa276b0044a8448177c11a933`, null Source-Bytecode, CLI, Example-only Privacy, Registry, mehrzeilige Darstellung bis zum Renderer und HTTP `4x200/4x303`. Image `sha256:ad1bbba9ead220b1837636ea8ec2f395e54d8b66110205a2670504cb30025d7d`; TAR/Alias SHA256 `3019d94a4ea285be3406f1a7e6750878d5641e0358a39de4690d13b97e93b7bc`, `254104064` Bytes, `0600`, Retention alpha786-alpha790. Workspace/CLI/Build Alpha790, Public Alpha604; User-Livereview steht aus.

### alpha789 candidate - Fixed

- **Dokument-Owner bleibt bei Dokumentanfragen autoritativ.** Der lokale modellgestuetzte Dokumententscheid unterscheidet jetzt `inventory`, exakte `search`, echte `clarify`-Rueckfrage und `none`. Die Grenze zwischen Dokumentartefakten und persoenlichen Fakten wird dem Modell objektbezogen erklaert; eine Speicher- oder Gedaechtnismetapher allein verschiebt eine Dokumentanfrage nicht in Personal Memory.
- **Kein zweiter Semantik-Hop bei echter Dokumentambiguitaet.** Eine modellgewaehlte Dokumentrueckfrage endet nach genau einem Call, bindet keine ID und laedt keine Quelle. Nur ein valides `none` uebergibt einen echten Nicht-Dokument-Turn an Main. Exakte IDs, Confidence, Source Authority und interne Metadaten bleiben strikt mechanisch validiert; `answer_decision_cannot_load_context` wurde nicht gelockert.
- **Der zuvor unsichtbare Erstaufruf ist messbar.** Bei `none`, ungueltigem Ergebnis oder Providerfehler uebernimmt die finale Arbitration Outcome, Kandidatenzahl, Confidence und die komplette Erst-Usage. Damit koennen Token- und Call-Count-Diagnosen keinen seriellen Dokumententscheid mehr unterschlagen.
- **Keine Wortlisten-Semantik; intern gebaut und exportiert.** Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenregel wurde hinzugefuegt. Fokustests `14`, Hochrisikonachbarschaft `395`, BUILD-Preflight `521` und Vollsuite `2591 passed` mit 5 bekannten Warnungen; Compileall, Pyflakes, strict i18n, Acceptance-JSON und Diff-Hygiene gruen. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `548e285c5c58f9abb5475009666581abce692fa668decdaa30233c92325ba827`, null Source-Bytecode, CLI, Privacy, Registry, Dokumentvertraege und passive HTTP-Routen. Image `sha256:10a169d767663f2a044422dd438bc288607ad1bc3feed00d715529f4fea3d807`; TAR/Alias SHA256 `0ac1b424cedc8567558098f94eb57af8bb4ad259cec250786d51b3391ea6dd5a`, `254102528` Bytes, Modus `0600`, Retention alpha785-alpha789. Registry unveraendert `135/583/66/0/0`, 295 Owner, 53 Integrationspunkte und 3 dauerhafte Aliase. Workspace/CLI/letzter Build Alpha789, Public Alpha604; fachlicher User-Livereview steht aus.

### alpha788 candidate - Changed

- **Einfache Actions koennen einen seriellen LLM-Hop sparen.** Der Main-Entscheid darf den strukturierten Input genau seiner bereits ausgewaehlten Action im selben Ergebnis liefern. Exakte konfigurierte IDs, Capability-, Scope-, Payload- und Confirmation-Validierung bleiben autoritativ; fehlt ein brauchbarer Input, laeuft unveraendert der bestehende begrenzte `aria_meta_catalog_action_input`-Fallback. Routing Debug zeigt dafuer `action_input_calls=0|1`.
- **Eine klare, lokalisierte Confirmation statt dreier Versionen.** Der kanonische Renderer zeigt bei strukturiertem Payload genau einen Block mit deklarativem Capability-Label, exaktem Ziel und konkretem Inhalt sowie den Policy-Grund einmal. Alte englische Producer-Previews und Laufzeitsummaries werden dann nicht zusaetzlich wiederholt. Der Alpha787-Snapshot-, One-shot- und Fail-closed-Vertrag bleibt unveraendert.
- **Keine Wortlisten-Semantik und kein neues Risiko-Hop.** Das Main-LLM bleibt alleiniger Owner fuer natuerlichsprachliche Bedeutung und Action-Wahl. Code validiert nur strukturierte Felder und exakte IDs; es gibt keine neue Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik, keinen Retry, dritten LLM-Call, Final Composer oder Runtime-I/O vor Confirmation.
- **Intern gebaut und exportiert.** Red-first Live-Reproduktion, finaler Fokus `5`, Hochrisikonachbarschaft `440`, BUILD-Preflight `560`, Registry-/Package-Gate `101`; Post-Bump- und finaler Post-Export-Lauf jeweils `2588 passed` mit 5 bekannten Warnungen. Der frische netzlose read-only/tmpfs/cap-drop-Smoke pruefte `716/716` Source-/Wheel-Dateien, Tree-SHA256 `b510b6e9cff62a2c1d53f02cffd81fe359fcf7c6e3b1195af498f269cafdb4fd`, null Source-Bytecode, CLI, Privacy, Registry, Ein-Aufruf-/Fallback-Diagnostik, lokalisierte Confirmation, Snapshot-Sicherheit und passive HTTP-Routen. Image `sha256:7a447be2fb1a19d2531cd857736d261e2720b0b0c0d51da6979bb79db2d18479`; TAR/Alias SHA256 `7ae7988d0e456aa845ea657135a6a9d1f5222e9ad4ab00cfa2c5c02ab454fb95`, `255891456` Bytes, Modus `0600`, Retention alpha784-alpha788. Registry unveraendert `135/583/66/0/0`, 295 Owner, 53 Integrationspunkte und 3 dauerhafte Aliase. Workspace/CLI/letzter Build Alpha788, Public Alpha604.
- **User-Livereview akzeptiert und eingefroren.** Der Alpha788-Discord-Turn nutzt `action_input_calls=0`, zeigt genau eine lokalisierte Confirmation mit `discord/fischerman-aria-messages` und `Testnachricht` und fuehrt nach Userbestaetigung einmal aus. Gegen Alpha787: Tokens `6210->4871` (-21,6%), Kosten `$0.025915->$0.019774` (-23,7%), Browser-Walltime `18.145->13.910s` (-23,3%), MetaCatalog `15.339->7.918s` (-48,4%) und Execution `1.704->0.766s`. Andere Action-Capabilities bleiben dadurch nicht live akzeptiert. Evidence `.codex/aria_acceptance/action-planning-efficiency-confirmation-alpha788-live-closure.json`.

### alpha787 candidate - Fixed

- **Bestaetigte Zielmenge ist jetzt die maximale Ausfuehrungsmenge.** `full_kind` materialisiert vor Dry-Run und Confirmation alle zu diesem Zeitpunkt konfigurierten exakten SSH-IDs. Der sichtbare und signierte Payload enthaelt damit den vollstaendigen Snapshot; die Runtime darf spaeter keine neu hinzugekommenen oder zuvor ausgelassenen Ziele mehr ergaenzen.
- **Confirmation zeigt jeden ausfuehrbaren Ziel-Identifier.** Multi-Target-Bestaetigungen nennen neben Capability und konkretem Kommando alle exakten Ziel-Refs. Ein integrierter Fake-Runtime-Test belegt, dass ein sichtbarer Snapshot `srv-a/srv-b` auch bei inzwischen vorhandenem `srv-c` ausschliesslich auf `srv-a/srv-b` ausgefuehrt wird.
- **Ein Pending-Action-Contract statt zweier Wahrheiten.** Chat-Oberflaeche und Pipeline verwenden dieselbe strukturierte Vollstaendigkeitspruefung fuer Payload, Capability, Ziel, Kommando, Nachricht, Suchbegriff und Pfad. Spezifische agentische Rueckfragen bleiben sichtbar; der fehlende Maschinenvertrag wird darunter explizit benannt und der Confirm-Button bleibt gesperrt.
- **Keine Wortlisten-Semantik und kein Zusatzcall.** Die alte UI-Pruefung auf Varianten von `bestaetigen` ist entfernt. Natuerlichsprachliche Bedeutung bleibt beim Main-LLM; Code erzwingt nur Schema, exakte IDs, Scope-Snapshot, Confirmation und fail-closed Runtime. Kein neuer Modell-, Embedding-, Qdrant- oder Runtime-Aufruf.
- **Intern gebaut und exportiert.** Red-first drei reproduzierte Snapshotfehler einschliesslich mutierendem `full_kind`; danach 607 breite Action/Pipeline/Chat/MetaCatalog- und 141 Registry-/Manifest-/Package-Tests. Post-Bump-Vollsuite `2586 passed` mit 5 bekannten Warnungen. Der erste nicht exportierte Imageversuch wurde wegen von `pip` erzeugtem Source-Bytecode verworfen; der bereinigte Neubau bestand den netzlosen read-only/tmpfs/cap-drop-Smoke mit `716/716` Source-/Wheel-Dateien, Tree-SHA256 `366b2850f2c6b6be8dde07dc35b84df17b02b86513d225e74dd93ba0a11d09b6`, null Source-Bytecode, CLI, Privacy, Registry, Confirmation-/Snapshot-Vertraegen und passiven HTTP-Routen. Image `sha256:d9e490d53edde88e21784828f878046fd5fdeb43146fda1716db1fe69d50b74d`; TAR/Alias SHA256 `7e76d6c8d31f429895f5761d819288d0dab7e49313038743aa8bea0314dbe1a0`, `254271488` Bytes, Modus `0600`, Retention alpha783-alpha787. Registry unveraendert `135/583/66/0/0`, 295 Owner und 53 Integrationspunkte. Workspace/CLI/letzter Build Alpha787, Public Alpha604.

### alpha786 candidate - Fixed

- **Exakter Personal-Recall verliert keinen Main-Text durch fremde Scope-Operation.** Ein vollstaendig modellentschiedener `answer/source_bound/matched`-Plan mit vorhandenem Antworttext, exakten angebotenen Claim-IDs, `explicit_refs`, ohne Context, Action oder Confirmation behandelt eine zusaetzliche Scope-Operation als strukturell nicht anwendbar. Die Operation wird vor Same-Hop mechanisch entfernt; kein Antworttext wird im Code erzeugt.
- **Prompt und Diagnose machen den Vertrag sichtbar.** Matched Personal-Recall fordert explizit `no scope_operation`. Routing Debug unterscheidet `accepted`, `response_missing` und `contract_blocked` und meldet die mechanische Scope-Normalisierung ohne Antwortinhalt. Context, Actions, Confirmations, `full_kind`, hoehere Risiken, unbekannte IDs und fehlender Text bleiben ausgeschlossen oder fail-closed.
- **Keine Sprachsimulation und kein neuer Call.** Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik; keine Aenderung an Alpha785-Transportkompaktierung, Web, Dokumenten, Connections, Qdrant oder Persistenz. Der echte Router-zu-Pipeline-Test belegt einen Main-Aufruf und keinen Final-Composer.
- **Build-Preflight gruen.** Red-first reproduziert den Alpha785-Livefehler; Fokus `5`, erneuerter Hochrisikoblock `504`, CODE-Vollsuite `2583 passed` mit 5 bekannten Warnungen. Compileall, Pyflakes, strict i18n, `403` Acceptance-JSONs, Diff-Hygiene und Registry-/Release-/Package-Gate `164` sind gruen. Workspace/CLI sind fuer den kontrollierten Build auf Alpha786 gesetzt; letzter Build bleibt bis zum Export Alpha785 und Public Alpha604.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.786` / `aria:alpha-local`, Image `sha256:9f0a8bbe61cb5a4dda14f5f4cb01a0b21795b06948df03a296d2d474a363e7ae`; TAR/Alias SHA256 `d5eb43e5df210faaed8193a34396c0fb852979a85d354063a2a7c45c8998c85a`, `254100992` Bytes, Modus `0600`, Retention alpha782-alpha786. Der isolierte netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `7a8e384e28f8467e8029fae846d04290a5f6a060c8ae0df965830bee96008374`, null Source-Bytecode, CLI, Privacy, Registry sowie positive und fail-closed Scope-Kohaerenzfaelle. Der finale Post-Export-Gate bestand erneut mit `2583 passed` und 5 bekannten Warnungen. Public Alpha604 blieb unveraendert.
- **Userreview akzeptiert; Personal Memory eingefroren.** Capture speicherte `Smaragd`; der exakte Recall antwortete `Smaragd` mit `source_bound`, exakter Claim-ID, `personal_same_hop=accepted`, `final_llm=skipped` und 28ms Pipeline. Gegen Alpha785 sank der Recall auf `10.229s`, 5054 Tokens und `$0.020360` (-21.78% Zeit, -15.91% Tokens, -15.70% Kosten). Der alte Alpha740-Memory-Befund ist damit geschlossen. Weitere Memory-Aenderungen brauchen einen neuen konkreten Fail und eine eigene E2E-Matrix.

### alpha785 candidate - Changed

- **Kompakterer Main-Entscheid ohne neue Semantikschicht.** Das Main-LLM bleibt alleiniger Owner der natuerlichsprachlichen Entscheidung. Exakte Connection-Refs bleiben angeheftet; das gemeinsame Kandidatenbudget sinkt evidenzbasiert nur von 16 auf 14, weil kleinere Werte einen gueltigen RSS-Kandidaten verloren. Doppelte Surface-Vertragsmetadaten und runtime-interne Connection-`safe_fields` werden nicht mehr an das Modell transportiert; alle registrierten Surface-, Action-, ID-, Authority- und Confirmation-Vertraege bleiben erhalten.
- **Sparse Ausgabe bleibt strikt validiert.** Nicht anwendbare leere Branch-Felder duerfen fehlen, waehrend anwendbare Authority-, Target-, Request- und Confirmation-Felder weiterhin fail-closed geprueft werden. Diagnosezeilen zeigen Connection-Kind-Bytes, Kandidatenbudget/-anzahl und die tatsaechlich ausgegebenen Decision-Keys.
- **Keine Sprachsimulation und kein Zusatzcall.** Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik, kein Classifier, Repair- oder Composer-Aufruf. Die konservative Projektion auf die beiden Alpha784-Livevertraege spart 2113 Bytes beziehungsweise 15.9 und 15.5 Prozent; echte Providerlatenz bleibt Gegenstand des Userreviews.
- **CODE- und Prebuild-Gates gruen.** Red-first `3`, Vertragsuite `140`, Hochrisikonachbarschaft `527`, CODE- und BUILD-Preflight-Vollsuite jeweils `2582 passed` mit 5 bekannten Warnungen. Compileall, Pyflakes, strict i18n, `401` Acceptance-JSONs, Diff-Hygiene sowie Registry-/Release-/Package-Gates sind gruen. Registry unveraendert `135/583/66/0/0`, 295 Owner und 53 Integrationspunkte. Public Alpha604 bleibt unveraendert.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.785` / `aria:alpha-local`, Image `sha256:edc1542831307a684dcde01ea22924dd03648f1e0144281d81525cbbac7070e6`; TAR/Alias SHA256 `d4f6bc98a2cd6a4f696ab8b05e847fc6a6d58bf15d8f122147f0ade58be3cbd2`, `254092288` Bytes, Modus `0600`, Retention alpha781-alpha785. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `9676f650d3a0078aacb1cf5747d339117dc596b7600f27c908f88669d5108d8c`, null Source-Bytecode, CLI, Privacy, Registry, den kompakten Alpha785-Vertrag und passive HTTP-/Auth-Routen. Der finale Post-Export-Gate bestand erneut mit `2582 passed` und 5 bekannten Warnungen. Public Alpha604 blieb unveraendert.

### alpha784 candidate - Changed

- **Exakter Personal-Recall bleibt im Main-Hop.** Ein bereits modellseitig als `matched` und `source_bound` entschiedener Recall mit exakt angebotenen Claim-IDs darf auch mit `target_scope_authority=explicit_refs` den vollstaendigen Main-Antworttext direkt ausgeben. Actions, Context Loads, Scope Operations, ungebundene IDs und `allow_general` bleiben ausgeschlossen; der im Alpha783-Liveexport beobachtete zweite Final-LLM-Aufruf entfaellt.
- **Neue Claims bezahlen keine unverbundene Relationspruefung.** Der Relations-LLM sieht nur aktive Claims derselben strukturierten Proposition oder ein explizit validiertes Supersession-Target. Echte Konflikte und unklare Korrekturen bleiben modellgestuetzt und fail-closed; neue sachlich unabhaengige Claims gehen direkt zum Memory-Write.
- **Kompaktere lokale Datenpfade.** Personal-Claim-Listen filtern `personal_claim_v1` bereits serverseitig in Qdrant. Exakte Connection-Refs bleiben im MetaCatalog angeheftet; Dokument-, sichtbarer Kontext- und allgemeine semantische Treffer teilen danach ein einziges score-basiertes Kandidatenbudget. Registrierte Faehigkeiten, Source Authority, Targets und Confirmation werden nicht gekuerzt.
- **Messbare Capture-Stufen ohne Sprachsimulation.** Diagnosezeilen zeigen Relations-Callcount sowie List-, Relations-, Store- und Gesamtzeit. Es gibt keine neue Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik und keinen codegenerierten Recall-Text.
- **CODE- und Prebuild-Gates gruen.** Red-first `2`, breite Risikonachbarschaft `666`, finaler Scope `129`, CODE-Vollsuite `2579 passed` mit 5 bekannten Warnungen und BUILD-Preflight `766 passed`. Compileall, Pyflakes, strict i18n, `399` Acceptance-JSONs, Diff-Hygiene und Registry-/Release-/Package-/CLI-Gates sind gruen. Registry unveraendert `135/583/66/0/0`, 295 Owner und 53 Integrationspunkte. Public Alpha604 bleibt unveraendert.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.784` / `aria:alpha-local`, Image `sha256:d2de64ece822bab2540e6be8eeddb804df1b68e43a9a68dbff678d946d5a4ac6`; TAR/Alias SHA256 `4a5d5af380ff04a945a00dfcb0a19695e3633d11ebf889976240cb4488c7ffe5`, `254093824` Bytes, Modus `0600`, Retention alpha780-alpha784. Ein erster nicht exportierter Imageversuch mit 281 uebernommenen Workspace-pyc wurde verworfen; der saubere No-Cache-Neubau bestand den netzlosen read-only/tmpfs/cap-drop-Smoke mit `716/716` Source-/Wheel-Dateien, Tree-SHA256 `927b49318295cdbdc10b0f74d32400e341287ceae42a58d23b2616f1fa04a0e2`, null Source-Bytecode, CLI, Privacy, Registry, Same-Hop-Gegenfaellen und passiven HTTP-Routen. Nach einem rein mechanischen Backlog-Parser-Nachlauf bestand der finale Post-Export-Gate `2579 passed` mit 5 bekannten Warnungen. Public Alpha604 blieb unveraendert.

### alpha783 candidate - Fixed

- **Aktuelle Memory-Operation bleibt vor altem Zustand autoritativ.** Der Main-Input stellt den aktuellen User-Prompt nach aelterem Conversation-, Learning- und Personal-Kontext bereit. Die gefuehrte Modellentscheidung muss eine angeforderte Capture-Operation vor angebotenem Zustand waehlen; ein bereits vorhandener Claim darf den Schreibauftrag nicht mehr durch eine Recall-Antwort ersetzen.
- **Recall-Claim und Capture-Action werden sauber getrennt.** Hat das Modell bereits die registrierte `personal_memory_capture`-Action mit `explicit_personal_memory` gewaehlt, entfernt die Contract-Grenze nur zusaetzlich ausgewaehlte, exakt angebotene Recall-Claim-IDs. Unbekannte oder erfundene IDs bleiben fail-closed. Gespeichert, aktualisiert oder unveraendert darf weiterhin nur der Memory-Runtime-Outcome behaupten.
- **Keine Sprachsimulation und kein Zusatzcall.** Keine Keyword-, Regex-, Substring-, Token-, Stem- oder Phrasenlogik; keine Aenderung an Web, Dokumenten, Connections, Qdrant, Confirmation oder Action Runtime. Capture bleibt Main plus fester Action-Input-Aufruf, exakter Recall ein Main-Aufruf ohne Final Composer.
- **Lokale Gates gruen.** Fokus `124`, breite Memory-/Pipeline-Nachbarschaft `314`, Vollsuite `2576 passed` mit 5 bekannten `aiohttp`-Warnungen; Pyflakes, Compileall, strict i18n, `397` Acceptance-JSONs, Diff-Hygiene sowie `115` Registry-/Release-/Package-/CLI-Tests. Registry unveraendert `135/583/66/0/0`, 295 Owner und 53 Integrationspunkte. Ein retryfreier Routing-only Dev-Providercall fuer `0.01736250 USD` waehlt Capture korrekt; Offline-Adjudikation des redundanten bekannten Recall-Claims ist ohne weiteren Call gruen. Gesamtverbrauch im bewilligten Scope `0.08163750/0.10 USD`.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.783` / `aria:alpha-local`, Image `sha256:45b03d9b79338c30c946a9406391ee61702187c5b79fc61e5eefa460ae5b97d3`; TAR/Alias SHA256 `0db2a66d19ba3ef17726ce6a54d447019158624b7ef2dc4910ade73018867ec4`, `254095872` Bytes, Modus `0600`, Retention alpha779-alpha783. Prebuild `553`, Post-Bump- und finaler Post-Export-Gate jeweils `2576 passed` mit 5 bekannten Warnungen. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `c245df793aba091a9012cbc3f4057eab87f5414af6abc329caed1e73d6330a5a`, null Source-Bytecode, CLI, Privacy, Registry, Capture-/Claim-Gegenfaelle und passive HTTP-Routen. Public Alpha604 blieb unveraendert; produktive Persistenz, Antwortqualitaet und Live-Walltime brauchen den Userreview.

### alpha782 candidate - Fixed

- **Explizites Speichern erreicht wieder den registrierten Memory-Vertrag.** Wenn der Main-Entscheid bereits einen vollstaendig kohaerenten Action-Header mit `explicit_personal_memory` liefert, aber den redundanten Aktionsnamen auslaesst, kompiliert die Contract-Grenze genau die eine passende registrierte Aktion. Surface-Kind, Risiko und Confirmation muessen exakt uebereinstimmen; gemischte Context-/Response-Zustaende, Orphan-Inputs und mehrdeutige Vertraege bleiben fail-closed.
- **Belegter persoenlicher Recall spart den zweiten LLM-Aufruf.** Ein validierter `matched`-/`source_bound`-Plan mit exakten Claim-IDs, fertigem Antworttext und ohne Context, Surface, Action oder Confirmation darf `local_retrieval` als bereits erfuellte Quellenmarkierung behandeln. Dokument-, Web- und Connection-Retrieval laufen weiterhin durch ihre bestehenden Source-/Composer-Pfade.
- **Keine Wortlisten-Semantik und kein Blindpatch.** Beide Alpha781-Livefehler wurden vor der Aenderung rot reproduziert. Die Umsetzung liest ausschliesslich strukturierte Modellfelder, registrierte Aktionsmetadaten und exakte IDs; Usertext wird nicht mit Keywords, Regex, Substrings, Tokens, Stems oder Phrasen klassifiziert.
- **Lokale Gates gruen.** Fokus `5`, Vertrags-/MetaCatalog-/Pipeline-Nachbarschaft `28 + 93 + 196`, Memory-/Semantik-/Context-Nachbarschaft `224`; Post-Bump-Vollsuite und finaler Post-Export-Gate jeweils `2573 passed` mit 5 bekannten `aiohttp`-Warnungen. Pyflakes, Compileall, strict i18n, `396` Acceptance-JSONs, Registry-/Release-/CLI-Gates und Diff-Hygiene sind gruen. Registry unveraendert `135/583/66/0/0`, 295 Owner und 53 Integrationspunkte.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.782` / `aria:alpha-local`, Image `sha256:21e44f02d84f8382a71fc828e3f97c48fa866cb563b5d4e394f6acdf34c65583`; TAR/Alias SHA256 `deac6539902882455edab42fc1d8030cf1aaa76a030ce506c543c9829f686ba3`, `254093824` Bytes, Modus `0600`, Retention alpha778-alpha782. Der erste nicht exportierte Imageversuch wurde wegen 578 uebernommenen Source-Bytecode-Dateien verworfen; nach ausschliesslicher Cachebereinigung bestaetigte der netzlose read-only/tmpfs/cap-drop-Smoke `716/716` Source-/Wheel-Dateien, Tree-SHA256 `ad99b25f8cab2f59659ee0b207fd4825a4d1260dfe4c605baad277597e16a18d`, null Source-Bytecode, installierten CLI-/Paketpfad, Privacy, Registry, Capture-/Recall-Vertraege und passive HTTP-Routen. Public Alpha604 blieb unveraendert; keine Live-/Produktiv-/Provideraktion erfolgte.

### alpha781 candidate - Fixed

- **Provider-Erreichbarkeit statt weiterer Blindflug.** Der Alpha780-Liveexport verwarf Dokumentfrage, explizites persoenliches Speichern und Recall bereits am Main-Entscheid mit niedriger oder fehlender Confidence. Die gueltigen Alpha780-Same-Hop- und Dokumentvertraege wurden deshalb nie erreicht.
- **Kanonisches Maschinenformat wieder explizit.** Der Main-Prompt nennt wieder alle `turn_decision_v3`-Ausgabefelder und behaelt gleichzeitig den Alpha780-Vertrag fuer source-bound Same-Hop-Recall. Confidence-Anwesenheit und normalisierter Wert werden vor dem Fallback diagnostiziert; Schema-Validierung bleibt sichtbar.
- **Niedrige Confidence erhaelt keine erfundene Autoritaet.** Statt synthetischem `allow_general` mit Confidence 1.0 und einem bezahlten Final-LLM-Aufruf folgt nach genau einem Main-Entscheid eine direkte lokalisierte Klaerung. Keine Quelle wird geladen, keine Aktion oder Persistenz ausgefuehrt und weder Speichererfolg noch No-Hit behauptet.
- **Keine Wortlisten-Semantik.** Die wiederhergestellte Liste besteht ausschliesslich aus Maschinenoutput-Feldnamen. Bedeutung und Route bleiben beim Main-LLM; Code validiert danach Schema, exakte IDs, Confidence und Authority.
- **Lokale und echte Dev-Provider-Gates gruen.** Red-first drei Confidence-Fehler plus ein durch Sonnet entdeckter Recall-Vertragsfehler; exakte Capture-/Dokument-Guardrails sechs Tests, betroffene Nachbarschaft `513 passed`, Vollsuite `2568 passed` mit 5 bekannten `aiohttp`-Warnungen. Compileall, Pyflakes, strict i18n, `392` Acceptance-JSONs, Registry `135/583/66/0/0` und Diff-Hygiene sind gruen. Retryfreie Header-only-Sonnet-Proben belegen gueltigen Capture, exakte Mill-Dokumentwahl und nach Promptklaerung source-bound Same-Hop-Recall ohne Kontextnachladung. Fuenf Modellantworten kosteten zusammen `0.064275 USD` vom bewilligten `0.10 USD`; keine Quelle, Qdrant, Aktion, Persistenz oder Final-LLM wurde ausgefuehrt. Das gespeicherte Dev-Profil blieb unveraendert. Alpha781 ist `build_allowed:true`.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.781` / `aria:alpha-local`, Image `sha256:c04dd2c64b30e50d722525d76b4278990274787d7a0bfb6b6e0338682d06d510`; TAR/Alias SHA256 `3e1a8dca1910574dddf0df34c327ca31a14ba325e10c54e22db7fd8a5fa742f1`, `254091776` Bytes, Modus `0600`, Retention alpha777-alpha781. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `549cb337a302fb6a26d95dd129779057c3094eb0b4be19ee6c5f7a479bf3a2f9`, null Source-Bytecode, installierten CLI-/Paketpfad, Privacy, Registry sowie die Prompt- und Confidence-Guardrail-Vertraege. Public Alpha604 blieb unveraendert; keine Live-/Produktiv-/Provideraktion erfolgte.

### alpha780 candidate - Changed

- **Persoenlicher Recall antwortet im selben Main-Hop.** Ein gueltiger `personal_context_resolution=matched`-Entscheid muss die fertige Antwort liefern. `source_bound` Same-hop-Text wird nur mit exakt validierten angebotenen Claim-IDs freigegeben; Pipeline ueberspringt danach den seriellen Final-LLM-Aufruf.
- **Dokumentantworten werden als Antwort statt als Retrieval-Protokoll formuliert.** Der bestehende `docs_search`-Composer fuehrt mit der direkten Antwort, synthetisiert zusammengehoerende Evidence, nennt Unsicherheit bei Luecken und blendet interne IDs, Collections und Chunk-Zaehler aus, sofern der User sie nicht verlangt.
- **Keine neue Sprachsimulation oder Call-Stufe.** Main- und Dokument-LLM bleiben die semantischen Besitzer; Schema, exakte IDs und Source Authority werden danach mechanisch validiert. Kein Pre-Router, keine Wortlisten-/Regex-/Substring-/Token-/Stem-/Phrasenlogik, keine Aenderung an Qdrant-Ranking, Confirmation, Web oder Connections. Red-first `2`, Fokus `506`, Vollsuite `2563 passed` mit 5 bekannten aiohttp-Warnungen; Compileall, Pyflakes, strict i18n, `390` Acceptance-JSONs, Registry `135/583/66/0/0` und Diff-Hygiene sind gruen.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.780` / `aria:alpha-local`, Image `sha256:743e562276e7e944a3c19b7497cccd4dc510b8a3b2d3ba02b11d7fbbfcae301c`; TAR/Alias SHA256 `1cb7c556ac11794d71adb560c3f64a8d97a6fbedf6a2b43c00146600c55e0ac9`, `254091264` Bytes, Modus `0600`, Retention alpha776-alpha780. Der erste, nicht exportierte Imageversuch wurde wegen 579 aus dem Workspace uebernommenen Source-Bytecode-Dateien verworfen und sauber neu gebaut. Vorbuild/final je `2563 passed` mit 5 bekannten Warnungen, Post-Bump-Nachbarschaft `529`; der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, Tree-SHA256 `00b4822e3736572fca4a3db842597ad0ef38a97fd570dff9fbbae283ddfcb759`, null Source-Bytecode, installierten CLI-/Paketpfad, Privacy, Registry, Same-Hop-Claim-Authority, Dokument-Composervertrag und passive HTTP-Routen. Public Alpha604 unveraendert.

### alpha779 candidate - Fixed

- **Kohaerenter Full-Kind-Entscheid wird nicht mehr verworfen.** Wenn der einzige Main-Entscheid bereits `context`, die alleinige Surface `connections`, `full_kind`, `hosts|profiles` und vollstaendig bewertete exakte Connection-Kinds liefert, kompiliert die Contract-Grenze einen ausgelassenen redundanten `connections:inventory`-Request. Gemischte Surfaces, Actions, Clarify sowie unvollstaendige, doppelte, unbekannte oder widerspruechliche Assessments bleiben fail-closed.
- **Weniger Completion-Prosa bei gleicher Authority.** Die exhaustive Kind-Matrix braucht nur noch `{kind,include}`; die semantische Begruendung steht einmal im allgemeinen Decision-Reason. Exakte ID-Abdeckung und Gleichheit von `include=true` mit `selected_connection_kinds` bleiben unveraendert bindend.
- **Der kanonische Connection-Katalog ist wieder alleiniger Besitzer.** Angebotene Kinds sind die Schnittmenge aus nicht leerer Konfiguration und `ordered_connection_kinds()`. Ein internes Legacy-SearXNG-Feld bleibt fuer seinen Kompatibilitaetsbesitzer bestehen, erscheint aber nicht mehr als User-Connection im Main-Prompt.
- **Kompakte source-bound Maschinenansicht.** Statt verschachtelter Wiederholungen zeigt die Hostansicht eine Mengenuebersicht und genau eine Zeile je exaktem Host. Alle Kind-/Ref-Mitgliedschaften bleiben sichtbar, abweichende Titel erscheinen einmal, identische Ref-/Titelwerte werden nicht wiederholt und Profile ohne Host bleiben als gezaehlte Endpunkte erhalten.
- **Kein Pre-Prompt, keine Wortlistenlogik und kein Zusatzcall.** Das Main-LLM bleibt alleiniger semantischer Besitzer der `hosts|profiles`-Wahl; der Presenter formatiert danach nur strukturierte Evidence-Felder. Red-first insgesamt fuenf gezielte Fehler, danach Praesentationsnachbarschaft `214` und Vollsuite `2561 passed` mit 5 bekannten aiohttp-Warnungen. Compileall, Pyflakes, strict i18n, `389` Acceptance-JSONs, Registry `135/583/66/0/0` und Diff-Hygiene sind gruen.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.779` / `aria:alpha-local`, Image `sha256:59ee7181949a61283762ba6dbe38021891f42963a7cf3a8dd9fc224610bf7e8c`; TAR/Alias SHA256 `2b9185c9149d58e5143fdd1efca2ed48a79e546dbcc168fdd086f3ad42275c6d`, `254093824` Bytes, Modus `0600`, Retention alpha775-alpha779. Vorbuild und finales Post-Export-Gate bestanden jeweils `2561` Tests mit 5 bekannten Warnungen; Post-Bump-Nachbarschaft `436`. Der netzlose read-only/tmpfs/cap-drop-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, installierten CLI-/`aria.main`-Pfad, Privacy, Registry, Contract-Kompilierung, kanonische Kindfilterung, exakte 14/24-Kompaktdarstellung, hostlose Endpunkte, HTML-Escaping und passive HTTP-Routen. Public Alpha604 unveraendert.

### alpha778 candidate - Changed

- **Kleinerer Main-LLM-Transport ohne neue Semantik.** Nach erfolgreichem MetaCatalog-Retrieval werden keine sechs beliebigen konfigurierten Connection-Profile mehr zusaetzlich zu den semantisch gerankten Treffern transportiert. Exakte konfigurierte Refs und der config-backed Ausfallfallback bleiben erhalten.
- **Personal Claims verlustfrei tabellarisch.** Das kompakte Routerprofil uebertraegt dieselben Claim-IDs, Werte und Authority-Felder als `fields`/`rows`; nur wiederholte JSON-Schluessel und bereits im Systemvertrag gebundene statische Authority-Prosa entfallen. Im 24-Claim-Fixture sinkt der Block von 6.350 auf 3.668 Bytes (-42,2 Prozent), beim 14-Host-Shape entfallen zusaetzlich 2.143 Bytes ungerankte Dubletten.
- **Keine Wortlistenlogik und kein weiterer Call.** Qdrant und das Main-LLM bleiben die semantischen Besitzer. Code projiziert und validiert nur strukturierte IDs, Zeilen und Authority. Vollsuite `2556 passed` mit 5 bekannten aiohttp-Warnungen; Compileall, Pyflakes, strict i18n, `385` Acceptance-JSONs, Registry `135/583/66/0/0` und Diff-Hygiene sind gruen. Reale Providerlatenz bleibt bis zum Userreview offen.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.778` / `aria:alpha-local`, Image `sha256:c7d44eb17bc36dff9b684ef84144652df94eae522c074f4dafa9b656b7bdfc90`; TAR/Alias SHA256 `c480fc3a473ef08fb7d07bfce5ea01fd78d94c151c804aefd8d25be2e9ee8ecc`, `254086144` Bytes, Modus `0600`, Retention alpha774-alpha778. Prebuild und finales Post-Export-Gate bestanden jeweils `2556` Tests mit 5 bekannten Warnungen; Post-Bump-Releasegate `283`. Der netzlose read-only/tmpfs-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, installierten `aria.main`-Import, Privacy, Registry, Vollinventarvertrag, kompakte Claims, gerankten Katalog, exakte Refs und Ausfallfallback. Public Alpha604 unveraendert.

### alpha777 candidate - Fixed

- **Vollstaendigkeit gilt jetzt auch ueber Connection-Arten hinweg.** Bei einem mehrartigen `full_kind`-Inventar bewertet das Main-LLM jeden tatsaechlich konfigurierten Connection-Kind genau einmal. Code validiert anschliessend nur die angebotenen IDs, verlangt die exakte Uebereinstimmung von `include=true` und ausgewaehlten Kinds und stoppt bei fehlenden, doppelten, unbekannten oder widerspruechlichen Assessments source-bound.
- **Reale Konfiguration fuehrt den Agenten.** Der begrenzte Main-Input enthaelt pro konfiguriertem Kind Label, Anzahl, vorhandene sichere Feldnamen und registrierte Capability-IDs. Diese Daten helfen der semantischen Auswahl, duerfen aber keine Profile, Hosts oder Fakten erzeugen; sichtbare Zeilen stammen weiterhin ausschliesslich aus der kanonischen Konfiguration.
- **Maschinenansicht statt Profilduplikate.** Der Agent waehlt explizit `hosts` oder `profiles`. Die Hostansicht gruppiert nur exakt gleiche, nicht leere Hostwerte und behaelt darunter jede zugehoerige Kind-/Ref-Identitaet; Profile ohne Host bleiben einzeln sichtbar.
- **Keine neue Wortlistenlogik und kein zusaetzlicher Call.** Bedeutung und Scope bleiben beim einzigen Main-LLM-Aufruf. Schema-, ID- und Authority-Validierung, kanonische Expansion und Darstellung sind mechanisch; ungueltige Assessments verwenden weder Repair noch Composer. Red-first `3/4`, danach Fokus `4`, Hochrisiko-Nachbarschaft `581` und Vollsuite `2553 passed` mit 24 bekannten aiohttp-Warnungen. Pyflakes, strict i18n, `383` Acceptance-JSONs, Registry `135/583/66/0/0` und Diff-Hygiene sind gruen.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.777` / `aria:alpha-local`, Image `sha256:82d0da009eee6e1e6f6ebafc5e49d15370cd008814f0f5fd75fe76928f54fb4f`; TAR/Alias SHA256 `b3a4ef73166a0bd5c1116090e377d582f1cf1345004703233c97abd440f02799`, `254083072` Bytes, Modus `0600`, Retention alpha773-alpha777. Vorbuild/final je `684 passed`, Post-Bump-Vollsuite `2553 passed` mit 24 bekannten aiohttp-Warnungen. Der netzlose read-only/tmpfs-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, installierten `aria.main`-Import, Privacy, Registry, exhaustive Kind-Validierung, Hostgruppierung und passive HTTP-Routen. Public Alpha604 unveraendert; Providerbefolgung und reale Latenz bleiben bis zum Userreview offen.

### alpha776 candidate - Fixed

- **Source-bound bleibt source-bound.** Ein ungueltiger Connection-, Dokument- oder Web-Quellenauftrag kann nicht mehr zu allgemeinem Chat mit null Quellen degradieren. Fehlende oder unbekannte Connection-Kind-Autoritaet endet vor Repair und Composer mit einer ehrlichen quellgebundenen Klaerung.
- **Connection-Kindwahl bleibt beim Agenten.** Das Main-LLM waehlt exakte IDs aus den tatsaechlich konfigurierten Connection-Kinds. Code validiert nur diese IDs, normalisiert die redundante `full_kind`-Operation und expandiert danach kanonische Konfigurationszeilen; keine Keyword-, Regex-, Substring-, Token- oder Stem-Semantik wurde hinzugefuegt.
- **Alpha775-Livehalluzination eingefroren.** Der Originalprompt, die erfundenen Ziele `fischerman_home_server`/`fischerman_backup_nas` und IPs, Route, Source Authority, Scope, Confirmation, Reihenfolge, Call-Count und Latenzklasse stehen in `.codex/aria_acceptance/connection-source-authority-alpha776.json`. Gueltige wie ungueltige Vollinventare brauchen genau einen Main-Aufruf und weder Repair noch Composer.
- **Lokale CODE-Gates gruen.** Red-first `4`, Fokus `8`, Hochrisiko-Nachbarschaft `329`, Vollsuite `2548 passed` mit 24 bekannten aiohttp-Warnungen. Compileall, Pyflakes, strict i18n, `379` Acceptance-JSONs, Registry `135/583/66/0/0` und Diff-Hygiene sind gruen. Workspace/CLI/letzter Build bleiben alpha775, Public alpha604; Providerbefolgung und echte Latenz sind bis zum Userreview offen.
- **Erster Build vor Export abgewiesen.** Der isolierte Package-Smoke fand `aria/contracts/notes_commands.json` im Source-Layer, aber nicht im installierten Wheel; ohne diesen aktiven Vertrag scheitert `aria.main`. Kein TAR wurde erzeugt, `aria:alpha-local` und CLI/Workspace wurden auf Alpha775 zurueckgestellt, Public alpha604 blieb unveraendert. Package-Data und Wheel-Identitaet brauchen einen separaten CODE-Nachlauf.
- **Wheel-Vertrag lokal korrigiert.** `contracts/*.json` ist jetzt explizites Package-Data und der Asset-Coverage-Test umfasst `aria/contracts`. Ein echtes offline gebautes Wheel enthaelt den kanonischen Notes-Vertrag byteidentisch; eine frische Installation importiert `aria.main` ohne Workspace-Prioritaet. Notes-Semantik bleibt beim LLM, der bestehende Regexpfad parst nur kanonischen Maschinenoutput. Vollsuite `2548 passed`; der erfolgreiche Build/Export ist direkt darunter dokumentiert.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.776` / `aria:alpha-local`, Image `sha256:460af74c7fc04f1a375b172cca0f844dabf7279eba4ec95402ebfdefde0c6ca1`; TAR/Alias SHA256 `ac5e36751292f716563ba8a421a5fbc72b7d47d9581826d1ac60f706c0c98380`, `254066688` Bytes, Modus `0600`, Retention alpha772-alpha776. Vorbuild und finales Exportgate jeweils `334 passed`, Release/CLI `32`, Vollsuite `2548 passed` mit 24 bekannten aiohttp-Warnungen. Der netzlose read-only/tmpfs-Smoke bestaetigt `716/716` Source-/Wheel-Dateien, installierten `aria.main`-Import, Notes-Vertrag, Privacy, null Source-Bytecode, Registry und passive HTTP-Routen. Keine produktiven Zugriffe; Public alpha604 unveraendert.

### alpha775 candidate - Fixed

- **Vollstaendige Connection-Inventare statt Top-K-Samples.** Ein vom Main-LLM gewaehlter `full_kind`-Vertrag braucht eine validierte, exakt angebotene Connection-Art und expandiert danach vollstaendig aus der kanonischen Konfiguration. Kandidaten bleiben nur Auswahlhilfe und duerfen keine Vollstaendigkeit behaupten; mehrdeutige Auswahl faellt geschlossen zurueck.
- **Weniger Main-LLM-Transport und kein zweiter Inventar-Composer.** Der Routing-Katalog behaelt exakte IDs, Arten, Refs, Beschreibungen und Authority-Felder, uebertraegt aber keine doppelten Retrieval-Aliase und Tags. Ein vollstaendiges konfigurationsgebundenes Inventar wird nach genau einem semantischen Main-Aufruf source-bound praesentiert; der zweite serielle Antwort-Composer entfaellt.
- **Zwei Hochrisikovertraege sind eingefroren.** Route, Prompt/Source Authority, Target Scope, Confirmation, Runtime-Reihenfolge, Call-Count und Latenzklasse stehen in `.codex/aria_acceptance/connection-inventory-completeness-alpha775.json` und `.codex/aria_acceptance/main-semantic-efficiency-alpha775.json`. CODE-Fokus `359`, Architektur `151`, Vollsuite `2542 passed` mit 24 bekannten aiohttp-Warnungen; Compileall, Pyflakes, strict i18n, `377` Acceptance-JSONs und Diff-Hygiene gruen. Public alpha604 bleibt unveraendert.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.775` / `aria:alpha-local`, Image `sha256:277e0699b12927f397546973aaac5980973d68a7a48cf5d712e132f239a228e4`; TAR/Alias SHA256 `68465face14b7fd04a5852dc4d56ca98ae894ded36fc66f98c1b146be9a6f8e5`, `254062592` Bytes, Modus `0600`, Retention alpha771-alpha775. Vorbuild-Vollsuite `2542 passed`, isolierter netzloser read-only/tmpfs-Smoke `716/716`, finales Exportgate `545 passed`; keine produktiven Daten, Qdrant-, Connection- oder Provideraufrufe. Public alpha604 blieb unveraendert.

### alpha774 candidate - Changed

- **Natuerliche Sprache bleibt beim Agenten.** Web, Memory, Actions, Notes und Recipes verwenden fuer Bedeutung, Route und Zielwahl gefuehrte, begrenzte LLM-Entscheidungen statt produkt- oder formulierungsbezogener Wortlisten, Regex-Router und Keyword-Fallbacks. Deterministische Logik bleibt auf Protokolle, exakte IDs, Schemas, Rechte, Confirmation, Security, URLs/Citations, Budgets und Maschinenoutput begrenzt.
- **Vier Hochrisikovertraege sind eingefroren.** Route, Prompt/Source Authority, Target Scope, Confirmation, Runtime-Reihenfolge, Call-Count und Latenzklasse stehen in den vier `.codex/aria_acceptance/agentic-semantics-*-alpha774.json`-Matrizen. Ungueltige, nicht angebotene oder niedrig-konfidente Modellentscheidungen fallen geschlossen zurueck; sie erzeugen keine zweite semantische Wahrheit.
- **Lokale CODE- und Vorbuild-Gates sind gruen.** Vollsuite `2539 passed` mit 24 bekannten aiohttp-Warnungen; fokussierte CODE-Nachbarschaft `394 passed`; BUILD-Release-/Registry-/i18n-Gate `159 passed`. Compileall, Pyflakes, strict i18n, `375` Acceptance-JSONs und Diff-Hygiene sind gruen. Registry `135/583/66/0/0`, 295 Python-Owner, 53 Integrationspunkte und drei dauerhafte Aliase. Public alpha604 bleibt unveraendert.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.774` / `aria:alpha-local`, Image `sha256:a8d45758f7401d3f5e7d8edbd5324c8677a9300df5d33f07a9c8d42932fd7874`; TAR/Alias SHA256 `b21356cb5d6f5270d0aa65c05e261c443340ae3fcac8bc41c721af8f6f9bc1b4`, `254063104` Bytes, Modus `0600`, Retention alpha770-alpha774. Der netzlose read-only/tmpfs-Smoke bestaetigt 716/716 Source-/Paketdateien, Privacy, null Source-Bytecode, Registry und 101 dauerhaft entfernte produktive Semantikmarker; finales Exportgate `874 passed`. Keine produktiven Daten, Qdrant-, Connection- oder Provideraufrufe; Public alpha604 blieb unveraendert.

### alpha773 candidate - Changed

- **Local Context Fast Lane.** Explizites persoenliches Speichern braucht einen kompakten Extraktionsaufruf, exakter persoenlicher Recall keinen Chat-Modell-Aufruf, Dokumentinventar keinen Chat-Modell-Aufruf und exakte Dokument-QA einen kompakten Composer-Aufruf. Mehrdeutige, ungueltige oder niedrig-konfidente Faelle fallen geschlossen auf den bestehenden MetaCatalog-Router zurueck.
- **Vertraege bleiben eingefroren.** Route, Prompt, Source Authority, Target Scope, Confirmation, Runtime-Reihenfolge, Call-Count und Latenzklasse sind fuer alle vier Hochrisikopfade in `.codex/aria_acceptance/local-context-fast-lane-alpha773.json` festgehalten. Native Web Alpha770 und Public alpha604 bleiben unveraendert.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.773` / `aria:alpha-local`, Image `sha256:6f276e1dde8f8100614bbb61919792c5528e9c8b52fc4801275a0379d1d79e26`; TAR/Alias SHA256 `04fce2117fc8a4315bcab872fc4dc277d3e38514137f9f2f2dcfad4cc40c14a8`, `254176256` Bytes, Modus `0600`, Retention alpha769-alpha773. CODE-Nachbarschaft `443`, Architektur `137` und Vollsuite `2555 passed` mit fuenf bekannten aiohttp-Warnungen sind gruen. Der isolierte Image-Smoke bestaetigt CLI, 5/5 Source-/Paket-Hashes, Privacy, null Source-Bytecode, Registry und die Call-Counts `1/0/0/1`; keine produktiven Daten, Qdrant- oder Provideraufrufe. Public alpha604 blieb unveraendert.

### alpha772 candidate - Changed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.772` / `aria:alpha-local`, Image `sha256:2ada962d662b6cb7fae875cfb347dc2692ec007d2e1d712fb857357fbe9bb026`; TAR/Alias SHA256 `d23221046f9d6c7dd7882858764ff39b77687686414cb2960bfed4abe4467e19`, `254148608` Bytes, Modus `0600`, Retention alpha768-alpha772. Public alpha604 blieb unveraendert.

- **Persoenliches Speichern ist exklusiv.** Ein validierter `personal_memory_capture`-Turn verwirft jetzt einen geerbten Legacy-`memory_recall`-Hinweis. Die bestehende Claim-Persistenz und Relationserkennung laufen weiter, aber Dokumente, Sessions und breite Memory-Collections werden nicht mehr parallel zur Capture-Aktion durchsucht.
- **Unabhaengiger Dokumentkontext bleibt persoenlich isoliert.** Bei `personal_context_resolution=independent_context` gelangen unselektierte globale Preference-/Boundary-/Identity-Claims weder in den finalen Composer-Prompt noch in die Presentation-/Influence-Erfassung. `matched`-Claims und die normale globale Baseline ausserhalb dieses Vertrags bleiben unveraendert.
- **Kleinere MetaCatalog-Kandidaten.** Bereits semantisch vorselektierte Dokument- und lokale Kontextzeilen wiederholen keine Retrieval-Aliase, Tags oder Gruppenmetadaten mehr. Dokument-ID, Name, Zielcollection, Catalog-/Surface-/Kind-/Ref-Identitaet und Score bleiben fuer Routervalidierung und Runtime-Bindung erhalten; eine repraesentative Dokumentzeile sinkt von 487 auf 299 Bytes.
- **Lokale Gates gruen, Livelatenz offen.** Rote Regressionen `3/3`, Fokus `6`, kompletter Pipeline-Beweis `1`, Nachbarschaft `579` und Vollsuite `2546 passed` mit fuenf bekannten aiohttp-Warnungen. Build-Vorblock `732 passed`, Post-Bump `731/732` plus erwarteter Release-Metadatenabgleich und danach `31 passed`; isolierte CLI-/Hash-/Privacy-/Bytecode-/Registry-/Memory-/HTTP-Smokes sind gruen. Keine produktiven Daten, Qdrant- oder Provideraufrufe; Workspace/CLI und letzter Build sind alpha772, Public alpha604.

### alpha771 candidate - Fixed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.771` / `aria:alpha-local`, Image `sha256:beb15467663a2fd0eb6091cd897f6b5f5bffd891f68bcb8d2d0a15383fce4ba5`; TAR/Alias SHA256 `3f2b58876b65f6b760c3d53b144e8da6bf951c3150bec944934f8027dd452230`, `254147584` Bytes, Modus `0600`, Retention alpha767-alpha771. Public alpha604 blieb unveraendert.

- **Direkter persoenlicher Recall verliert keinen exakten Projekt-Claim mehr.** Meldet der alleinige Turn-Router einen vorhandenen persoenlichen Kontext als `matched`, vergisst aber dessen ID, bindet ARIA bei normalen Antworten den laengsten exakt genannten strukturierten Claim-Subject aus der bereits geladenen User-Capsule. Der historische `Projekt Nebel`-Pfad degradiert dadurch nicht mehr zu claimlosem Standardchat.
- **Keine neue semantische Nebenroute.** Die Bindung validiert nur die bereits getroffene LLM-Entscheidung gegen angebotene IDs. Teilnamen, mehrere gleich lange Entitaeten, der generische Subject `user`, unbekannte IDs und alle Aktionen einschliesslich Vergessen bleiben ausgeschlossen beziehungsweise fail-closed.
- **Weniger Calls im Fehlerpfad.** Der exakte Recall braucht einen Router-Aufruf statt Router plus Decision-Header-Repair. Es kommen keine LLM-, Embedding-, Qdrant-, Search-, Fetch- oder Retry-Aufrufe hinzu; Capture, Persistenz, Confirmation, Runtime-Reihenfolge und Web Alpha770 bleiben unveraendert.
- **Build-Gates gruen, User-Review offen.** CODE-Vollsuite `2541 passed`; finales Post-Export-Gate `540 passed` mit drei bekannten aiohttp-Warnungen. Das isolierte Image bestand Version, 3/3 Hashes, Privacy, Registry, Bytecode-, Memory-Vertrags- und passive HTTP-Smokes ohne Netzwerk oder persistente Daten. Produktive Memory-/Qdrant-/Userdaten und Live-ARIA wurden nicht beruehrt.

### alpha770 candidate - Changed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.770` / `aria:alpha-local`, Image `sha256:64be7710bd99e0bb57bce0f6840f4cbe49fc397ea702407264eccb4ca803495c`; TAR/Alias SHA256 `e52a5ddeaf947fa81152ec5533da344df72411bd2287922b0014af6485e22271`, `254148608` Bytes, Modus `0600`, Retention alpha766-alpha770. Public alpha604 blieb unveraendert.
- **Providerseitige Web-Tokens werden aufgeschluesselt.** Der Chat-Export zeigt Prompt-, Completion-, Reasoning-, Cache- und Gesamttokens sowie die begrenzte ARIA-Requestgroesse, ohne Promptinhalt, Secrets oder Raw-Payloads offenzulegen.
- **Niedriges Reasoning fuer GPT-5-Webmodelle.** OpenAI-Responses-Anfragen an GPT-5-Familienmodelle setzen `reasoning=low`. Andere Modellfamilien und Transporte behalten ihre bisherigen Providerdefaults.
- **Webvertrag bleibt eingefroren.** Exakter Userprompt, Source Authority, Suchbudget, ein Webrequest, null Main-Aufrufe und null Retries bleiben unveraendert. Eine echte Tokenreduktion wird erst nach einem einzelnen Alpha770-Livevergleich akzeptiert.
- **Lokale CODE-Gates gruen.** Vollsuite `2536 passed` mit 5 bekannten aiohttp-Warnungen; breites Risikogate `345 passed`, Struktur-/i18n-/Release-Gate `103 passed`. Registry `135/582/66/0` mit 296 Python-Ownern und 53 Integrationspunkten. Public alpha604 bleibt unveraendert.

### alpha769 candidate - Fixed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.769` / `aria:alpha-local`, Image `sha256:476361f2fe66791409a22a1d7d690499dfc2eecb9d93da11fae94a0b964591b3`; TAR/Alias SHA256 `05c68089134fa75fe7af871c2a36cf240d3f0e2218106f89798c1cbb98c1e4f3`, `254149632` Bytes, Modus `0600`, Retention alpha765-alpha769. Public alpha604 blieb unveraendert.
- **Expliziter Chat-Modus erreicht den Dispatcher.** Die Auswahl `Auto | Main | Web` wird bei jeder normalen Chat-Anfrage mitgesendet. Die bestehende deterministische Route, Source Authority sowie der Web-Vertrag mit genau einem Providerrequest, null Main-Aufrufen und null Retries bleiben unveraendert.
- **LLM-Konfiguration nach Aufgabe getrennt.** Modellzuweisung, aktuell verwendete Modelle und Profilverwaltung sind klar getrennt. Main-LLM und Web-LLM referenzieren beide normale gespeicherte LLM-Profile; Profilbearbeitung aktiviert kein Profil mehr stillschweigend als Main-Rolle.
- **Tests und Kosten klar benannt.** Der normale Verbindungstest prueft ein Profil ohne Websuche. Der kostenpflichtige Web-Test bleibt separat, verlangt eine explizite Bestaetigung und fuehrt genau einen Web-Providerrequest ohne Main-Aufruf oder Retry aus.
- **Build-Akzeptanz gruen.** Vollsuite `2533 passed` mit 5 bekannten aiohttp-Warnungen; finales Post-Export-Gate `326 passed`. Compile, strict i18n, 361 Acceptance-JSONs, Registry `135/582/66/0/0` mit 296 Python-Ownern und 53 Integrationspunkten sowie Diff-Hygiene sind gruen. Public alpha604 bleibt unveraendert.

### alpha768 candidate - Changed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.768` / `aria:alpha-local`, Image `sha256:12c1b3df804e933fd4036201d90d097a88e0f57e1b96fe9b0e2c2816acfee159`; TAR/Alias SHA256 `afabe9fe2f41d626a0d0a439117b0315c462b4e80aa32a365daf604887d50703`, `254137856` Bytes, Modus `0600`, Retention alpha764-alpha768. Public alpha604 blieb unveraendert.
- **Sauberes isoliertes Artefakt.** Der erste nicht exportierte Versuch wurde wegen 579 Workspace-pyc/140 pycache verworfen. Der Neubau enthaelt null Source-Bytecode-Caches und bestand netzlos/read-only/cap-drop/no-new-privileges 12/12 Hashes, Privacy, CLI, Registry, Health und passive HTTP-Smokes.
- **Main-LLM und Web-LLM sind getrennte Rollen.** Beide referenzieren weiterhin den bestehenden LLM-Profilkatalog ohne Secret-Duplikation. Ein Web-Profil wird erst nach einem explizit bestaetigten Capability-Test aktiviert; passive Konfigurations-, Betriebs- und Statistikseiten verursachen keine Provideraufrufe.
- **Native Websuche in exakt einem Providerrequest.** Deterministisches `Auto | Main | Web`-Dispatch schickt oeffentliche aktuelle Fakten direkt an das Web-LLM. Der Pfad verwendet genau einen Web-LLM-Providerrequest, null Main-LLM-Aufrufe und null automatische Retries; ein bis drei providerinterne Suchen werden gemessen und bepreist, mehr als drei stoppen fail-closed.
- **Providerzitate und Source Authority bleiben bindend.** Nur providerseitige oeffentliche Zitationen koennen passieren. Private/lokale URLs, fehlende offizielle Pfade, Text-URLs ohne Providerannotation und unzureichende Authority werden deterministisch abgewiesen. Lokale Instanzen, SSH, Dateien, Memory, Feeds und Aktionen bleiben ausserhalb des automatischen Webpfads.
- **Qdrant nur als begrenzte Public-Evidence-Schicht.** Vor dem Webrequest ist hoechstens ein zeitbegrenzter Read erlaubt. Nach einer gueltigen Antwort darf ein asynchrones Update nur oeffentliche Providerprovenienz speichern; Userprompt und generierte Antwort werden nicht als Public Truth persistiert.
- **Nutzung und Kosten transparent.** Usage-Log und Stats unterscheiden Main/Web-Rollen, native Suchaktionen und deren Kosten. Ein Chat-Scope persistiert den Webrequest genau einmal. Unbekannte Suchpreise bleiben als unbepreist sichtbar.
- **SearXNG bleibt vorerst erhalten.** Der bestehende Pfad ist ausschliesslich Transition-Fallback und wird erst nach gruenem Alpha768-Capability-Test, Produkt-E2E und User-Live-Review entfernt.
- **Lokale Build-Akzeptanz gruen.** Vollsuite `2527 passed` mit 5 bekannten aiohttp-Warnungen; finales Fokusgate `331 passed`. Compile, strict i18n, 358 Acceptance-JSONs, 12/12 eingefrorene Produkthashes und Diff-Hygiene sind gruen. Registry `135/582/66/0/0`, 296 Python-Owner und 53 Integrationspunkte. Public alpha604 bleibt unveraendert.

### alpha767 candidate - Fixed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.767` / `aria:alpha-local`, Image `sha256:e63ec0f883923a0e093f563c0e9fc156d5512a2e70a6e15792e137934511b381`; TAR/Alias SHA256 `9f101407559d5d22416856b6f2f0fd6050dcb8f0aa08772c295e4f479bf9a2cd`, `254056448` Bytes, Modus `0600`, Retention alpha763-alpha767. Public alpha604 blieb unveraendert.
- **Artefakt- und Exportgates gruen.** Ein erster nicht exportierter Imageversuch wurde wegen 569 generierten Workspace-Bytecode-Dateien verworfen; nach ausschliesslicher Cache-Bereinigung enthielt der Neubau `0` Source-pyc/pycache. Isolierter network-none/read-only/cap-drop-Smoke pruefte 13/13 eingefrorene Hashes, Privacy, CLI und Registry. Post-Bump-Vollsuite `2499 passed` mit 5 bekannten Warnungen, finales Exportgate `320 passed` mit 3 bekannten Warnungen.
- **Live-Upgrade-Luecke nach alpha766 geschlossen.** Der erste User-Review scheiterte nach 21,6s/7.591 Tokens mit drei leeren Suchen: ARIA forderte `google cse`, der laufende SearXNG-Container meldete aber Brave-, DuckDuckGo-, Startpage-, Wikipedia- und weitere Enginefehler. Ursache waren eine veraltete breite Engine-Konfiguration im exportierten Portainer-Stack und ein lokaler Updatepfad, der nur ARIA neu erzeugte.
- **Verwaltete Provider-Konfiguration konvergiert.** Alle unterstuetzten Stackvarianten liefern `keep_only: google cse`. Normale lokale, Managed- und Host-Updates erzeugen den zustandslosen SearXNG-Dienst vor ARIA mit `--no-deps` neu; Qdrant, Valkey, Updater und alle Volumes bleiben unangetastet.
- **Kostenlose Readiness statt gruener Leerprobe.** Betrieb prueft zuerst den aktiven Enginebestand und danach mit genau einer begrenzten SearXNG-Suche nutzbare, Google-CSE-zugeordnete Treffer sowie Providerfehler. Breite/stale Engines, leere Treffer, fremde Enginefehler und ungueltige Payloads sind nicht bereit. Isolierte Dev-Evidence: exakt eine Config-Abfrage plus eine Suche, 20 offizielle n8n-Dokumenttreffer, nur Google CSE, 0 Enginefehler, 0 LLM/0 USD.
- **Lokale Gates vor dem Build gruen.** Red-first `7 failed`; danach Fokus `203`, breite Nachbarsuite `300` und Vollsuite `2499 passed` mit 5 bekannten aiohttp-Warnungen. Bash/YAML/JSON, Pyflakes, Compile, strict i18n und Diff-Hygiene sind gruen; Registry `134/579/65/0/0`, 288 Owner und 53 Integrationspunkte. Router-/Planner-/Composer-Prompts, Source Authority und Chat-Call-Counts bleiben unveraendert; echte Antwortqualitaet und Chatlatenz sind weiter offen.

### alpha766 candidate - Fixed

- **Provider policy follows measured evidence.** The canonical `public-current-facts` transport requests `google cse`, and fresh-stack SearXNG defaults keep only that engine. Planner metadata remains semantically neutral; saved user-profile engines no longer influence transport or source authority.
- **Preferred targets fit the existing search budget.** Current primary-fact acquisition schedules up to three preferred sites before a broad fallback, without adding searches, fetches, retries or model calls.
- **Concrete software versions fail closed.** Current software-version turns require a dotted version identifier in retained readable non-legacy evidence. Without it, the pipeline returns an honest source failure before the final model instead of spending tokens on a major-only guess. Product-name questions such as the newest iPhone are not subjected to this version rule.
- **Websuche ist ein verwalteter Systemdienst.** SearXNG ist nicht mehr als Benutzer-Connection, Profilformular, Statuszeile oder Mutation sichtbar. WebSearch bleibt auch ohne gespeicherte Profile verfuegbar; alte Profil-Refs stoppen vor IO und vorhandene Konfigurationsdaten werden nur abwaertskompatibel geparst, weder gelesen noch umgeschrieben.
- **Transport bleibt austauschbar.** Die Pipeline verwendet einen neutralen `WebSearchProvider`-Vertrag. SearXNG ist die aktuelle interne Implementierung und wird unter Betrieb ueberwacht und neu gestartet, ohne Routing, Source Authority oder andere Connections an den Provider zu binden.
- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.766` / `aria:alpha-local`, Image `sha256:6461638209f7e27c73c53ec7d03e80b5fa693aa14038ef939e729bc39b73c74d`; TAR/Alias SHA256 `0ac3add0557ec8d7dfa132d5b99eb5f7d7ce8e12882b4e468fdae81dba247097`, `254040576` Bytes, Modus `0600`, Retention alpha762-alpha766. Ein erster nicht exportierter Imageversuch enthielt 580 generierte Workspace-Bytecode-Dateien; nach ausschliesslicher Cache-Bereinigung wurde sauber neu gebaut.
- **Build-Gates gruen.** Red-first `8 failed`; danach breite Nachbarsuite `767`, CODE-Vollsuite und Post-Bump-Vollsuite je `2493 passed` mit 5 bekannten aiohttp-Warnungen, Vorbuild `247` und finales Exportgate `252 passed`. Pyflakes, compileall, strict i18n, 347 Acceptance-JSONs, Registry `134/579/65/0/0` mit 288 Python-Ownern, Privacy, 27/27 Workspace- und 25/25 Wheel-Hashes sowie Diff-Hygiene sind gruen. Public alpha604 bleibt unveraendert; echte Antwortqualitaet und der 31s-Latenzbefund sind weiterhin offen.

### alpha765 candidate - Fixed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.765` / `aria:alpha-local`, Image `sha256:92ed4d7a5c5e7a914b00126a6a97ad5d0874ad98101528c732fb387a5282391b`; TAR/Alias SHA256 `e4f1b74eb3b113404d74b70867651f9742b4afd435e1f2fd37d0a63b06312e81`, `254064128` Bytes, Modus `0600`, Retention alpha761-alpha765. Der erste, nicht exportierte Imageversuch enthielt generierten Workspace-Bytecode; nach ausschliesslicher Cache-Bereinigung wurde das Image neu gebaut und bestand den Bytecode-/Privacy-Smoke.
- **Neutraler WebSearch-Systemstandard.** Automatische Websuche nutzt ausschliesslich `public-current-facts` ohne User-Tags, Aliase, Kategorien, Engines, Sprache oder Zeitraum als Planner-Wahrheit. Der Transport funktioniert auch ohne gespeicherte SearXNG-Profile ueber den Stack-/Environment-Endpunkt.
- **Userprofile nur noch bewusst.** Bestehende SearXNG-Profile bleiben unveraendert gespeichert und sind weiterhin ueber eine exakte explizite `connection_ref` nutzbar; der Planner waehlt sie nicht automatisch. Unbekannte oder versteckte Planner-Refs stoppen fail-closed.
- **Quellenbudget schuetzt primaere Evidence.** Das Fast-Answer-Viererbudget priorisiert exakte bevorzugte Hosts/Pfade vor geerbten Community-/Forum-Subdomains und expliziten Archiv-/Legacy-Signalen. Explizit verlangte Communityquellen bleiben erlaubt.
- **Interner Review-Kandidat.** Post-Bump-Vollsuite `2505 passed` mit 5 bekannten aiohttp-Warnungen; finales Exportgate `289 + 5 passed`. Exakte Source-/Paket-Hashes, Registry `134/580/65/0/0`, CLI, Privacy und kanonische Profilwahl wurden netzlos/read-only/tmpfs geprueft. Public alpha604 unveraendert; echte Antwortqualitaet und der offene `22.555s`-Latenzbefund sind nicht lokal akzeptiert.

### alpha764 candidate - Fixed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.764` / `aria:alpha-local`, Image `sha256:9be865ccfc5189ed101c06a18a7bcf24e30ecaed25409b5b532cb99d1a1ca785`; TAR/Alias SHA256 `184ee11bd597529478fd68e4ed434d0a8beb574af5f83a7f1f6f9541ebd74fe6`, Modus0600. Post-Bump `2416 passed`, final `259 passed`; isolierte Paket-/Privacy-/CLI-/Registry-/ChatFlow-Smokes gruen. User-Installation und fachlicher Review dieses neuen Builds stehen aus; alpha763-Live-Fail bleibt dokumentiert.
- **Ausgewaehlte Quellen ausfuehrbar halten.** Fehlende ausgewaehlte Read-Surfaces werden auch bei teilweise vorhandenen Context-Requests ergaenzt. Ungueltige Quellenauftraege stoppen vor Zugriff; terminale Clarify-/Empty-Vertraege werden nicht durch Web-Recovery ersetzt.
- **Public und lokal unterscheiden.** Der Router-Systemprompt trennt oeffentliche Produkt-/Releasefragen von lokalen Installationen. Ein passender Connection-Katalogtreffer allein begruendet keine lokale Quellenautoritaet.
- **Interner Review-Kandidat.** 34 neue Regressionen mit echtem Router, darunter sechs ChatFlow-Faelle. CODE-Vollsuite `2416 passed`, sechs bekannte Warnungen; Registry `134/580/65/0/0`. Reale Modellbefolgung, Providerqualitaet und Latenz bleiben offen. Public alpha604 unveraendert; keine Produktverhaltensaenderung im BUILD-Modus.

### alpha763 candidate - Changed

- **Intern gebaut und exportiert.** `fischermanch/aria:0.1.0-alpha.763` / `aria:alpha-local`, Image `sha256:e4d9f50167aba774ecc00135d03dd04b03d61dca057aba4a9da4e484e3077e76`; TAR/Alias SHA256 `5308bf5122868b7174710593ed0d5fad17189c490b399eddee47f3b693455d31`, Modus0600. Post-Bump-Vollsuite `2382 passed`, final `197 passed`; isolierte netzlose Paket-/Privacy-/CLI-/Registry-/Web-Vertrags-/HTTP-Pruefungen gruen. User-Installation und fachlicher Review stehen aus.
- **WebSearch-Anfragefolge begrenzt.** Fast Answer fragt seine maximal drei Suchvarianten seriell innerhalb eines gemeinsamen Zeitbudgets ab. Deadline und verbleibender Socket-Timeout begrenzen das Warten; ausgelassene Anfragen und Teilabdeckung bleiben sichtbar. Keine neuen Provider-/Modellaufrufe oder produktiven Profilanpassungen.
- **Release-Provenienz im Antwortvertrag.** Version, Kanal, Branch und Release-Datum muessen zur selben Quellenangabe gehoeren. Begrenzte Archivausschnitte beweisen keinen neuesten datierten Release; historische Angaben bleiben fuer passende Fragen erhalten.
- **Gezielter interner Kontrollbuild.** Lokaler CODE-Gate `2382 passed`, sechs bekannte Warnungen; Registry `134/580/65/0/0`. Provider-Sperren und echte Modellbefolgung sind nicht als behoben akzeptiert. Serielle Suche kann laenger dauern; MetaCatalog-/Quellenplan-Latenz bleibt offen. Public alpha604 unveraendert, keine Installation oder Live-Abnahme durch Codex.

### alpha762 candidate - Changed

- **Interner Diagnosebuild erstellt und exportiert.** `fischermanch/aria:0.1.0-alpha.762` und `aria:alpha-local`, Image `sha256:01cb8766ad0d7f0a20627bcbfb80faca7d11821b015202c43c559b11b2239494`; TAR/Alias SHA256 `a180d192274277a02dc09ac00e3cbd72dbdbc8e2e2dea622927a925dcd33b2be`, Modus 0600. Post-Bump-Vollsuite `2367 passed`; isolierte netzlose CLI-/Paket-/Privacy-/Registry-/Diagnose-/Profilwarnungs-/HTTP-Smokes gruen. Keine Installation oder fachliche Live-Abnahme, Public alpha604 unveraendert.
- **WebSearch-Diagnose im Chat-Export.** Pro bestehender Suchanfrage werden bereinigte tatsaechliche Requestparameter, liefernde Engines vor Sitefilterung und feste Engine-/Transportfehlerklassen angezeigt. Unbekannte Engine-Namen erscheinen als `other`; neue Felder enthalten keine rohen Fehlertexte, Endpunkt-URLs oder Header. Keine zusaetzlichen Such-/Modellaufrufe, keine Aenderung an Queryplanung, Source Authority oder Antwortverhalten.
- **SearXNG-Profilpruefung und Cache-Status.** Die Profilpruefung beruecksichtigt Engines, Kategorien und Zeitfilter sowie SafeSearch 0. Leere oder degradierte Ergebnisse warnen statt gruen zu erscheinen. DE/EN-Statusseiten kennzeichnen gespeicherte Pruefergebnisse; Warnbanner und Problemzaehler sind konsistent. Bestehende Chat-Skill-Umwandlung SafeSearch 0 auf 1 bleibt unveraendert und wird in der Diagnose sichtbar.
- **Diagnose statt Qualitaetsversprechen.** Der alpha761-User-WebSearch-Review ist fehlgeschlagen. Dieser intern freigegebene Diagnosebuild dient einem einzelnen manuellen n8n-Test samt vollstaendigem Chat-Export; bessere Antworten und geringere Latenz sind nicht nachgewiesen. Lokaler CODE-Gate: `2367 passed`, sechs bekannte Warnungen; Registry `134/580/65/0/0`. Public alpha604 bleibt unveraendert.

### alpha761 candidate - Fixed

- **Interner Kontrollbuild erstellt.** `fischermanch/aria:0.1.0-alpha.761` und `aria:alpha-local`, Image `sha256:f06effa4ab14c5541ae54a00fb4ee71a09795c075dbb0e5299dcb209a5e469f0`; isolierte netzlose CLI-/Paket-/Registry-/WebSearch-Vertrags-/HTTP-Smokes gruen. TAR/Alias SHA256 `63351e60682d343165ae4a24ce08f57c821963826658502afb57f4025e06117b`, Modus 0600. Post-Bump-Vollsuite `2341 passed`; Public alpha604 unveraendert. Installation und fachlicher Livevergleich stehen aus.
- **Sitefilter vor Ergebnislimit.** Site-/Pfadgebundene SearXNG-Antworten werden vor dem Ergebnislimit gegen den kanonischen Zielvertrag gefiltert; maximal 50 Rohzeilen werden geprueft.
- **Suchvarianten und Pflichtziele.** Fast Answer behaelt unterschiedliche geplante Suchabsichten innerhalb von maximal drei parallelen Requests. Nicht abdeckbare Pflichtziele stoppen vor IO; Authority-, Profil-, Fetch-, Composer- und Routervertraege bleiben unveraendert.
- **Verluststufen und Vorlaufzeiten sichtbar.** Begrenzte numerische Retrieval-Receipts zeigen Provider-, Filter- und Authority-Verluste auch im Fehlerfall. Vier Vorlaufintervalle messen vorhandene Vorbereitungsschritte ohne neue Calls oder geaenderte Reihenfolge. Der Web-Fehlerpfad behaelt die vorhandene UsageMeter-Messung statt sie zu nullen.
- **Lokale Evidence, keine Live-Abnahme.** 19 neue Regressionen, Nachbarsuite `502 passed` und Vollsuite `2341 passed`; finale Runner ohne DNS-/externen Netzwerkzugriff. Reale Quellenqualitaet und Latenz bleiben offen. Interner Kontrollbuild separat freigegeben, Public alpha604 unveraendert.

### alpha760 candidate - Fixed

- **Interner WebSearch-Kontrollbuild erstellt.** Separat freigegeben als `fischermanch/aria:0.1.0-alpha.760` und `aria:alpha-local`, Image `sha256:4ac4397f5f7d85803f93ddeaf85126da93003df48364589963c537f9e7b01217`. Netzlose read-only/tmpfs-Smokes prueften Release, Registry/Lifecycle, Privacy, exakte WebSearch-Dateien, Queryvertraege und passive HTTP-Routen. TAR/Alias SHA256 `fd4805eff17382324bd18ce7953a388631a5288749c400e5b30f86e7a9bdb8f9`, Modus 0600; Vorbuild/Post-Bump je `429 passed`. Public alpha604 bleibt unveraendert; User-Installation und fachlicher Livevergleich stehen aus.
- **WebSearch bindet relative Aktualitaet nicht mehr blind an ein Kalenderjahr.** Vierstellige Jahre aus dem LLM-Quellenplan werden entfernt, wenn sie im Originalprompt nicht vorkommen; explizit verlangte Jahre sowie Required-/Preferred-Domainziele bleiben erhalten.
- **Fast-Answer-Query-Verstaerkung begrenzt.** Ein valider Quellenplan erzeugt maximal drei SearXNG-Requests. Required-/Preferred-Sites werden vor dem breiten Fallback geplant, explizite `site:`-Queries bleiben erhalten und Research behaelt sein bestehendes Budget.
- **Current-Fact-Fail-Closed bleibt wirksam.** Das Authority-Gate bewertet den Originalprompt und verliert Aktualitaetssignale wie `neuste` nicht durch materialisierte Provider-Queries. Source Authority, Profilwahl, Page Fetch, Routing, Confirmation und Runtime-Reihenfolge wurden nicht aufgeweicht.
- **Lokale Gates gruen.** Fokus `69`, WebSearch-/Routing-/Authority-Nachbarschaft `407`, Vollsuite Exit `0` bei `2322` gesammelten Tests; Pyflakes `0`, Compileall, strict i18n, `322` Acceptance-JSONs und Diff-Hygiene gruen. Workspace bleibt alpha759, Public alpha604; kein Build/Export oder Live-Zugriff. Home-Assistant-/interne-Build-Route und Pre-Pipeline-Latenz bleiben offen.

### alpha759 candidate - Changed

- **Testwahrheit bereinigt.** Zehn reine Import-Selbsttestdateien und vier redundante Selbsttestbloecke sind entfernt. Ein neuer statischer Gate verhindert, dass derselbe kanonische Owner erneut unter mehreren Aliasnamen importiert und mit sich selbst verglichen wird. Der Testbaum ist mit Pyflakes bei 0 Befunden.
- **Registry-Prosa synchronisiert.** 15 Modulmanifeste behaupten keine laengst entfernten privaten Core-Identitaetsaliase mehr. Registry `134/580/65/0/0`, Lifecycle `112/22/0/0` und die drei dauerhaften Skill-Aliase bleiben unveraendert.
- **Produktcode statisch bereinigt.** Alle 109 Produkt-Pyflakes-Befunde sind consumer- und vertragsbasiert klassifiziert und konvergiert; Produkt und Tests stehen gemeinsam bei 0. Echte Reexport-Consumer lesen Recipe-, Dry-run-, Behavior- und Boundary-Symbole direkt bei ihren kanonischen Ownern, dynamische Injection-/Testhooks bleiben explizit erhalten.
- **Latente Fehler reproduziert und behoben.** Eigene E2E-Matrizen belegen das lokale Stored-Recipe-JSON-Laden sowie die Erfolgszweige von `/memories/edit`, Memory-Select/Create und Auto-Save. Vorher scheiterten exakt fuenf neue Regressionen an fehlendem `json`, `lang` oder `settings`; danach sind sie gruen. Route, Prompt, Source Authority, Target Scope, Confirmation, Runtime-Reihenfolge und bestehende Mutations-Call-Counts bleiben eingefroren.
- **Versteckte Kompatibilitaet beendet.** Der produktconsumerlose interne `recipe_store.manifest_view`-Wrapper ist entfernt; aktuelle Projection-Tests verwenden den kanonischen `recipe_learning`-Owner und ein Import-Failure-Vertrag verhindert seine Rueckkehr. Nur die drei zentralen dauerhaften `aria.skills.*`-Vertraege bleiben.
- **Paketartefakte fail-closed klassifiziert.** Sechs Null-Consumer-Templates sind entfernt. Ein neues Gate verlangt fuer jedes verbleibende Template, statische Asset, Prompt, Lexikon und Sample einen Manifestowner, direkten Consumer oder expliziten Directory-Loader; `web_search` besitzt `prompts/web/` nun deklarativ.
- **Lokale Gates gruen.** H3-Fokus `74`, H4-Fokus `305`, Struktur/Ownership `263`, Vollsuite `2320 passed` mit 6 bekannten Warnungen. Registry `134/580/65/0/0`, Lifecycle `112/22/0/0`, 287 Owner und 53 Integrationspunkte unveraendert; Compileall, strict i18n, 321 Acceptance-JSONs, Pyflakes und Diff-Hygiene gruen. H1-H4 sind abgeschlossen; kein Build/Export, Public alpha604.
- **Interner Hygiene-Review-Build.** `0.1.0-alpha759` wurde als `fischermanch/aria:0.1.0-alpha.759` und `aria:alpha-local` sauber gebaut, isoliert netzlos/read-only/tmpfs gesmoked und exportiert. Image `sha256:f34b5305b02a11d2b288e3443f3b76a7f7dcedc7ae4eacbd1431f4820c933cb5`; TAR/Alias SHA256 `4ca06939a1c420b312000907aa860dca2712c253fb859008a4f7019be6cdc805`, Modus 0600, Rotation alpha749/750/754/758/759. Vorbuild, Post-Bump und final jeweils `373 passed`; ein erster nicht exportierter Imageversuch mit generiertem Bytecode wurde vor dem sauberen Neuaufbau verworfen. Kein Public-, Live- oder produktiver Zugriff.

### alpha758 candidate - Changed

- **Modularisierung strukturell abgeschlossen.** Die Makrobloecke B-E klassifizieren den Lifecycle aller 134 Module, reduzieren private Legacy-Kompatibilitaet auf drei dauerhafte `aria.skills.*`-Erweiterungsvertraege und schneiden die Pipeline in kanonische Action-, Context-, Process- und WebSearch-Owner. `Pipeline.process()` bleibt der einzige Einstiegspunkt.
- **Alte private Namespace-Baeume entfernt.** Unter `aria/core` und `aria/web` verbleiben keine Python-Dateien; der AST-Audit findet keine produktiven Imports dieser privaten Altpfade. Die drei verbleibenden Skill-Aliase sind bewusst dauerhafte oeffentliche Kompatibilitaetsvertraege und keine Migrationskandidaten.
- **Strukturstand vor Review-Build.** Registry `134/580/65/0/0`; 65 dauerhafte und 0 transitionale Grenzen, Lifecycle `112 bootstrap_static/22 contract_only/0 declarative_runtime/0 unclassified`, 287 Python-Owner, 53 Integrationspunkte und 0 Legacy-Manifestverweise. Vollsuite `2338 passed` mit 6 bekannten Warnungen; Compileall, strikter i18n-Audit, Acceptance-Parsing und Diff-Hygiene gruen.
- **Scope bleibt strukturell.** Die vertagten Live-Befunde aus alpha740/alpha743 bleiben ungeloest und unangetastet. Der Review-Build prueft Installation, Paketstruktur und passive Oberflaechen, nicht Chat-, Routing-, WebSearch-, Runtime-, Persistenz-, Qdrant- oder Latenzverhalten. Public bleibt alpha604.
- **Interner Review-Build.** `0.1.0-alpha758` wurde als `fischermanch/aria:0.1.0-alpha.758` und `aria:alpha-local` gebaut, mit `network=none`, read-only Rootfs, tmpfs und ohne Binds/Volumes isoliert gesmoked und exportiert. Image `sha256:825fd4f43afc8bfe556dc38ee83e78799f2ae69b5460036f35a9ecdd7850e76c`; TAR/Alias SHA256 `54023e9117bdbb1d655868b562bafba0fbca9159fa9fb9f541c6faca2050014`, Modus 0600, Rotation alpha748/749/750/754/758. Vorbuild `432 + 3`, final `435 passed`; kein Public-, Live-, produktiver Daten-, Connection-, Secret-, Qdrant- oder Runtime-Zugriff.

### alpha754 candidate - Changed

- **Makroblock A abgeschlossen.** Das leere und consumerlose `chat_pending_tokens`-Doppelmodul wurde entfernt; alle behaupteten Parser-, HMAC-, Encode-/Decode- und Pending-Token-Helper bleiben unveraendert beim bereits physischen Owner `chat_admin_composition`. Die letzte transitionale Grenze entfaellt ohne neue Dependency oder Importkante.
- **Provisorische Metadatenstatus beendet.** Alle `metadata_only*`, `needs_split`, `needs_subsplit`, `readpoint_prepared` und `implementation_owner_active_needs_split`-Zustaende sind als belegte Domain-/Surface-Namespace-, Surface-/Route-/Integration-/Compatibility-Contracts oder Implementierungs-/Composition-Owner klassifiziert. Ein neuer Truth-Gate verlangt fuer jedes Non-Python-Modul konkrete Consumer-/Submodul-, Route-, Template-, Prompt- oder Integrationsevidence.
- **Strukturstand.** Registry `134/577/65/0/0`; alle 65 External Boundaries dauerhaft, 0 transitional/unklassifiziert, 282 Python-Owner, 53 Integrationspunkte, 285 Aliase zu 281 Zielen und 0 Legacy-Manifestverweise. Fokus `333`, Token-/Confirmation-Nachbarschaft `331`, Lifecycle-/Registry-Regression `622`, Release/Registry `141`, Vollsuite `2617 passed` mit 6 bekannten Warnungen; alpha740/alpha743 bleiben offen.
- **Interner Review-Build.** `0.1.0-alpha754` wurde als `fischermanch/aria:0.1.0-alpha.754` und `aria:alpha-local` gebaut, ohne Netzwerk/Binds/Volumes isoliert gesmoked und nach `/mnt/NAS/aria-images/aria-alpha754-local.tar` exportiert. Image `sha256:70f75a9b9a039516144729d494794e0f77a5c61d0a9687d5697d59f56059fbf0`; TAR/Alias SHA256 `9926fa2c50650a38c4e4d75da4aeba132e06f9272ee5e6fe641bc398464ce978`, Modus 0600, Rotation alpha747-alpha750 plus alpha754. Ein vor Export entdeckter lokaler `__pycache__`-Altbestand wurde als generiertes Buildartefakt entfernt und das Image sauber neu gebaut; das verunreinigte Image wurde nie exportiert. Public bleibt alpha604, kein produktiver Zugriff.

### alpha753 candidate - Changed

- **Domain-Ownergrenzen bis auf einen belegten Stop-Punkt konvergiert.** Elf weitere transitionale `chat`-/`routing`-Records wurden aus Action-Komposition, Connections-Mutations-UI, Context/Learning und Memory entfernt, weil bestehende interne Consumer-, Parent-/Child- und Kompositionskanten die Beziehungen bereits ausdruecken. Keine Python-Implementierung, Dependency oder Importkante wurde geaendert.
- **Ein Marker bewusst erhalten.** `chat_pending_tokens:chat` bleibt als einziger transitionaler Record stehen: das Metadatenmodul hat weder einen Python-Claim noch einen Registry-Consumer. Eine Entfernung ohne vorherige physische Ownership-Klaerung waere keine belegte Konvergenz.
- **Vier Hochrisikoklassen vorab eingefroren.** `.codex/aria_acceptance/domain-owner-final-chat-routing-boundary-convergence-rail-alpha753.json` fixiert Action Confirmation/Pending, Connection Mutations, Context/Learning und Memory samt Route, Prompt, Source Authority, Target Scope, Confirmation, Runtime-Reihenfolge, Call-Count und Latenzklasse. Die alpha740-/alpha743-Livebefunde bleiben ungeloest.
- **Strukturziel nach dem Schnitt.** Registry-Zielwerte: `135/579/66/0/0`, 65 dauerhafte und 1 transitionale Grenze. Build/Export bleibt im CODE-Modus verboten.

### alpha752 candidate - Changed

- **Pipeline-Ownergrenzen konvergiert.** 15 weitere transitionale `chat`-/`routing`-Records wurden an neun Hochrisiko-Ownern entfernt, weil `pipeline_orchestrator` diese Owner bereits explizit per `depends_on` und kanonischem Import konsumiert: Planung/Aufloesung, Kontextprojektion, Dry-run-Payloads, Pending-Vertraege, Trace/Follow-up, SSH-Zielscope und WebSearch. Keine Python-Implementierung, Dependency oder Importkante wurde geaendert.
- **Sieben Hochrisikoklassen vorab eingefroren.** `.codex/aria_acceptance/pipeline-high-risk-owner-boundary-convergence-rail-alpha752.json` fixiert Route, Prompt, Source Authority, Target Scope, Confirmation, Runtime-Reihenfolge, Call-Count und Latenzklasse fuer jede beruehrte Klasse. Die alpha740-/alpha743-Livebefunde bleiben ungeloest und unangetastet.
- **Strukturziel nach dem Schnitt.** Registry-Zielwerte: `135/579/77/0/0`, 65 dauerhafte und 12 transitionale Grenzen; uebrig bleiben sieben `chat`- und fuenf `routing`-Records an mehrdeutigen Umbrella-, Persistence-, Learning-, Mutation-, Token- und Memory-Ownern. Build/Export bleibt im CODE-Modus verboten.

### alpha751 candidate - Changed

- **Redundante Chat-/Routing-/Pipeline-Grenzen konvergiert.** 16 transitionale Pseudo-Grenzen wurden entfernt, weil ihre Owner-Beziehung bereits durch bestehende interne Consumer-Kanten belegt war: elf `pipeline`-Records ueber `pipeline_orchestrator`, drei `chat`-Records ueber `chat_execution_composition` und zwei `routing`-Records ueber `meta_catalog_routing`. Es wurden keine neuen `depends_on`-Kanten, Imports, Routen, Callbacks oder Runtime-Pfade angelegt.
- **High-Risk-Vertraege eingefroren.** Die Acceptance `.codex/aria_acceptance/chat-routing-pipeline-redundant-boundary-convergence-rail-alpha751.json` friert Route, Prompt, Source Authority, Target Scope, Confirmation, Runtime-Reihenfolge, Call-Count und Latenzklasse ein. Die alpha740-/alpha743-Livebefunde bleiben ungeloest und unangetastet.
- **Strukturziel nach dem Schnitt.** Registry-Zielwerte: `135/579/92/0/0`, 65 dauerhafte und 27 transitionale Grenzen, 282 Python-Owner, 53 Integrationspunkte und 285 Legacy-Aliase zu 281 Zielen. Build/Export bleibt im CODE-Modus verboten.

### alpha750 candidate - Changed

- **Legacy-Skill-Implementierungen evakuiert.** `BaseSkill`/`SkillResult`, `MemorySkill` und `WebSearchSkill` mit zusammen `4352` Zeilen liegen jetzt bei `skill_contracts`, `memory_learning_bridge` und `web_search`. Unter `aria/skills` bleibt nur das Kompatibilitaets-Paket-Init; die drei historischen Modulnamen sind exakte lazy Identitaetsaliase.
- **Skill-Grenzen in echte Ownerkanten verwandelt.** 16 produktive Consumer importieren die kanonischen Besitzer. Vier generische `skills`-Migrationsgrenzen und sechs dauerhafte `skills.result_contract`-Grenzen sind durch explizite interne Abhaengigkeiten ersetzt. Registry `135/579/108/0/0`; 65 dauerhafte und 43 transitionale Grenzen, 282 eindeutige Python-Owner sowie 285 Legacy-Aliase zu 281 Zielen.
- **Verhalten eingefroren und lokal belegt.** Baseline `729`, Struktur/Registry/Authority `424`, breite Memory-/WebSearch-/Pipeline-Regression `732` und Vollsuite `2615 passed` mit 6 bekannten `aiohttp`-Warnungen. Compileall, strikter i18n-Audit, 304 Acceptance-JSONs, Release-Identitaet und Diff-Hygiene sind gruen. Keine produktiven Daten, Qdrant-, Netzwerk-, Runtime- oder Build-Aktion; die alpha740-/alpha743-Livebefunde bleiben ungeloest.
- **Build-Trennung eingehalten.** Die CODE-Acceptance ist abgeschlossen und bleibt `build_allowed: false`; Build/Export erfolgten erst mit separater `FREIGABE: BUILD` und eigener Build-Acceptance. `0.1.0-alpha750` wurde als `fischermanch/aria:0.1.0-alpha.750` und `aria:alpha-local` gebaut und isoliert mit `network=none`, tmpfs und ohne Binds/Volumes geprueft. Pre-Build/final jeweils `664 passed`, Post-Bump `361 passed`. Image `sha256:998515edfcbdf7d34e1f7f3bc7e5ff22d6caf569b1355de1ec126ac332179c23`; TAR/Alias SHA256 `89ceedbbaa3c4c61a19ad1011d52f1de408aecc891d60548963feee945de4870`, Modus 0600, Rotation alpha746-alpha750. Public bleibt alpha604; kein produktiver Zugriff.
- **User-Strukturreview akzeptiert.** Stats zeigt alpha750, `135/579/108`, 43 Migrationskandidaten, 8 gruen/2 bekannte gelbe/0 rot, Preflight `4/0/0` und Runtime Health `8/0/0`. Modul-Admin zeigt 65 dauerhafte/43 transitionale Grenzen, 282 Python-Owner, 53 Integrationspunkte, 285 Legacy-Aliase sowie 0 Validierungsfehler/0 Zyklen/0 Legacy-Manifestverweise. Das ist keine fachliche Chat-/Routing-/WebSearch-/Runtime-/Persistenzakzeptanz.

### alpha749 candidate - Changed

- **Boundary-Owner zusammengefuehrt.** 55 veraltete externe Claims wurden gegen bestehende Modulowner geprueft. 51 eindeutige interne `depends_on`-Kanten ersetzen alte Kernel-/Composition-Namen; sechs selbst besessene Pseudogrenzen entfallen. Die Registry steht damit bei `134/563/118/0/0` statt `134/512/179/0/0`.
- **Eine explizite External-Boundary-Wahrheit.** Alle 134 Manifeste speichern nur noch `external_boundaries`-Records mit `id`, `category` und `disposition`; kein Manifest speichert mehr `external_dependencies`. Der alte Stringpfad bleibt ausschliesslich als abgeleitete Read-Model-Kompatibilitaet und wird als Manifestautoritaet fail-closed abgelehnt.
- **Restarbeit messbar gemacht.** Die 118 verbleibenden Grenzen sind vollstaendig klassifiziert: 56 Composition Contracts, 10 Data Boundaries, 21 Kernel/Platform, 20 Library/Service und 11 Runtime Callbacks. Davon sind 71 bewusst dauerhaft und 47 als Migrationskandidaten (`chat`, `pipeline`, `routing`, `skills`) markiert; 0 unklassifiziert.
- **Alias-Schuld und Fortschritt sichtbar.** Modul-Admin und Stats zeigen die neue `134/563/118`-Projektion sowie die 47 Migrationskandidaten. Der Admin zeigt zusaetzlich 71 dauerhafte Grenzen, 282 zentral kontrollierte Legacy-Aliase zu 278 Zielen und 0 Legacy-Core/Web-Verweise in Manifesten. Keine Aliase wurden in diesem Rail entfernt.
- **Lokale Gates gruen.** Registry-/Config-/Stats-Fokus `328 passed`, Release-/Alias-Gate `309 passed`, Vollsuite `2607 passed` mit 6 bekannten `aiohttp`-Warnungen. Compileall, 302 vorbestehende Acceptance-JSONs, strikter i18n-Audit und isolierter HTTP-Smoke fuer `/config/admin/modules` sind gruen. Kein produktiver Zugriff und keine fachliche Chat-/Routing-/Runtime-Akzeptanz.
- **Build-Trennung eingehalten.** Alle drei CODE-Acceptances sind abgeschlossen und behalten `build_allowed: false`; Build/Export erfolgten erst mit separater `FREIGABE: BUILD` und eigener Build-Acceptance. Public Release und produktiver Zugriff blieben gesperrt.
- **Interner Review-Build erstellt.** `0.1.0-alpha749` wurde als `fischermanch/aria:0.1.0-alpha.749` und `aria:alpha-local` gebaut und nach `/mnt/NAS/aria-images/aria-alpha749-local.tar` exportiert. Post-Bump `722 passed` mit 6 bekannten Warnungen, final `425 passed`; isolierter `--network none`-/tmpfs-Smoke pruefte CLI, Registry, 71/47 Boundary-Dispositionen, alle 282 Legacy-Identitaeten, Privacy, Health, Login, Service Worker sowie die geschuetzten Stats-/Modul-Admin-Routen. Image `sha256:f83ec0edd6744f250e7f1c2e8bcd7a93200ca98aff6acc55de963549987965e7`; TAR/Alias SHA256 `accad3ffaa32b010ced742161b2e719dc6635a65b5387d69dc0ba15364d919f7`, Modus 0600, Rotation alpha745-alpha749. Public bleibt alpha604; kein produktiver Zugriff und keine fachliche Chat-/Runtime-Akzeptanz.

### alpha748 candidate - Changed

- **Modul-Lebenszyklus explizit gemacht.** Die passive Registry-Projektion weist fuer alle 134 Module `application_bootstrap` als Aktivierungsowner aus. Deklarative Aktivierung bleibt 0; `build_allowed` und `runtime_access_allowed` sind weiterhin Acceptance-Autoritaet und keine Aktivierungsschalter. Die bestehende Modul-Adminseite zeigt diese Trennung ohne Loader-, Route-, Startup- oder Runtime-Aenderung.
- **Legacy-Wrapper physisch beendet.** 276 reine Weiterleitungsdateien unter `aria/core` und `aria/web` wurden entfernt. Eine exakte, lazy und idempotente Kompatibilitaetsgrenze erhaelt 282 historische Importnamen als Identitaetsaliase zu 278 kanonischen `aria.modules`-Zielen; unbekannte Namen schlagen weiterhin fehl. In beiden Altbaeumen verbleibt nur das Paket-Init.
- **Manifestwahrheit bereinigt.** 245 mehrzeilige und weitere kompakte historische Core-/Web-Dateiansprueche wurden aus den Modulmanifesten entfernt. Produktive Importe und Manifeste benennen nur noch kanonische Ownerpfade; die zentrale Alias-Tabelle ist die einzige Legacy-Kompatibilitaetswahrheit.
- **Dependency-Wahrheit normalisiert.** Manuell gepflegte `used_by`-Listen wurden vollstaendig entfernt; die 512 Rueckkanten werden deterministisch aus `depends_on` abgeleitet. `python` bezeichnet jetzt ausschliesslich 281 existierende, eindeutig besessene Python-Dateien. 53 nicht besitzende Symbol-/Callsite-/Shared-File-Verweise sind separat als `integration_points` sichtbar.
- **Externe Grenzen klassifiziert.** Alle 179 unveraenderten externen Deklarationen werden im passiven Read-Model genau einer Kategorie zugeordnet: 69 Composition Contracts, 10 Data Boundaries, 64 Kernel/Platform, 25 Library/Service und 11 Runtime Callbacks; 0 unklassifiziert. Die Modul-Adminseite zeigt Ownership, Integrationspunkte, externe Klassen und abgeleitete Consumer.
- **Lokale Gates gruen.** Lifecycle/Registry `401 passed`, Alias-/Route-Fokus `292/352 passed`, Architektur-Regression `514 passed`, neuer Registry-/UI-Fokus `326 passed`, Vollsuite `2605 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry bleibt `134/512/179/0/0`; 281 Owner, 53 Integrationspunkte, 0 Ownership-/Syntaxfehler, Compileall, 299 Acceptance-JSONs, strikter i18n-Audit und Diff-Hygiene gruen. Kein produktiver Zugriff und keine fachliche Chat-/Routing-/Runtime-Akzeptanz.
- **Build-Trennung eingehalten.** Alle fuenf CODE-Acceptances sind abgeschlossen und behalten `build_allowed: false`. Build/Export erfolgten erst mit separater `FREIGABE: BUILD` und eigener Build-Acceptance; Public Release und produktiver Zugriff blieben gesperrt.
- **Interner Review-Build erstellt.** `0.1.0-alpha748` wurde als `fischermanch/aria:0.1.0-alpha.748` und `aria:alpha-local` gebaut und nach `/mnt/NAS/aria-images/aria-alpha748-local.tar` exportiert. Post-Bump und final jeweils `640 passed`; isolierter `--network none`-/tmpfs-Smoke pruefte CLI, Registry/Lifecycle, 282 Legacy-Identitaeten, Ownership-/Boundary-Metadaten, Pfadwurzeln, Privacy, Package-Daten, Service Worker, 10 passive GETs und 12 Login-Redirects. TAR/Alias SHA256 `e75f3ac1d2f0358c37ee1415be0759015540c54e2a6b9441bdb5914f5fc16200`, Modus 0600, Rotation alpha744-alpha748. Public bleibt alpha604; kein produktiver Zugriff und keine fachliche Chat-/Runtime-Akzeptanz.

### alpha747 candidate - Changed

- **Drei grosse Chat-/Runtime-Kompositionsrails ohne Zwischenbuild.** 14 Implementierungen/`5461` Zeilen fuer passive Chat-Surface/Katalog, Chat-Admin/Pending/Notes/Websites, Chat-Execution sowie Runtime-Bootstrap/Inbound-Routen liegen kanonisch in acht Fachownerpaketen; alle 14 historischen `aria.web`-Pfade bleiben Identitaetsaliase.
- **Abhaengigkeitsrichtung bereinigt.** `chat_admin_composition -> action_pending_chat_boundary -> chat_execution_composition` ist azyklisch; Pending konsumiert den Pipeline-Pending-Vertrag ohne deklarative Rueckkante. Website-Chat liegt beim bereits von `website_ui` abhaengigen `website_runtime`; `/chat` und `/chat/history/clear` besitzen mit `chat_execution_composition` genau einen Route-Owner.
- **High-Risk-Vertraege eingefroren.** Drei vorab erstellte Acceptances sichern Public-Current-Fact/Source Authority, Target Scope, Pending/Confirmation, Callback-/Adapterreihenfolge, Runtime-Konstruktion sowie Inbound-Token-/Body-/Storage-Vertraege. Der alpha743-Live-Fail bleibt unveraendert und ungeloest.
- **Lokale Gates gruen.** Baseline `101`, Struktur/Registry `122`, unmittelbare Nachbarsuite `223`, Risikomatrix `622` und Vollsuite `2309 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `134/512/179/0/0`; 14 Identitaeten, AST-Produktimportinventur, Repository-/Contract-/I18N-Wurzeln, Compileall, 293 Acceptance-JSONs, Release-Hygiene, strikter i18n-Audit und Diff-Hygiene sind gruen.
- **Interner Review-Build erstellt.** `0.1.0-alpha747` wurde als `fischermanch/aria:0.1.0-alpha.747` und `aria:alpha-local` gebaut und nach `/mnt/NAS/aria-images/aria-alpha747-local.tar` exportiert. Post-Bump und final jeweils `148 passed`; isolierter `--network none`-/tmpfs-Smoke pruefte CLI, 14 Identitaeten, Registry `134/512/179/0/0`, Pfadwurzeln, Privacy, Package-Daten, Service Worker, 8 passive GETs und 12 Login-Redirects. TAR/Alias SHA256 `02d8430efb72edb76090c38df789f11d76af30e8dbea69f24703b44aa91c1357`, Modus 0600, Rotation alpha743-alpha747. Public bleibt alpha604; kein produktiver Zugriff und keine fachliche Chat-/Runtime-Akzeptanz.
- **User-Strukturreview akzeptiert.** Stats zeigt alpha747 mit 8 gruen/2 bekannten gelben/0 rot und Registry `134/512/179`; Modul-Admin zeigt 0 Validierungsfehler und 0 Zyklen. Die vereinbarten Punkte 3-5 funktionieren laut User; keine fachliche Chat-/Runtime-/WebSearch-/Mutationsakzeptanz daraus ableiten.

### alpha746 candidate - Changed

- **Memory/Notes/Release-Komposition physisch geschnitten.** `memories_routes`, `notes_routes` und `system_update_routes` mit zusammen `6035` Zeilen liegen kanonisch in `memory_admin_ui`, `notes` und `release_update`; drei historische `aria.web`-Pfade bleiben Identitaetsaliase.
- **Auth UI mit eigener E2E-Matrix geschnitten.** Middleware, Login-/Logout-Routen, scoped Cookie Helpers und signierte Session Helpers mit `1058` Zeilen liegen kanonisch in `auth_ui`; vier Webpfade bleiben Identitaetsaliase. Signatur, Scope, Ablauf, Cookie-Fallback, CSRF, Rollen, Rate Limit und Bootstrap-Vertraege blieben unveraendert.
- **Lokale Gates gruen.** Insgesamt sieben Implementierungen/`7093` Zeilen und sieben Identitaetsaliase; Baselines `245/503`, Auth-Fokus `111`, gemeinsame Nachbarsuite `530 passed`, Vollsuite `2297 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `131/483/172/0/0`; AST-Importinventur, Pfadwurzeln, Compileall, 289 Acceptance-JSONs, Release- und Diff-Hygiene gruen.
- **Kein produktiver Zugriff.** Memory-/Notes-/Auth-/Update-/Persistenzpfade wurden nur mit Fakes, Monkeypatches, synthetischen Requests und `tmp_path` geprueft. Die CODE-Acceptances bleiben `build_allowed: false`; Build/Export erfolgten erst mit separater Freigabe und Build-Acceptance. Public bleibt alpha604.
- **Interner Review-Build erstellt.** `0.1.0-alpha746` wurde als `fischermanch/aria:0.1.0-alpha.746` und `aria:alpha-local` gebaut, nach `/mnt/NAS/aria-images/aria-alpha746-local.tar` exportiert und mit `--network none`/tmpfs passiv geprueft. Sieben Importidentitaeten, Registry `131/483/172/0/0`, Modul-Readmodel, Pfadwurzeln, Privacy, Package-Daten, Service Worker, 8 passive GETs und 12 Login-Redirects sind gruen; finaler Gate `552 passed`. TAR/Alias SHA256 `75248b64d3b92595a2e980c927f994aa0877490da05fbe144d519626c500b9a9`, Modus 0600, Rotation alpha742-alpha746. Public bleibt alpha604; kein produktiver Zugriff.

### alpha745 candidate - Changed

- **Grosser Config-/Connections-Kompositionsblock.** 18 Implementierungen mit `9136` Zeilen liegen kanonisch bei `config_ui`, `ops_config_backup` und `connections_mutations`; 18 historische `aria.web`-Pfade bleiben identitaetserhaltende Aliase. Produktivcode importiert nur Ownerpfade.
- **Config UI physisch geschnitten.** Route Composer, allgemeine/Profile-/Support-/Surface-Helfer, Access/Persona, Intelligence/Workbench, Routing-Admin und Operations-Details wurden zu ihren bestehenden Ownern verschoben. Repository-, Sample- und I18N-Wurzeln bleiben identisch; keine Route, Methode, Auth-/CSRF-, Redirect-, Probe-, Routing-, Config-, Backup- oder Service-Semantik wurde geaendert.
- **Connection Mutations physisch geschnitten.** Admin-Helfer, Provider-Mutationshandler, Route Registration und Support-/Key-/Sample-Helfer liegen bei `connections_mutations`. Secret-, Save/Delete-, Key-Exchange-, Guardrail-, Factory-Reset-, Probe- und Routing-Refresh-Vertraege wurden nur mit Fakes, Monkeypatches und `tmp_path` geprueft; kein produktiver Zugriff.
- **Lokale Gates gruen.** Baselines `363/381 passed`, kombinierte Nachbarsuite `385 passed`, Vollsuite `2289 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `131/475/172/0/0`; 18 Identitaeten, Legacy-Importinventur, Compileall, 286 Acceptance-JSONs und Diff-Hygiene gruen. Vor dem separaten Build blieben Workspace/CLI auf alpha744; kein produktiver Zugriff.
- **Build bewusst separat.** Beide CODE-Acceptances sind abgeschlossen und bleiben `build_allowed: false`; Build/Export erfolgten erst mit eigener Freigabe und `.codex/aria_acceptance/modularization-alpha745-review-build.json`. Die alpha740-/alpha743-Livebefunde bleiben unveraendert Backlog-only.
- **Interner Review-Build erstellt.** `0.1.0-alpha745` wurde als `fischermanch/aria:0.1.0-alpha.745` und `aria:alpha-local` gebaut, nach `/mnt/NAS/aria-images/aria-alpha745-local.tar` exportiert und mit `--network none`/tmpfs passiv geprueft. 18 Importidentitaeten, Registry `131/475/172/0/0`, Modul-Readmodel, Paketwurzeln, Privacy, Package-Daten, Service Worker, 7 passive GETs und 13 Login-Redirects sind gruen; finaler Gate `448 passed`. TAR/Alias SHA256 `f6db4a5e3801a09c968600f881bd4586237194842f6c4f643e25409c4a02de2e`, Modus 0600, Rotation alpha741-alpha745. Public bleibt alpha604; kein produktiver Zugriff.

### alpha744 candidate - Changed

- **Grosser Outside-Core-Kompositionsrail.** 26 Implementierungen mit zusammen `9810` Zeilen fuer Stats/Activities, Help/Docs, Navigation-Helfer, read-only Connections-Oberflaechen sowie Recipe UI/Store/Learning liegen kanonisch in ihren bestehenden Fachmodulen. Die 26 historischen Web-/Store-Pfade bleiben identitaetserhaltende Aliase; Produktivcode importiert nur Ownerpfade.
- **Recipe-Abhaengigkeitsrichtung korrigiert.** Recipe UI komponiert Store und Learning; Store/Learning kennen keinen UI-Owner mehr. Stored-Manifest-Candidate-Projektion liegt beim Learning-Owner, waehrend Redirect-/Erfolg-URL-Komposition im UI-Owner bleibt. Keine Recipe-, Promotion-, Persistenz-, Auth-/CSRF- oder Runtime-Semantik wurde geaendert.
- **Lokale Gates gruen.** Kombinierte alpha744-Nachbarsuite `416 passed`, Vollsuite `2281 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `131/475/172/0/0`; Importidentitaeten, Paketpfade, AST-Importgrenzen und Diff-Hygiene gruen. Vor dem separaten Build blieben Workspace/CLI auf alpha743; kein produktiver Zugriff.
- **Build bewusst separat.** Drei CODE-Acceptances sind abgeschlossen und bleiben `build_allowed: false`; Build/Export erfolgten erst mit eigener Freigabe und `.codex/aria_acceptance/modularization-alpha744-review-build.json`. Die alpha740-/alpha743-Livebefunde bleiben unveraendert Backlog-only.
- **Interner Review-Build erstellt.** `0.1.0-alpha744` wurde als `fischermanch/aria:0.1.0-alpha.744` und `aria:alpha-local` gebaut, nach `/mnt/NAS/aria-images/aria-alpha744-local.tar` exportiert und mit `--network none`/tmpfs passiv geprueft. 26 Importidentitaeten, Registry `131/475/172/0/0`, Stats-/Modulprojektion, Privacy, Package-Daten, Service Worker, 7 passive GETs und 7 Login-Redirects sind gruen; finaler Gate `419 passed`. TAR/Alias SHA256 `cad54a3bff671c0adff84700f46458a38dc38b9d0954a99d9c3e3155bec07079`, Modus 0600, Rotation alpha740-alpha744. Public bleibt alpha604; kein produktiver Zugriff.
- **User-Strukturreview akzeptiert.** Stats zeigt alpha744 mit 8 gruen/2 bekannten gelben/0 rot und Modul-Registry `131/475/172`; die Detailseite zeigt 0 Validierungsfehler und 0 Zyklen. Help/Produktinfo, Connections-GET und Recipe-GET-Seiten funktionieren laut User. Keine Mutation und keine fachliche Chat-/Runtime-/WebSearch-/Qdrant-Akzeptanz daraus ableiten.

### alpha743 candidate - Changed

- **Physische Core-Evakuierung abgeschlossen.** SearXNG-Client, Answer Composer, Watched-Website-Projektion, AuthManager, Access Policy und Maintenance-Orchestrierung mit zusammen `782` Implementierungszeilen liegen kanonisch in ihren Fachmodulen. Drei Recipe-Kompatibilitaetswrapper und zwei UI-Link-Reexports wurden zu identitaetserhaltenden Aliasen verdichtet. Unter `aria/core` verbleiben `211` Identitaetsaliase und ein leeres Paket-Init, aber keine Implementierungsdatei; produktive `aria.core`-Imports sind leer.
- **Fuenf Acceptance-gesicherte Ownership-Slices.** Web-/Website-, Answer-, Auth-/Access-, Maintenance- und Recipe-Kompatibilitaetsvertraege frieren Source Authority, Call-Count/Latenz, Auth-/Pfadpolitik, Wartungsreihenfolge sowie Recipe-Store-/Runtime-Kompatibilitaet ein. Tests nutzen nur synthetische Antworten, Monkeypatches, Fakes und In-Memory-/`tmp_path`-Daten; kein produktiver Netzwerk-, Auth-, Config-, Qdrant-, Memory-, Recipe-, Runtime- oder Userdatenzugriff.
- **Registry und lokale Gates gruen.** Neue Owner `answer_composer`, `website_runtime` und `auth_policy`; Registry `131/460/177/0/0`. Teilgates `405`, `229` (nur alter Zaehlerbefund), `138` und Abschlussfokus `346 passed`; Vollsuite `2267 passed` mit 6 bekannten `aiohttp`-Warnungen.
- **Interner Review-Build erstellt.** `0.1.0-alpha743` wurde als `fischermanch/aria:0.1.0-alpha.743` und `aria:alpha-local` gebaut, nach `/mnt/NAS/aria-images/aria-alpha743-local.tar` exportiert und mit `--network none`/tmpfs passiv geprueft. Container-CLI, elf neue Importidentitaeten, vollstaendige Core-Alias-Inventur, Registry `131/460/177/0/0`, Stats-Modulprojektion, Modul-Readmodel, Privacy, Package-Daten, Service Worker, 9 passive GETs und 8 Login-Redirects sind gruen. Finaler Post-Build-Gate `412 passed`; TAR/Alias SHA256 `60d31c471b9df8698cf545fd93006ec04903bf1f0718246504b7733234c9014c`, Modus 0600, Rotation alpha739-alpha743. Public bleibt alpha604; kein produktiver Zugriff.
- **Bekannte Live-Befunde bleiben vertagt.** Der alpha740 Memory-/Kontextauswahlbefund, die sichtbare Latenz sowie weitere vom User gemeldete Funktionsfehler wurden weder analysiert noch veraendert. Der alpha742 Apple-Watch-Test bleibt fachliche Evidence mit plausibler offizieller Quellenbasis und rund 26,5 Sekunden sichtbarer Laufzeit, nicht Beweis einer Latenzloesung.

### alpha742 candidate - Changed

- **Turn-Arbitration und MetaCatalog als grosser Ownership-Rail.** Die drei Implementierungen `aria_turn_arbitration`, `meta_catalog` und `meta_catalog_routing` mit zusammen `3048` Zeilen liegen kanonisch in den neuen Modulen `turn_arbitration` und `meta_catalog_routing`. Alle Produktionsconsumer verwenden Modulpfade; die drei historischen Core-Pfade bleiben identitaetserhaltende Aliase.
- **High-Risk-Verhalten vor der Bewegung eingefroren.** Die Acceptance `.codex/aria_acceptance/meta-catalog-turn-arbitration-ownership-rail-alpha742.json` deckt Public Current Fact vs explizite lokale Authority, RSS/Source Boundaries, exakte/unbekannte/Fleet-Ziele, Confirmation/Fail-Closed, synthetische Memory-Capture/Forget-Kontrakte sowie Catalog-Degrade und Call-Count ab. Der vertagte alpha740-Livebefund bleibt unangetastet.
- **Lokale Gates gruen.** Baseline `462 passed`, breite Nachbarsuite `796 passed`, Vollsuite `2238 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `121/361/156/0/0`, drei Importidentitaeten, keine Legacy-Produktionsimporte, Compileall, 268 Acceptance-JSONs und `git diff --check` gruen. Workspace/CLI bleiben alpha741; kein Build/Export und kein produktiver Runtime-, Qdrant-, Connection- oder Userdatenzugriff.
- **Pipeline-Kontext und Ausfuehrungsgrenzen als zweiter Grossrail.** Agentic Context Runtime, Pipeline Turn Stages, Pipeline SSH Helpers und provideruebergreifende Capability-Ausfuehrung mit `5033` Zeilen liegen kanonisch in `agentic_context_runtime`, `pipeline_turn_orchestration`, `ssh_runtime` und `pipeline_capability_execution`. Vier Core-Pfade bleiben Identitaetsaliase. Baseline `406`, Nachbarsuite `732`, Zwischen-Vollsuite `2242 passed`; Registry danach `124/393/165/0/0`.
- **Vollstaendiger Pipeline-Orchestrator als dritter Grossrail.** Die bisherige `Pipeline`-Quelle mit `8845` Zeilen liegt kanonisch in `pipeline_orchestrator`; inklusive der drei Zeilen fuer die Legacy-Modulbruecke umfasst der Owner `8848` Zeilen. `aria.core.pipeline` bleibt dasselbe Modulobjekt und wird auch bei direktem Canonical-Import fuer bestehende dynamische Monkeypatch-Bruecken registriert. Relative I18N-/Projektpfade zeigen weiterhin auf dieselben Verzeichnisse; sieben Produktionsconsumer nutzen den Modulpfad.
- **Kumulierter ungebauter Alpha742-Stand.** Drei Rails bringen acht kanonische Implementierungen auf zusammen `16929` Zeilen und halten acht Legacy-Identitaeten. Finale Nachbarsuite `736 passed`, Vollsuite `2246 passed` mit 6 bekannten Warnungen; Registry `125/442/174/0/0`, 270 Acceptance-JSONs, Compileall, Release-Hygiene, Legacy-Importinventur und Diff-Hygiene gruen. Workspace/CLI bleiben alpha741; kein Build/Export und kein produktiver Zugriff.
- **Runtime-/Authority-Kernelgrenzen als vierter Rail.** Web-Source-Target-Normalisierung, passiver RouterDecision-Vertrag, Runtime-Guardrails, Safe-Fix-Planung und SSHRuntime mit `813` Zeilen liegen kanonisch in `web_search`, `turn_decision`, `runtime_guardrails`, `safe_fix` und `ssh_runtime`. Fuenf Core-Pfade bleiben Identitaetsaliase; Source Authority, Guardrails, Confirmation, SSH-Ausfuehrung und Call-Count sind in eigener Acceptance eingefroren.
- **Memory-/Qdrant-Kernelgrenzen als fuenfter Rail.** Personal Memory, neutraler Memory Assist, Admin Query, review-only Procedure Guidance, Auto Memory, Recall-Source-Projektion und Qdrant-Client-Konstruktion mit `2319` Zeilen liegen kanonisch in `memory`, `memory_learning_bridge`, `auto_memory` und `qdrant_gateway`. Sieben Core-Pfade bleiben Identitaetsaliase. Der alpha740-Livebefund bleibt explizit ausgeschlossen; Qdrant-Tests monkeypatchen nur den Konstruktor und machen keine Requests.
- **Aktueller kumulierter Alpha742-Stand.** Fuenf Rails umfassen 20 kanonische Implementierungen/`20061` Zeilen und 20 Identitaetsaliase. Finale Nachbarsuite `780 passed`, Vollsuite `2250 passed` mit 6 bekannten Warnungen; Registry `128/450/177/0/0`, 272 Acceptance-JSONs, Compileall, Release-Hygiene, Legacy-Importinventur und Diff-Hygiene gruen.
- **Interner Review-Build erstellt.** `0.1.0-alpha742` wurde als `fischermanch/aria:0.1.0-alpha.742` und `aria:alpha-local` gebaut, nach `/mnt/NAS/aria-images/aria-alpha742-local.tar` exportiert und mit `--network none`/tmpfs passiv geprueft. Container-CLI, 20 Importidentitaeten, Registry `128/450/177/0/0`, Stats-Modulprojektion, Modul-Readmodel, Privacy, Package-Daten, Service Worker, 9 passive GETs und 8 Login-Redirects sind gruen. Finaler Post-Build-Gate `398 passed`; TAR/Alias SHA256 `f12b56aaf22edb3722f926b0d62eb4975b2c4d0d1470bff4d2ef2c7007a5da1c`, Modus 0600, Rotation alpha738-alpha742. Public bleibt alpha604; kein produktiver Zugriff.

### alpha741 candidate - Changed

- **Drei grosse Ownership-Rails ohne Mikro-Build.** Sieben Implementierungen mit zusammen `1787` Zeilen liegen nun bei ihren Fachowner-Modulen: File-, Forced-, Messaging- und Read-Resolution in `action_resolution`, Pending-Action-Vertraege in `pipeline_pending_action_contracts`, Routing-Debug-Projektion in `action_runtime_debug` und Runtime-Outcome-Follow-ups im neuen Modul `runtime_outcome_followup`. Die sieben historischen `aria.core`-Pfade bleiben identitaetserhaltende Aliase; Produktionsconsumer nutzen die kanonischen Modulpfade.
- **High-Risk-Verhalten explizit eingefroren.** Drei getrennte Acceptances sichern File-/Messaging-/Read-Aufloesung, Forced-Ref/Target/Confirmation/Fallback, Pending-Input/-Confirmation/-Debug-Projektion und read-only Follow-ups auf vorherige Runtime-Ergebnisse. Tests verwenden nur synthetische Turns, Fakes und lokale Daten. Keine produktive Runtime-, Connection-, WebSearch-, Qdrant-, Memory-, Session- oder Userdatenaktion.
- **Lokale Gates gruen.** Einzelrails vor/nach Bewegung `258/310`, `259/358` und `13/64 passed`; gemeinsame Nachbarsuite `486 passed`; Vollsuite `2231 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `117/331/154/0/0`, sieben Importidentitaeten, keine Legacy-Produktionsimporte, Compileall, 265 Acceptance-JSONs und `git diff --check` gruen.
- **Vor dem Build strikt getrennt.** Die CODE-Acceptances blieben auf `build_allowed: false`; der separate alpha740-Livebefund zu Memory-Auswahl und sichtbarer Latenz ist nur im Backlog dokumentiert und wurde in diesem Modularisierungsblock weder analysiert noch veraendert.
- **Connection-Routing als weiterer grosser Ownership-Rail.** Sechs Implementierungen/`2020` Zeilen fuer Routing Index, exakte Candidate-Validierung, bounded Router-LLM, Routing Admin/Resolution, Pipeline-Qdrant-Bridge und sprachbewusste Metadaten-Hints liegen kanonisch in `connection_routing` beziehungsweise `routing_hint_generation`. Sechs historische Core-Pfade bleiben Identitaetsaliase; Produktionsconsumer nutzen nur Modulimporte.
- **Routing-End-to-End-Matrix unveraendert gruen.** Public Current Fact vs lokale Connection, exaktes/unbekanntes Ziel, Fleet Scope, bounded/fail-closed Candidates, Qdrant-Degrade/Cleanup und reine Hint-Generierung sind in `.codex/aria_acceptance/connection-routing-ownership-rail-alpha741.json` eingefroren. Baseline `564`, Nachlauf `567`, Struktur/UI `350` und Vollsuite `2234 passed` mit 6 bekannten Warnungen.
- **Kumulierter alpha741-Stand.** Vier Rails verschieben 13 Implementierungen/`3807` Zeilen; Registry `119/339/157/0/0`, 13 Importidentitaeten, keine Legacy-Produktionsimporte, Compileall, 266 Acceptance-JSONs und Diff-Hygiene gruen. Keine produktive Qdrant-/Runtime-/Connection-/Userdatenaktion.
- **Interner Review-Build erstellt.** `0.1.0-alpha741` wurde als `fischermanch/aria:0.1.0-alpha.741` und `aria:alpha-local` gebaut, nach `/mnt/NAS/aria-images/aria-alpha741-local.tar` exportiert und mit `--network none`/tmpfs passiv gesmoked. Container-CLI, 13 Importidentitaeten, Registry `119/339/157/0/0`, Privacy, Stats-Modulprojektion, 9 passive GETs, 8 Login-Redirects, Update-Redirect und Service Worker gruen. TAR/Alias SHA256 `bbff3510f13545071dd23c001a7b2ad6c370adfea0bebff2cf017ddde9123564`, Modus 0600, Rotation alpha737-alpha741; Public bleibt alpha604.

### alpha740 candidate - Changed

- **Fuenf Implementierungen in klare Owner gezogen.** Surface Loader Runtime und LLM Input Contract liegen kanonisch in den neuen Modulen `context_loader_runtime` und `llm_input_contract`; Chat Learn Mode in `recipe_learning`, Artifact Review Patterns in `learning_artifacts` und Session Compression im neuen `memory_session_compression`. Insgesamt wurden `2059` Implementierungszeilen verschoben. Fuenf historische `aria.core`-Pfade bleiben identitaetserhaltende Aliase; Produktionsconsumer verwenden nur Modulimporte.
- **High-Risk-Matrizen eingefroren.** Public-Current-vs-local, exakte/fehlende SSH-Ziele, Fleet Scope, Confirmation, LLM-Redaction/Allowlist, Chat-Learn-Review-only und Memory-Rollup/Delete-Reihenfolge besitzen getrennte Acceptances. Tests nutzten nur synthetische Turns, Fake-LLM/Memory/Qdrant/Store und `tmp_path`; keine produktive Runtime-, WebSearch-, Connection-, Qdrant-, Recipe-, Session- oder Userdatenaktion.
- **Lokale Gates gruen.** Gemeinsame Baseline `343 passed`, Nachlauf mit fuenf neuen Identitaetschecks `348 passed`, Vollsuite `2223 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `116/319/152/0/0`; Compileall, Acceptance-JSONs, Legacy-Importinventur und `git diff --check` gruen.
- **Interner Review-Build erstellt.** `0.1.0-alpha740` wurde als `fischermanch/aria:0.1.0-alpha.740` und `aria:alpha-local` gebaut, als `aria-alpha740-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, fuenf Importidentitaeten, Registry `116/319/152/0/0`, Privacy, 5 passive/public GETs, 14 erwartete Redirects, Service Worker und die synthetisch gerenderte Stats-Modulkarte sind gruen. Rotation haelt alpha736-alpha740; Public bleibt `0.1.0-alpha604`. Das ist Build-Evidence, keine fachliche Live-Akzeptanz fuer Chat, Routing, Runtime, WebSearch, Connections, Qdrant oder Memory-Kompression.

### alpha739 candidate - Changed

- **Drei grosse Owner-Rails statt Build-Mikroschritten.** Fuenf Recipe-Experience-/Candidate-/Pipeline-Implementierungen liegen kanonisch in `recipe_learning` beziehungsweise `recipe_runtime`; Learning Worker und Pipeline-Learning-Mixin in `learning_runtime`; Connection Profile Admin in `connections_profiles`. Insgesamt wurden `3345` Implementierungszeilen verschoben. Acht historische `aria.core`-Pfade bleiben identitaetserhaltende Aliase, Produktionsconsumer nutzen ausschliesslich Fachmodulimporte.
- **High-Risk-Vertraege ohne produktiven Zugriff eingefroren.** Recipe Experience/Qdrant lief nur gegen Fake Memory/Qdrant, Learning Worker nur mit `tmp_path`-SQLite und Fake-Handlern, Connection Admin nur mit `tmp_path`-YAML und FakeStore. Collection-/Filter-/Payload-, Budget-/Retry-/Receipt-, Profile-/Secret-Key-/Token-/Error- und Pipeline-Vertraege blieben unveraendert; keine Runtime-, Provider-, Connection-, WebSearch-, Qdrant-, Userdaten- oder Build-Aktion.
- **Lokale Gates gruen.** Einzelrails `360`, `499` und `368 passed`; gemeinsame Recipe-/Learning-/Connection-/Pipeline-/Config-/Stats-Nachbarsuite `882 passed`; Vollsuite `2218 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `113/311/149/0/0`, Compileall, 257 Acceptance-JSONs, Legacy-Produktionsimportinventur und `git diff --check` gruen.
- **Interner Review-Build erstellt.** `0.1.0-alpha739` wurde als `fischermanch/aria:0.1.0-alpha.739` und `aria:alpha-local` gebaut, als `aria-alpha739-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, acht Importidentitaeten, Registry `113/311/149/0/0`, Privacy, 5 passive/public GETs, 14 erwartete Redirects, Service Worker und die synthetisch gerenderte Stats-Modulkarte sind gruen. Rotation haelt alpha735-alpha739; Public bleibt `0.1.0-alpha604`.
- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt alpha739, Modul-Registry `113/311/149` gruen, insgesamt 8 gruen/2 bekannte gelbe/0 rot, Startup-Preflight `4/0/0`, Runtime-Health `8/0/0`, Learning 30 fertig/0 fehlgeschlagen/30 rejected/30 Budget-Rejects. Keine fachliche Live-Akzeptanz fuer Chat, Routing, Runtime-Actions, Connections, WebSearch, Qdrant oder Memory Compression ableiten.

### alpha738 candidate - Changed

- **Modul-Registry im Operator Guardrail.** Die Stats-Seite projiziert die bestehende read-only `module_registry_diagnostics()`-Quelle als zehnte Guardrail-Karte: aktueller Workspace `113 Module · 311 interne Abhaengigkeiten · 149 externe Grenzen`, strukturell gruen bei 0 Validierungsfehlern/0 Zyklen und rot bei leerer Registry, Validierungsfehlern oder Abhaengigkeitszyklen. Die Karte verlinkt ueber den registrierten `config_ui`-Readpoint auf `/config/admin/modules`; sie behauptet bewusst keine funktionale Live-Gesundheit jedes Moduls.
- **Grosser Recipe-Store-/Learning-Ownership-Rail.** Acht bisher kernel-eigene Implementierungen fuer Stored-Recipe-Manifeste sowie Learned-Recipe-Candidate-View, Store-Vertrag, JSON-Store, Updates, Integration, Curation und Promotion liegen kanonisch in `aria.modules.recipe_store` beziehungsweise `aria.modules.recipe_learning`. Alle Produktionsconsumer nutzen Modulpfade; die acht historischen `aria.core`-Pfade bleiben identitaetserhaltende Aliase statt zweiter Implementierungen.
- **Lokale Gates gruen.** Import-/Registry-Gate `114 passed`, breite Recipe-/Planner-/Pipeline-/UI-Nachbarschaft `380 passed`, Vollsuite `2210 passed` mit 6 bekannten `aiohttp`-Warnungen; Registry `113/311/149/0/0`, Compileall, 253 Acceptance-JSONs, Legacy-Importinventur und `git diff --check` gruen. Tests verwendeten nur `tmp_path`, Fake-LLM-Antworten und synthetische Plaene.
- **Interner Review-Build erstellt.** `0.1.0-alpha738` wurde als `fischermanch/aria:0.1.0-alpha.738` und `aria:alpha-local` gebaut, als `aria-alpha738-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, acht Recipe-Importidentitaeten, Registry `113/311/149/0/0`, Privacy, 5 passive/public GETs, 14 erwartete Redirects, Service Worker sowie die gerenderte Stats-Modulkarte mit Link `/config/admin/modules` sind gruen. Rotation haelt alpha734-alpha738; Public bleibt `0.1.0-alpha604`.
- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt alpha738 und die neue Modul-Registry-Karte gruen mit `113 Module / 311 interne Abhaengigkeiten / 149 externe Grenzen`; insgesamt 8 gruen, 2 bekannte gelbe und 0 rot. Startup-Preflight `4/0/0`, Runtime-Health `8/0/0`, Learning 30 fertig/0 fehlgeschlagen/30 rejected/30 Budget-Rejects. Keine fachliche Live-Akzeptanz fuer Chat, Runtime-Actions, Connections, WebSearch oder Qdrant ableiten.

### alpha737 - Changed

- **Grosser Kernel-Contracts-/Gateway-/Integration-Rail lokal akzeptiert.** PipelineResult und Capability-Detailprojektion liegen in `pipeline_contracts`, der Capability Catalog in `action_contracts`, Error Interpreter/Runtime Endpoint/Google-Calendar-Fehler in `integration_support` und LLM-/Embedding-Clients in `model_gateway_clients`. Acht Core-Pfade bleiben Identitaetsaliase; Produktionsconsumer nutzen Modulpfade.
- **Notification-/Inbound-Storage-Rail lokal akzeptiert.** Discord Alerting und Inbound Event Normalization/SQLite Storage liegen in eigenen Modulen; zwei Core-Pfade bleiben Identitaetsaliase. Discord-Tests patchen den Transport, Inbound-Tests verwenden nur `tmp_path`-SQLite und synthetische Requests. Route-Codes, Redaction, Idempotenz und Retention bleiben testabgedeckt.
- **Lokale Gates gruen.** Fokus `207 passed`, breite Nachbarsuite `463 passed`, Vollsuite `2203 passed` mit 6 bekannten `aiohttp`-Warnungen; Post-Build-Gate `139 passed`; zehn Importidentitaeten, Registry `113/311/148/0/0`, Compileall, Acceptance-JSON, Produktionsimportinventur und `git diff --check` gruen. Workspace/CLI sind alpha737; kein produktiver Netzwerk-/Runtime-/Qdrant-/Datenzugriff.
- **Interner Review-Build erstellt.** `0.1.0-alpha737` wurde als `fischermanch/aria:0.1.0-alpha.737` und `aria:alpha-local` gebaut, als `aria-alpha737-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, zehn Importidentitaeten, Registry `113/311/148/0/0`, Privacy, 5 passive/public GETs, 14 erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha733` bis `alpha737`. Public bleibt `0.1.0-alpha604`.
- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt alpha737, 7 gruen/2 bekannte gelbe/0 rot, Startup-Preflight `4/0/0`, Runtime-Health `8/0/0`, Learning 30 fertig/0 fehlgeschlagen. Der Screenshot belegt ausserdem, dass die bisherige Stats-Seite noch keine Modul-Registry-Karte enthielt; keine fachliche Live-Akzeptanz fuer Chat, Runtime, Connections, WebSearch oder Qdrant.

### alpha736 - Changed

- **Agentic Contract-/Prompt-Flow-Import-Rail lokal akzeptiert.** `agentic_prompt_flow`, `agentic_contracts` und `agentic_stabilization` besitzen kanonische Modulpfade; drei Core-Pfade bleiben Identitaetsaliase. Prompt-Flow-Debug, Evidence-/Answerability-Derivation und Stabilization-Gate-Ausgaben bleiben unveraendert; `enforce_stabilization_gate_answerability` schreibt Antworttext weiterhin nicht um.
- **Active-Learning-Hints in `learning_feedback` gezogen.** `active_learning_hint_runtime` liegt kanonisch in `aria.modules.learning_feedback.active_hints`; der Core-Pfad bleibt Identitaetsalias und Produktionsconsumer nutzen den Modulpfad. Tests verwenden Fake-Memory und `tmp_path`; keine produktive Memory-/Qdrant-/Learning-Worker-/Userdatenaktion.
- **Authority-Chain-Audit aus dem Kernel geloest.** Die statische Authority-Audit-Definition liegt in `aria.modules.authority_chain_audit.audit`; der Core-Pfad bleibt Identitaetsalias. Historische Markerpfade bleiben absichtlich unveraendert, und das Modul bleibt Test-/Operator-Dokumentationsmetadata, keine Runtime-Dependency.
- **Alpha736-CODE-Block lokal komplett akzeptiert.** Kombinierte Fokussuite `119 passed`; Vollsuite `2196 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `108/297/149/0/0`; Compileall, Acceptance-JSON, Legacy-Importinventur und `git diff --check` gruen. Kein Build/Export, keine Runtime-Ausfuehrung, kein WebSearch-/Source-Authority-/Routing-/Guardrail-/Confirmation-/Qdrant-/Userdatenzugriff.
- **Interner Review-Build erstellt.** `0.1.0-alpha736` wurde als `fischermanch/aria:0.1.0-alpha.736` und `aria:alpha-local` gebaut, als `aria-alpha736-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, 14 Importidentitaeten, Registry `108/297/149/0/0`, Privacy, 5 passive/public GETs, 14 erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha732` bis `alpha736`. Public bleibt `0.1.0-alpha604`.
- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt alpha736, 7 gruen/2 bekannte gelbe/0 rot, Startup-Preflight `4/0/0`, Runtime-Health `8/0/0`, Learning 30 fertig/0 fehlgeschlagen, 30 rejected und 30 Budget-Rejects. Chat, Runtime-Actions, Connections, WebSearch und Qdrant wurden dadurch nicht fachlich live akzeptiert.

### alpha735 - Changed

- **Turn-Decision-/Answer-Influence-Import-Rail lokal akzeptiert.** Answer-Influence-Receipt, Turn-Semantics und Turn-Decision-Validation liegen kanonisch in `aria.modules.answer_influence`, `aria.modules.turn_semantics` und `aria.modules.turn_decision`; drei Core-Pfade bleiben Identitaetsaliase. Fokus `76`/`30`, Nachbarsuite `330`, Vollsuite `2171 passed` mit 6 bekannten `aiohttp`-Warnungen; Registry `97/274/130/0/0`. Kein Build/Export und keine Router-Prompt-/Source-Authority-/Confirmation-/Guardrail-/Runtime-/Persistenz-/Userdaten-Aenderung.
- **Chat-Context-/Capability-Context-Import-Rail lokal akzeptiert.** Recent Capability Context Store sowie sichtbare Chat-Context-Projektion/-Filterung liegen kanonisch in `aria.modules.capability_context` und `aria.modules.chat_context`; drei Core-Pfade bleiben Identitaetsaliase. Fokus `163`, Nachbarsuite `285`, Vollsuite `2172 passed` mit 6 bekannten Warnungen; Registry `99/275/136/0/0`. Kein Chat-Dispatch, keine Router-/Source-/Runtime-/WebSearch-/Qdrant-/Userdaten-Aenderung und kein Build/Export.
- **Actions-/Recipe-Import-Rails weiter gebuendelt.** Vier weitere alpha735-CODE-Rails sind lokal akzeptiert: `action_executor_registry`, `agentic_content_access_registry`, `agentic_content_access`, `action_runtime_debug`, `agentic_deterministic_boundaries` und die `recipe_store`-Manifest-View besitzen kanonische Modulpfade; sechs Core-Pfade bleiben Identitaetsaliase. Fokus `123`/`124`/`119`/`116`, gemeinsame Nachbarsuite `381`, Vollsuite `2186 passed` mit 6 bekannten Warnungen; Registry `104/285/142/0/0`. Keine Runtime-Ausfuehrung, Handler-Reihenfolge, Source-Authority, Routing-, Guardrail-/Confirmation-, Recipe-Persistenz-, Qdrant-/Userdaten-Aenderung und kein Build/Export.
- **Interner Review-Build erstellt.** `0.1.0-alpha735` wurde als `fischermanch/aria:0.1.0-alpha.735` und `aria:alpha-local` gebaut, als `aria-alpha735-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, 12 Importidentitaeten, Registry `104/285/142/0/0`, Privacy, 5 passive/public GETs, 14 erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha731` bis `alpha735`. Public bleibt `0.1.0-alpha604`.

### alpha734 - Changed

- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt `0.1.0-alpha734`, 7 gruen, 2 bekannte gelbe und 0 rote Guardrails. Release-Metadaten, Model Gateway, Pricing Coverage, Recipe Experience Memory, Startup-Preflight und Runtime-Health sind gruen; Learning meldet 29 fertige und 0 fehlgeschlagene Jobs. Kosten-Tracking und Learning-Budget bleiben bekannte Betriebsbefunde; Chat-History und Config-Backup wurden durch diesen Screenshot nicht fachlich live geprueft.
- **Interner Doppelrail-Review-Build erstellt.** `0.1.0-alpha734` wurde als `fischermanch/aria:0.1.0-alpha.734` und `aria:alpha-local` gebaut, als `aria-alpha734-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, sechs Importidentitaeten, Registry `95/269/130/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha730` bis `alpha734`. Public bleibt `0.1.0-alpha604`.
- **Configuration Foundations als kanonischer Modulowner.** Die bestehende Config-Implementierung mit Modellen, Defaults, Validierung, Environment-Overrides und Normalisierung liegt jetzt in `aria.modules.configuration_foundations.config`. Produktionsconsumer importieren den Modulpfad; `aria.core.config` bleibt ein identitaetserhaltender Kompatibilitaetsalias ohne zweite Implementierung.
- **Security Storage als kanonischer Modulowner.** Encrypted Settings/User/Session Storage, sichere Config-Migration und User-Administration liegen jetzt in `aria.modules.security_storage`. Die drei alten Core-Pfade bleiben identitaetserhaltende Aliase. Verhalten, Schema, Rollen-/Active-Vertrag und Migration-Counter bleiben unveraendert.
- **Registry-Grenzen nachgezogen.** `configuration_foundations` und `security_storage` sind registriert; bestehende Consumer-Abhaengigkeiten wurden von den alten externen Kernel-Grenzen auf interne Modulabhaengigkeiten umgestellt. Registry: `94` Module, `269` interne Abhaengigkeiten, `127` externe Grenzen, `0` Validierungsfehler, `0` Zyklen.
- **Lokale Acceptance gruen.** Generierte Testschluessel sowie temporaere SQLite-/YAML-Pfade pruefen Secret-Roundtrip, User-Verwaltung und sichere Migration ohne produktive Daten. Fokus vor/nach Bewegung `346`/`349 passed`; Vollsuite `2167 passed` mit 6 bekannten `aiohttp`-Warnungen. Vier Legacy-/Modulidentitaeten, Compileall, Acceptance-JSON, Importinventur und `git diff --check` sind gruen. Kein Build/Export und kein produktiver Config-/Secret-/DB-/User-/Session-Zugriff im CODE-Block.
- **Config Backup als aktiver Modulowner.** Parser, Schema-/Pfadvalidierung, Snapshot-/Summary-Komposition, Secure-Store-Synchronisierung und Restore liegen kanonisch in `aria.modules.config_backup.backup`; Route- und Chat-Admin-Consumer nutzen den Modulpfad. `aria.core.config_backup` bleibt ein Identitaetsalias. Backup-/Restore-Verhalten wurde nur mit `tmp_path` und Fake-/Test-Stores geprueft, nie gegen produktive Config, Secrets, User, Recipes oder Prompts.
- **Chat History Storage vom Kernel getrennt.** Der per Caller-Pfad gebundene JSON-Store liegt kanonisch in `aria.modules.chat_history_storage.store`; `aria.core.chat_history` bleibt ein Identitaetsalias. User-ID-Sanitization, defensive Reads, Trim, Cache-Invalidierung, Deep-Copy und atomarer Replace bleiben unveraendert; Tests verwenden nur synthetische Nachrichten unter `tmp_path`.
- **Alpha734-Doppelrail lokal komplett akzeptiert.** Persistenz-Fokus vor/nach Bewegung `369`/`372 passed`; finale Vollsuite `2170 passed` mit 6 bekannten Warnungen. Insgesamt sechs Legacy-/Modulidentitaeten; Registry `95/269/130/0/0`; Compileall, Acceptance-JSON, Produktionsimportinventur und Diff-Check gruen. Workspace/CLI sind alpha734; kein produktiver Zugriff.

### alpha733 - Changed

- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt `0.1.0-alpha733`, 7 gruen, 2 bekannte gelbe und 0 rote Guardrails. Release-Metadaten, Model Gateway, Pricing Coverage, Recipe Experience Memory, Startup-Preflight und Runtime-Health sind gruen; Learning meldet 29 fertige und 0 fehlgeschlagene Jobs. Kosten-Tracking und Learning-Budget bleiben bekannte Betriebsbefunde; weitere Funktionspfade sind aus dem Screenshot nicht abgeleitet.
- **Interner Review-Build erstellt.** `0.1.0-alpha733` wurde als `fischermanch/aria:0.1.0-alpha.733` und `aria:alpha-local` gebaut, als `aria-alpha733-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, sieben Importidentitaeten, Registry `92/245/144/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha729` bis `alpha733`. Public bleibt `0.1.0-alpha604`.
- **System Inventory aus dem Kernel geloest.** Deterministische Inventory-Dokumente/-Fingerprints, Collection-Namen, Store sowie explizit aufgerufene Status-/Rebuild-Projektion liegen kanonisch in `aria.modules.system_inventory`; zwei Core-Pfade bleiben Identitaetsaliase. Tests nutzen Fake-Qdrant/Fake-Embeddings und keine produktiven Daten oder Rebuilds.
- **Qdrant- und Runtime-Diagnostik fachlich getrennt.** Reine Collection-Klassifikation und lokale, caller-supplied Storage-Diagnostik liegen in `system_diagnostics`; explizit aufgerufene Qdrant-/Embedding-/LLM-Diagnosepayloads in `runtime_diagnostics`. Drei Core-Pfade bleiben Identitaetsaliase. Die Trennung vermeidet einen kuenstlichen Memory-/Recipe-/Usage-Zyklus; Registry bleibt zyklusfrei.
- **Release-Readclients im bestehenden Owner.** Release-Normalisierung/-Sortierung, Changelog-/History-Extraktion, Cache/Fallbacks sowie Update-Helper-Konfiguration, Statusprojektion und Request-/Error-Mapping liegen kanonisch in `aria.modules.release_update`; zwei Core-Pfade bleiben Identitaetsaliase. Kein Live-HTTP, Update oder Service-Restart wurde ausgefuehrt.
- **Alpha733-Doppelrail lokal komplett akzeptiert.** System-Fokus `622 passed`, Release-Fokus `190 passed`; komplette Suite `2164 passed` mit 6 bekannten `aiohttp`-Warnungen. Sieben Importidentitaeten, Registry `92/245/144/0/0`, Compileall, Acceptance-JSON, Produktionsimportinventur und Diff-Check gruen. Workspace/CLI sind alpha733; kein produktiver Zugriff.

### alpha732 - Changed

- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt `0.1.0-alpha732`, 7 gruen, 2 bekannte gelbe und 0 rote Guardrails. Release-Metadaten, Model Gateway, Pricing Coverage, Recipe Experience Memory, Startup-Preflight und Runtime-Health sind gruen; Learning meldet 29 fertige und 0 fehlgeschlagene Jobs. Kosten-Tracking und Learning-Budget bleiben bekannte Betriebsbefunde; weitere Funktionspfade sind aus dem Screenshot nicht abgeleitet.
- **Interner Review-Build erstellt.** `0.1.0-alpha732` wurde als `fischermanch/aria:0.1.0-alpha.732` und `aria:alpha-local` gebaut, als `aria-alpha732-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, 14 Importidentitaeten, Registry `89/233/136/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha728` bis `alpha732`. Public bleibt `0.1.0-alpha604`.
- **Gemeinsame Plattform-Primitiven aus dem Kernel geloest.** I18N-Store, Text-/JSON-Helfer, BoundedDecision-Transport, PromptLoader und Stage-Timing liegen kanonisch in `aria.modules.platform_primitives`; 108 Produktionsdateien importieren den Modulpfad, die fuenf historischen Core-Pfade bleiben Identitaetsaliase. Sprachfallbacks, Promptinhalt/-cache, kompakte LLM-Payloads, Usage/Error-Vertrag und Timing-Zeilen bleiben unveraendert.
- **Plattform-Rail lokal komplett akzeptiert.** Eigene Acceptance friert I18N, JSON-Extraktion, Fake-LLM-Transport, Promptpfade und Timing-Reihenfolge ein. Fokus `220 passed`; komplett `2155 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `87/230/132/0/0`, Compileall, Acceptance-JSON, Importidentitaet und Produktionsimportinventur gruen; kein Build/Export und kein produktiver Zugriff.
- **Model-Usage-Observability aus dem Kernel geloest.** Pricing Catalog, TokenTracker, UsageMeter und redaktierter LLM-Audit liegen kanonisch in `aria.modules.model_usage_observability`; Produktionsconsumer nutzen den Modulpfad, vier Core-Pfade bleiben Identitaetsaliase. Preis-/Aliasauflösung, Kostenaggregation, Recipe-Aktivitaeten, Secret-Redaction, Retention und der bisherige Repository-Auditpfad bleiben unveraendert. Fokus `419 passed`; komplett `2158 passed` mit 6 bekannten Warnungen.
- **Prepared Artifacts als aktive Modulgrenze.** App-Plan-Drafting/-Validation, Health-/Regression-Drafts, Pytest-Proposals und Apply-/Review-Payloads liegen kanonisch in `aria.modules.prepared_artifacts`; fuenf Core-Pfade bleiben Identitaetsaliase. Target-Path-, Duplicate-, Review-, Write- und Runtime-Aktivierungsgates bleiben fail-closed. Fokus `441 passed`; SafeFix/SSH-Ausfuehrung blieb bewusst ausserhalb.
- **Alpha732-Dreierblock lokal komplett akzeptiert.** Gemeinsame Endregression `2160 passed` mit 6 bekannten `aiohttp`-Warnungen; Registry `89` Module, `233` interne Abhaengigkeiten, `136` externe Grenzen, `0` Validierungsfehler und `0` Zyklen. 14 Importidentitaeten, Compileall, Acceptance-JSON, Produktionsimportinventur und Diff-Check gruen; Workspace/CLI sind alpha732, kein produktiver Zugriff.

### alpha731 - Changed

- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt `0.1.0-alpha731`, 7 gruen, 2 bekannte gelbe und 0 rote Guardrails. Release-Metadaten, Model Gateway, Pricing Coverage, Recipe Experience Memory, Startup-Preflight und Runtime-Health sind gruen; Learning meldet 29 fertige und 0 fehlgeschlagene Jobs. Kosten-Tracking und Learning-Budget bleiben bekannte Betriebsbefunde; weitere Funktionspfade sind aus dem Screenshot nicht abgeleitet.
- **Interner Review-Build erstellt.** `0.1.0-alpha731` wurde als `fischermanch/aria:0.1.0-alpha.731` und `aria:alpha-local` gebaut, als `aria-alpha731-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, 30 Importidentitaeten, Registry `86/209/149/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha727` bis `alpha731`. Public bleibt `0.1.0-alpha604`.
- **Action-Draft/Policy und Guardrail-Drafts als aktive Modulgrenze.** Action-Draft-/Policy-Vertraege und Guardrail-Draft-Kontext/Normalisierung liegen kanonisch in `aria.modules.action_draft_policy`; Produktionsconsumer nutzen die Modulpfade, alte Core-Pfade bleiben Identitaetsaliase. Policy-/Guardrail-Entscheidungen, Payloads und Fake-LLM-Normalisierung bleiben unveraendert.
- **Confirmation, Block-Erklaerungen und Operator Trace aus dem Kernel geloest.** One-shot Confirmation Ledger, bereits entschiedene Block-Erklaerungen und abgeleitete Operator-Trace-Projektion liegen in `action_confirmation`, `blocked_action_explanations` und `operator_trace_boundary`. User-/Token-/Fingerprint-Scope, SQLite-Schema, Fail-closed-/Replay-Verhalten, Security-Links und Trace-Phasen bleiben unveraendert.
- **Runtime Result Summaries kanonisch modularisiert.** Das komplette SSH-/HTTP-/IMAP-/RSS-/File-Summarizer-Paket liegt unter `aria.modules.runtime_result_summary`; Core-Paket und Submodule sind Identitaetsaliase. Eigene Acceptance friert Raw-Result-Autoritaet, Confirmation, Guardrails, Block-Fallbacks und Trace-Reihenfolge ein. Rail-Fokus `422 passed`; komplett `2143 passed` mit 6 bekannten Warnungen; 11 Importidentitaeten, Registry `85/200/147/0/0`, Compile/JSON/Importinventur gruen. Workspace/CLI bleiben alpha730, kein Build/Export oder produktiver Zugriff.
- **Action-Planner-Support und Execution Dry Run aus dem Kernel geloest.** Behavior Families, Candidate-Helfer und Bounded Planner liegen kanonisch in `aria.modules.action_planner`; die vollstaendige nicht-ausfuehrende Dry-Run-Komposition besitzt das neue registrierte Modul `execution_dry_run`. Produktionsconsumer nutzen die Modulpfade, alte Core-Pfade bleiben Identitaetsaliase; Auswahl, Scoring, Confirmation, Guardrails und Runtime bleiben unveraendert.
- **Document Ingest, Document Memory und Notes als aktive Importgrenzen.** Ingest, Meta-Katalog, Memory-Helfer/-Service sowie Notes Store, Index, Context, Web-Source-Vorbereitung und Action-Arbitration liegen kanonisch in ihren Fachmodulen. Tests nutzen nur `tmp_path`, BytesIO und Fake-Index/LLM/Responses; keine produktiven Notes, URLs, Embeddings, Qdrant- oder Userdaten wurden gelesen oder veraendert.
- **Learning Feedback und Artefakte kanonisch modularisiert.** User-Feedback, Learning-Outcome-Vertraege, Artifact Review und reine Host-Artefakt-Signalprojektion liegen in `learning_feedback` und `learning_artifacts`. Ein zuvor nicht isolierter Pipeline-Test faked nun auch den Worker-Queue-Pfad und schreibt keine Testjobs mehr in den lokalen Worker-Store. Feedback-, WebSearch-/Connection-Event-, Review-only-, Promotion- und Runtime-Autoritaet bleiben unveraendert.
- **Alpha731-Sammelblock lokal komplett akzeptiert.** Die zusaetzlichen Rails pruefen ihre Legacy-/Canonical-Identitaet und Produktionsimportgrenzen einzeln; finale Gesamtsuite `2153 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry `86` Module, `209` interne Abhaengigkeiten, `149` externe Grenzen, `0` Validierungsfehler und `0` Zyklen. Workspace/CLI sind `0.1.0-alpha731`; kein produktiver Runtime-/Connection-/WebSearch-/Worker-/Qdrant-/Userdatenzugriff.

### alpha730 - Changed

- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt `0.1.0-alpha730`, 7 gruen, 2 bekannte gelbe und 0 rote Guardrails. Release-Metadaten, Model Gateway, Pricing Coverage, Recipe Experience Memory, Startup-Preflight und Runtime-Health sind gruen; Learning meldet 29 fertige und 0 fehlgeschlagene Jobs. Die gelben Kosten- und Learning-Budget-Hinweise sind bekannte Betriebsbefunde; weitere Funktionspfade sind aus dem Screenshot nicht abgeleitet.
- **Interner Review-Build erstellt.** `0.1.0-alpha730` wurde als `fischermanch/aria:0.1.0-alpha.730` und `aria:alpha-local` gebaut, als `aria-alpha730-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, 11 Importidentitaeten, Registry `85/200/147/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha726` bis `alpha730`. Public bleibt `0.1.0-alpha604`.
- **Provider Planning und Policy als kanonische Modulgrenzen.** SSH Guardrail-Command-Projektion, Read-only Policy, Target Scope und Action Resolution sowie HTTP/API Policy und Resolution liegen kanonisch in `aria.modules.ssh_*` bzw. `aria.modules.http_api_*`. Produktionsconsumer nutzen diese Pfade; historische Core-Pfade bleiben identitaetserhaltende Aliase.
- **RSS Digest/OPML und Capability-Fehler aus dem Kernel geloest.** Digest-Optionen, Action-Selection-Notizen, Gruppierung/Cache und reine OPML-Parser/Serializer liegen in `aria.modules.rss_digest` bzw. `rss_opml`; Missing-Input-, HTTP-Status-, Guardrail- und Runtime-Fehlermeldungen liegen in `capability_error_messages`. Gruppierung, Limits, XML, Fehlercodes und sichtbare Klassifikation bleiben unveraendert.
- **Rail-7-Acceptance und komplette Regression gruen.** Eigene Matrix friert Current-Fact-vs-local, exact/unknown/fleet SSH-Scope, Read-only/Mutation-Policy, HTTP-Methode/Pfad/Confirmation, explizites RSS, OPML und Guardrail-Fehlerklassifikation ein. Fokus `495 passed`; kompletter lokaler Satz `2141 passed` mit 6 bekannten `aiohttp`-Warnungen. Workspace/CLI sind `0.1.0-alpha730`; keine echte Runtime/Connection/Feed-/Dateiaktion, Public bleibt `0.1.0-alpha604`.

### alpha729 - Changed

- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt `0.1.0-alpha729`, 7 gruen, 2 bekannte gelbe und 0 rote Guardrails. Release, Gateway, Pricing Coverage, Recipe Experience Memory, Startup-Preflight und Runtime-Health sind gruen; Learning meldet 0 fehlgeschlagene Jobs. Der kurze Reconnect-Hinweis passt zur Update-Unterbrechung; weitere Funktionspfade sind aus dem Screenshot nicht abgeleitet.
- **Interner Review-Build erstellt.** `0.1.0-alpha729` wurde als `fischermanch/aria:0.1.0-alpha.729` und `aria:alpha-local` gebaut, als `aria-alpha729-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, Importidentitaet, Registry `85/200/147/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha725` bis `alpha729`. Public bleibt `0.1.0-alpha604`.
- **Action Planning als kanonische Modulgrenze.** Action-Plan- und Connection-Action-Vertraege, Candidate-Taxonomie/-Assembly, Recipe-Candidate-Projektion, Planner-Templates/-Result-State und nicht ausfuehrende Dry-Run-Payloads liegen kanonisch in `aria.modules.action_*` bzw. `aria.modules.execution_dry_run_payloads`. Produktionsconsumer nutzen die Modulpfade; historische Core-Pfade bleiben identitaetserhaltende Aliase.
- **Connection Health und Runtime Status aus dem Kernel geloest.** Health-Cache sowie Connection-Status-/Probe-Implementierung liegen kanonisch in `aria.modules.connections_health_cache` und `aria.modules.connections_runtime_status`; Config, Stats und Connection-Admin nutzen diese Owner. Profile, Mutationen, Secrets, produktiver Cache und echte Probes blieben ausserhalb und wurden nicht ausgefuehrt.
- **Importgrenzen und Gesamtregression gruen.** Eigene alpha729-Acceptance friert Current-Fact-vs-local, RSS, exact/unknown/fleet Targets, Candidate-Reihenfolge, Dry-Run/Confirmation sowie Connection-Status/Fake-Probes ein. Fokus Action `460 passed`, Connection `422 passed`; kompletter lokaler Satz `2139 passed` mit 6 bekannten `aiohttp`-Warnungen. Workspace/CLI sind `0.1.0-alpha729`; Public bleibt `0.1.0-alpha604`.

### alpha728 - Changed

- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt `0.1.0-alpha728`, 7 gruen, 2 bekannte gelbe und 0 rote Guardrails. Release, Gateway, Pricing Coverage, Recipe Experience Memory, Startup-Preflight und Runtime-Health sind gruen; Learning meldet 0 fehlgeschlagene Jobs. Weitere Funktionspfade sind aus dem Screenshot nicht abgeleitet.
- **Interner Review-Build erstellt.** `0.1.0-alpha728` wurde als `fischermanch/aria:0.1.0-alpha.728` und `aria:alpha-local` gebaut, als `aria-alpha728-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, Importidentitaet, Registry `85/200/147/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha724` bis `alpha728`. Public bleibt `0.1.0-alpha604`.
- **Recipe Runtime vollstaendig hinter die Modulgrenze verschoben.** Runtime-Komposition, Matching, Steps sowie Calendar-, File-, HTTP-, Messaging- und RSS-Adapter liegen kanonisch in `aria.modules.recipe_runtime`; Pipeline und weitere Produktionsconsumer importieren die Modulpfade. Historische `aria.core.recipe_runtime*`-Pfade bleiben identitaetserhaltende Aliase, sodass bestehende Monkeypatch- und Legacy-Imports dasselbe Modulobjekt sehen.
- **Learning Candidates als aktive Importgrenze.** Entity-Alias-, Classifier-, Validator-, Synthesis- und Promotion-Implementierungen liegen kanonisch in `aria.modules.learning_candidates`; Outcomes, Feedback, Artifacts, Memory UI, Recipe Runtime und Pipeline nutzen diese Pfade. Produktive Stores, Regression-Subprozesse, Aktivierung, Worker, Memory/Qdrant und Userdaten wurden nicht ausgefuehrt.
- **Rail-4-Acceptance und komplette Regression gruen.** Eigene Matrix grenzt Current-Fact-vs-local, RSS, exact/unknown/fleet Targets, Confirmation, weak-signal Learning, Entity-Alias- und Promotion-Autoritaet ab. Fokus Recipe Runtime `603 passed`, Learning Candidates `598 passed`; kompletter lokaler Satz `2129 passed` mit 6 bekannten `aiohttp`-Warnungen. Workspace/CLI bleiben `0.1.0-alpha727`; kein Build/Export, Public bleibt `0.1.0-alpha604`.
- **Connection Semantic und Action Resolution als aktive Importgrenzen.** Semantic Resolver, Target Dossiers und Routed Action Resolver liegen kanonisch in `aria.modules.connections_semantic` bzw. `aria.modules.action_resolution`. Alle Produktionsconsumer nutzen die Modulpfade; historische Core-Pfade bleiben identitaetserhaltende Aliase. Pipeline-Callbacks, LLM-/Routing-/Source-Authority-, Confirmation-, Guardrail- und Target-Semantik wurden nicht geaendert.
- **Konkrete Runtime-Handler ihren Fachmodulen zugeordnet.** Multi-Target SSH und RSS Feed liegen in `ssh_runtime` bzw. `rss_runtime`, Execution Learning in `learning_runtime`; der generische Handler besitzt das neue explizite Modul `capability_runtime`. Pipeline-Konstruktion und First-Match-Reihenfolge bleiben SSH, RSS, Generic und sind durch einen direkten Vertragstest gesichert. Kein Handler wurde gegen echte Ziele ausgefuehrt, keine Connection, kein Secret, kein Worker/Store, kein Qdrant oder Userdatum angefasst.
- **Rail-5-Acceptance und Gesamtregression gruen.** Die eigene E2E-Matrix friert Current-Fact-vs-local, exact/unknown/fleet Targets, RSS, Confirmation und Handler-Reihenfolge ein. Fokus `558 passed`; kompletter lokaler Satz `2135 passed` mit 6 bekannten `aiohttp`-Warnungen. Registry jetzt `85/200/147/0/0`; Workspace/CLI bleiben `0.1.0-alpha727`, kein Build/Export, Public bleibt `0.1.0-alpha604`.

### alpha727 - Changed

- **User-Install-/Versions-/Stats-Check akzeptiert.** `/stats` zeigt `0.1.0-alpha727`, 7 gruen, 2 gelb und 0 rot. Release-Metadaten, Model Gateway, Pricing Coverage, Recipe Experience Memory, Startup-Preflight und Runtime-Health sind gruen; gelb bleiben die bekannte Kosten-Schaetzdifferenz und Learning-Budget-Rejects bei 0 fehlgeschlagenen Learning-Jobs.
- **Interner Review-Build erstellt.** `0.1.0-alpha727` wurde als `fischermanch/aria:0.1.0-alpha.727` und `aria:alpha-local` gebaut, als `aria-alpha727-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, Importidentitaet, Registry `84/196/145/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und Service Worker sind gruen; Rotation haelt `alpha723` bis `alpha727`. Public bleibt `0.1.0-alpha604`.
- **Drei grosse kanonische Importzuege statt weiterer Mikro-Slices.** Context-Surfaces inklusive Assembler, Verträgen, Adaptern, State-/Answer-Readmodels und Source-Counts liegen unter `aria.modules.context_surfaces`; der reine Memory-Recall-Parametervertrag liegt unter `aria.modules.memory`. Context-Auswahl/Loading, AnswerComposer, Memory/Qdrant und Source Authority bleiben unveraendert ausserhalb.
- **Connections-Katalog und Providerprojektion aus dem Kernel geloest.** Der statische Katalog, die read-only Provider-/Adapterstatus-Projektion und der reine Ref-Scope-Vertrag liegen in `aria.modules.connections_*`. Alle Produktionsconsumer nutzen die kanonischen Pfade; Profile, Secrets, Probes, Mutationen, Routingautoritaet und Runtime bleiben unveraendert.
- **Learning-Governance und reine Recipe-Vertraege modularisiert.** Learning-Directive/Event/Governor sowie Recipe-Intent-/Confirmation-, Result-/Status-, Candidate-/Experience- und Promotion-Vertraege liegen kanonisch in `aria.modules.learning_governance`, `aria.modules.recipe_learning` und `aria.modules.recipe_runtime`. Side-effect-/Multi-Target-Promotion, Guardrails, Confirmation, Worker, Stores und Provider-Ausfuehrung wurden nicht geaendert oder ausgefuehrt.
- **Kompatibilitaet und komplette Regression belegt.** Historische `aria.core`-Importe sind identitaetserhaltende Modulaliase, keine zweite Implementierung. Fokusgates: `543` Context, `739` Connections vor Korrektur einer veralteten Manifest-Assertion und `534` Recipe/Learning; finaler kompletter lokaler Satz `2125 passed` mit 6 bekannten `aiohttp`-Warnungen. Workspace/CLI sind `0.1.0-alpha727`; Public bleibt `0.1.0-alpha604`.

### alpha726 — Changed

- **User-Install- und Funktionscheck akzeptiert.** `/stats` zeigt `0.1.0-alpha726`; Release, Model Gateway, Pricing Coverage, Startup-Preflight und Runtime-Health sind gruen, Navigation und eine harmlose normale Chat-Antwort funktionieren. Es gibt `0` rote Guardrails; die zwei gelben Hinweise betreffen die bekannte Kosten-Schaetzdifferenz und Learning-Budget-Rejects ohne fehlgeschlagene Learning-Jobs.
- **Interner Review-Build erstellt.** `0.1.0-alpha726` wurde als `fischermanch/aria:0.1.0-alpha.726` und `aria:alpha-local` gebaut, als `aria-alpha726-local.tar` exportiert und netzlos mit tmpfs passiv gesmoked. Container-CLI, Modulimportidentitaet, Registry `84/196/145/0/0`, Privacy, zehn passive/public GETs, neun erwartete Redirects und der Service-Worker-Readpoint sind gruen; Rotation haelt `alpha722` bis `alpha726`. Public bleibt `0.1.0-alpha604`.
- **Erste echte Modul-Importgrenzen fuer UI-Readpoints.** Config-Security-, Website- und Notes-Linkimplementierungen liegen kanonisch in `aria.modules.config_ui.links`, `aria.modules.website_ui.links` und `aria.modules.notes.links`; neun Produktionsconsumer importieren die Modulpfade. Die drei alten `aria.core`-/`aria.web`-Module sind identische Kompatibilitaets-Re-Exports, keine zweite Implementierung. URLs, Encoding und fail-closed Registry-Ownership bleiben unveraendert.
- **Navigation Shell ist kanonische Implementierung.** Die bisherige `aria.web.navigation_registry` liegt nun in `aria.modules.navigation_shell.navigation`; `aria.main` importiert den Modulpfad. Der Legacy-Pfad ist ein Alias auf dasselbe Modulobjekt, sodass Tabellen, Funktionen und Monkeypatch-Verhalten kompatibel bleiben. Navigationsknoten, Hrefs, Sichtbarkeit und Active-State-Logik wurden nicht geaendert.
- **Release-Metadaten hinter `release_update` verschoben.** CLI, Config-Backup, Config-Helfer und Stats lesen `aria.modules.release_update.release_meta`; der alte Core-Pfad bleibt Modulalias. Workspace-Label und CLI bleiben `0.1.0-alpha725`; kein Versionsbump, Update-Lauf, Build oder Export.
- **Action-Runtime-Contracts und Handler-Registry besitzen eine echte Modulgrenze.** `AgenticExecutionRequest`, `AgenticExecutionResult`, `AgenticExecutionHooks`, Handler-Protocol und unveraenderte First-Match-Registry liegen in `aria.modules.runtime_execution_registry`; Pipeline, SSH-, RSS-, Capability-Handler und Providerdiagnostik importieren diese Pfade. Legacy-Core-Module sind identische Aliase. Keine Handlerreihenfolge, Ausfuehrung, Confirmation, Guardrail-, Routing-, Source-Authority- oder Learning-Semantik wurde geaendert oder produktiv ausgefuehrt.

### alpha725 — Changed

- **User-Install- und Funktionscheck akzeptiert.** `/stats` zeigt `0.1.0-alpha725`; die Module Registry zeigt `84` Module, `196` interne Abhaengigkeiten, `145` externe Grenzen, `0` Validierungsfehler und `0` Abhaengigkeitszyklen. Connections-Konfigurationsseiten, Recipes, Notes/Documents, Memory und `/memories/auto-memory` wurden vom User passiv geprueft und als ok bestaetigt.
- **Interner Review-Build erstellt.** `0.1.0-alpha725` wurde als `fischermanch/aria:0.1.0-alpha.725` und `aria:alpha-local` gebaut, als `aria-alpha725-local.tar` exportiert und mit netzlosem tmpfs-Container passiv gesmoked. Container-CLI, Registry-Diagnostik, Privacy, zehn passive/public GETs, neun erwartete Login-Redirects und der Service-Worker-Health-Readpoint sind gruen; Rotation haelt `alpha721` bis `alpha725`. Public bleibt `0.1.0-alpha604`.
- **Core-Umbrellas in explizite Ownership-Module zerlegt und Registry-Zyklen entfernt.** Die Sammelmodule `recipes`, `documents`, `memory`, `actions`, `ssh`, `http_api`, `rss` und `learning` delegieren ihre bisherigen Python-/Surface-Claims an 31 engere Module fuer Store/Runtime/Learning/Legacy-Recipe-Kompatibilitaet, Notes/Ingest/Document-Memory/Context, Memory-Learning-Bruecken, Planner/Draft-Policy/Block-Erklaerungen/Pending-Tokens, Provider-Policy/Resolution/Runtime/Admin-UI sowie Learning-Governance/Kandidaten/Feedback/Artefakte/Runtime/Auto-Memory/Answer-Influence/UI. Bestehende Python-Importpfade, FastAPI-Decorator, Worker-/Pipeline-Wiring und Runtimehandler bleiben unveraendert. Die Registry umfasst nun 84 Module, 196 interne Verweise, 145 externe Grenzen, 0 Validierungsfehler und 0 Dependency-Zyklen. Covered by the ownership-focused module, Recipe, Notes/Document, Memory/Learning, Action, SSH/HTTP/RSS, Config, release-hygiene, and CLI suites (`1108 passed`, 4 known aiohttp warnings).
- **SSH-/HTTP-Config-Readpoints folgen den neuen UI-Ownern.** Template-Aufloesung und Required-Route-Readpoints fuer SSH/SFTP verwenden `ssh_admin_ui`; HTTP API/Webhook verwenden `http_api_admin_ui`. Sichtbare URLs, Form-Actions und Handler bleiben gleich, fehlende Ownership faellt weiterhin geschlossen aus. Covered by `tests/test_config_routes.py` (`158 passed`).
- **Connections-Umbrella in drei passive Restgrenzen zerlegt.** `connections_runtime_status` besitzt nun `connection_runtime.py`, `connections_provider_manifest` die read-only Capability-/Adapterprojektion und `connections_mutations` die bestehenden Mutation-/Support-Kompositionsdateien. Das historische `connections`-Umbrella beansprucht keine pauschalen `connection_*`-Pythonpfade und keine Rueckabhaengigkeiten auf Actions, SSH, HTTP API, RSS oder WebSearch mehr; direkte Imports und injizierte Provider-Callbacks sind an den neuen Submodulen dokumentiert. Der Registry-Stand umfasst 53 Module, 155 interne Verweise, 93 externe Grenzen und eine verbleibende Zyklusgruppe mit acht statt zehn Umbrella-Modulen. Keine Imports, FastAPI-Routen, Provider-Callbacks, Probes, Mutationen oder Runtimeadapter wurden umverdrahtet oder ausgefuehrt. Covered by `tests/test_module_manifest_validation.py`, `tests/test_connection_provider_manifest.py`, `tests/test_connection_runtime.py`, `tests/test_connection_health.py`, and `tests/test_config_routes.py`.
- **Modulabhaengigkeiten sind explizit klassifiziert und passiv diagnostizierbar.** Alle 50 Manifeste trennen registrierte Modulziele in `depends_on` von Kernel-/Legacy-Grenzen in `external_dependencies`. Fehlende interne Ziele, doppelte Klassifikation und als extern markierte registrierte Module brechen den fail-closed Registry-Vertrag. Das Readmodel und die bestehende read-only Seite `/config/admin/modules` zeigen 150 interne Verweise, 88 externe Grenzen, Validierungsstatus und deterministische Zykluszugehoerigkeit. Die verbleibende zehnmodulige Core-Zyklusgruppe wird als Architekturdiagnostik sichtbar, erzeugt aber weder Importreihenfolge noch Runtime-, Dispatch- oder FastAPI-Verdrahtung. Covered by `tests/test_module_manifest_validation.py`, `tests/test_module_registry_read_model.py`, and `tests/test_config_routes.py`.
- **Falsche `config_backup`/`memory_export`-Dependency-Rueckkante entfernt.** `config_backup` konsumiert weiterhin den registrierten `/memories/export`-Readpoint und haengt deshalb von `memory_export` ab. `memory_export` deklariert seinen Verbraucher nicht mehr als eigene Abhaengigkeit; die historische Zwei-Modul-Zyklusdiagnose verschwindet, ohne Route, Handler, Template, Exportpayload, Restore oder User-Memory anzufassen. Covered by `tests/test_module_manifest_validation.py`, `tests/test_module_registry_read_model.py`, and `tests/test_config_backup.py`.
- **Modulmanifeste haben einen zentralen fail-closed Contract.** `aria.modules.validation` validiert beim passiven Registry-Import Pflichtfelder, IDs, Safety-Flags, Listen/Duplikate, Routes, Prefixgrenzen, Templates, Static-/Promptpfade, Navigation-IDs, Parentbeziehungen und Acceptance-Pfade. Jede vorhandene `aria/modules/*/manifest.py` muss importiert und unter ihrer Verzeichnis-ID registriert sein; jede deklarierte Acceptance muss existieren und valides JSON enthalten. Die Validierung generiert weder Runtime noch Dispatch oder FastAPI-Routen. Covered by `tests/test_module_manifest_validation.py`, `tests/test_module_registry.py`, and `tests/test_module_registry_read_model.py`.
- **Exklusive Surface-Ownership aus historischen Umbrella-Manifeste herausgeloest.** Redundante exakte Claims fuer Route-Prefixes, Templates und `style.css` wurden aus `ui_admin`, `connections`, `recipes`, `navigation_shell`, `rss`, `memory`, `learning` und `memory_export` entfernt, nachdem die getesteten Fachmodule `auth_ui`, `config_ui`, `navigation_shell`, `stats_ui`, `connections_ui_readonly`, `recipes_ui`, `rss_ui`, `memory_admin_ui` und `config_backup` diese Readpoints besitzen. Python-/Test-/Dokumentpfade bleiben bewusst nicht-exklusive Uebergangsreferenzen. Produktcode, Handler, Templates und sichtbare URLs bleiben unveraendert.

### alpha724 — Changed

- **Connector-Config-Template-Actions fail-closed ueber Required-Route-Readpoints.** Ein neuer Template-Helper `required_module_route_path(...)` wirft beim Rendern, wenn ein benoetigter Modul-Route-Owner fehlt, waehrend der bestehende optionale `module_route_path(...)` fuer optionale Links unveraendert leer bleiben darf. Discord-, IMAP-, MQTT-, SMB-, SMTP-, Google-Calendar-, SearXNG-, SSH-, SFTP-, HTTP-API- und Webhook-Config-Templates nutzen den Required-Helper fuer ihre sichtbaren Save-/Key-/Metadata-Action-Ziele. Sichtbare URLs bleiben gleich; keine POST-/Save-/Delete-/Import-/Export-, Connection-Probe-, WebSearch-/SearXNG-, SSH-/SFTP-/HTTP-, Runtime-, Qdrant-/Userdaten- oder Secret-Semantik wurde ausgefuehrt oder geaendert. Covered by `tests/test_config_routes.py`.
- **RSS-/Website-Connector-Multi-Actions fail-closed ueber Required-Route-Readpoints.** Die RSS-Config-Template-URLs fuer Page, Poll-Interval-Save, OPML Export/Import, Ping, Save und Suggest-Metadata sowie die Website-Config-Template-URLs fuer Page, Save und Suggest-Metadata nutzen nun ebenfalls `required_module_route_path(...)`. Sichtbare URLs und `data-connection-meta-endpoint`-Werte bleiben gleich; keine RSS-/Website-POST-, GET-Refresh-, OPML-, Ping-, Save-, Suggest-, Fetch-/Probe-, LLM-, Runtime-, Qdrant-/Userdaten- oder Secret-Semantik wurde ausgefuehrt oder geaendert. Covered by `tests/test_config_routes.py`.
- **Main-UI-Error-Surface liest Home/Stylesheet ueber Modul-Readpoints.** Die direkt gerenderte HTML-Fehlerseite in `aria.web.main_ui_helpers.exception_response(...)` liest ihr Stylesheet ueber `navigation_shell`-Static-Ownership und den Zurueck-zum-Chat-Link ueber `chat_surface`-Route-Ownership. Sichtbare URLs bleiben `/static/style.css` und `/`; JSON-Fehlerantworten, Exception-Handler-Registrierung, Auth/Session, StaticFiles-Mount, Chat-Dispatch, Runtime, Qdrant und Userdaten bleiben unveraendert. Covered by `tests/test_error_handling.py`.
- **Recipes-Legacy-Return-to-Kanonisierung liest Ziel ueber `recipes_ui`.** Legacy-`/skills`-Ruecksprungwerte werden weiterhin zu `/recipes` bzw. `/recipes/...` kanonisiert, lesen diese Zielroute und den `/recipes`-Prefix nun aber ueber `recipes_ui`-Readpoints statt ueber harte zweite Pfadwahrheiten. Legacy-Route-Entfernung, Recipe-Ausfuehrung, Wizard-Save/Import/Delete/Export, Learned-Promotion, Persistenz, Auth/Session, Runtime, Qdrant und Userdaten bleiben unveraendert. Covered by `tests/test_recipes_routes.py` and `tests/test_module_registry_read_model.py`.
- **UI-Background-Asset-URLs lesen `background-*` ueber `navigation_shell`.** Dynamisch entdeckte UI-Hintergrunddateien behalten ihre sichtbaren `/static/background-*`-URLs, werden vor Ausgabe aber ueber einen neuen `module_static_asset_prefix_path(...)`-Readpoint gegen `navigation_shell`-Ownership geprueft. StaticFiles-Mount, Auth/Public-Path-Klassifikation, Theme-/Background-Persistenz, Bilddateien, Runtime, Qdrant und Userdaten bleiben unveraendert. Covered by `tests/test_error_handling.py`, `tests/test_config_routes.py`, and `tests/test_module_registry_read_model.py`.
- **Recipe-Promptpfade lesen kanonische und Legacy-Roots ueber `recipes`.** `prompts/recipes/` und der explizite Kompatibilitaetsroot `prompts/skills/` werden durch `module_prompt_path(...)` validiert. Default-, Legacy-Kanonisierungs-, Rename- und Delete-Kandidaten sowie die Wizard-Defaults nutzen diese Ownership; unregistrierte Promptpfade werden nicht geloescht. Tests mutieren ausschliesslich `tmp_path`, keine produktiven Recipe-Dateien. Covered by `tests/test_recipe_manifests.py`, `tests/test_recipes_routes.py`, and `tests/test_module_registry_read_model.py`.
- **Auth-Public-Static-Ausnahme liest `/static/` ueber `navigation_shell`.** Die bestehende unauthentifizierte `/static/...`-Klassifikation der Auth-Middleware wird durch `module_public_path_prefix(...)` gegen die explizite `navigation_shell`-Ownership geprueft. `/static`, `/staticx/...` und fehlende Ownership werden nicht als diese Ausnahme akzeptiert; Login-, Session-, Cookie-, Rollen-, API- und CSRF-Semantik bleiben unveraendert. Covered by `tests/test_auth_middleware.py` and `tests/test_module_registry_read_model.py`.

### alpha723 — Changed

- **Memory-Admin-Redirect-Helfer lesen Zielpfade ueber `memory_admin_ui`.** Die zentralen Memory-Redirect-Helfer fuer `/memories`, `/memories/import`, `/memories/create` und `/memories/maintenance` bauen ihre bestehenden `Location`-Ziele nun ueber `module_route_path("memory_admin_ui", ...)` statt ueber zweite harte Pfadwahrheiten. Query-Feedback `info`/`error` bleibt unveraendert; fehlende Route-Ownership faellt geschlossen aus. Keine Memory-Import-/Create-/Delete-/Compress-/Reindex-/Learning-Worker-, Qdrant-/Userdaten- oder Runtime-Aktion wurde ausgefuehrt. Covered by `tests/test_memories_routes.py`.
- **Connections-Surface-Fallbacks lesen Zielpfade ueber `connections_ui_readonly`.** Passive Render- und Page-Context-Defaults fuer die Connections-GET-Surface und die bestehenden Sanitizer-/Import-Sample-Ruecksprung-Fallbacks fuer `/connections` und `/connections/templates` lesen ihre Zielpfade nun ueber `connections_ui_readonly` statt ueber harte zweite Wahrheiten. Erlaubte `return_to`-Pfade, sichtbare GET-URLs und Import-Handler-Semantik bleiben unveraendert; die Tests nutzen nur den nicht-admin Redirect-Pfad und fuehren keinen Sample-Import aus. Covered by `tests/test_config_routes.py`.
- **Recipes-Surface-Defaults lesen Zielpfade ueber `recipes_ui`.** Passive Render- und Page-Context-Defaults fuer die Recipes-GET-Surface lesen `/recipes` nun ueber `recipes_ui` statt ueber harte zweite Wahrheiten. Sichtbare GET-URLs, Templates und Navigation bleiben unveraendert; Learned-Admin-, Wizard-, Import-/Export- und Persistenzpfade bleiben bewusst out-of-scope. Covered by `tests/test_recipes_routes.py`.
- **Config-Hub-Home-Default liest Zielpfad ueber `chat_surface`.** Der passive Logical-Back-Default von `GET /config` liest die bestehende Home-Route `/` nun ueber `chat_surface` statt ueber einen harten Literalpfad. Config-Templates, sichtbare Links, Admin-Gating und POST-/Save-Pfade bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Surface-Sanitizer-Fallback liest Zielpfad ueber `config_ui`.** Der passive `return_to`-Sanitizer fuer Config-Surfaces bekommt seinen bestehenden Default `/config` nun aus `config_ui` statt aus einem harten Literal. Erlaubte Config-Return-to-Pfade, sichtbare URLs, Admin-Gating und POST-/Save-Pfade bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Dependency-Logical-Back-Defaults lesen Zielpfade ueber `config_ui`.** Die passiven Logical-Back-Defaults fuer Config-Routing/Workbench und Config-Intelligence werden nun in der Dependency-Verdrahtung ueber `config_ui` gelesen statt als harte `/config...`-Strings weitergereicht. Routing-Rebuild/Test, LLM-/Embedding-Probes, Profile-Saves und Admin-/Operations-Pfade bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Recipes-Home-Logical-Back-Default liest Zielpfad ueber `chat_surface`.** Der passive Logical-Back-Default von `GET /recipes` liest die bestehende Home-Route `/` nun ueber `chat_surface` statt ueber einen harten Literalpfad. Recipe-Templates, sichtbare Links, POST-/Wizard-/Import-/Export- und Persistenzpfade bleiben unveraendert. Covered by `tests/test_recipes_routes.py`.
- **Config-Intelligence-GET-Fallbacks lesen Zielpfade ueber `config_ui`.** Die passiven Page-Context-Fallbacks von `GET /config/llm/debug`, `GET /config/llm` und `GET /config/embeddings` lesen `/config/workbench` bzw. `/config/intelligence` nun ueber `config_ui`. LLM-/Embedding-Probes, Profile-Saves, Model-Endpoints und File-/Error-Interpreter-Saves bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Updates-Page-Context liest Zielpfade ueber `config_ui` und `release_update`.** `GET /updates` liest den passiven Logical-Back-Default `/config` nun ueber `config_ui` und `page_return_to` `/updates` ueber `release_update`. Update-Ausfuehrung, Helper-Protokoll, Reconnect-Service-Worker, Relogin/Session und Status-JSON bleiben unveraendert. Covered by `tests/test_updates_ui.py`.
- **Config-Intelligence-Redirect-Fallbacks lesen Zielpfade ueber `config_ui`.** Redirect-Fallbacks in Config-Intelligence lesen `/config` und `/config/workbench` nun ueber `config_ui` statt ueber harte Literale. Redirect-Ziel-URLs, LLM-/Embedding-Probes, Profil-Save-/Load-/Delete-Logik, Model-Endpoints, File-/Error-Interpreter-Saves und Runtime-Reloads bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Intelligence-Redirect-Ziele lesen Zielpfade ueber `config_ui`.** LLM-Debug-Clear, LLM-Profil-/Save-/Test-Redirects und Embedding-Profil-/Save-/Test-Redirects behalten ihre sichtbaren `/config/llm`, `/config/llm/debug` und `/config/embeddings`-Ziele, lesen die Zielbasen aber nun ueber `config_ui`. Echte LLM-/Embedding-Probes, Model-Endpoint-Fetches, Profilvalidierung, Embedding-Switch-Confirmation und Runtime-Reload-Semantik bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Workbench-Editor-Redirect-Ziele lesen Zielpfade ueber `config_ui`.** Error-Interpreter- und Files-Editor-Save/Error-Redirects behalten ihre sichtbaren `/config/error-interpreter`- und `/config/files`-Ziele, lesen die Zielbasen aber nun ueber `config_ui`. Produktive Dateien, File-Allowlist, Parser-Semantik und Runtime-Reload-Verhalten bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Auth-Middleware-Config-Guard-Redirects lesen Zielpfade ueber `config_ui`.** Admin-only- und Advanced-View-HTML-Redirects der Auth-Middleware behalten ihre sichtbaren `/config?error=...`-Ziele, lesen die Zielbasis aber nun ueber `config_ui`. Auth-/Session-/CSRF-/Cookie-Policy, Login-/Session-Expired-Pfade und Rollenentscheidungen bleiben unveraendert. Covered by `tests/test_auth_middleware.py`.
- **Config-Routing-Legacy-Redirect-Fallback liest Zielpfad ueber `config_ui`.** Der Legacy-GET-Redirect von `/config/routing?routing_query=...` zum Routing-Workbench behaelt seine Ziel-URL unveraendert, liest den bestehenden Ruecksprung-Fallback `/config` aber nun ueber `config_ui` statt ueber einen harten Literalpfad. Routing-Testbench, Index-Status/-Rebuild, Qdrant, Runtime-Reloads und Routing-Saves bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Recipes-Learned-GET-Fallbacks lesen Zielpfade ueber `recipes_ui`.** Readonly-/Error-Fallbacks von `GET /recipes/learned/maintenance` und `GET /recipes/learned/promote-preview` lesen `/recipes/learned` nun ueber `recipes_ui` statt ueber harte zweite Pfadwahrheiten. Promote-/Dismiss-/Delete-POSTs, Store-Mutationen, Experience-Memory-Cleanup, Wizard/Import/Export und Runtime bleiben unveraendert. Covered by `tests/test_recipes_routes.py`.
- **Recipes-Wizard-GET-Defaults lesen Zielpfade ueber `recipes_ui`.** Der Readonly-Redirect und der Logical-Back-Default von `GET /recipes/wizard` lesen `/recipes` nun ueber `recipes_ui` statt ueber harte Literalpfade. Wizard-Save, Rezeptdateien, Keyword-Generierung, Runtime-Reloads, Import/Export/Delete und Admin-Policy bleiben unveraendert. Covered by `tests/test_recipes_routes.py`.
- **Recipes-POST-Fallbacks lesen Zielpfade ueber `recipes_ui`/`chat_surface`.** Learned-Admin-, Save-, Wizard-, Import-, Import-Sample- und Delete-Redirects behalten ihre sichtbaren `/recipes`, `/recipes/learned` und `/recipes/wizard`-Ziele, lesen Surface-/Home-Fallbacks aber nun ueber `recipes_ui` bzw. `chat_surface`. Recipe-Ausfuehrung, produktive Rezeptdateien, Learned-Store-Mutationen, Import-/Export-Payloads, LLM-Keyword-Generierung und Runtime-Reloads bleiben unveraendert. Covered by `tests/test_recipes_routes.py`.
- **Recipes-Helper-Defaults lesen Zielpfade ueber `recipes_ui`.** Learned-Admin-Success- und Sample-Import-Success-Helfer behalten ihre sichtbaren `/recipes/learned`- bzw. `/recipes`-Defaults, lesen diese Default-Ziele aber nun ueber `recipes_ui`. Promotion-, Sample-Import-, Manifest- und Runtime-Semantik bleiben unveraendert. Covered by `tests/test_recipes_routes.py` and `tests/test_recipe_samples.py`.
- **Config-Debug-Legacy-Redirect liest Zielpfade ueber `config_ui`.** `GET /config/debug` leitet weiterhin nach `/config/admin-mode`, liest Ziel und Fallback aber nun ueber `config_ui` statt ueber harte Literalpfade. Debug-Save, User-/Security-Settings, Auth/Session, Runtime-Reloads und Operations bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Persona-Redirect-Fallbacks lesen Zielpfade ueber `config_ui`.** Appearance-, Language- und Prompt-Save/Error-Redirects behalten ihre sichtbaren Ziel-URLs, lesen Ziel und Fallback aber nun ueber `config_ui` statt ueber harte Literalpfade. Theme-/Language-/Prompt-Persistenz, Cookie-Verhalten, Runtime-Reloads, Prompt-Resolver und i18n-Cache bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Access-Debug-Save-Fallbacks lesen Zielpfade ueber `config_ui`.** `/config/admin-mode/save` und `/config/users/debug-save` behalten ihre sichtbaren Redirect-Ziele, lesen den Fallback `/config` aber nun ueber `config_ui`. Security-Store-Userverwaltung, Guardrail-Persistenz, Auth-/Session-Policy und Operations bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Access-Security-Settings-Fallbacks lesen Zielpfade ueber `config_ui`.** `/config/security/save` und `/config/users/security-save` behalten ihre sichtbaren Redirect-Ziele, lesen den Fallback `/config` aber nun ueber `config_ui`. Security-Store-Userverwaltung, Guardrail-Persistenz, Auth-/Session-Policy und Operations bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Access-User-Management-Redirects lesen Zielpfade ueber `config_ui`.** `/config/users/create` und `/config/users/update` behalten ihre sichtbaren `/config/users`-Redirect-Ziele, lesen Ziel und Fallback aber nun ueber `config_ui`. Produktive Security-Store-Daten, Passwort-/Cookie-/Session-Policy und Userverwaltungs-Semantik bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Access-Guardrail-Fallbacks lesen Zielpfade ueber `config_ui`.** Guardrail-Save/Delete/Import-Sample-Redirects behalten ihre sichtbaren `/config/security`-Ziele, lesen Ziel und Fallback aber nun ueber `config_ui`. Guardrail-Policy, AI-Draft, Runtime-Routing, Security-Store-Userverwaltung und Auth-/Session-Policy bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Operations-Logs-Fallbacks lesen Zielpfade ueber `ops_config_backup`/`config_ui`.** Log-Settings-Save, Cleanup und Reset behalten ihre sichtbaren `/config/logs`-Ziele, lesen Ziel und Fallback aber nun ueber `ops_config_backup` bzw. `config_ui`. Factory-Reset, Backup-Import/Export, Service-Restart, Qdrant-Cleanup und echte Runtime-/Logdateien bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Backup-Import-Fallbacks lesen Zielpfade ueber `config_backup`/`config_ui`.** Backup-Import-Success/Error-Redirects behalten ihre sichtbaren `/config/backup`-Ziele und lesen den Fallback `/config` nun ueber `config_ui`. Backup-Payloads, Restore-Parser, Secure-Store-Semantik, Runtime-Reloads und produktive Backup-Dateien bleiben unveraendert. Covered by `tests/test_config_backup.py`.
- **Config-Routing-Admin-Fallbacks lesen Zielpfade ueber `config_ui`.** Routing-Index-Rebuild- und Qdrant-Settings-Redirects behalten ihre sichtbaren `/config/routing`-Ziele, lesen Ziel und Fallback aber nun ueber `config_ui`. Routing-Dispatch, echte Qdrant-Zugriffe, Runtime-Routing, WebSearch/Source-Authority, Guardrails und Latenz bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Config-Skill-Routing-Fallbacks lesen Zielpfade ueber `config_ui`.** Skill-Routing-Save/Suggest/Suggest-All/Rebuild-Redirects behalten ihre sichtbaren `/config/skill-routing`-Ziele, lesen Ziel und Fallback aber nun ueber `config_ui`. Routing-Dispatch, echte LLM-Keyword-Generierung, Runtime-Routing, WebSearch/Source-Authority, Qdrant, Guardrails und Latenz bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Auth-Surface-Auto-Memory-Fehlerredirect liest Zielpfad ueber `memory_admin_ui`.** Der lokale Fehlerpfad von `POST /set-auto-memory` behaelt sein sichtbares `/memories/config?error=...`-Ziel, liest die Zielbasis aber nun ueber `memory_admin_ui`. Erfolgreiche Auto-Memory-Persistenz, Runtime-Reload, Cookies und Auth-/Session-Policy bleiben unveraendert. Covered by `tests/test_auth_surface_routes.py`.
- **Memory-Learning-Worker-Redirects lesen Zielpfade ueber `memory_admin_ui`.** Retry-, Flush- und Admin-required-Feedback behalten ihre sichtbaren `/memories/maintenance?...`-Ziele, lesen die Zielbasis aber nun ueber `memory_admin_ui`. Job-Queue, Retry-/Flush-Semantik, Worker-Persistenz und Learning-Runtime bleiben unveraendert. Covered by `tests/test_memories_routes.py`.
- **Memory-Overview-Guard-Redirects lesen Zielpfade ueber `memory_admin_ui`.** Memory-inactive- und No-admin-Guards behalten ihre sichtbaren `/memories?error=...`-Ziele, lesen die Zielbasis aber nun ueber `memory_admin_ui`. Memory-/Qdrant-Mutationen, Learning-Candidate-Ausfuehrung und Auto-Memory-Detailredirects bleiben unveraendert. Covered by `tests/test_memories_routes.py`.
- **Auto-Memory-Feedback-Redirects lesen Zielpfade ueber `memory_admin_ui`.** Saved- und Error-Feedback behalten ihre sichtbaren `/memories/auto-memory?...`-Ziele, lesen die Zielbasis aber nun ueber `memory_admin_ui`. Auto-Memory-Extraktion, Personal-Claim-Logik, Learning-Candidate-Ausfuehrung und Qdrant-Mutationen bleiben unveraendert. Covered by `tests/test_memories_routes.py`.
- **Memory-Config-Feedback-Redirects lesen Zielpfade ueber `memory_admin_ui`.** Saved-, Error- und Rollup-Feedback behalten ihre sichtbaren `/memories/config?...`-Ziele inklusive `#rollup`, lesen die Zielbasis aber nun ueber `memory_admin_ui`. Backend-/Config-Persistenz, Compression-Ausfuehrung, Cookies und Runtime-Reloads bleiben unveraendert. Covered by `tests/test_memories_routes.py`.
- **Auth-Middleware-Home-Guard-Redirects lesen Zielpfade ueber `chat_surface`.** No-admin- und No-settings-HTML-Guards behalten ihre sichtbaren `/?error=...`-Ziele, lesen die Zielbasis aber nun ueber `chat_surface`. Auth-/Session-/CSRF-/Cookie-Policy, Login-/Session-Expired-Pfade und Rollenentscheidungen bleiben unveraendert. Covered by `tests/test_auth_middleware.py`.
- **Auth-Surface-Login-Redirects lesen Zielpfade ueber `auth_ui`.** Login-Fehlerredirects und Logout behalten ihre sichtbaren `/login?error=...`- bzw. `/login`-Ziele, lesen die Zielbasis aber nun ueber `auth_ui`. Erfolgreiche Login-Ziele, Rate-Limit-Schwellen, Bootstrap, Cookies und Session-Policy bleiben unveraendert. Covered by `tests/test_auth_surface_routes.py`.
- **Auth-Middleware-Login-Redirects lesen Zielpfade ueber `auth_ui`.** Login-required- und Session-expired-Redirects der Middleware behalten ihre sichtbaren `/login?next=...`- und `/session-expired?next=...`-Ziele; auch JSON-`login_url` liest die Zielbasis ueber `auth_ui`. Public-Path-Klassifikation, Auth-/Session-Aufloesung, Cookie-Clearing, CSRF und Rollenentscheidungen bleiben unveraendert. Covered by `tests/test_auth_middleware.py`.
- **Update-Relogin liest Login-Ziel ueber `auth_ui`.** `GET /updates/relogin` behaelt sein sichtbares `/login?next=...`-Ziel und das bestehende scoped Cookie-Clearing, liest die Login-Zielbasis aber nun ueber `auth_ui`. Update-Ausfuehrung, Status-APIs, Helper-Protokoll und Reconnect-Service-Worker bleiben unveraendert. Covered by `tests/test_updates_ui.py`.
- **Set-Username liest Home-Ziel ueber `chat_surface`.** `POST /set-username` behaelt sein sichtbares `/`-Redirect-Ziel, liest die Zielbasis aber nun ueber `chat_surface`. Username-Sanitizing, Auth-Override, Cookie-Namen/-Werte/-Flags und Session-ID-Erzeugung bleiben unveraendert. Covered by `tests/test_auth_surface_routes.py`.
- **Return-to-Home-Fallbacks lesen Home ueber `chat_surface`.** Die generischen Config- und Recipes-Return-to-Helfer behalten fuer invalid/leere Fallbacks den sichtbaren `/`-Ruecksprung, lesen diese Home-Zielbasis aber nun ueber `chat_surface`. Gueltige `return_to`-/Referer-Logik, Query-Rewriting, Config-/Recipe-Saves und Runtime-Verhalten bleiben unveraendert. Covered by `tests/test_config_routes.py` and `tests/test_recipes_routes.py`.
- **Connections-SearXNG-Link liest Ziel ueber `web_search`.** Der passive SearXNG-Konfigurationslink in der Connections-Uebersicht behaelt sein sichtbares `/config/connections/searxng?return_to=...`-Ziel, liest die Zielbasis aber nun ueber `web_search`. SearXNG-Probes, WebSearch-Ausfuehrung, Source Authority, Profilpersistenz und Sample-Import bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Memory-Learning-Preview-Redirects lesen Ziel ueber `memory_admin_ui`.** Learning-Candidate-Regressions-, Pytest-Prepare-, Artifact-Review-, Activation-Preflight- und Activation-Redirects behalten ihre sichtbaren `/memories/learning-candidate/apply-preview?...`-Ziele, lesen die Zielbasis aber nun ueber `memory_admin_ui`. Store-Updates, Regression-Ausfuehrung, Artifact-Review-Learning, Activation-Preflight und Active-Hint-Storage bleiben unveraendert. Covered by `tests/test_memories_routes.py`.
- **Chat-Learn-Rezeptlink liest Ziel ueber `recipes_ui`.** Der Link nach beendetem Chat-Lernmodus bleibt sichtbar `/recipes/learned?recipe_ref=...`, liest die Zielbasis aber nun ueber `recipes_ui` und faellt ohne Owner geschlossen aus. Chat-Pipeline, Learn-Mode-Erfassung, Learned-Recipe-Persistenz, Promotion und Runtime bleiben unveraendert. Covered by `tests/test_chat_tooling.py`.
- **Settings-Navigation liest passive Hrefs ueber Modul-Readpoints.** Settings-, Persona-, Update-, Connections- und Recipes-Navigationslinks behalten ihre sichtbaren URLs, werden beim Rendern aber ueber `config_ui`, `release_update`, `connections_ui_readonly` und `recipes_ui` aufgeloest. Active-Nav-Matching, Legacy-Nav-IDs, Route-Registrierung, Auth/Session und Runtime bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Admin-/Memory-Navigation liest passive Hrefs ueber Modul-Readpoints.** Admin-Gruppen, Admin-Leaf-Links und Memory-Subnav behalten ihre sichtbaren URLs, werden beim Rendern aber ueber `config_ui`, `ops_config_backup`, `recipes_ui`, `stats_ui` und `memory_admin_ui` aufgeloest. Active-Nav-Matching, Legacy-Nav-IDs, Route-Registrierung, Runtime, Memory-Daten und Qdrant bleiben unveraendert. Covered by `tests/test_config_routes.py`.
- **Memory-Graph-Links lesen passive Ziele ueber Modul-Readpoints.** Auto-Memory-Overview-Check, Notes-Graphlinks, Recipe-Experience-Graphlinks und System-/Qdrant-Setup-Fallbacks behalten ihre sichtbaren `/memories/auto-memory`, `/notes`, `/recipes/learned` und `/memories/config#qdrant-access`-Ziele, lesen die Zielbasen aber ueber `memory_admin_ui`, `documents` und `recipes_ui`. Memory-Browser-Aktionen, Learning Worker, Auto-Memory, Qdrant, Userdaten und Runtime bleiben unveraendert. Covered by `tests/test_memories_routes.py`.

### alpha722 — Changed

- **Update-Reconnect-Health-URL liest ueber den `release_update` Readpoint.** Der Reconnect-Service-Worker bekommt die bestehende `/health`-Poll-URL nun aus `module_route_path("release_update", "/health")` injiziert statt einen harten JS-Literalpfad zu behalten; fehlt der Owner, faellt `/update-reconnect-sw.js` geschlossen aus. `updates.html` nutzt denselben Readpoint fuer den JS-Fallback. Keine Update-Ausfuehrung, kein Helper-Protokoll, keine Route-Generierung, keine Runtime-/Qdrant-/Userdaten-Aktion wurde geaendert oder ausgefuehrt. Covered by `tests/test_updates_ui.py`.

### alpha721 — Changed

- **Passive Update-/Reindex-/Routing-Guard-Readpoints gebuendelt.** `release_update`-eigene Python-Redirects und Update-Live-Health-URLs, Memory-Reindex-Legacy-/Admin-Redirects in `ops_config_backup` und Config-Routing-Admin-Guard-Redirects zur Recipes-Uebersicht lesen ihre bestehenden Zielbasen jetzt ueber `release_update`, `ops_config_backup` bzw. `recipes_ui`. Sichtbare `Location`-Header und Poll-Ziele bleiben gleich; keine Update-Ausfuehrung, Reindex-Ausfuehrung, Routing-Rebuild-/Suggest-Ausfuehrung, Runtime-/Qdrant-/Userdaten-Aktion wurde produktiv ausgefuehrt. Covered by `tests/test_updates_ui.py` and `tests/test_config_routes.py`.

### alpha720 — Changed

- **Passive Config-/Connection-Redirect-Readpoints gebuendelt.** Der Legacy-Redirect `/config/connections/email` liest sein bestehendes SMTP-Ziel ueber `smtp_ui`. Config-Admin-/Module-/Unknown-Group-, Security-Sample-Import-, Config-Backup-Admin-Fail-, Operations-Service-Restart-Fail- und Logs-Error-Redirects lesen ihre bestehenden Zielbasen ueber `config_ui` bzw. `ops_config_backup`. Sichtbare `Location`-Header bleiben gleich; keine Service-Restart-, Backup-Export-/Import-, Guardrail-Import-, Runtime-/Qdrant-/Userdaten-Aktion wurde produktiv ausgefuehrt. Covered by `tests/test_config_routes.py`.

### alpha719 — Changed

- **Passive Python-Redirect-/Stats-Meta-Readpoints weiter gebuendelt.** Stats-Operator-/Health-/Sidecar-Links sowie Stats-Pricing-/Recipe-Review-/Reset-Redirects lesen ihre bestehenden Ziele ueber `stats_ui`, `release_update` und `recipes_ui` Registry-Readpoints. Notes-Save/Delete/Move/Bulk-Move/Folder/Create/Rename/Export-Fehler-Redirects lesen die bestehende `/notes`-Basis ueber den `documents` Readpoint. Sichtbare URLs und Redirect-Ziele bleiben gleich; keine Save-/Delete-/Move-/Export-/Index-/Runtime-/Qdrant-/Userdaten-Aktion wurde gegen produktive Daten ausgefuehrt. Covered by `tests/test_stats_routes.py`, `tests/test_notes_routes.py`, and registry/release hygiene gates.

### alpha718 — Changed

- **Passive Template-/JS-UI-Readpoints weiter gebuendelt.** Connection-Intro-Backlinks, Config-Backup-Export-/Import-Fallbacks, Memory-Browser-/Brain-Delete-URLs, der Memory-Fullscreen-Link, Recipe-Wizard-Config-Link sowie Prompt-/Files-Editor Picker-/Save-URLs lesen ihre bestehenden sichtbaren Ziele jetzt ueber Modul-Readpoints statt ueber zweite harte UI-Wahrheiten. `config_ui` und `memory_admin_ui` deklarieren die dafuer benoetigten bestehenden UI-/POST-Zielpfade explizit; Route-Registration bleibt unveraendert. Keine Delete-/Save-/Export-/Import-/Runtime-/Qdrant-/Userdaten-Aktion wurde ausgefuehrt. Covered by `tests/test_help_page.py`, `tests/test_config_routes.py`, `tests/test_config_backup.py`, `tests/test_memories_routes.py`, `tests/test_recipes_routes.py`, and `tests/test_module_registry_read_model.py`.

### alpha717 — Changed

- **Template-Route-/Asset-Readpoints fail-closed statt auf harte UI-Pfade zurueckzufallen.** Registry-gestuetzte Template-Links, Formziele, HX-Ziele, Shell-Assets und Route-Prefixes nutzen in `aria/templates/` keine zweite harte `or "/..."`-Wahrheit mehr. Wenn ein Modul seine Route oder sein Asset nicht besitzt, rendert der Template-Readpoint leer statt den alten Pfad trotzdem zu verwenden. Keine Handler-/Redirect-/POST-/Save-/Export-/Probe-/Runtime-/Qdrant-/Userdaten-Semantik wurde geaendert oder ausgefuehrt. Covered by `tests/test_help_page.py`, `tests/test_config_routes.py`, `tests/test_notes_routes.py`, `tests/test_memories_routes.py`, `tests/test_recipes_routes.py`, `tests/test_stats_routes.py`, and `tests/test_module_registry_read_model.py`.

### alpha716 — Changed

- **Export-/Operations-nahe Python-Route-Readpoints fail-closed statt auf harte Pfade zurueckzufallen.** Embedding-Wechsel-Guard, Config-Backup-Seitenkontext und Memory-Reindex-Seitenkontext nutzen `memory_export` bzw. `memory_admin_ui` Route-Ownership jetzt strikt; die produktive Python-Inventur fuer `module_route_path(...) or "/..."`/`or route_path` in `aria/web` und `aria/core` ist damit leer. Keine Export-/Backup-/Reindex-Ausfuehrung, keine POST-/Save-/Runtime-/Qdrant-/Userdaten-Aenderung. Covered by `tests/test_config_routes.py`, `tests/test_config_backup.py`, and `tests/test_module_registry_read_model.py`.

### alpha715 — Changed

- **Passive Route-Ownership-Readpoints fail-closed statt auf alte harte sichtbare GET-/UI-Pfade zurueckzufallen.** Config-, Connections-, Recipes-, Documents/Notes-, Memory-Admin-, Stats-, Website-, Chat- und Chat-Catalog-Link-Helper brechen bei fehlender Route-Ownership nun explizit ab, statt `module_route_path(...) or "/..."` oder `or route_path` als zweite Wahrheit zu behalten. `config_ui` besitzt nun auch die bestehende `/config/access` Route im Manifest. Operations-/Memory-Export-nahe Reste bleiben bewusst als separater Block ausgeschlossen. Keine Route-Registration aus Manifesten, keine POST-/Save-/Probe-/Export-/Reindex-/Runtime-/Qdrant-/Userdaten-Aenderung. Covered by `tests/test_config_routes.py`, `tests/test_recipes_routes.py`, `tests/test_memories_routes.py`, `tests/test_document_link_readpoints.py`, `tests/test_website_link_readpoints.py`, `tests/test_config_link_readpoints.py`, `tests/test_connection_context_helpers.py`, `tests/test_stats_routes.py`, `tests/test_chat_tooling.py`, and `tests/test_session_recovery.py`.

### alpha714 — Changed

- **Passive Template-Ownership-Readpoints fail-closed statt auf alte harte Template-Namen zurueckzufallen.** Config-, Recipe-, Notes/Documents-, RSS-/Connection-Config- und Memory-Admin-GET-Helper brechen bei fehlender Modul-Template-Ownership nun explizit ab, statt `module_template_name(...) or template_name` als zweite Wahrheit zu behalten. `config_ui` besitzt die konkreten Config-Templates; `ui_admin` beansprucht keine breiten `config*.html`-/`_config*.html`-Wildcards mehr. Keine Route-Registration aus Manifesten, keine POST-/Save-/Probe-/Export-/Rebuild-/Runtime-/Qdrant-/Userdaten-Aenderung. Covered by `tests/test_config_routes.py`, `tests/test_recipes_routes.py`, `tests/test_notes_routes.py`, `tests/test_memories_routes.py`, `tests/test_module_registry.py`, and `tests/test_module_registry_read_model.py`.

### alpha713 — Changed

- **Navigation-Shell-Assets lesen globale Shell-URLs ueber Registry-Readpoints.** `navigation_shell` besitzt jetzt `/favicon.ico` sowie die expliziten Shell-Assets fuer Favicons, Apple Touch Icon, HTMX, Stylesheet und Brandlogo. `base.html`, der Memory-Fullscreen-Header und die `/favicon.ico`-Route nutzen diese Readpoints; sichtbare URLs bleiben `/favicon.ico` und `/static/...` mit Release-Cache-Busting. StaticFiles-Mount, Auth/Session, Routing, Memory-/Qdrant-Daten und Runtime bleiben unveraendert. Covered by `tests/test_help_page.py`, `tests/test_memories_routes.py::test_memories_fullscreen_semantic_request_without_point_stays_in_structure_browser`, and `tests/test_module_registry_read_model.py`.
- **Chat-Surface-Home-GET und Brand-Home-Links lesen ueber einen eigenen Registry-Readpoint.** Das neue passive Modul `chat_surface` besitzt `GET /` und `chat.html`; der GET-Handler nutzt den Template-Readpoint, `base.html` und der Memory-Fullscreen-Header nutzen den Home-Route-Readpoint. Sichtbare Links bleiben `href="/"`; POST `/chat`, Pending/Confirmation, Auth/Session, Runtime, Qdrant, Userdaten und Route-Registration bleiben unveraendert. Covered by `tests/test_session_recovery.py::test_chat_surface_home_get_uses_registry_template_readpoint`, `tests/test_help_page.py`, `tests/test_memories_routes.py::test_memories_fullscreen_semantic_request_without_point_stays_in_structure_browser`, and `tests/test_module_registry_read_model.py`.

### alpha712 — Changed

- **Watched-Website-Antwortlinks lesen die bestehende Website-UI-Route ueber den Registry-Readpoint.** Chat-Websites-Antworten, selected-action-not-handled-Fallbacks und Website-Runtime-Empty/List/Read-Texte nutzen nun einen gemeinsamen `website_ui` Helper mit statischem Fallback. Der sichtbare URL-Vertrag bleibt `/config/connections/websites`, `?mode=create#create-new` und `?website_ref=...#manage-existing`; Website/WebSearch-Runtime, Connection-Persistence, Routing, Qdrant und Userdaten bleiben unveraendert. Covered by `tests/test_website_link_readpoints.py`, `tests/test_chat_websites_flows.py`, `tests/test_chat_tooling.py::test_website_action_not_handled_message_uses_website_route_readpoint`, and `tests/test_aria_turn_arbitration.py::test_selected_side_action_without_executor_result_does_not_fall_back_to_chat`.

### alpha682 — Fixed

- **WebSearch-Profilzustand bleibt konsistent zwischen Settings, Pipeline und Runtime-Skill.** `connections.searxng` wird jetzt vor der finalen Settings-Validierung normalisiert, auch wenn kein Secure Store aktiv ist oder der Secure-Store-Pfad frueh zurueckkehrt. Die Pipeline erzeugt den WebSearch-Skill lazy aus dem aktuellen Settings-Zustand und reicht denselben Getter an die RecipeRuntime weiter, statt dauerhaft vom Init-Zustand abzuhaengen. Dadurch soll ein sichtbarer UI-Zustand mit vorhandenen SearXNG-Profilen nicht mehr im WebSearch-Pfad als `Keine SearXNG-Verbindung konfiguriert` enden. Bestehende Test-/Runtime-Injektionen eines WebSearch-Skills bleiben autoritativ. Covered by `tests/test_config_env_overrides.py::test_load_settings_normalizes_invalid_searxng_connection_section`, `tests/test_pipeline.py::test_pipeline_lazily_enables_web_search_when_profile_state_becomes_visible`, and the existing WebSearch profile/source-plan regression tests.

### alpha681 — Fixed

- **Public-vs-local Current-Fact-Kollisionen fragen jetzt zwingend zurueck, bevor eine lokale Connection-Action geplant wird.** Wenn eine aktuelle oeffentliche Faktfrage wie `welche Version ist aktuell bei Home Assistant` durch eine passende lokal konfigurierte Connection faelschlich als Runtime-Action gebunden wird, ersetzt die MetaCatalog-Recovery den Turn vor Web/Runtime durch `ask_clarification`: oeffentliche aktuelle Version/Information oder lokale Instanz/Quelle auf dem gebundenen Ziel. Der Fix ist generisch auf `ConnectionActionContract` gebaut, nicht SSH- oder Home-Assistant-spezifisch, und schuetzt damit auch HTTP-API/weitere modulare Connection-Actions. Explizite lokale Ziel-/Instanzfragen wie `welche Version laeuft auf ubnsrv-homeassistant` bleiben Runtime-faehig. Covered by `tests/test_agentic_context_runtime.py::test_current_fact_connection_action_without_explicit_local_authority_requires_clarification`, `...::test_current_fact_connection_clarification_is_generic_for_non_ssh_actions`, `...::test_current_fact_named_connection_ref_does_not_require_connection_clarification`, and `...::test_current_fact_connection_clarification_arbitration_asks_public_or_local`.
- **Arbeitsvertrag nachgezogen:** `docs/ai-context/07-agentic-routing-acceptance-contract.md` verlangt nun explizit "Problemklasse vor Fix-Ort", damit sichtbare Einzelfaelle wie `SSH/Home Assistant` nicht mehr zu engen Sonderfall-Patches fuehren.

### alpha680 — Fixed

- **Aktuelle externe Faktfragen werden nach falschem MetaCatalog-Connections-Routing auf Web-Recovery gezogen.** Wenn Prompts wie `welches ist die neuste apple watch ultra`, `was ist das neueste iPhone` oder `welche Version ist aktuell bei Home Assistant` vom MetaCatalog faelschlich als lokale `connections:search`/semantische RSS-Action geplant werden, gewinnt nun der bestehende source-bound Web-Fallback statt einer leeren lokalen Quellenantwort oder eines unklaren Action-Preflights. Explizit genannte Feed-Leseauftraege wie `lies mac-i-neueste-meldungen ...` bleiben ausgenommen. Covered by `tests/test_agentic_context_runtime.py::test_current_product_question_misrouted_to_empty_connections_requires_web_recovery`, `tests/test_agentic_context_runtime.py::test_current_product_question_misrouted_to_semantic_rss_action_requires_web_recovery`, and `tests/test_agentic_context_runtime.py::test_explicit_named_rss_read_does_not_require_web_recovery`.
- **Contract-Preflight bestaetigt keine unsichtbare Aktion mehr.** Bei routed Pending-Actions mit `turn_contract_action_preflight` zeigt der Confirmation-Text jetzt eine konkrete Payload-Zusammenfassung aus Capability, Ziel und Inhalt, z.B. `RSS lesen: rss/mac-i-neueste-meldungen; Home Assistant Version`, statt die widerspruechliche Dry-Run-Summary `ARIA wuerde diese Aktion ohne weitere Rueckfrage freigeben.` zu uebernehmen. Covered by `tests/test_agentic_context_runtime.py::test_routed_confirmation_with_contract_preflight_shows_concrete_read_action`.

### alpha679 — Fixed

- **Weak-only Webquellen duerfen aktuelle Produkt-/Versionsantworten nicht mehr tragen.** Wenn ein Source-Plan `authority_mode=prefer_primary` mit bevorzugten/offiziellen Quellen fuer aktuelle Produkt-, Modell-, Versions- oder Release-Fakten verlangt, aber keine bevorzugte Quelle gefunden wird, fail-closed WebSearch jetzt mit `web_source_no_reliable_sources` statt News-/Leak-/Deal-Treffer als Antwortkontext weiterzugeben. Das verhindert konkrete Antworten wie Apple Watch Ultra 2 aus schwachen News nach einer offiziellen Ultra-3-Antwort, iPhone-18-Geruechte als "neuestes iPhone" oder Home-Assistant-Versionen aus nicht-offiziellen Artikeln. Normale nicht-current Recherche darf weak-only Quellen weiterhin, klar als schwach markiert, weitergeben. Covered by `tests/test_searxng_client.py::test_web_search_skill_fails_closed_for_current_product_with_only_weak_candidates`, `tests/test_searxng_client.py::test_web_search_skill_fails_closed_for_current_product_when_preferred_domains_are_missing`, and `tests/test_web_search_skill_still_continues_with_non_current_research_when_preferred_domains_are_missing`.

### alpha678 — Fixed

- **Aktuelle externe Fakten fallen nicht mehr auf quellenloses Modellwissen zurueck.** Prompts wie `welches ist die neuste apple watch ultra` werden als aktuelle externe Fakten erkannt und in einen source-bound Web-Kontextvertrag umgebogen, selbst wenn der Meta-Katalog bereits eine selbstbewusste Direct Answer ohne Kontext geliefert hat. Wenn Websuche in der Instanz nicht verfuegbar ist, antwortet ARIA ehrlich, dass eine aktuelle Webquelle noetig ist, statt eine Produktversion zu raten. Lokale Autoritaeten wie SSH-/Server-/Dokument-/ARIA-Build-Fragen bleiben ausgenommen. Covered by `tests/test_agentic_context_runtime.py::test_confident_current_product_answer_without_context_is_not_direct_answer`, `tests/test_agentic_context_runtime.py::test_current_product_question_without_web_search_does_not_guess`, and `tests/test_pipeline.py::test_pipeline_recovers_confident_current_product_answer_without_sources_to_web_context`.

### alpha677 — Fixed

- **Personal "all my servers" claims now restore full SSH fleet scope instead of preserving an incomplete MetaCatalog subset.** If Personal Context selects a claim that declares "alle meine Server"/"all my servers" and MetaCatalog only passes a partial SSH ref list, ARIA promotes the action draft to `target_scope_authority:full_kind` so the existing config-bound full-kind executor covers the configured SSH fleet. Named subsets such as "meine Datenbank-Server" remain explicit subsets and are not widened. This targets the live `Wie fit sind meine Server?` regression where ARIA honestly reported 5 of 14 checked but should have planned all configured SSH servers. Covered by `tests/test_agentic_context_runtime.py::test_aria_turn_seed_promotes_all_my_servers_claim_subset_to_full_kind_scope` and `tests/test_agentic_context_runtime.py::test_aria_turn_seed_keeps_personal_server_subset_without_all_server_claim`.

### alpha676 — Fixed

- **Multi-target SSH health checks canonicalize before the multi-target policy gate even when the LLM omits `target_intent`.** If a multi-target SSH contract already has a plural target scope and an observational health command shape (`uptime`, `df -h`, `free -h`, `hostname`, `top`/formatted variants), ARIA now normalizes it to the existing read-only profile `uptime -p && df -h / && free -h` before policy evaluation. Mutating commands are still excluded and the SSH policy is not weakened. This targets the live `Wie fit sind meine Server?` and `Pruefe Uptime, Root-Disk und RAM auf allen SSH-Zielen` failures where all/most targets were recognized, but the LLM-formatted command was rejected before normalization. Covered by `tests/test_pipeline.py::test_apply_ssh_plural_multi_target_resolution_infers_health_without_target_intent_note`.
- **Explicit "all SSH targets" requests use config full-kind authority instead of an incomplete LLM subset.** When the user asks for all SSH targets and MetaCatalog supplies only part of the configured set, the capability draft is promoted to `target_scope_authority:full_kind`; the existing full-kind executor completion then expands against current config. This preserves fail-closed behavior for non-full-kind subsets and targets the live 11-of-14 pattern. Covered by `tests/test_agentic_context_runtime.py::test_aria_turn_seed_all_ssh_targets_promotes_incomplete_llm_subset_to_full_kind_scope`.
- **Unknown SSH refs no longer fall through to free chat with invented alternatives.** If a no-context/no-action fallback sees an unknown ref-like SSH target from a configured ref family, ARIA returns the normal config-bound missing-profile answer instead of letting the final chat composer suggest ungrounded servers. This targets the live `ubnsrv-gigegugel` hallucinated alternatives. Covered by `tests/test_pipeline.py::test_unknown_ssh_ref_missing_profile_plan_uses_config_authority`.

### alpha675 — Fixed

- **Valid single-target SSH actions are no longer blocked by irrelevant personal-context matches.** If the turn is a normal connection/action contract, no personal claim is selected, and the model nevertheless labels personal context as `matched`, runtime now normalizes that irrelevant match to `independent_context` instead of failing the whole action contract with `personal_context_match_requires_selected_claim`. Personal-memory actions (`memory_forget`, `personal_memory_capture`) stay strict. This targets the live `Pruefe den Status von srv-dev02` failure after `alpha674`. Covered by `tests/test_turn_decision_contract.py::test_turn_decision_action_normalizes_irrelevant_unselected_personal_match`.
- **Broad multi-target fitness checks use an allowable read-only SSH health profile.** A health/fitness command containing pipes such as `uptime && df -h / | tail -1 && free -h | grep Mem` is normalized, for multi-target SSH only, to the existing read-only profile `uptime -p && df -h / && free -h` before the multi-target policy gate. The SSH policy is not weakened and generic pipes remain confirmation/block candidates. This targets the live `Wie fit sind meine Server?` fallback to "which profile?" despite 14 bound targets. Covered by `tests/test_pipeline.py::test_apply_ssh_plural_multi_target_resolution_adapts_piped_health_command`.

### alpha674 — Fixed

- **SSH-/Connection-Inventarfragen bleiben source-bound, auch wenn MetaCatalog ausfaellt.** Wenn die MetaCatalog-Route in den sicheren Fallback faellt und der User nach bekannten SSH-Zielen/Connection-Quellen fragt, erzeugt Runtime nun einen `connections:inventory`-ContextRequest statt eines freien Chat-Fallbacks. `Welche SSH-Ziele kennst du?` wird dadurch aus der konfigurierten Connection-Metadatenquelle beantwortet und darf nicht mehr quellenlos behaupten, es gebe keine SSH-Ziele. Fuer `ssh` wird der vorhandene Full-Kind-Inventarpfad mit `selected_kinds=["ssh"]` genutzt; es werden keine SSH-Actions erzeugt und keine Ziel-/Server-Scope-Logik fuer Status-/Disk-Checks geaendert. Covered by `tests/test_agentic_context_runtime.py::test_safe_fallback_source_listing_query_keeps_connection_inventory_context` and `tests/test_aria_turn_arbitration.py::test_pipeline_meta_catalog_unavailable_source_listing_uses_connection_inventory`.

### alpha673 — Fixed

- **SSH target authority fails closed for unknown ref-like host names.** A prompt such as `Pruefe den Status von dev-node-02` can no longer be silently mapped to a similar configured profile like `srv-dev02` when the requested identifier is not configured. Ref-like tokens are detected before capability-draft binding and rechecked by the requested-connection guard; ARIA must ask for a valid target instead of executing on the nearest-looking sibling. Covered by `tests/test_agentic_context_runtime.py::test_aria_turn_seed_blocks_unconfigured_ref_like_prompt_target` and `tests/test_pipeline.py::test_pipeline_requested_connection_guard_blocks_unconfigured_ref_like_target`.
- **Complete personal server groups become full-kind SSH scope instead of a partial sample.** When a selected personal claim describes the complete configured SSH set, a smaller MetaCatalog priority/action subset is promoted to `target_scope_authority:full_kind`, allowing the existing full-kind executor completion to cover all configured SSH targets. This addresses the `5 von 14` scope-loss pattern after "meine Server" turns. Covered by `tests/test_agentic_context_runtime.py::test_aria_turn_seed_promotes_complete_personal_server_claim_to_full_kind_scope` and `tests/test_pipeline.py::test_pipeline_multi_target_ssh_full_kind_completes_missing_configured_ref_before_preflight`.
- **Plural SSH scope no longer falls back to one semantic target after a blocked multi-target preflight.** If ARIA has already decided that a plural SSH scope blocks single-target resolution, the later missing-`connection_ref` repair is skipped instead of selecting one host from semantic fallback. Covered by `tests/test_pipeline.py::test_try_unified_routing_does_not_backfill_single_ref_after_blocked_plural_scope`.
- **Full-kind read-only SSH may execute after policy allow while single-target confirmation contracts stay pending.** The MetaCatalog preflight hold now exempts only `ssh_command` drafts with both `target_scope:multi_target` and `target_scope_authority:full_kind`; single-target `needs_confirmation=true` SSH contracts remain held for user confirmation. Covered by the full `pytest` suite.

### alpha672 — Fixed

- **SSH read-only actions now honor the turn contract confirmation flag.** If the MetaCatalog/AriaTurn contract marks an SSH action as `needs_confirmation=true`, the pre-RAG action gate keeps it pending even when the lower-level SSH read-only policy would allow the command. This fixes the live `Pruefe den Status von dev-node-02` failure where `systemctl status` executed immediately despite a confirmation-required contract. Covered by `tests/test_pipeline.py::test_pipeline_honors_turn_contract_confirmation_for_readonly_ssh`.
- **Multi-target SSH summaries can no longer widen checked subsets into "all servers".** Runtime summaries now mark partial configured-SSH coverage explicitly and scope overbroad LLM wording such as "alle Server" down to the checked SSH targets. This fixes the live pattern where 2 selected targets were summarized as if all configured servers had been checked. Covered by `tests/test_pipeline.py::test_pipeline_multi_target_ssh_limits_subset_summary_scope`.
- **Beipackzettel/document inventory fallback stays source-bound.** If MetaCatalog falls back on a document-inventory style prompt such as "was fuer beipackzettel hast du in deinem memory", ARIA now recovers into a docs inventory ContextRequest instead of plain chat with no sources. That allows an honest empty/source-bound answer and prevents personal-memory snippets from being presented as the complete document inventory. Covered by `tests/test_agentic_context_runtime.py::test_safe_fallback_document_inventory_query_keeps_docs_context`.

### alpha671 — Fixed

- **RSS/Heise read routing no longer falls into empty action preflight.** A MetaCatalog-selected RSS connection with an action-mode ContextRequest but no explicit `action_name` now seeds a bounded `feed_read` capability draft from the validated connection target instead of returning `no_executable_preflight`. The fix keeps single-target SSH without an explicit action fail-closed and is covered by `tests/test_meta_catalog.py::test_meta_catalog_rss_contract_without_selected_action_seeds_feed_read`.
- **Uncertain action input now fails closed with a clear clarification instead of the generic invalid-contract text.** Action turns with invalid/low-confidence extracted inputs still execute nothing, but the user-facing German/English text now asks for the exact configured target and required input instead of saying ARIA could not form a valid action contract. Covered by `tests/test_meta_catalog.py::test_meta_catalog_action_input_low_confidence_asks_for_action_details`.

### alpha670 — Fixed

- **Web search now reads the official source it found instead of asking.** After Codex documented the design rationale (`docs/ai-context/06-web-search-authority-rationale.md`), the intentional repository-path authority and the `required_primary` sibling fail-close are kept **unchanged**; the fix is additive and only ever touches sources that already passed site-target validation (`aria/skills/web_search.py`). Three changes: (1) a validated preferred/required source stays a page-fetch candidate even when it ranks below the top-3; (2) if the short first fetch pass yields no readable excerpt, that validated source is retried with the full profile timeout and a larger excerpt window (e.g. a GitHub releases page whose version sits past the first 1800 chars) — never degrading to a foreign source; (3) an **honest fallback**: when the preferred/required source was found but could not be read, the answer path is told "official source found but not readable" and given the URL (metadata `preferred_source_unreadable` / `preferred_source_urls`) instead of guessing or asking vaguely. This targets the "found but didn't read the version" live failure (16:45 log). The separate **recall** failure (engine returns nothing domain-matched → fail-closed, 19:32 log) is intentionally left for a later, separate decision. Tests: `tests/test_searxng_client.py` (`…refetches_preferred_source_with_longer_timeout`, `…reports_preferred_source_unreadable_honestly`); full `test_searxng_client.py` re-run to protect the authority tests. Built internally as `alpha670`.
- **Hygiene:** moved the alpha666 immutable capability-awareness directive text out of Python and into `aria/i18n/{de,en}.json` (`context.capability_awareness_directive`); the German literal in `aria/core/context.py` had been failing the i18n code-literal audit. Also refreshed `docs/backlog/alpha-backlog.md` release-stand lines (were stale at `alpha664`). Both were latent red states surfaced by the full test run, now green.

### alpha669 — Reverted / Note

- Reverted the alpha667/alpha668 web-search `site:` changes and a proposed `required_primary` degrade. They conflicted with **intentional** repository-path authority that `tests/test_searxng_client.py` encodes: the `site:github.com/qdrant` path target distinguishes the official `github.com/qdrant/*` repo from unrelated sibling repos (e.g. `github.com/MADPANDA3D/QDRANT-MCP`), and `required_primary` deliberately fails closed for a sibling-only result set rather than answering from the wrong source. Domain-normalizing the query and degrading to best-available both broke that authority guarantee (4 tests). The `site:`+strict-filter design also does not fetch the found official page (it stops at snippets and asks), and did not work against the live SearXNG engines regardless. `#4` (official-source version lookups like "latest Qdrant version") therefore needs a design decision, not a strict-filter relaxation. The RSS routing guidance (R1, alpha667) is kept — it works. Reverted to a green tree.

### alpha668 — Fixed

- Web search `site:` queries now use a bare domain at the real build site. The executed queries are built in the web-search skill (`aria/skills/web_search.py::_search_queries`) from the plan's preferred/required domains; a path target like `github.com/qdrant` produced a malformed `site:github.com/qdrant` that engines ignore, so all results were dropped as `site_query_target_miss` and official-source lookups returned nothing (still seen in the alpha667 live log). Queries are now built with the domain (`site:github.com`); the path stays on the required/preferred targets for precise filtering, and two paths on one domain collapse to a single query. Test: `tests/test_web_search_site_queries.py`. Note: alpha667's `Pipeline._web_source_plan_search_targets` change only covered the recovery/freshness queries, not these executed queries — this is the effective fix. (Still open, deciding after live test: degrade `required_primary` to best-available-with-caveat when engines return nothing domain-matched.) Built internally as `alpha668`.

### alpha667 — Fixed

- Web search against official/preferred sources no longer fails closed with zero results because of malformed `site:` queries. A path-shaped source target (e.g. `github.com/qdrant`) produced `site:github.com/qdrant`, which search engines do not honor, so every result was dropped as `site_query_target_miss` and official-source lookups returned "keine belastbaren Quellen" (live log 2026-08-09 msg 63/65). `Pipeline._web_source_plan_search_targets` (`aria/core/pipeline.py`) now builds `site:` queries with the bare domain (`github.com`), while the full path stays on the required targets for precise post-filtering. Test: `tests/test_web_source_site_targets.py`. (Open follow-up: whether `required_primary` should degrade to best-available-with-caveat instead of absolute zero when engines return nothing domain-matched — to be decided.) Built internally as `alpha667`.

### alpha666 — Fixed

- ARIA no longer falsely denies its real capabilities on unknown/unresolvable targets. alpha665 removed the dead end, but the plain-chat / clarify response then claimed "Ich bin nur ein Textassistent ohne Zugriff auf Systeme / kann keine Nachrichten senden / keine Dateien lesen" (live log 2026-08-09 msgs 13, 15). The final chat/clarify system message now carries an **immutable** capability-awareness directive (`aria/core/context.py`, new `capability_awareness_directive`), appended on top of the user-editable persona so it cannot be edited away — it affirms the configured capabilities (SSH, SFTP/SMB files, webhook/Discord/email/MQTT messaging, HTTP APIs, RSS/web/website, calendar, notes, memory, documents), forbids denying them, tells ARIA to name the available targets and ask which when a specific one is not configured, and keeps answer/clarify turns non-executing. Unit test: `tests/test_context_capability_awareness.py`. (Part 1 of the capability-aware clarify; injecting the exact per-turn candidate refs — "did you mean pae-blog-discovery?" — is a separate follow-up.) Built internally as `alpha666`.

### alpha665 — Fixed

- Turn decisions that fail the coherence contract now degrade by turn class instead of a single generic dead end. Non-action turns — a plain knowledge answer, a context turn, or an over-eager `clarify` that also wanted to load context — fall back to a safe plain-chat answer, while action turns keep the by-design fail-closed hard stop (action safety unchanged). Fixes the alpha664 regression where general questions and unknown action targets returned "I could not form a valid action contract" (`aria/core/meta_catalog_routing.py`, new pure helper `turn_decision_degradable_to_chat`; regression cases from the live log in `tests/test_turn_decision_degrade.py`). Built internally as `alpha665`.

### Known Internal Regression State

- Internal build `0.1.0-alpha664` passed local unit and image gates but failed the subsequent end-to-end user evaluation and is not an accepted release candidate.
- Confirmed internal regressions include a normal chat turn blocked by an action-contract error, failed official-source acquisition, irrelevant web follow-up evidence, and a correctly identified multi-server scope blocked before execution.
- Successful Personal Memory, exact-document, confirmed webhook, and separate multi-target disk checks do not offset the failed overall quality gate.
- The current post-public development tree is a large uncommitted integration state and requires independent review before further release work. Public release `0.1.0-alpha604` remains unchanged.

### Fixed

- Removed productive deterministic free-language authority across memory/learning extraction, action and connection planning, recipe selection, context/follow-up handling, document/note retrieval fallback, Web query/source handling, website/RSS selection, and runtime outcome recovery. MetaCatalog/LLM now owns meaning and selection; configured metadata and Qdrant provide bounded candidates only, while invalid/no-LLM paths remain neutral or fail closed. Retained deterministic behavior is limited to safety, guardrails, confirmation, exact configured identities, structured contracts, technical normalization/runtime protocols, literal retrieval evidence, and observability. Added authority-audit regression markers, removed obsolete skipped parser/resolver tests, and removed Memory phrase stripping plus language stopword lists. Built internally as `alpha664`; not published.
- Fixed several post-decision authority losses in personal learning and connection actions. Personal-memory capture no longer enters repair merely because it does not consume an existing claim; fixed connection input extraction receives selected personal claims and the complete configuration-bound target allowlist; structured SSH read-only intents can normalize an unsafe draft before policy evaluation; and pending connection references accept only exact configured references while consuming the validated structured value. This adds no free-language trigger list or secondary semantic router. Built internally as `alpha664`; not published.
- Fixed Web source-target authority after the `alpha663` live gate: only structured domain fields can produce `site:` targets, DNS/IP validation rejects dotted software versions such as `1.18.3`, and `required_primary` plans fail closed without a valid typed target. Added a final source-bound Web answer guard that rejects concrete version or ISO-date anchors absent from the selected source metadata, preventing a drafted `1.18.3` claim from overriding evidence that states `1.16.3`. Built internally as `alpha664`; not published.
- Fixed the `alpha662` Web source-plan regression that rejected already-supported technical `search_mode` variants before normalization. Initial planning and same-owner repair now receive one machine-readable output schema, bounded enum normalization precedes validation, unknown modes remain fail-closed, and traces expose both input and repaired modes. Built internally as `alpha663`; not published.
- Corrected the internal local-update health contract after an `alpha662` false-negative: host and container health now share one observable deadline, terminal/restart-loop states fail early, failed updates print container status plus recent logs automatically, and stale internal-local errors reconcile to `ok` once ARIA health has recovered. Built internally as `alpha663`; not published.
- Preserved full Web source targets, including repository paths, across source planning, provider queries, quality gates, curation, and observability. The LLM source owner now returns a structured `authority_mode`; required primary-source requests actively search preferred targets, receive semantic LLM curation, and fail closed when no matching primary source exists. The source-intent prompt and structured contract both require that field; a missing or invalid value gets one complete repair by the same LLM owner and then fails closed instead of silently degrading to open search. The source-plan contract is transported as bounded structured fields instead of a truncated long string. Final user prose is also separated from the optional answer-influence receipt suffix, so malformed receipt JSON can no longer leak an internal response wrapper into chat.
- Preserved a validated replayed Web query when MetaCatalog labels an elliptical follow-up as ordinary `chat` while selecting a Web `ContextRequest` with `last_turn_scope/reuse_same_set`. Query transport now follows the selected Web context contract rather than the redundant `web_research` intent label, preventing downstream source acquisition from losing the resolved entity and searching for an unrelated product. No query rewriting, phrase list, or secondary semantic owner was added.
- Removed secondary semantic owners from the Web and context entry path. Explicit/fresh Web intent, follow-up meaning, and context selection now remain with the MetaCatalog turn contract; the Web route always forwards the original cleaned user message and history instead of an independently rewritten `pipeline_message`. Missing or low-confidence context relevance review preserves already loaded context instead of falling back to phrase lists, while technical source-type filtering and normalization of an already selected Web action remain unchanged.
- Made complete Personal Model no-hit handling an enforceable part of `turn_decision_v3` instead of prompt-only guidance. When a personal capsule is present, the sole MetaCatalog LLM owner now returns a structured `personal_context_resolution`; runtime validation checks only cross-field coherence with capsule coverage, selected claim IDs, context requests, and the direct response. Missing or contradictory resolution triggers the existing full-header repair by the same owner before any context loader runs, preventing a complete no-hit from silently widening into broad Memory/Notes retrieval without introducing keyword rules or another semantic authority.
- Preserved LLM-selected Personal Context across the Web-arbitration-to-Pipeline handoff. The typed turn envelope now carries the user-bound capsule and active learning hints into the final answer hop instead of letting Pipeline initialization erase them; a mismatched user fails closed. Capsules also declare whether they contain the complete active claim set or only a relevance-selected subset, allowing the sole MetaCatalog decision owner to treat a complete missing claim as a structured no-hit without an otherwise unnecessary broad Memory/Notes search. Early Web action results such as Forget preview now expose request-wide arbitration usage instead of showing zero tokens.
- Unified Personal Memory target authority for Forget preview after internal `alpha656` could recall a newly stored structured claim but not find it for deletion. The fixed `memory_forget` action-input hop can now select exact allowlisted `claim_ids` from active personal-context targets; invented IDs fail closed. Preview resolves active user-bound claims by those IDs or a redundant exact stored claim value before falling back to general vector search. General influence receipts remain separate and can never become deletion targets; signed preview, confirmation, and execution are unchanged.
- Replaced the raw Personal Memory forget confirmation instruction with the same visible chat action box used by routed Connection confirmations. The Forget flow keeps its signed user-bound cookie and manual command fallback, exposes no token in the assistant copy, uses a dedicated localized `Confirm deletion` label, and keeps the inline button single-use without changing deletion execution or safety checks.
- Removed the remaining Qdrant Top-K authority gate from Web turn arbitration after the `alpha654` live test. Capture and recall succeeded, but `memory_forget` was only recognized by a second Pipeline arbitration because the Web pre-pass required a managed-action catalog hit; the correctly selected Forget contract then fell into generic capability preflight and stopped as `no_executable_preflight`. Web now obtains one complete role/config-bound turn decision, handles Forget/Admin from that decision, and passes every other decision including safe fallback unchanged into Pipeline. Qdrant continues to rank context and targets but cannot hide actions, and the obsolete managed-action set and required-candidate contract were removed.
- Replaced the failed post-`alpha653` action wire with `turn_decision_v3`. The first LLM hop selects one `action_name` without receiving or returning input schemas; only after that header validates does a focused second hop receive the fixed action and its single input schema. Runtime composes and validates the pair, a header repair cannot inject inputs, and any attempt by the input hop to rename `memory_forget` as capture fails closed. Legacy complete decisions remain readable, while the normal producer no longer emits independent `actions` and `action_inputs` fields that can diverge.
- Kept the role/config/pending-bound runtime menu as the complete first-hop action authority while removing all action input schemas from that large World Map. Qdrant catalog hits continue to rank context and targets without hiding or injecting capabilities; only the selected action schema enters the bounded input-extraction hop.
- Fixed the post-`alpha651` live failure where the compact turn-decision producer and its validator disagreed about the `contract` wire shape. The normal router and full-decision repair now share an explicit contract object schema; an unknown redundant mode is technically canonicalized only from an already explicit valid decision kind, while missing actions, invalid inputs, known mode conflicts, semantics mismatches, and side-effect safety still fail closed.
- Removed the legacy turn-semantics action recovery that could replace a correctly selected `memory_forget` action with `personal_memory_capture`. Turn semantics now validates capture fail-closed but never selects, restores, or substitutes actions; explicit deletion remains bound to the high-risk signed-confirmation forget flow.
- Preserved explicit single-target SSH commands when the authoritative MetaCatalog turn selected a validated `ssh_command` action and exact configured connection but omitted the duplicate structured command field. The authority-free capability input adapter now completes only the missing technical draft input from the current user message after target binding and before status fallback; ordinary status requests remain eligible for the status contract, unknown targets remain unbound, and mutating commands still pass through the existing SSH guardrail.
- Separated Document context depth from Document target scope. `deep` now increases only the bounded recall budget within the selected target set and never directly authorizes a corpus scan. A planned full scan requires an explicit documents-family/corpus contract, while exact document IDs/names remain exact; the existing no-hit fallback remains limited to already unbound docs-only recall.
- Fixed generic last-turn scope replay at the MetaCatalog authority boundary. Source-bound turns now persist their validated executable ContextRequests in the TurnFrame; `last_turn_scope/reuse_same_set` materializes those requests for the current turn with the original bounded scope and current request identity. Missing or invalid replay contracts fail closed as source-bound clarification instead of reaching general chat with zero sources. This applies to registered context surfaces without document terms, intent word lists, or surface-specific semantic overrides.
- Rejected Same-Hop general-chat text when its own structured turn contract depends on `target_scope_authority` or `scope_operation`. A repeated source-bound inventory question can no longer be treated as context-free merely because the router emitted `needs_context=false`; it falls through to the normal answer path instead of returning an incomplete prior-turn summary.
- Fixed the remaining broad Document inventory fan-out exposed by internal `alpha635`: when a structured `docs_family` inventory contract is selected, simultaneous document-meta candidates are now absorbed as catalog hints into that single executable request. Exact multi-document inventories without a family contract remain separately bound, while broad inventory candidates cannot become accidental completeness filters.
- Fixed duplicate broad Document inventory requests when the authoritative MetaCatalog selected both the Docs surface and its broad documents family. Unbound requests for the same surface, query, and collection are now consolidated into one request with catalog hints, while exact multi-document inventory bindings remain separate and complete.
- Fixed exact Document Meta scope being dropped by the normal RecipeRuntime memory adapter after MetaCatalog and ContextOverride had already bound it correctly. Answer-mode document recall now forwards document IDs and names alongside the target collection, preventing Memory from mistaking an exact contract for an unbound collection-wide request and activating corpus fallback.
- Fixed a higher-level MetaCatalog context authority gap exposed after internal `alpha632`: top-level selected catalog IDs are now the sole semantic catalog authority, while duplicated request IDs and canonical document metadata are treated only as untrusted LLM budget fields and rebuilt from the selected hits. Conflicting child requests can no longer discard or redirect an exact document selection before retrieval.
- Removed post-routing document-scope inference based on German/English query word lists. Exact document, inventory, and corpus behavior now follows the structured ContextRequest/catalog contract, with `document_scope=exact|inventory|corpus|unbound` and bound-document counts exposed in the context ledger.
- Fixed exact Document Meta handoff across MetaCatalog routing, ContextRequest normalization, the Surface Loader, and Memory recall. A uniquely selected document now remains bound by document ID/name/collection even when the LLM omits the already selected catalog ID from its request, and exact document scope cannot widen into an unrelated corpus or keyword fallback.
- Tightened document catalog discovery for non-document collections: generic `title`/`name` metadata alone no longer promotes Recipe Experience or similar payloads into the document world map; explicit document identity or source metadata is required.

### Added

- Added the P4A.1 inbound-event core: a hidden-until-UI `inbound_webhook` Connection manifest, generated per-source Secure Store tokens, a browser-session-independent authenticated endpoint, the passive `inbound_event_v1` contract, and a persistent bounded Activity ledger. The first `senscap_watcher` profile normalizes only technical fields; all events remain `log_only`, redact sensitive payload fields, store no raw body by default, deduplicate explicit source event IDs, and cannot authorize runtime actions.
- Added the P4B.3 closed learning loop: one validated `learning_directive_v1` from the authoritative turn decision selects bounded learning lanes, while only selected personal claims and active hints can reach the final composer.
- Added same-hop `answer_influence_receipt_v1` output with strict presented-ID allowlisting, durable per-user/request SQLite receipts, and restart-safe feedback attribution.
- Added a persistent typed Learning Worker ledger in `data/runtime/learning_worker.sqlite3` with restart recovery, retry metadata, token reservations, idempotency, and registered handlers for Auto-Memory, feedback learning, and global synthesis.
- Added visible personal-claim support counts, application receipts, and separated matched/presented/applied/feedback/effectiveness metrics to `/memories/auto-memory`.
- Added the Learning Governor for Qdrant learning events, candidates, and evals: stable content fingerprints deduplicate equivalent artifacts despite volatile event/candidate IDs, and configurable per-source day/session FIFO limits bound new intake.
- Added structured learning purpose metadata (`active_effective`, `review_only`, `audit_only`), LLM-assigned review-worthiness/importance/synthesis targets, and Memory Browser badges/details without hiding any Qdrant entries.
- Added self-cleaning importance retention for internal Qdrant learning events, candidates, and evals. It runs at startup and after governed writes, removes duplicate and lower-value overflow points with point-level deletes, preserves source diversity, and protects activated, promoted, regression-passed, or explicitly protected evidence without using age as authority.
- Added Auto-Memory controls and status for Learning FIFO limits, minimum eval importance, and the automatic retention target per learning collection. The Memory Browser keeps showing every retained point without hidden filtering.
- Added an LLM-first Learning Synthesis lifecycle. At startup or on explicit admin request, related unprocessed review candidates can be consolidated into a canonical review-only candidate with bounded provenance; source candidates are removed only after successful persistence, while uncertain/noisy candidates are deferred or marked for review instead of silently activated.
- Added a complete Learning inventory to `/memories/auto-memory`, including all events, candidates, evals, active hints, effect/status metadata, synthesis provenance, and point-level admin deletion protected by CSRF, learning-collection allowlisting, and stored-user verification.
- Added first-class Learning Candidate review controls to `/memories/auto-memory`: accept/reject, server-authoritative promotion gating, eligible apply preparation, and a link into regression/preflight review. Accepting a candidate never activates runtime behavior.
- Added a closed Learning Effectiveness lifecycle for active hints: structured Qdrant recall now reaches the preferred MetaCatalog/AriaTurn path, the LLM reports which bounded hint IDs it actually used, and each hint tracks matches, uses, feedback, version, and lifecycle state.
- Added automatic suspension after repeated negative feedback linked to a recently used hint, plus explicit suspend/reactivate controls and effectiveness counters on `/memories/auto-memory`.
- Added a structured `entity_alias_v1` learning contract for explicitly confirmed spelling/name aliases. The LLM extracts meaning, deterministic validation requires distinct observed/canonical forms and an exact link to existing non-learning Memory evidence, and only the reviewed/promoted Active Hint can influence future LLM-first entity resolution.
- Added Entity Alias provenance to Learning Candidate storage, apply/activation previews, active-hint payloads, and structured runtime recall. A lone typo cannot create an alias, and missing confirmation or Memory evidence blocks activation.
- Added `personal_claim_v1` in existing fact/preference collections with typed scope, authority, lifecycle status, evidence references, LLM-reviewed claim relations, fail-closed conflicts, and non-destructive supersession history.
- Added a bounded `personal_context_capsule_v1` for MetaCatalog/AriaTurn and the final answer composer. Only active claims enter the capsule; current user input, safety, configuration, explicit targets, and source evidence remain stronger authority.
- Added persistent personal-claim effectiveness fields for presented, LLM-reviewed used, changed-outcome, and feedback counts. Recent feedback links through Qdrant-backed use receipts after restart instead of relying on process memory.
- Added a Personal model section to `/memories/auto-memory` with active, suspended, historical, and disputed claims plus point-level suspend, reactivate, and delete controls.

### Changed

- Built internal `0.1.0-alpha662` for exact Web source-target authority, complete same-owner source-plan repair/fail-closed behavior, required-primary curation, and receipt-safe response transport. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha658` for the user-bound Personal Context handoff, explicit capsule coverage, structured complete-set no-hit contract, and request-wide usage on early Web actions. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha657` for exact structured Personal Memory deletion targeting. Forget receives only allowlisted active `claim_ids`, resolves user-bound claims by ID or redundant exact stored value before general vector fallback, and fails closed on invented IDs. Influence receipts remain separate from deletion targets; signed preview, visible confirmation, single-use behavior, and execution are unchanged. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha656` for the Personal Memory Forget confirmation UX. The signed user-bound deletion preview now renders the same inline action box used by Connection confirmations with a localized `Confirm deletion` label, while the hidden command fallback, one-time behavior, preview contract, and executor remain unchanged. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha655` for the Web single-arbitration authority fix. The Web entry path no longer requires a matching Qdrant top-K action candidate or drops a validated safe fallback before execution; one role/config-bound turn decision now drives Web-owned Forget/Admin handling and is reused unchanged by Pipeline for all other paths. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha654` for the `turn_decision_v3` producer boundary. The first LLM hop now selects only one `action_name` without action input schemas; a header-only repair cannot inject inputs, and a second bounded hop receives only the fixed action and its single schema. Runtime composes and validates the final action/input pair, while attempts to rename `memory_forget` as capture fail closed. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha653` for stable action-capability authority in the first-hop turn contract. The canonical output schema now declares `actions` explicitly, the role/config/pending-bound runtime menu supplies the complete available action set, and Qdrant catalog hits rank context and targets without hiding or injecting runtime capabilities. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha652` for the shared turn-decision wire contract and its corrected ownership boundary. `turn_decision_contract` now owns the output profile, schema, technical normalization, and validation; `llm_input_contract` only transports that canonical schema. The LLM/MetaCatalog remains the sole authority for meaning, action, target, and inputs, while invalid or contradictory decisions still fail closed. Public release metadata remains `0.1.0-alpha604`.
- Migrated initial Web-chat admin and personal-memory deletion intent to bounded MetaCatalog actions. Free-text request parsers no longer select these terminal flows; the LLM-owned turn contract supplies validated operation inputs, while role checks, signed pending state, one-time confirmation, runtime sanitization, and fail-closed execution remain deterministic. Managed action catalog entries are ensured additively without rebuilding Qdrant collections.
- Generalized action-input repair at the sole MetaCatalog decision owner. Actions declare required turn semantics and input schemas in the World Map; Memory, Connections, Pending, and Admin decisions use the same full-decision validator instead of a Personal-Memory-only partial patch.
- Built internal `0.1.0-alpha651` for the atomic `turn_decision_v2` authority boundary. Decision kind, semantics, action, schema-bound input, context, contract mode, and same-hop response now validate as one unit; one generic full-decision repair replaces the complete decision, and an invalid repair fails closed without execution or a final free-form answer hop. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha650` for removal of the legacy turn-semantics action recovery. `memory_forget` can no longer be replaced by `personal_memory_capture`; capture semantics validates only a selected capture action, while deletion remains on the signed preview/confirmation path. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha649` for the explicit personal-memory action-input repair. The selected `personal_memory_capture` action can now complete only its missing schema-bound claim payload in a small focused LLM hop; action and turn semantics cannot be reclassified, and invalid completion still performs no write. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha648` for the P0 Web pre-router authority migration. Initial admin, connection administration, update, backup/info, and personal-memory deletion intent now comes from bounded MetaCatalog actions; signed confirmations, roles, user binding, pending state, payload validation, and execution remain deterministic. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha647` for exact SSH command transport after authoritative target binding. The capability input adapter completes only missing technical command content for a validated single configured target before status fallback; ordinary status requests, unknown targets, guardrails, and public release metadata remain unchanged.
- Built internal `0.1.0-alpha646` for the CapabilityRouter adapter cleanup. `Pipeline` no longer constructs the legacy router; planner, dry-run, context-filter, calendar/SSH follow-up, and payload-normalization paths consume the authority-free technical input adapter. Unknown SSH follow-up targets are not heuristically rewritten, while known references remain bounded to configured catalog labels. Public release metadata remains `0.1.0-alpha604`.
- Modularized the remaining legacy `CapabilityRouter` adapter dependencies. Planner, dry-run payload construction, chat-context filtering, calendar follow-ups, file payload normalization, and SSH follow-up handling now use an authority-free technical input adapter; `Pipeline` no longer constructs a `CapabilityRouter`. Known Connection references are bound only against configured catalog labels, while unknown SSH follow-up targets are left to the authoritative turn contract instead of being heuristically rewritten. The retained legacy router delegates shared technical extraction to the same adapter for one parser source of truth.
- Built internal `0.1.0-alpha645` for the Agentic Core/P2 cleanup. Direct capability execution now consumes the validated MetaCatalog/AriaTurn draft without reclassifying free text through the legacy `CapabilityRouter`; the unused standalone SSH action path and now-unused alias preparation at that boundary were removed. Safety, policy, confirmation, target validation, and executors remain unchanged. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha644` for P7.4 MetaCatalog first-turn contract compaction. Canonical surfaces, actions, and catalog candidates now use schema-declared field/row tables; duplicated literal output allowlists are replaced by pointers to those canonical columns while runtime validation still enforces the complete computed ID sets. Stable contract data precedes request-specific context, and component-byte diagnostics expose the remaining payload cost. No candidates, action schemas, evidence, semantic authority, or safety boundaries were removed. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha643` for the P7.3 exact context replay fast path. An immediately repeated, normalized-identical, recent, actionless source-bound turn can reuse its validated registered ContextRequest before MetaCatalog routing, while loaders still refresh evidence with the current request identity. Changed, non-adjacent, stale, action/confirmation, learning, pending-action, and invalidated surface contracts remain on the normal LLM-first path; no response or evidence is cached. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha642` for the P7.2 source-bound answer-quality follow-up. The Answer Composer now requests final plain text in its existing single LLM hop, accepts legacy structured `answer` output only as wire normalization, and validates positive wording against supplied outcome/source evidence before existing safety and scope guards. Empty, malformed, and ungrounded output remains fail-closed. Public release metadata remains `0.1.0-alpha604`.
- Reduced source-bound answer and router contract overhead without removing candidates or evidence: document answers no longer carry irrelevant inventory rules, router surface signatures omit repeated cost/latency/load prose, and action metadata remains once in the canonical action schema instead of being copied into each catalog candidate.
- Built internal `0.1.0-alpha641` for the Document depth/scope authority fix. `context_depth=deep` now raises only the bounded recall budget inside the selected target set; exact IDs/names stay exact and corpus scans still require an explicit documents-family/corpus contract. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha640` for generic executable last-turn ContextRequest replay after the failed `alpha639` live gate. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha639` for the P7 Same-Hop scope-contract follow-up. Same-Hop response text is now accepted only when the structured turn has no target-scope authority or scope operation; Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha638` for P7 Agentic Performance pass 1. Safe context-free general chat can now return its final text from the authoritative MetaCatalog hop, while source-bound context, actions, confirmation, and fallback paths retain their existing boundaries. Public release metadata remains `0.1.0-alpha604`.
- Compacted the active MetaCatalog routing contract without changing semantic authority: raw collection inventory is no longer sent to the router, Surface catalog candidates reuse canonical registry signatures, and repeated candidate `knows`/`can_do` prose is collapsed into one bounded semantic description while IDs, refs, aliases, tags, actions, risk, and scores remain available.
- Added an answer-specific compact LLM input profile for the source-bound Answer Composer instead of attaching the unrelated general router output schema. Composer payload/system sizes are now visible in routing debug output; supplied Outcome/Evidence and source chunks remain intact.
- Allowed the authoritative MetaCatalog turn decision to include a user-facing response for high-confidence, context-free, actionless `allow_general` turns. Strict contract validation rejects this Same-Hop response for local/source-bound context, actions, confirmations, clarification, and fallback paths, and existing Personal Claim/Learning Hint receipts remain supported.
- Built internal `0.1.0-alpha637` local image/TAR for the Agentic Core cleanup, retired secondary turn arbiter, modular process-turn routing stage, and World Map contract coverage. Public release metadata remains `0.1.0-alpha604`.
- Retired the unused secondary `AriaTurnArbiter` and its deterministic free-text connection inventory conversion. Active process-turn contracts, runtime follow-up, and routing orchestration now live in `PipelineTurnStagesMixin`, with architecture and World Map coverage gates for built-in surfaces, documents, recipes, connections, and actions.
- Built internal `0.1.0-alpha636` local image/TAR for single-authority broad Document inventory execution when a structured `docs_family` contract is present. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha635` local image/TAR for broad Document inventory request consolidation and the shared Memory recall adapter contract. Public release metadata remains `0.1.0-alpha604`.
- Extracted the duplicated RecipeRuntime and SurfaceLoader Memory recall parameter assembly into one shared technical contract builder, keeping document IDs, names, collections, corpus scope, inventory mode, and learning-audit flags consistent across both adapters.
- Built internal `0.1.0-alpha634` local image/TAR for complete exact-document contract transport through the normal RecipeRuntime memory adapter. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha633` local image/TAR for sole top-level MetaCatalog selection authority, canonical ContextRequest binding, structured document-scope observability, and removal of post-routing document query-wordlist semantics. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha632` local image/TAR for exact Document Meta handoff through ContextRequest, Surface Loader, and filtered Memory recall, plus stricter non-document collection classification. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha631` local image/TAR for raw Learning collection isolation from document discovery, source-bound direct `docs:inventory` answers, and generic alphanumeric Document Meta candidate normalization. Public release metadata remains `0.1.0-alpha604`.
- Removed the second `AriaTurnArbiter` call from the normal MetaCatalog fallback path. A failed MetaCatalog decision now yields an actionless `meta_catalog_safe_fallback` that cannot authorize runtime actions or confirmations; the downstream action blocker remains defense in depth.
- Retired adapter-era Pipeline fixtures that asserted removed routing operations, removed the remaining test-local `CapabilityRouter` semantic adapter, and migrated current downstream tests to explicit structured MetaCatalog/Turn contracts. The Pipeline suite is green without that adapter (`180 passed`), the architecture matrix is green (`425 passed`), and the full suite excluding the separately tracked strict i18n audit is green (`1870 passed`).
- Built internal `0.1.0-alpha630` local image/TAR for Agentic Core cleanup pass 2, the actionless MetaCatalog safe fallback, historical Pipeline fixture retirement, and stateless Active Learning metadata safety. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha629` local image/TAR for persistent one-shot routed-action confirmation, independent pending/confirmation state, exact pending-field authority, and request-wide usage accounting. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha628` local image/TAR for contract-bound pending-input arbitration: only the authoritative MetaCatalog/AriaTurn `pending_action` decision may continue an incomplete action, while an independent request reuses the same arbitration on the normal pipeline path without a second semantic router hop. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha627` local image/TAR for capability-specific Connection action inputs, exact SSH command preservation, and fail-closed contract-bound missing-command handling. Public release metadata remains `0.1.0-alpha604`.
- Removed the unseeded Pre-RAG action migration adapter and its duplicate `capability_draft_decision` / `pre_rag_action_arbitration` semantic hops. Runtime actions now require a capability draft seeded by the authoritative MetaCatalog/AriaTurn contract; executors, policy, confirmation, guardrails, and technical normalization remain deterministic.
- Added bounded Connection action inputs to the Turn menu and preserved validated capability, refs, path, content, and target intent through CapabilityDraft creation. MetaCatalog Connection hits now expose bounded aliases and tags, and generic `connection_action_{kind}` actions remain visible when provider-specific catalog candidates are projected.
- Migrated SSH update/capacity objectives and representative SFTP, SMB, RSS, HTTP API, IMAP, Webhook, and MQTT tests to the contract-bound path. The focused Authority/MetaCatalog/AriaTurn/Operator matrix is green (`189 passed`); the monolithic historical Pipeline suite still contains adapter-era fixtures and remains an explicit migration gate rather than a build gate.
- Preserved missing required action inputs in the bounded planner decision and made payload, safety, and execution dry-runs honor that contract. A missing SSH command now remains a clarification instead of being replaced by a later heuristic `uptime` payload.
- Removed post-LLM prompt-phrase authority from MetaCatalog routing: document/note/memory words no longer overwrite the selected local surface, inventory phrasing no longer converts a structured Connection plan, and RSS verbs no longer synthesize an action. Structured LLM contracts remain authoritative; deterministic code validates and normalizes them.
- Changed unsupported multi-action MetaCatalog output to fail closed as a clarification until ARIA has an explicit composite-action contract, instead of allowing the single-action runtime to pick one branch and synthesize missing operational details.
- Removed the second `meta_catalog_surface_contract_review` decision hop. Local-context versus Connections routing is now owned by the primary MetaCatalog turn contract instead of a later semantic reviewer; obsolete reviewer recovery and trace code plus its reviewer-specific tests were removed.
- The first unseeded Pre-RAG removal attempt exposed 139 adapter-dependent tests and was reverted. The subsequent contract migration removed the runtime adapter cleanly; remaining failures are tracked as legacy fixture migration rather than a reason to restore semantic fallback authority.
- Built internal `0.1.0-alpha626` local image/TAR for the contract-bound Agentic Core cleanup and missing-input propagation fix. The current non-monolithic suite is green (`1675 passed`), while the explicit historical Pipeline audit improved to `78 failed, 249 passed`. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha625` local image/TAR for the passive P4A.1 `inbound_webhook` core, Secure Store source tokens, bounded inbound Activity ledger, and the first technical `senscap_watcher` normalization profile. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha624` local image/TAR for authoritative explicit Personal Memory capture when the router omits or contradicts the action marker, truthful fail-closed no-store responses, and suppression of mentioned side-effect actions. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha623` local image/TAR for current-config connection candidates in MetaCatalog routing, without automatic Qdrant reindexing or profile-specific semantics. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha622` local image/TAR for action-contract precedence over legacy Recipe Status and replay-safe routed-action confirmation state. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha621` local image/TAR for the compact P4B.3 router contract, collapsed-row feedback visibility, and canonical Webhook connection-action binding through confirmation-required `webhook_send`. Public release metadata remains `0.1.0-alpha604`.
- Compacted the canonical MetaCatalog/backup-router boundary with `aria_turn_router_output_v1`: dynamic allowlists remain explicit, while duplicated static schema/authority prose is no longer repeated in the JSON payload. MetaCatalog candidates omit redundant loader/executor/surface text and transmit only action schemas advertised by retrieved catalog evidence. Added contract/world-map/schema byte diagnostics; a representative route drops from 13,985 to 9,151 payload bytes without adding a semantic fast path.
- Changed collapsed Personal Model rows to show presented/used and positive/negative feedback counts directly, so asynchronous effectiveness updates are visible without opening each claim.
- Built internal `0.1.0-alpha620` local image/TAR for structured global Personal Context presentation when the router omits optional claim IDs, same-hop receipt evidence, and explicit selection observability. Public release metadata remains `0.1.0-alpha604`.
- Changed Personal Context presentation so an omitted optional router ID list can no longer silently remove active explicit global preferences, boundaries, or identity claims before the final composer. The structured bounded baseline is presentation-only: the final LLM still decides semantic use and only an allowlisted same-hop receipt records influence. Scoped, inferred, and unrelated claim kinds remain router-selected. Added explicit available/selected/baseline/presented trace accounting.
- Built internal `0.1.0-alpha619` local image/TAR for the unified `turn_semantics_v1` authority across Personal Memory and Learning, fail-closed contradictory capture normalization, and pre-write LLM-first batch consolidation of same-turn Personal Claims. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha618` local image/TAR for exclusive Personal Memory capture, exact receipt-bound feedback attribution, and the separation of transient effectiveness feedback from review-worthy Learning artifacts. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha617` local image/TAR for the P4B.3 closed learning loop, persistent budgeted Learning Worker, same-hop influence receipts, restart-safe attribution, and visible effectiveness accounting. Public release metadata remains `0.1.0-alpha604`.
- Changed no-signal turns to schedule no semantic Learning job. The Web chat layer no longer owns a parallel feedback-learning scheduler, and the separate per-turn personal influence LLM review is no longer used by the pipeline.
- Changed Active Hint recall to verify that a compatible collection exists before paying for an embedding, and changed startup Learning Synthesis to a persistent budgeted worker job.
- Changed repeated exact Personal Memory claims to strengthen the existing claim with bounded support/evidence metadata instead of creating another active point.
- Changed confident context-free chat turns so agentic Auto-Memory extraction runs as a budgeted post-response Learning job without pre-answer Memory recall. Durable extraction remains enabled, while transient questions no longer delay the visible answer with synchronous recall and relevance review.
- Compacted the MetaCatalog LLM input without changing semantic authority: canonical surfaces, collections, and actions are transmitted once, empty catalog fields are omitted, and surface catalog hits reuse the richer canonical Surface Registry instead of repeating its descriptions.
- Built internal `0.1.0-alpha616` local image/TAR for Personal Memory action-contract guard inheritance and explicit activation-blocker observability. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha615` local image/TAR for single-pass structured Personal Memory capture, truthful routing usage, effective Personal-Claim review activation, and closed Entity-Alias authority. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha614` local image/TAR for explicit Personal Memory capture authority, direct store confirmation, and feedback-learning deduplication. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha613` local image/TAR for Personal Memory Authority & Context, bounded personal-context selection, persistent influence accounting, temporal claim lifecycle, and Personal Model controls. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha612` local image/TAR for the structured Entity Alias learning contract, Memory-evidence binding, direct Candidate review, activation gates, and weak runtime hint integration. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha611` local image/TAR for the reorganized Auto-Memory operational workspace and its complete review/hint/audit inventory grouping. Public release metadata remains `0.1.0-alpha604`.
- Reorganized `/memories/auto-memory` as an operational workspace: removed the three static explanatory cards and redundant status badges, compacted the settings and save controls, and grouped the complete unfiltered inventory into review candidates, active/suspended hints, and raw evidence/audit.
- Built internal `0.1.0-alpha610` local image/TAR for the closed Learning Effectiveness lifecycle, canonical review queue, active-hint usage and feedback accounting, automatic negative-feedback suspension, and bounded deferred reconsideration. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha609` local image/TAR for first-class Learning Candidate review, server-authoritative promotion gating, eligible apply preparation, and protected regression/preflight controls. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha608` local image/TAR for LLM-first Learning Synthesis, the complete Auto-Memory learning inventory, and protected point-level learning deletion. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha607` local image/TAR for automatic importance retention of internal learning events, candidates, and evals. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha606` local image/TAR for the single-location Auto-Memory navigation follow-up. Public release metadata remains `0.1.0-alpha604`.
- Built internal `0.1.0-alpha605` local image/TAR for the completed P1 authority-chain regression gate and P4B Learning Governor / Purposeful Memory slice. This is an internal-only build; public release metadata remains `0.1.0-alpha604`.
- Classified Pre-RAG action gate debug output by authority: action paths now report whether they are `turn_contract_bound` or the remaining `legacy_migration_adapter`, so the P1 authority-chain audit can distinguish contract-seeded actions from the unseeded migration path without changing routing semantics.
- Hardened the P1 authority chain so a confident non-action AriaTurn contract skips legacy routing, recipe arbitration, and unseeded Pre-RAG action fallback; migrated the Management Server disk regression to a MetaCatalog-seeded action contract and changed the low-confidence capability-draft regression so uncertain legacy drafts do not execute.
- Closed the current P1 authority-chain manifest by marking the remaining trace-only / action-blocked P1 boundaries as `mitigated_p1` and adding a regression gate that fails if a `red_p1` boundary is reintroduced.
- Changed Learning Eval creation so non-review-worthy or below-threshold candidates stop before Qdrant persistence; review-only candidates remain non-promoting and only explicitly activated `learning_active_hint` points affect normal turn context.
- Changed Learning Synthesis so deferred evidence is reconsidered in a bounded way only when new evidence arrives. Existing raw backlogs are processed in finite batches, while active-hint outcome observations no longer create recursive learning candidates/evals.
- Changed normal Memory recall so raw learning events, candidates, and evals are excluded unless a structured Learning/Review contract explicitly authorizes the selected raw collection. Active Learning Hints remain available as weak runtime context.
- Changed inferred, sensitive, action-bearing, or unresolved personal claims to remain review-only Learning Candidates. Only explicit, low-risk, sufficiently confident user claims can become active directly.

### Fixed

- Excluded raw Learning Event, Candidate, Eval, and reflection collections from document catalog discovery even when audit payloads contain generic document-like metadata fields.
- Kept structured `docs:inventory` requests on the existing source-bound direct inventory path, so counts and listed documents come from the same filtered evidence without a second answer-composer hop.
- Normalized alphanumeric document identifiers at letter/number boundaries for bounded MetaCatalog candidate matching, allowing a subject token to match a document filename with an appended dosage, version, or unit suffix without product-specific routing rules.
- Prevented stateless Memory adapters from raising `AttributeError` when Active Learning attempts to persist last-turn metadata.
- Fixed routed-action confirmation replay across repeated button submissions and process restarts. Signed confirmation payloads are now atomically claimed in a persistent server-side ledger before any side effect; replay or ledger failure blocks execution.
- Fixed stale confirmation payloads overriding or clearing a newer missing-input action. The current pending continuation and the explicitly submitted confirmation candidate are now separate states, and only matching state may be cleared.
- Fixed exact user input supplied to a structured pending field being semantically rewritten by later SSH status fallback. The pending draft marks the current message as field authority while planning, safety validation, and the original request context remain intact.
- Fixed pending-turn arbitration usage disappearing from the visible chat badge. The Web request now owns one usage scope across pre-pipeline arbitration and the normal Pipeline result.
- Fixed an open routed-action input prompt consuming the next independent user request before the authoritative turn router ran. Pending missing-input state is now exposed as a bounded `pending_action_context_v1` only for the current user and only while it exists; MetaCatalog/AriaTurn decides whether the message continues that exact action or starts a normal new turn. The same arbitration is reused for a replacement action, stale pending state is cleared, and deterministic free-text kind/capability inference no longer owns pending continuation semantics.
- Fixed explicit SSH commands being placed in the generic Connection `path` field and then expanded by the missing-command status fallback. Connection action schemas now expose capability-specific payload fields such as `command` and `message`, normalize them through the declarative executor contract, discard fields irrelevant to the selected capability, and preserve an explicit command unchanged through the SSH runtime resolution. A contract-bound action that still lacks its required command now remains fail-closed instead of invoking semantic status backfill.
- Fixed authoritative `explicit_personal_memory` semantics falling into local recall, connection inventory, and a final chat composer when the router omitted or contradicted the `personal_memory_capture` action marker. When Personal Memory is available, the unified turn semantics now normalizes that turn exclusively to capture: valid structured claims use the direct store path, missing claims fail quickly and truthfully without persistence, and mentioned side-effect actions cannot execute.
- Fixed freshly created or changed connection profiles being absent from MetaCatalog routing until a full inventory reindex. The router now merges matching, secret-free connection documents from the current canonical configuration into the bounded LLM world map alongside Qdrant candidates. Semantic selection remains LLM-owned; stale or unavailable MetaCatalog storage can no longer hide an explicitly configured profile, while action validation, guardrails, and confirmation remain unchanged.
- Prevented legacy Recipe Status from overriding an already selected authoritative action contract, and hardened routed-action confirmation against stale browser state: a signed pending payload alone no longer confirms execution, while completed confirmation controls are removed from client-side pending synchronization.
- Fixed MetaCatalog connection actions losing their configured webhook target between semantic selection and executable preflight. A uniquely and explicitly named catalog profile is now bound as an action request, generic provider actions normalize through the canonical connection capability contract, ambiguous targets remain fail-closed, and webhook side effects still stop at the existing confirmation and HTTP guardrail boundary.
- Fixed the post-`alpha617` P4B.3 feedback authority gap: explicit `personal_memory_capture` now suppresses parallel general Learning materialization, while the canonical turn contract requires evaluative feedback to select the `behavior_feedback` lane.
- Fixed feedback attribution across turns and restarts by persisting each assistant request ID in chat history and targeting only that immediately previous request's receipt. Missing or mismatched IDs fail closed instead of crediting an older claim or hint.
- Fixed feedback noise and attribution races: transient praise/dislike updates only exactly receipted claim/hint effectiveness and creates no Event/Candidate/Eval artifacts; review-worthy durable feedback remains auditable. Exact receipt IDs are authoritative instead of asynchronously updated Qdrant `last used` metadata, and the old phrase-list feedback fallback was removed.
- Fixed ordinary high-confidence direct-answer turns paying for synchronous Auto-Memory extraction plus session/user recall even after the authoritative TurnPlan declared `needs_context=false`. Operator traces now distinguish deferred extraction, skipped recall, and successful queueing.
- Fixed the `alpha614` Personal Memory live path after a valid `personal_memory_capture` action could still fall back to the legacy unstructured fact store when the general Auto-Memory extractor returned only its old `preferences` field. The existing MetaCatalog/AriaTurn semantic pass now returns validated `action_inputs.personal_memory_capture.personal_claims`; persistence accepts only normalized `personal_claim_v1` output, reports `stored`, `review`, or `not_stored`, and never claims success or writes generic fallback memory when no valid claim exists.
- Fixed direct Personal Memory responses reporting `0 tokens`: they now expose the already incurred routing usage while still skipping Memory recall, a second extraction call, and the final answer composer.
- Fixed structured Personal Memory claims being sent to review when the selected low-risk `personal_memory_capture` action already established explicit user authority but the LLM omitted duplicate per-claim guard fields. Missing guard fields now inherit the validated action contract while explicit restrictive claim values remain fail-closed; review traces also expose stable activation blockers.
- Fixed accepted `personal_claim_candidate` reviews being marked but never becoming effective. A successful review now writes the reviewed low-risk claim into the Personal Model and records the activated claim reference on the candidate.
- Closed an authority bypass where `entity_alias` could enter through direct Personal Memory activation. Aliases remain exclusively on the evidence-bound `entity_alias_v1` learning, review, and promotion path.
- Fixed explicit durable personal-memory requests being misrouted as source-bound Memory searches. Facts and preferences now advertise a real low-risk `personal_memory_capture` MetaCatalog action, the action executes through `personal_claim_v1`, and success/review wording is emitted directly only after the structured store path completes, without a Qdrant recall or second answer-composer call.
- Prevented the asynchronous chat-feedback learner from creating parallel Learning Event/Candidate/Eval artifacts for an already completed explicit `memory_store` turn. Feedback classification now starts after turn execution and remains enabled for ordinary feedback turns.
- Fixed the Entity Alias live path after `alpha612`: `learning_capture` is no longer advertised as an executable MetaCatalog runtime action, because chat feedback capture already belongs to the asynchronous Learning worker. This removes the false `no_executable_preflight` stop while keeping `learning_feedback` as the visible semantic surface.
- Added a production-safe built-in `entity_alias_v1` activation regression. Valid explicit aliases with non-learning Memory evidence no longer depend on repository pytest files that are intentionally absent from the runtime image; other learning candidate types keep the existing linked-test gate.
- Moved the admin-only Auto-Memory page from the Admin hub into the visible Memory subnavigation, so it has one menu location alongside Import, Create Memory, and Memory Maintenance.
- Separated retained raw Learning Candidate evidence from the human review queue. All points remain visible, while only canonical multi-source synthesis candidates receive review controls; the server rejects review actions against raw evidence.
- Fixed active Learning Hints being discarded by the preferred MetaCatalog/AriaTurn path. Hints remain weak signals and cannot override safety, configuration, explicit targets, or source authority.
- Fixed legacy text deduplication for structured personal claims: matching legacy facts/preferences can be adopted into the claim contract, while different claim keys with the same text no longer collide.
- Added bounded personal-claim validity windows. Future claims remain scheduled, expired claims leave runtime context automatically, and the Personal Model distinguishes effective, scheduled, expired, suspended, and historical states.
- Added history-preserving Personal Model corrections and explicit goal/project lifecycle controls for pause, resume, complete, and reopen. Session-scoped extraction remains in session memory instead of becoming durable personal truth.
- Added LLM-first personal-context selection when more active claims exist than the bounded capsule can carry, plus visible non-destructive `review_after` due state and Operator Trace presentation metadata.

### Security

- Protected the Learning Candidate regression, prepared-artifact review, preflight, and activation forms with admin and CSRF checks; Auto-Memory candidate actions also verify the stored Qdrant point, owning user, collection family, artifact type, and risk instead of trusting browser fields.

## [0.1.0-alpha604] - 2026-07-21

### Public Release Candidate Notes

- Published the post-`0.1.0-alpha511` agentic stabilization line after internal `alpha604` validation. This release consolidates the LLM-first authority-chain work, source-bound evidence contracts, RuntimeOutcome follow-ups, multi-target SSH hardening, Memory Browser fixes, WebSearch source discipline, and UI/help refinements that were validated internally between `alpha512` and `alpha604`.
- Live validation for `alpha604` confirmed the key Server/Agentic matrix: disk-capacity and diagnostic prompts execute on 14/14 SSH targets, package-update checks execute on 14/14 SSH targets, SSH inventory remains config-bound, dev-server follow-ups stay narrowed, unknown explicit SSH refs fail closed, medication package-insert inventory returns the expected six documents, and Notes retrieval finds `Sample Project Note`.
- Known nuance: exact Note recall can still summarize selectively for long notes; the note is retrieved, but the final answer may omit some lower-priority bullets. This is not a Memory Browser or Qdrant visibility blocker.

### Added

- Added the internal `alpha603` P1 MetaCatalog backup-fallback action authority gate: if `aria_meta_catalog_routing` falls back because the meta catalog is unavailable, low-confidence, or invalid, a backup AriaTurn action plan is now blocked before Pre-RAG/Runtime with `meta_catalog_backup_fallback ... legacy_semantics=blocked`; valid MetaCatalog action contracts still run through the existing preflight path.
- Added the internal `alpha598` P1 Explicit Target Authority Validator slice after live `alpha597` testing: AriaTurn now only turns LLM/MetaCatalog `target_scope_authority=explicit_refs` into an executable `explicit_ref` when the user prompt actually binds the configured ref, alias, or label; unbound identifier-like target words are carried as `requested_connection_ref` and handled by the existing target guard chain.
- Added the internal `alpha597` P1 Legacy Authority Gate / test-migration slice after internal `alpha596`: routed action tests now enter through the current LLM capability-draft contract instead of the old local `_classify_capability_draft` hook, and the authority audit explicitly checks that semantic candidates cannot promote themselves to `explicit_ref`.
- Added the internal `alpha596` P1 Agentic Contract Model slice: `agentic_contracts.py` defines canonical turn-decision, evidence, and answerability contracts; the Stabilization Gate now derives its debug/guard lines from these objects and normalizes `runtime_outcome_evidence_contract` into the same `evidence_contract` / `answerability` model used by EvidenceBundle and ContextPacket paths.
- Added the internal `alpha595` P1A RuntimeOutcome full-kind/disk-measurement contract slice after live `alpha594` testing: SSH runtime contracts with `target_scope_authority=full_kind` now complete missing configured refs at the executor/preflight boundary, and disk-capacity runtime records preserve structured measurements from `df` tables or summarized runtime output so follow-ups like "over 75%" / "least free" answer from `runtime_records` instead of failing closed with missing structured values.
- Added the internal `alpha594` P1A RuntimeOutcome fail-closed authority slice after live `alpha593` outliers: when the runtime follow-up review declines or returns an invalid/low-confidence outcome for an actual previous package-update or disk-capacity question, ARIA now answers from the last source-bound runtime records and emits a `runtime_outcome_evidence_contract` instead of falling through to WebSearch, RSS/security-source inventory, SSH config inventory, or incomplete action preflight.
- Added the internal `alpha593` P1A Last-Observation Continuation Authority slice after `alpha592`: runtime outcome follow-ups are reviewed before Web Freshness / MetaCatalog surface re-routing can take over; package-update and disk-capacity follow-ups can answer from the previous source-bound SSH runtime records instead of drifting to WebSearch or connection inventory.
- Added the internal `alpha592` P1A Action-Preflight Contract fix for SSH full-kind runtime tasks: MetaCatalog `connection_action_ssh` plans with `target_scope_authority=full_kind` can now seed a valid multi-target Runtime contract even when the action plan carries no concrete refs; safe read-only package-update and capacity profiles execute through the existing SSH preflight/guardrail path, while incomplete SSH action preflights no longer reframe to candidate inventory.
- Added the internal `alpha591` P1A Stabilization Gate final-answer guard: pipeline finalization now enforces existing `evidence_contract` / `answerability` boundaries and fails closed when candidate-only context is about to become a hard counted or complete inventory claim, while still allowing cautious observed RSS/website candidates; guard blocks are mapped into Operator Trace as `source=stabilization_gate_final_answer_guard`.
- Added the internal `alpha590` P1A Contract-Authority follow-up: contradictory connection follow-ups that say both `target_scope_authority=last_turn_scope` and `scope_operation=surface_change` are reviewed against the existing config-bound connection EvidenceBundle when the plan still targets `connections`, while real docs/memory surface changes remain isolated; seeded MetaCatalog action contracts keep capability/preflight authority instead of degrading to chat or executing action-less contracts too early; local memory-family catalog IDs bind their target collections from structured MetaCatalog data.
- Added the internal `alpha589` Evidence/Answerability follow-up: document inventory metadata is now treated as a source-bound evidence contract even when the LLM selected the `memory` surface because the user asked about documents "im Memory"; bound EvidenceBundle subset/exclusion follow-ups can also answer non-address set questions from config evidence instead of falling back to candidate context.
- Added the internal `alpha588` P1A Scope-History / LLM Scope-Review follow-up: direct EvidenceBundle follow-ups now keep config-bound evidence in the turn frame, and a new `connection_evidence_scope_review` can bind or clarify semantic subset/exclusion follow-ups against the existing config-bound connection evidence without adding Dev/server keyword routing.
- Added the internal `alpha587` P1A MetaCatalog TurnPlan contract follow-up: MetaCatalog now carries `scope_operation`, system inventories normalize to inventory mode, full-kind connection inventory can bind configured kinds at the loader boundary, and unbound Host/IP candidate answers are rejected when they make uncautious count/completeness claims.
- Added the internal `alpha586` Agentic scope-operation contract: AriaTurn can now emit explicit last-turn scope operations (`reuse_same_set`, `narrow_subset`, `expand_to_kind`, `exclude_subset`, `surface_change`, `new_scope`) so follow-ups describe the intended set operation instead of relying on ambiguous `last_turn_scope`.
- Added real `capabilities` and `recipes` ContextSurfaces with system inventory loaders, so questions about active ARIA capabilities or stored recipe templates can be answered from runtime/recipe metadata instead of drifting into memory or documents.
- Added a P1A Agentic Stabilization Gate observability slice: a reusable live-prompt matrix now anchors the regression gate, pipeline finalization derives `turn_decision_owner`, `evidence_contract`, and `answerability` debug lines from existing contracts, and Operator Trace maps those boundaries without adding new routing semantics.
- Added a `connections` EvidenceBundle v1 slice: config-bound connection inventory now records safe rows, authority, completeness, field set, selected refs/kinds, and row count in the turn frame so follow-up Host/IP questions can reuse already loaded evidence instead of relying on visible chat text.
- Added a Runtime Target Scope Contract for Multi-Target SSH planning: `target_scope_authority` distinguishes whole-kind fleet scope, semantic groups, explicit refs, last-turn follow-ups, and priority samples.
- Added a P1 Authority Chain Audit/Test slice: a manifest of known legacy authority boundaries classifies old routers, fallbacks, candidate heuristics, guardrails, and observability-only paths without adding new free-semantics routing.
- Removed the red `capability_router_kind_inference` authority path: `CapabilityRouter` no longer imports or calls `infer_preferred_connection_kind`, so free text cannot choose a connection kind there.
- Added a client-side Chat/Debug Export control that turns the current chat into Markdown, including collapsed Details, Routing Debug, and Operator Trace lines, with clipboard-first behavior and a download fallback.

### Changed

- Built internal `0.1.0-alpha604` local image/TAR for the finalized multi-target ActionContract missing-field pruning fix; included in this public release line.
- Built internal `0.1.0-alpha603` local image/TAR for the P1 MetaCatalog backup-fallback action authority gate; included in this public release line.
- Built internal `0.1.0-alpha602` local image/TAR for the Memory-Browser structure drilldown type-state follow-up; included in this public release line.
- Live-accepted internal `0.1.0-alpha602` for the Memory-Browser fixing session: notes are visible again from real Qdrant rows, structure drilldown keeps hierarchy edges stable, and the browser is closed for now unless a new concrete bug or tweak is reported.
- Built internal `0.1.0-alpha601` local image/TAR for the Memory-Browser Notes read-model follow-up; included in this public release line.
- Built internal `0.1.0-alpha600` local image/TAR for the Memory-Browser Qdrant structure source-of-truth slice; included in this public release line.
- Built internal `0.1.0-alpha599` local image/TAR for the raw-prompt follow-up to the `alpha598` explicit-target validator; included in this public release line.
- Live-accepted internal `0.1.0-alpha599` after export `internal live export`: the `ops-unknown-01` prompt no longer executes SSH against a similar configured target; ARIA keeps `requested_ref=ops-unknown-01`, clears the executable `explicit_ref`, and asks for a valid SSH profile.
- Fixed the `alpha598` explicit-target validator after export `internal live export`: the validator now checks prompt-bound `explicit_ref` authority against the raw user message passed from the pipeline, not against the LLM-rewritten `ContextRequest.query` that may already contain the wrong selected ref.
- Built internal `0.1.0-alpha598` local image/TAR for the P1 Explicit Target Authority Validator slice; included in this public release line.
- Changed routed action authority handling so a strong semantic candidate may replace stale memory only as `semantic_candidate_resolution` / `semantic_alias`, never as `explicit_ref`; explicit draft targets remain higher authority.
- Changed requested-target fallback behavior so an unmatched concrete requested ref can block stale/default single-profile selection and still produce an incomplete capability payload instead of silently executing on the only configured profile.
- Built internal `0.1.0-alpha597` local image/TAR for the P1 Legacy Authority Gate / test-migration slice; included in this public release line.
- Built internal `0.1.0-alpha596` local image/TAR for the P1 Agentic Contract Model follow-up; included in this public release line.
- Live-accepted internal `0.1.0-alpha596` after export `internal live export`: RuntimeOutcome follow-ups now expose normal `turn_decision_owner`, `evidence_contract`, and `answerability` lines, update/disk follow-ups remain bound to `runtime_records`, inventory/docs/capabilities/recipes stay source-bound, and the broad "what do you know about my servers" probe stayed safely limited to the last runtime evidence instead of inventing wider server knowledge.
- Built internal `0.1.0-alpha595` local image/TAR for the RuntimeOutcome full-kind/disk-measurement contract follow-up; included in this public release line.
- Live-accepted internal `0.1.0-alpha595` after export `internal live export`: update checks and disk checks ran on 14/14 SSH targets, update and disk follow-ups stayed source-bound on `runtime_records`, SSH inventory/dev subset remained config-bound, and the package-insert document inventory returned the expected six medication documents.
- Built internal `0.1.0-alpha594` local image/TAR for the RuntimeOutcome fail-closed authority follow-up; included in this public release line.
- Built internal `0.1.0-alpha593` local image/TAR for the Last-Observation Continuation Authority follow-up; included in this public release line.
- Built internal `0.1.0-alpha592` local image/TAR for the SSH full-kind Action-Preflight Contract follow-up; included in this public release line.
- Built internal `0.1.0-alpha591` local image/TAR for the P1A Stabilization Gate final-answer guard; included in this public release line.
- Built internal `0.1.0-alpha590` local image/TAR for the P1A Contract-Authority follow-up; included in this public release line.
- Changed the fast document-inventory answer path so it can list loaded document sources from `document_inventory=true` results independently of whether the selected local surface was `docs` or `memory`.
- Changed last-turn EvidenceBundle follow-up answers so reviewed `narrow_subset`/`exclude_subset` contracts are not forced through the Host/IP query gate when the user asks a set question such as "which of these are not ...".
- Built internal `0.1.0-alpha589` local image/TAR for the Evidence/Answerability follow-up; included in this public release line.
- Built internal `0.1.0-alpha588` local image/TAR for the P1A Scope-History / LLM Scope-Review follow-up; included in this public release line.
- Built internal `0.1.0-alpha587` local image/TAR for the P1A MetaCatalog TurnPlan contract / system inventory / candidate answerability follow-up; included in this public release line.
- Live-rejected internal `0.1.0-alpha585` for the Agentic follow-up slice after export `internal live export`: it kept useful alias/token fixes, but the last-turn evidence contract was too weak and let same-set, dev-subset, non-dev-exclusion, capabilities, and recipes prompts regress.
- Built internal `0.1.0-alpha586` local image/TAR for the Agentic scope-operation / fail-closed / capabilities-recipes surface follow-up; included in this public release line.
- Changed last-turn EvidenceBundle reuse so `last_turn_scope` alone is incomplete and cannot imply all rows; reuse now requires a matching `scope_operation`, with fail-closed behavior for malformed last-turn follow-ups instead of falling into legacy memory/docs chat.
- Built internal `0.1.0-alpha585` local image/TAR for the P1A Last Evidence Reuse Gate / Follow-up Scope Contract; included in this public release line.
- Changed `docker/export-local-build.sh` so internal exports update `internal image archive alias` to the freshly exported versioned TAR instead of leaving the alias on an older build.
- Changed the P1A last-turn EvidenceBundle reuse path so it no longer finalizes before AriaTurn arbitration. Host/IP evidence can now only be reused after a structured turn contract confirms the same `connections:inventory` surface, a valid scope operation, and available fields; rejected reuse is traced and normal context loading continues.
- Changed the last-turn frame and LLM frame compaction so full EvidenceBundle rows stay runtime-internal, while AriaTurn/MetaCatalog only receive a compact summary with surface, authority, completeness, field set, row count, selected kinds, and selected refs.
- Built internal `0.1.0-alpha584` local image/TAR for EvidenceBundle v1 and P1A Agentic Stabilization Gate Observability; included in this public release line.
- Built internal `0.1.0-alpha583` local image/TAR for the P1 preferred-kind / KeywordRouter authority slice; included in this public release line.
- Changed `RoutingResolver.resolve_connection()` so it no longer uses free-text kind inference as a preferred-kind filter; Qdrant connection candidates without an authorized kind only bind directly when exactly one connection kind is configured; Routing Workbench reports inferred preferred kinds as `diagnostic_only`; active-learning hints are no longer suppressed by free-text kind inference and remain weak LLM context signals; KeywordRouter is signal-only for turn intent, with safe chat fallback on unavailable or low-confidence arbitration and recipe status gated by turn-intent arbitration.
- Built internal `0.1.0-alpha582` local image/TAR for the Runtime Target Scope Contract follow-up after `alpha581`; included in this public release line.
- Changed MetaCatalog runtime-action planning so it transports `target_scope_authority`; priority refs without scope authority become `priority_sample` hints, and SSH multi-target execution only expands empty multi-target contracts for `full_kind` while stopping `priority_sample` without target refs.
- Live-accepted internal `0.1.0-alpha582` for the server slice: status checks ran on 14/14 SSH targets, SSH host/IP inventory returned 14 config-authoritative entries, and dev-server inventory stayed scoped to the two dev hosts.
- Built internal `0.1.0-alpha581` local image/TAR for the Runtime Target Scope Contract; included in this public release line.
- Changed Multi-Target SSH draft handling so LLM `priority` refs alone no longer become a complete runtime target list; `full_kind` expands against validated configured candidates before command preparation, while semantic/ref scopes must be explicitly authorized.
- Built internal `0.1.0-alpha580` local image/TAR for the P1 Authority Chain Audit/Test slice and `CapabilityRouter` kind-inference authority removal; included in this public release line.
- Built internal `0.1.0-alpha579` local image/TAR for the Connection Inventory Query-Kind Contract Normalizer; if the LLM emits a configured connection kind such as `ssh` in its inventory query contract but omits structured `selected_kinds`, runtime now normalizes that contract to config metadata authority instead of falling back to Qdrant candidate context for broad host/IP server inventories.
- Built internal `0.1.0-alpha578` local image/TAR for Semantic Group Authority Review in connection inventory; group-scoped Host/IP requests with selected refs now distinguish config data authority from semantic group membership, run an LLM review over selected config metadata when needed, and keep fallback answers as possible matches if review authority is unavailable.
- Built internal `0.1.0-alpha577` local image/TAR for Candidate Inventory Authority Guard plus rollback of the live-rejected `alpha576` scope continuation; unbound connection-inventory candidate context may still support cautious candidate answers, but host/IP answers cannot claim complete inventory/all-server coverage unless the evidence is contract-bound to config metadata.
- Live-rejected internal `0.1.0-alpha576` after export `internal live export`: the scope-continuation fix still left the broad server host/IP prompt incomplete and polluted later scoped prompts by carrying `continued_scope=last_turn`.
- Built internal `0.1.0-alpha576` local image/TAR for Follow-up Connection Inventory Scope Continuation; this artifact remains internal and is not accepted for the server-inventory slice after live testing.
- Built internal `0.1.0-alpha575` local image/TAR for the Structured Connection-Kind Host/IP Inventory follow-up; the LLM can bind a connection-kind scope in `context_requests[].budget.selected_kinds` with `bind_selected_kinds=true`, and runtime only validates that structured scope against configured kinds before loading safe connection metadata.
- Built internal `0.1.0-alpha574` local image/TAR for the Broad/Exact Server Host/IP Inventory follow-up; connection `answer` requests with host/IP questions are normalized to inventory requests, selected connection refs/kinds and broad server host/IP inventories now load safe non-secret connection metadata as the authoritative source, Qdrant remains for thematic inventory candidate search, and kind-only broad SSH inventories are no longer truncated back to the candidate limit after selecting all matching refs.
- Built internal `0.1.0-alpha573` local image/TAR for the Broad Server Host/IP Inventory follow-up; broad host/IP questions with multiple same-kind LLM priority refs now bind the inventory request by kind only (`ref_authority=kind_only`) instead of treating priority refs as a complete server list, while scoped groups such as dev servers remain ref-bound; included in this public release line.
- Built internal `0.1.0-alpha572` local image/TAR for LLM Input Contract boundary hardening and P1 RoutedActionResolver authority hardening; included in this public release line.
- Hardened P1 RoutedActionResolver authority boundaries: preferred connection kind is no longer authorized from free-text heuristics, and can only come from the draft contract or a single configured capability-catalog executor; the legacy inference remains trace-only with `authority=none`.
- Hardened LLM Input Contract boundaries: bound Inventory host/IP evidence is preserved only inside the Answer Composer evidence packet, while general meta/surface/connection hosts remain redacted from LLM input contracts.
- Built internal `0.1.0-alpha571` local image/TAR for the WebSearch Source Authority Contract; included in this public release line.
- Added a WebSearch Source Authority Contract after `alpha570`: planned fast-answer web searches now label sources as required/preferred/strong-secondary/weak-secondary/noise and pass explicit caution guidance plus `source_authority_outcome` when only weak or secondary evidence is available, without adding product-specific domains, a new router, or another LLM curation hop.
- Live-tested `alpha571` WebSearch with Apple Watch Ultra, Kindle, Rabbit R1, and Docker Compose prompts; the path is accepted for now, with later tuning deferred for better official-source acquisition and faster final answer condensation.
- Built internal `0.1.0-alpha570` local image/TAR for the WebSearch acquisition-boundary fix; included in this public release line.
- Changed WebSearch acquisition so `preferred_domains` no longer generate `site:` queries or hard-block fast answers; true must-have domains still use hard source validation, while obvious deal/rumor/shopping noise is removed before answer context.
- Built internal `0.1.0-alpha569` local image/TAR for the WebSearch LLM-hop reduction / evidence-budget follow-up; included in this public release line.
- Reduced the fresh external WebSearch fastpath by one LLM hop: the Search Intent Builder can now act as the first web hop, its `web_source_plan` is carried into context loading instead of replanning, preferred-domain evidence must still match the query topic, and `fast_answer` limits answer context to four web sources.
- Built internal `0.1.0-alpha568` local image/TAR for the WebSearch Direct-Fastpath / Source-Gate follow-up; included in this public release line.
- Added an early LLM-first WebSearch fastpath for current external web questions, so normal fresh web lookups can skip expensive Meta/Turn arbitration while local connection questions stay on the local context path.
- Built internal `0.1.0-alpha567` local image/TAR for the Web Search Intent Builder / Fast Web Answer Lane; included in this public release line.
- Added the Web Search Intent Builder / Fast Web Answer Lane: WebSearch now asks an LLM to formulate a compact SearXNG search intent before retrieval, supports editable runtime rules in `prompts/web/search_intent.md`, exposes that prompt from the Workbench, and skips expensive research-style source curation for normal `fast_answer` web questions.
- Built internal `0.1.0-alpha566` local image/TAR for the WebSearch provider-garbage boundary and source-plan validation follow-up; included in this public release line.
- Hardened profile-aware WebSearch at the contract boundary: inferred LLM hard domains are demoted unless the user explicitly named the domain, stale years in relative freshness queries are normalized against `current_date`, and source-plan searches filter off-topic provider results before expensive LLM curation.
- Built internal `0.1.0-alpha565` local image/TAR for profile-aware WebSearch planning; included in this public release line.
- Prepared profile-aware WebSearch planning: SearXNG profile metadata can now be exposed safely through the LLM input contract, the web source planner can select `search_profile_ref`, and runtime validates/executes the selected profile without adding product-specific routing rules.
- Built internal `0.1.0-alpha564` local image/TAR for the SearXNG connection save regression fix; included in this public release line.
- Built internal `0.1.0-alpha563` local image/TAR for the Web Evidence Contract `must_have_domains`/`preferred_domains` split and bound Inventory host/IP answer coverage follow-up; included in this public release line.
- Built internal `0.1.0-alpha562` local image/TAR for the Agentic Web/Inventory Evidence Contract follow-up; included in this public release line.
- Built internal `0.1.0-alpha561` local image/TAR for the Web Source Contract Observability follow-up; included in this public release line.
- Built internal `0.1.0-alpha560` local image/TAR for the P0 LLM Input Contract follow-up on Answer Composer and Web Source Relevance Review; included in this public release line.
- Built internal `0.1.0-alpha559` local image/TAR for the planned WebSearch freshness-sufficiency follow-up; included in this public release line.
- Built internal `0.1.0-alpha558` local image/TAR for the planned WebSearch required-domain retrieval/recovery follow-up; included in this public release line.
- Built internal `0.1.0-alpha557` local image/TAR for the planned WebSearch source-contract required-domain validation follow-up; included in this public release line.
- Built internal `0.1.0-alpha556` local image/TAR for the P0 LLM Input Contract V1 / Normalizer contract-only slice; included in this public release line.
- Built internal `0.1.0-alpha555` local image/TAR for WebSearch source-contract freshness and planned-query ordering; included in this public release line.
- Built internal `0.1.0-alpha554` local image/TAR for WebSearch fail-closed observability and single LLM-planned source retry; included in this public release line.
- Built internal `0.1.0-alpha553` local image/TAR for planned WebSearch source curation; included in this public release line.
- Built internal `0.1.0-alpha552` local image/TAR for the LLM-first Web Source Acquisition Plan; included in this public release line.
- Built internal `0.1.0-alpha551` local image/TAR for the WebSearch/Freshness latency-budget follow-up; included in this public release line.
- Built internal `0.1.0-alpha550` local image/TAR for the WebSearch/Freshness evidence follow-up and `/stats` release-header polish; included in this public release line.
- Built internal `0.1.0-alpha549` local image/TAR for the Runtime-Task authority removal, WebSearch action-contract normalization, and file-action evidence guard; included in this public release line.
- Built internal `0.1.0-alpha548` local image/TAR for the post-`alpha547` authority cleanup bundle; included in this public release line.
- Built internal `0.1.0-alpha547` local image/TAR for the Meta-Catalog self-contradictory keep-local fail-closed follow-up; included in this public release line.
- Built internal `0.1.0-alpha546` local image/TAR for the Meta-Catalog self-contradictory connection-evidence fail-closed follow-up; included in this public release line.
- Built internal `0.1.0-alpha545` local image/TAR for the Meta-Catalog surface-review recovery; included in this public release line.
- Built internal `0.1.0-alpha544` local image/TAR for the Meta-Catalog connection-evidence recovery; included in this public release line.
- Built internal `0.1.0-alpha543` local image/TAR for the Docs evidence-contract fix; included in this public release line.
- Built internal `0.1.0-alpha542` local image/TAR for the post-`alpha541` surface-review descriptor follow-up; included in this public release line.
- Built internal `0.1.0-alpha541` local image/TAR for the post-`alpha540` meta-catalog surface-review self-consistency hardening; included in this public release line.
- Built internal `0.1.0-alpha540` local image/TAR for the post-`alpha539` Connection-Contract repair; included in this public release line.
- Built internal `0.1.0-alpha539` local image/TAR for the Inventory Fast-Answer authority removal; included in this public release line.
- Built internal `0.1.0-alpha538` local image/TAR for the SSH blocked-action safety/observability follow-up and Operator Trace policy-consistency slice; included in this public release line.
- Built internal `0.1.0-alpha537` local image/TAR for the SSH Multi-Target Action-Contract follow-up; included in this public release line.
- Built internal `0.1.0-alpha536` local image/TAR for the SSH Status-Contract cost slice; included in this public release line.
- Built internal `0.1.0-alpha535` local image/TAR for the SSH Missing-Command Status-Contract follow-up; included in this public release line.
- Built internal `0.1.0-alpha534` local image/TAR for the SSH Status-Contract Fast-Path; included in this public release line.
- Built internal `0.1.0-alpha533` local image/TAR for SSH Capability-Draft Runtime Payload Recovery; included in this public release line.
- Built internal `0.1.0-alpha532` local image/TAR for the P0.2 Capability-Draft to Runtime-Payload Contract follow-up; included in this public release line.
- Built internal `0.1.0-alpha531` local image/TAR for P0 Executable Action Contract and Pending Integrity hardening; included in this public release line.
- Built internal `0.1.0-alpha530` local image/TAR for Agentic Runtime / Recipes / Observability Contract-Hardening; included in this public release line.
- Built internal `0.1.0-alpha529` local image/TAR for Chat Prompt Queue Collapse and P0 Connection Runtime Contract Recovery; included in this public release line.
- Built internal `0.1.0-alpha528` local image/TAR for the Web/Freshness and Recipe/Action-Planner heuristic cleanup; included in this public release line.
- Built internal `0.1.0-alpha527` local image/TAR for the P0 Legacy Semantic Authority Removal slice; included in this public release line.
- Built internal `0.1.0-alpha526` local image/TAR for the post-`alpha525` contract repair follow-up; included in this public release line.
- Built internal `0.1.0-alpha525` local image/TAR for the post-`alpha524` live-export follow-up; included in this public release line.
- Built internal `0.1.0-alpha524` local image/TAR for the post-`alpha523` live-export follow-up; included in this public release line.
- Refined the narrow iPhone admin indicator so the compact mobile header no longer shows a separate empty admin circle next to the section menu; the admin state is now folded into the menu button styling.
- Built internal `0.1.0-alpha522` local image/TAR for the post-`alpha521` iPhone admin-indicator and SSH explicit-ref/plural-scope follow-up; included in this public release line.
- Built internal `0.1.0-alpha523` local image/TAR for the post-`alpha522` live-export fix bundle; included in this public release line.
- Built internal `0.1.0-alpha521` local image/TAR for the AriaTurn meta-catalog seed follow-up and iPhone mobile header polish; included in this public release line.
- Tightened the authenticated mobile header for narrow iPhone viewports: the ARIA brand row stays compact, the section menu becomes icon-only, the admin state collapses to a small status chip, and long debug context IDs are ellipsized instead of making the chat header tall.
- Built internal `0.1.0-alpha520` local image/TAR for Runtime Target/Path Contract Hardening; included in this public release line.
- Built internal `0.1.0-alpha519` local image/TAR for the Learned-Recipe side-effect promotion gate and Provider Manifest runtime-adapter audit; included in this public release line.
- Added a Provider Manifest runtime-adapter audit against the Agentic Execution Registry so built-in adapters are classified as specialized or generic handler backed, while unknown adapters fail manifest validation.
- Built internal `0.1.0-alpha518` local image/TAR for the Agentic Operator Trace confirm-execute export follow-up; included in this public release line.
- Built internal `0.1.0-alpha517` local image/TAR for the Agentic Operator Trace confirmation follow-up; included in this public release line.
- Added Agentic Operator Trace confirmation follow-up after `alpha516`: confirmed routed actions now pass their execution details through the same trace appender, multi-target execution details are summarized as target counts instead of only the first ref, and live-shape golden tests cover SSH/API/pending/confirmed traces.
- Built internal `0.1.0-alpha516` local image/TAR for the Agentic Operator Trace live-shape fallback; included in this public release line.
- Added Agentic Operator Trace live-shape fallback after `alpha515`: existing `aria_turn_surface_action_arbitration` and execution detail lines can now produce draft/policy/runtime trace phases even when the routed-action debug objects are absent from the live detail payload.
- Built internal `0.1.0-alpha515` local image/TAR for Agentic Action Trace Completeness v1; included in this public release line.
- Added Agentic Action Trace Completeness v1: routed actions now expose existing action-contract, policy-decision, and executable next-step debug lines so Operator Trace can show draft/policy/runtime phases without changing routing behavior.
- Tightened the mobile Chat composer controls so the Tool-Box button becomes icon-only beside the Chat/Debug Export copy icon on narrow touch viewports, preventing label overflow on iPhone.
- Built internal `0.1.0-alpha514` local image/TAR for the mobile Chat composer icon-only polish; included in this public release line.
- Refined the Chat/Debug Export control from a full-width text action into a compact icon action beside the chat Tool-Box, while keeping the same clipboard/download behavior.
- Built internal `0.1.0-alpha513` local image/TAR for the compact Chat/Debug Export icon polish; included in this public release line.
- Built internal `0.1.0-alpha512` local image/TAR for the client-side Chat/Debug Export slice; included in this public release line.

### Fixed

- Fixed the post-`alpha603` ActionContract finalization gap in internal `alpha604` for multi-target actions: when a finalizer has already written concrete target refs and a read-only command, it now prunes only those stale `missing_fields` that are satisfied by the finalized payload before policy/dry-run evaluates it. This targets the live `alpha603` disk/diagnostic outlier without changing global pending-input semantics or adding prompt/SSH keyword rules.
- Fixed the remaining MetaCatalog backup action authority gap in internal `alpha603`: a legacy backup AriaTurn action plan can no longer become an executable Runtime/Pre-RAG owner after MetaCatalog unavailable, low-confidence, or invalid fallback; ARIA now stops with a visible contract-bound clarification instead of running backup-derived actions.
- Fixed the Memory-Browser structure drilldown state bug in internal `alpha602`: selecting collections, notes-as-documents, chunks, or entries now derives the browser type from the real collection so `notes`/document/entry hierarchy edges do not disappear because stale UI state falls back to `document`.
- Fixed the `alpha600` Memory-Browser follow-up in internal `alpha601`: own `aria_notes_*` collections are now listed slug-/case-tolerantly for the browser read model, legacy numeric chunk metadata no longer drops a whole collection, and notes collections no longer fall back to the limited semantic graph sample as visible structure truth.
- Fixed the Memory-Browser source-of-truth gap in internal `alpha600`: the structure drilldown now loads real Qdrant rows for memory entries and notes instead of depending on the limited semantic graph sample, groups `aria_notes_*` chunks by `note_id`/`note_title`, and exposes note chunks through the existing CSRF-protected point-delete path without offering unsafe whole-note deletion.
- Fixed the `alpha587` live follow-up gap in internal `alpha588` from `internal live export`: Same-Set Host/IP evidence no longer gets lost before the next turn, and incorrectly labeled Dev-Narrowing / Nicht-Dev-Exclusion follow-ups are reviewed against config-bound evidence before answering.
- Fixed the root cause behind the `alpha585` live regression family in internal `alpha586`: same-set Host/IP follow-ups reuse the previous config-bound SSH evidence without legacy memory, scoped dev follow-ups stay narrowed, exclusion follow-ups can return previous set minus selected refs, and missing scope operations block visibly.
- Fixed an unbuilt P1A regression from `internal live export`: last-turn SSH Host/IP evidence no longer captures unrelated Memory/Docs questions, and expanding from a dev-server subset back to all SSH servers falls through to the inventory loader instead of answering from the stale subset.
- Fixed an unbuilt inventory follow-up gap from `internal live export`: after a config-authoritative SSH Host/IP inventory, a scoped follow-up such as `Welche IP/Hostnamen haben meine dev-server?` can answer from the stored EvidenceBundle and remains narrowed to matching dev rows instead of saying the IPs are not in context.
- Hardened `llm_input_contract` redaction for common secret key variants such as access/refresh tokens, client secrets, secret keys, API keys, authorization fields, and nested token/secret suffixes.
- Hardened WebSearch source gating after the direct fastpath: empty or `0 Treffer` web contexts no longer count as usable evidence, path-aware `site:` queries stay intact, and current/latest answers fail closed when no preferred or official-adjacent source is present.
- Planned WebSearch with zero usable results now fail-closes as `web_source_no_reliable_sources` instead of passing an empty source set as a normal answer context; too-broad planned search intents can stop as a clarification before wasting retrieval/curation tokens.
- Hardened planned WebSearch provider evidence: existing `site:<domain>` queries from the LLM source plan are no longer double-prefixed, and off-domain results returned for a `site:<domain>` provider query are discarded before source curation.
- Counted bound connection inventory evidence by individual refs instead of source containers, so multi-ref context such as multiple dev servers reports and passes the correct source count to the answer contract.
- Migrated the Answer Composer LLM boundary to `llm_input_contract`: `aria_answer_composer` now sends only the canonical contract payload, with outcome/evidence under `world_map.answer_request`, preserving source-bound answer behavior without legacy top-level payload fields.
- Migrated the legacy Web Source Relevance Review LLM boundary to `llm_input_contract`: `web_source_relevance_review` and its retry validation now send only the canonical contract payload, with query, sources, runtime date, optional source plan, validation round, and review rules under `world_map.web_request`.
- Added a freshness-sufficiency boundary to planned WebSearch curation: when the user explicitly asks for a relative window such as "last few weeks" and the selected evidence only contains older dates, ARIA now performs one contract-bound freshness retry. If no fresher official evidence appears, older official evidence can still support a cautious "no recent evidence found" answer instead of a false positive. This is date/contract validation, not a product-specific fallback.
- Added contract-bound required-domain retrieval for planned WebSearch: when an LLM source plan names concrete required domains, WebSearch now executes generic `site:<domain>` queries from that plan, and source curation can perform one contract-validation recovery retry if the first result set lacks the required domain. This avoids product-specific fallbacks while ensuring required official sources are actually fetched.
- Hardened planned WebSearch source curation after `alpha556`: when the LLM source plan names concrete required source domains, selected sources are now validated against those domains before entering the answer context, or fail closed if none match. This is a generic source-contract boundary, not a product-specific Rabbit/Apple rule.
- Added current-date runtime context to LLM-planned WebSearch source acquisition and source curation so "latest", "current", and "last few weeks" claims are judged against the actual runtime date instead of stale inferred windows.
- Let planned WebSearch queries lead retrieval before the original user query, while keeping the original query as a recall fallback.
- Filtered registry/Docker/container-image results from planned WebSearch candidate sets only when the LLM source plan explicitly excludes those source classes, and removed the overly broad single-word `version` trigger that could boost registries for product comparison wording such as "old version".
- Added WebSearch fail-closed observability after `alpha553`: no-reliable-source WebSearch outcomes now carry `web_source_no_reliable_sources`, keep source/curation debug details in exports, show as WebSearch errors instead of `memory_error`, and route Discord alerts as `skill_errors` instead of `recipe_errors`.
- Added one bounded LLM-planned retry to planned WebSearch source curation: if the curator rejects off-topic sources and supplies retry queries, ARIA performs one second search round with the LLM-proposed query and curates that result set; no product-specific wordlists or retry loops were added.
- Added planned WebSearch source curation after `alpha552`: when an LLM Web Source Acquisition Plan is active, ARIA now asks a bounded LLM curator to select only sources that satisfy the requested entity, freshness, and source contract before the answer is composed; curation timeout, low confidence, or insufficient sources fail closed instead of answering from mixed SearXNG noise. WebSearch now carries snippets/page excerpts into source metadata and falls back to the `general` SearXNG category for planned source searches when the configured profile has no category.
- Added an LLM-first Web Source Acquisition Plan after `alpha551`: current/latest web questions can now plan concrete search queries and source requirements before SearXNG runs, the WebSearch skill executes those planned queries without product-specific code rules, and planned retry results fail closed if LLM source validation still finds off-topic evidence.
- Added runtime budgets to the post-`alpha550` web freshness path: page excerpts now fetch in parallel with a shorter per-page budget, the LLM web-source relevance review has a hard timeout with Routing Debug fallback, and the LLM freshness-query refinement falls back to the existing Web context if it stalls. This addresses live runs that stayed in `A.R.I.A. arbeitet weiter...` for several minutes on current product questions without adding product-specific rules.
- Hardened web evidence review after `alpha549`: a single irrelevant web source now still goes through LLM relevance review and retry, current/latest product or device web plans can get an LLM-refined freshness query even when the Meta-Catalog already selected Web, and the relevance-review contract now asks for semantically fitting current/primary-source evidence instead of accepting stale or off-topic hits.
- Removed the duplicate `Release` / current-version heading from the top of the `/stats` release card; the version panels remain.
- Removed the legacy runtime-task override/fastpath authority from production routing: RSS/chat/meta answers are no longer silently transformed into SSH package/update commands unless an executable SSH contract is explicitly present.
- Normalized LLM/Meta-Catalog `web_search` action contracts back into the existing Web context path, so web research uses the source-gathering pipeline instead of falling into a generic `searxng:web_search` runtime action.
- Added a file-action evidence boundary before SFTP/SMB action-mode seeds: real file/list/read prompts can still route to file operations, but document/manual questions such as Syncthing manuals no longer become blind root directory listings.
- Limited the Meta-Catalog connection-inventory normalizer to existing contracts: it no longer selects concrete connection IDs from the candidate hit list after the LLM/Meta plan; `connections:inventory` normalization now requires a connections surface, selected catalog ID, or existing connections context request.
- Removed the deterministic chat-freshness fallback after `alpha547`: current/latest/update/version wording no longer triggers web search when the LLM freshness arbiter is unavailable or invalid; only explicit web research requests and explicit URLs remain deterministic freshness fallbacks.
- Removed the old deterministic Meta-Catalog document-meta override after `alpha547`: a structured LLM/Meta-Catalog plan for `connections` is no longer rewritten to `docs:search` just because a document meta entry has lexical overlap. This keeps Syncthing connection-inventory prompts on the connections surface instead of falling through to unrelated document search.
- Kept Meta-Catalog surface review fail-closed when the review keeps a local Docs/Memory/Notes plan even though the router itself acknowledged connection evidence; this prevents self-contradictory `docs:search` answers from surviving when the review does not repair the route.
- Hardened the post-`alpha545` Meta-Catalog mismatch boundary: when the router's own structured output or reason acknowledges connection evidence but still selects local Docs/Memory/Notes, ARIA no longer silently continues with the wrong local search if no connection candidates can be recovered; the turn fails closed as a visible surface-review clarification instead.
- Recovered Meta-Catalog surface-review mismatches when the first routing window selects local Docs/Memory/Notes but the Meta-Collection still contains matching connection evidence: the review now reloads connection candidates from the Meta-Catalog before asking the LLM to resolve the surface contract, instead of silently falling through to the wrong local search.
- Hardened Meta-Catalog connection-evidence recovery after live Qdrant inspection confirmed Syncthing SSH/SFTP entries existed in both `aria_meta_catalog_aria_8800` and `aria_inventory_aria_8800`: the Connections surface now carries stronger bilingual inventory signals, and concrete connection evidence is sorted by query overlap before LLM surface review so specific candidates are not displaced by generic hits.
- Fixed the post-`alpha542` Docs evidence-contract failure in internal `alpha543`: exhaustive document corpus scans with zero match chunks no longer count their own "0 hits" diagnostics as source-bound evidence, so they cannot produce `fast_docs_search_answer` or `docs_search found/source_bound` responses. The trace now reports `matched=false reason=document_corpus_scan_no_matches`.
- Hardened the post-`alpha541` surface review so the LLM-first review can use the `surface|connections` descriptor as unbound connection-inventory evidence, preventing local Docs fastpaths from silently answering connection-inventory questions when concrete connection candidates are absent from the review set.
- Hardened the post-`alpha540` meta-catalog surface review: local Docs/Memory/Notes selections with competing connection candidates now pass the original router reason into the LLM-first review; accepted and kept-local outcomes are visible as `meta_catalog_surface_contract_review` Routing Debug lines, while unavailable, invalid, or low-confidence review outcomes fail closed as clarification instead of silently loading the wrong local context.
- Recovered two post-`alpha539` connection contract failures from the live export: meta-catalog docs choices that conflict with available connection catalog candidates now get an LLM-first surface-contract review before loading context, alias-bound resolved targets can defer a stale/wrong capability-draft `explicit_ref` before runtime payload construction, and the surface review is visible in Routing Debug/Operator Trace with a regression guard that real document questions stay on Docs.
- Removed the deterministic `connections:inventory` fast-list answer path after `alpha538`: inventory candidates no longer use query-term evidence filters or `fast_inventory_list_answer` to decide the visible answer scope. Unbound inventory hits now go through the LLM answer composer or fall back to a narrow-contract warning, while concrete Meta-Catalog refs/hints are preserved as bound inventory contracts through loading and merge metadata.
- Let concrete policy decisions override early turn-level confirmation hints in Operator Trace, so read-only actions that are allowed by policy no longer appear as `action=confirm` in the final policy phase.
- Redacted ungrounded mutating SSH command previews from blocked-action user messages: ARIA still reports the target and guardrail/security block, but no longer presents an unverified shell line as a planned executable action.
- Hardened the post-`alpha528` connection runtime contract: LLM capability drafts can return validated `connection_refs`, SSH `multi_target` no longer expands to all configured SSH profiles without explicit contract refs, exact requested refs are normalized to explicit refs, signed pending confirmations can execute without visible token text, incomplete action contracts no longer offer a run button, and recent-weeks/update product questions fall back to web freshness when no LLM freshness decision is available.
- Fixed the Chat Prompt Queue overflow on long waiting lists: more than two queued/pending entries now collapse into a compact queue header with an explicit show/hide toggle, so the chat remains visible while ARIA is busy.
- Removed P0 legacy semantic authority from the agentic front path: local capability fallback drafts, local fallback learning, deterministic unified-routing starts without authoritative drafts, the early runtime-task fastpath before Meta/AriaTurn, fleet expansion from sampled meta refs, and SSH scope group expansion from prompt seed terms no longer decide route, target scope, or tool choice.
- Kept P0-safe boundaries intact after the authority removal: explicit SSH refs still block contradictory multi-target runtime, SSH service probes require command/allowlist evidence, file paths are normalized or blocked at the contract boundary, WebSearch with zero sources stops before free-form answers, and inventory can still expose host/IP evidence.
- Cleaned the unbuilt post-`alpha526` agentic repair workspace against the Agentic Coding Manifest: removed RSS/Web overrides by update-word lists, IP/server inventory overrides, dev-scope marker filtering, product-family/Amazon/Rabbit WebSearch special filters, and fleet detection by word list.
- Kept the post-`alpha526` fixes that are boundary checks instead of meaning heuristics: SSH service-status probes require command/allowlist evidence, WebSearch with zero sources stops before free-form final answers, file paths are normalized or blocked at the action contract, explicit SSH refs block contradictory multi-target runtime, and inventory can expose host/IP evidence.
- Fixed post-`alpha523` to post-`alpha526` live-export regressions in workspace where the fix is a manifest-compliant contract, validation, fallback, or observability boundary rather than a prompt-specific router rule.
- Fixed a post-`alpha521` SSH scope edge where a concrete meta-catalog `explicit_ref` such as `ops-alert-01` for "monitoring server" could still be overridden by the later plural-target scope phase and expand to the full SSH fleet.
- Hardened the AriaTurn meta-catalog seed contract after `alpha520` live testing: SFTP file questions now seed explicit file operations and extracted remote paths instead of passing the whole user prompt as `path`, and SSH singular catalog targets no longer expand to multi-target execution without explicit fleet wording.
- Hardened Runtime Target/Path contracts after `alpha519`: SFTP/File-Read payloads no longer execute a whole user prompt as a remote path, and SSH health-style multi-target expansion now requires explicit fleet wording instead of expanding concrete singular targets such as "monitoring server".
- Fixed Learned Recipe promotion affordances so side-effect capabilities such as Discord, webhook, email, MQTT, and side-effectful file writes remain review-only/context-only instead of being shown as directly stored-recipe-promotable.
- Fixed the Agentic Operator Trace export follow-up for confirmed actions whose exported detail block contains only execution details plus web/browser timings: `Ausgeführt via ...` detail lines can now produce `operator_trace phase=runtime` without requiring a preceding `Routing Debug:` action line.

## [0.1.0-alpha511] - 2026-07-09

### Public Release Candidate Notes

- Prepared the post-`0.1.0-alpha437` public release line by consolidating the user-facing feature set: graphical Memory browser, Notes workspace improvements, Auto-memory and agentic learning UI, generated navigation, Chat Prompt Queue, visible pending confirmations, Agentic Operator Trace, stronger document inventory answers, web freshness source discipline, and safer multi-target runtime routing.
- Refreshed public-facing help coverage for Chat & Queue, Navigation & Menus, Notes, and the Agentic Operator flow so new capabilities are documented from the end-user perspective before the next public push.
- Published as public `0.1.0-alpha511` after internal `alpha511` validation; GitHub and Docker publication use the matching `v0.1.0-alpha.511` / `0.1.0-alpha.511` release line.

### Added

- Added the completed graphical Memory browser as an internal Qdrant/Memory maintenance and debug tool. It combines structure navigation, inspector drilldown, collection/document/entry/chunk hierarchy, point-level semantic proximity, deletion actions for chunks/points/documents, fullscreen support, iOS/touch handling, panbars, saved structure preferences, and organic graph physics.

### Changed

- Built internal `0.1.0-alpha511` local image/TAR for the Public Release Readiness slice: release draft, refreshed help/wiki/i18n coverage, and mobile queue polish; public release remains `0.1.0-alpha437`.
- Built internal `0.1.0-alpha510` local image/TAR for the product freshness official-source follow-up and post-`alpha509` full-suite fixes; public release remains `0.1.0-alpha437`.
- Improved current/latest product-line web searches so single product families can add official manufacturer/store/compare sources, while leak, rumor, and future-model sources are demoted for current availability claims.
- Built internal `0.1.0-alpha509` local image/TAR for Pending Confirmation Queue UX and the all-Linux full-fleet SSH scope follow-up; public release remains `0.1.0-alpha437`.
- Hardened Pending Confirmations in Chat Prompt Queue: confirmation-required actions now stay visible as their own queue/action item with waiting or expired status plus run, plan-again, and discard actions, without bypassing guardrails or executing automatically.
- Built internal `0.1.0-alpha508` local image/TAR for the server disk-capacity runtime fastpath and reusable local agentic prompt-test protocol; public release remains `0.1.0-alpha437`.
- Built internal `0.1.0-alpha507` local image/TAR for the HTTP API health fastpath, product-comparison freshness tweak, and Agentic Runtime Result Contract v1; public release remains `0.1.0-alpha437`.
- Added Agentic Runtime Result Contract v1 for multi-target SSH execution details: runtime records now emit a generic result contract with task intent, command profile, target/record/state counts, assumption or threshold, notable targets, and confidence, and Operator Trace prefers that contract as the visible `result` phase.
- Built internal `0.1.0-alpha506` local image/TAR for the Agentic Source Discipline / Action Contract follow-up; public release remains `0.1.0-alpha437`.
- Tightened current/latest product web answers so official vendor, release-note, documentation, and comparison sources dominate when available, while rumor, deal, news, and future-model sources are kept out of the answer context unless the user explicitly asks for them.
- Hardened connection action contracts so SSH/RSS action requests selected by the meta catalog cannot fall through to a plain inventory answer just because the action list is empty.
- Built internal `0.1.0-alpha505` local image/TAR for the Agentic Contract Trace follow-up; public release remains `0.1.0-alpha437`.
- Documented Chat Prompt Queue v1 as an accepted workflow improvement after the internal `0.1.0-alpha504` test/build: users can keep submitting prompts while ARIA is busy, then edit, remove, and reorder queued prompts before sequential execution. Mobile/iOS support is expected from responsive CSS, with future polish reserved for replacing the current browser `prompt()` edit dialog if needed.
- Built internal `0.1.0-alpha504` local image/TAR for Chat Prompt Queue v1; public release remains `0.1.0-alpha437`.
- Added Chat Prompt Queue v1: the chat composer can accept prompts while a response is running, keep waiting prompts in a per-tab FIFO queue, and let users edit, remove, or reorder not-yet-started prompts before sequential execution.
- Built internal `0.1.0-alpha503` local image/TAR for the Docs inventory evidence follow-up; public release remains `0.1.0-alpha437`.
- Fixed Docs inventory answers so `document_inventory=True` results are treated as document metadata evidence instead of being discarded by the normal search-term evidence filter.
- Built internal `0.1.0-alpha502` local image/TAR for the Web freshness contract follow-up; public release remains `0.1.0-alpha437`.
- Fixed Meta-Catalog/AriaTurn web context requests so `web:search` requests execute the web search runtime even when the high-level intent is only `chat`, and final web-backed answers receive freshness instructions.
- Built internal `0.1.0-alpha501` local image/TAR for the Docs inventory follow-up; public release remains `0.1.0-alpha437`.
- Fixed document-store inventory questions phrased as stored/archived content so they request document inventory instead of answering from only the top semantic chunks.
- Built internal `0.1.0-alpha500` local image/TAR for Agentic Operator Trace v1.1 contract propagation; public release remains `0.1.0-alpha437`.
- Extended Agentic Operator Trace observability so existing policy/preflight result lines become a generic `policy` phase, aggregate runtime timing lines are preferred over per-target runtime traces, summary timing is recognized by shape, and existing `target_intent` / `task_intent` contracts are preserved into multi-target runtime outcomes.
- Built internal `0.1.0-alpha499` local image/TAR for the first Agentic Operator Trace slice; public release remains `0.1.0-alpha437`.
- Added an Agentic Operator Trace debug contract that normalizes existing routing/runtime detail lines into stable phases for understanding, context, draft/policy, runtime, result, summary, and review-only learning. The trace is observability-only: it does not add semantic routing rules, prompt special cases, or new action decisions.
- Applied the HTTP API action contract before generic capability runtime execution, so configured health/status requests are normalized through the existing policy boundary before execution and mutating/confirmation-required HTTP API requests stay blocked from direct runtime execution.
- Built internal `0.1.0-alpha498` local image/TAR for the completed navigation follow-up; public release remains `0.1.0-alpha437`.
- Accepted the internal `alpha498` UI navigation follow-up after user live-testing on a real ARIA instance with live data; the menu/UI tweak block is considered closed.
- Built internal `0.1.0-alpha497` local image/TAR for the current Auto-memory, navigation, Appearance, Admin Mode, and final UI-polish changes; public release remains `0.1.0-alpha437`.
- Polished the generated navigation and hub pages: active states are quieter, Settings/Admin/Connections hubs are denser, Connections no longer acts as a status dashboard, Admin Mode is presented as `Extended view`, and long menu/help labels wrap more safely on mobile.
- Built the navigation follow-up in `alpha498`: `_section_nav.html` now renders through a central context navigation registry, header menus stay stable per section instead of switching into subchapter navigation, `/config`, `/config/persona`, and `/recipes` hub cards are generated from the same registry instead of hard-coded template links, `/config` now renders one card per meaningful Settings destination instead of a self-link card, Settings subpages keep the Settings main nav, Admin subpages keep `Admin` plus four stable real group pages (`/config/admin/config`, `/config/admin/recipes`, `/config/admin/memory`, `/config/admin/operations`) instead of hash anchors, each Admin group page renders only its own block while `/config/admin` remains the full overview, the global account menu no longer has a separate Admin overview entry, Settings becomes a real account-menu submenu with Admin inside it when Extended view is active, Admin is only exposed from `/config` when Extended view is active, `/recipes` is a real Recipes section hub and `/recipes/mine` is the explicit saved-recipes worklist, `/recipes/learned` stays the normal Recipes view while Admin maintenance moved to the distinct `/recipes/learned/maintenance` URL, the navigation registry now has regression tests against duplicate href ownership, wrong header-context switches, and wrong Admin menu exposure, System recipes stay in Admin navigation, Admin config pages no longer show Settings nav plus a second right-side Admin return link, Activities uses Admin navigation chrome, Auto-memory now has its own `/memories/auto-memory` page instead of an anchor inside technical Memory setup, Operations no longer duplicates the Updates entry, and Memory maintenance is no longer duplicated on the Admin overview.
- Refined the Recipes surface over the alpha UI work: saved recipes now live explicitly at `/recipes/mine`, `/recipes` is the Recipes section hub, New/Templates remains the combined creation/import/template entry point, Learned Recipes remains the review surface, and System recipes stay in the Admin maintenance context.
- Combined new recipe creation, JSON import, and template import on the New/Templates page while keeping `/recipes/templates` as a compatibility route.
- Reduced Recipes UI terminology drift by making visible labels recipe/template-first instead of skill/sample-first, and collapsed the Learned Recipes process explanation behind a compact help disclosure.
- Added a clearer global Admin section in the authenticated menu: daily work areas stay separate from Admin Mode links such as system recipes, learned-recipe maintenance, Memory import/maintenance, connections, stats, activities, and updates, while the Admin Mode toggle remains reachable even when Admin Mode is off.
- Hid advanced Config hub/subnav entries when Admin Mode is off, keeping the access/admin-mode path visible so users can re-enable administration without hunting through hidden tools.
- Collapsed the global Admin section into one Admin submenu so the account menu stays compact while still keeping all admin destinations available on demand.
- Moved Updates back into the normal user-facing navigation and grouped technical Config destinations under an Admin submenu, so `/config` stays focused while updates are not treated as an Admin-only destination.
- Moved Statistics back into the normal user-facing navigation because usage and cost overview are useful outside Admin Mode.
- Removed Memory Import from the global Admin submenu because document import is a normal Memory workflow reachable from the Memory area.
- Added a dedicated, collapsible-section `/config/admin` hub and shared Admin navigation source so the global Admin submenu and Admin page stay consistent while `/config` shows only one Admin entry.
- Simplified Config/Help chrome: technical Config subpages now link back to the Admin overview, contextual help blocks are compact links into the Help system instead of inline explanations, and visible German labels use recipes/templates/connections wording more consistently.
- Tightened the new Admin/Config layout for iPhone, iPad mini, and other narrow touch viewports with explicit wrapping, touch-target, and compact-help-link guards.
- Reduced global menu nesting by replacing the Admin submenu with one direct Admin overview entry; the generated `/config/admin` page remains the single place for grouped technical destinations and now has a dedicated Memory section with direct Auto-memory & learning and Memory maintenance links.
- Added user-facing Connections and Recipes entries to the Settings hub and Settings subnav so central workflows are reachable from `/config` without being hidden in Admin; Recipes is no longer duplicated as a separate global menu entry.
- Kept Memory Import as a normal Memory-area user action while moving Memory Maintenance out of the Memory subnav and leaving it reachable through the Admin overview's Memory section.
- Added parent navigation for moved areas: Recipes and Connections now link back to Settings from their subnavs, while Auto-memory setup and Memory Maintenance link back to the Admin overview.
- Added a central hierarchical navigation registry and shared subnav renderer so Settings, Recipes, Connections, Memory, and Admin navigation are generated from one movable page tree instead of hard-coded per-template links.
- Removed the Settings subnav from the Admin overview so `/config/admin` shows only the generated Admin sections instead of repeating normal Settings tabs.
- Removed status summary tiles from the Settings overview because those operational signals belong in Stats, leaving `/config` as a quieter navigation hub.
- Removed status summary tiles from the Connections overview because live connection signals belong in Stats or the dedicated Live Status page, leaving `/connections` as a quieter navigation hub.
- Moved the Admin Mode toggle out of the global Areas menu and the Users page into a compact account-level Extended view control, backed by a narrow `/config/admin-mode` page that only manages this one option.
- Kept Appearance and default Language settings user-accessible when Admin Mode is off, while leaving Prompt Studio and language-file editing behind Admin Mode.
- Added a direct `/memories/create` page and Memory subnav entry for creating a manual memory, so the create flow is no longer hidden below Document Import.
- Added combined Appearance theme sets that choose a matching theme palette and background image together while keeping the individual Theme and Background selectors available for manual fine-tuning.
- Clarified Auto-memory as Auto-memory & agentic learning: the new `/memories/auto-memory` page separates status, user-facing effects, help link, and advanced extraction details, and the chat/status entry points link directly to that page.
- Simplified the Learned Recipes page further with a compact summary strip, collapsible filters/sorting, flatter review rows, and admin-only process, contract, learning, curator, promotion, dismiss, and delete details tied to Admin Mode.
- Notes can now be moved directly from the board cards or the editor into another existing folder or back to Inbox. The move updates the Markdown source path/frontmatter and reindexes the note so the Qdrant Notes collection follows the new folder.
- Added a dense Notes list view with multi-select bulk move, so existing notes can be organized across folders without opening each card one by one.
- Added a compact clickable breadcrumb path to the Memory browser inspector so users can jump back to root, type, collection, or document context without hunting in the graph.
- Consolidated Memory browser inspector selection handlers into shared state helpers, reducing duplicated navigation logic between collection, document, chunk, and entry drilldowns.
- Simplified the unified Memory browser context model so structure navigation, inspector drilldown, and semantic proximity all derive availability from the same current point context instead of scattered special cases.
- Tightened the Memory browser fullscreen layout so the graph/inspector workspace uses more of the viewport and the semantic viewport follows the same compact fullscreen sizing as the structure graph.
- Stabilized the Memory browser as the primary graphical view for browsing and maintaining ARIA's Memory stores. Import and technical maintenance flows stay on separate pages so the browser can remain focused on reading, navigating, inspecting, and selectively deleting Memory data.
- Refined the Memory section into clearer `Memory`, `Import`, and `Maintenance` areas. The Memory view is now a focused graphical browser for stores, documents, chunks, and semantic proximity, while upload and technical maintenance actions live on separate pages.
- The Memory browser now keeps structure and semantic proximity as modes of the same browser space. Structure view auto-fits the graph to the available viewport and includes zoom, fit, and center controls for deeper drilldowns.
- Structure mode now uses the same round-node SVG graph language as semantic proximity, so switching modes feels like staying in one browser instead of jumping between unrelated layouts.

### Fixed

- Fixed the no-LLM action-planner fallback so stored recipe candidates do not make a clear built-in template action look ambiguous when ARIA has no LLM client available.
- Fixed SSH follow-up routing so a reconstructed current-target SSH prompt is not preempted by generic stored recipe arbitration.
- Fixed all-scope SSH target narrowing so prompts like "all Linux servers" keep the full SSH fleet when only OS/runtime words are present, while true groups such as dev, DNS, or management can still narrow normally.
- Fixed expired or invalid routed-action confirmation feedback so the user gets a recovery hint to plan the action again or discard the pending confirmation.
- Fixed plural server disk-capacity questions so an LLM-selected `capacity_check` capability draft can use the runtime-task SSH fastpath instead of falling through to unrelated local document search; exact single SSH refs still stay on the normal single-target path.
- Tightened web-backed product comparison answers so ARIA separates model-specific improvements from carried-over, ecosystem, or software-only features and only presents a change as "more than the old version" when the provided sources support that comparison.
- Suppressed stored-recipe arbitration for clear HTTP API status/health capability drafts, so configured single-profile health checks can stay on the local `health_path` contract without an unnecessary `recipe_execution_intent` LLM call.
- Added Agentic Contract Trace follow-up: current/latest public product comparison questions can override an accidental local Docs-only meta-catalog match and route to WebSearch, `context_packet` debug lines now summarize requested/loaded/empty/missing context per TurnPlan, and `answer_contract` debug lines expose source-bound answer status before direct or empty context answers.
- Removed the extra `Puke Unicorn` theme decorator and theme-specific background pattern layers so the selected background image is the only visual background source for that palette.
- Fixed Memory browser structure-node dragging so moved nodes become soft simulation anchors instead of snapping back to their old layout positions; connected neighbor nodes now receive a small settling impulse and drift with the dragged node.
- Persisted Memory browser structure view options in local browser storage and widened the spacing, clustering, and attraction ranges for stronger layout tuning.
- Fixed the Memory browser fullscreen header layout so the ARIA brand, browser title, and mode controls share one coherent header row instead of overlapping separate header blocks.
- Fixed detached fullscreen semantic Memory views so document, chunk, and entry focus are preserved instead of falling back to structure mode.
- Reworked the Memory browser fullscreen header into a compact topbar and added touch/iOS fallbacks so the graph and inspector get more usable height without cramped controls.
- Replaced the earlier fullscreen right-rail title placement with the compact topbar layout so the header stays coherent across graph and inspector.
- Fixed fullscreen semantic Memory graph clipping by allowing the SVG layer to render labels and shifted nodes beyond its internal viewBox edge.
- Fixed the Memory browser fullscreen brand mark by rendering the actual ARIA logo image plus its overlay, instead of an invisible overlay-only logo.
- Fixed theme collisions in Memory browser controls and inspector drilldown lists so broad theme button styles no longer turn browser navigation into oversized accent bars.
- Fixed semantic proximity availability for collections/documents that already expose concrete entries/chunks in the inspector: semantic proximity is offered from the current visible point context, while higher summary levels remain structure-only.
- Changed Memory browser semantic proximity into a point-level view: the semantic mode tab stays hidden on pure summary levels, appears when the current inspector level exposes concrete chunks/entries, and no longer exposes the global semantic collection overview inside the unified browser.
- Fixed Memory browser semantic-mode state handoff: inspector navigation now keeps the semantic browser active, focuses the selected collection/entry/chunk in the Qdrant Brain view, clears stale semantic detail on the entry page, and restores the ARIA brand mark in fullscreen.
- Reduced semantic overview label collisions by spreading collection nodes into a wider organic cloud with quieter overview labels, without changing the normal semantic point-graph layout.
- Changed the Memory browser semantic entry overview from a forced column list into an organic collection cloud, and removed the temporary semantic overview fit experiment so the real semantic point graph logic stays isolated.
- Fixed the Memory browser semantic switch so it no longer falls back to a global semantic root view when the current drilldown collection cannot be focused in the Qdrant Brain graph. Semantic proximity is only offered when the current collection can actually be shown.
- Fixed semantic availability for document collections by prioritizing document graph points in the Qdrant Brain sample used by the Memory browser.
- Fixed the Memory browser `Center` control so it recenters the current structure zoom level instead of resetting back to fit mode.
- Added drag-to-pan for the structure graph stage so zoomed drilldowns can be moved directly with the pointer.
- Fixed the Memory browser structure source so it shows all Qdrant collections from the live collection overview instead of only user-memory recall targets.
- Fixed structure drilldown navigation so clicking a node focuses, centers, and zooms that node instead of returning to the full-map overview.
- Fixed document-store counts in the Memory browser so non-document collections such as recipe experience or self-learning stores are not mixed into document totals.
- Moved Self-Learning out of the user Memory view and into Maintenance, keeping review and worker tooling separate from read-only browsing.
- Fixed structure graph interaction so nodes can be dragged like the semantic graph and connected edges update while dragging.
- Kept the Memory node inspector visible in fullscreen as a compact detail strip below the graph.
- Added cursor-centered mouse-wheel zoom and two-finger pinch zoom to the Memory structure graph.
- Moved the Memory fullscreen inspector into a right-side detail rail on wide windows.
- Added an automatic force-layout relaxation pass to the Memory structure graph so opened collections, documents, and chunks self-organize into clearer clusters.
- Fixed fullscreen semantic proximity for focused document stores so the selected collection is carried into the Qdrant Brain graph sample and document chunks remain visible instead of falling back to a sparse/global semantic view.
- Broadened Qdrant Brain sampling across ARIA collections so semantic proximity is also available for non-document stores such as Notes when they have visualizable vector-backed points.
- Changed the Memory structure graph from a static post-layout cleanup to a live force simulation that continues to settle nodes and reheats after drag interactions.
- Fixed semantic proximity detail panels so focusing a collection selects a real point immediately and falls back to readable label/meta previews when payload text is sparse.
- Fixed embedded semantic proximity graph scoping so clicking a node updates the detail panel belonging to that graph instance, including fullscreen/document-store views.
- Added compact Memory structure view options for spacing, clustering, and attraction, and made node focus less aggressively centered so open graphs use the available space better.
- Fixed semantic proximity document chunk nodes so chunk points are labelled and detailed as chunks instead of appearing as the parent PDF, and exposed spacing, clustering, and attraction controls in the semantic graph/fullscreen view.
- Fixed semantic proximity node details so clicked document chunks render as `Chunk N` with the actual chunk excerpt in the inspector, not as the parent PDF.
- Added a Memory structure `Expand all` control that opens all currently known graph levels at once; centering now preserves the expanded graph state.
- Adjusted Memory structure graph placement so relaxed node clusters are shifted into the usable middle of the stage instead of hugging the upper edge.
- Improved Memory structure fitting so `Fit` uses the visible node bounds rather than empty graph canvas space, making open graphs use the available viewport more evenly.

## [0.1.0-alpha437] - 2026-06-30

### Changed

- Continued the agentic runtime cleanup by moving runtime-outcome follow-up handling out of the main pipeline into a focused resolver module, reducing the size of the central pipeline without changing the public routing contract.
- Feedback learning from chat is now queued through the Learning Worker instead of being awaited directly in the web request, reducing avoidable wall time after user feedback.
- Clear multi-target runtime tasks, such as server package update checks, can use a bounded capability-draft fast path before the Meta-Catalog call while still going through the existing confirmation, policy, and execution guardrails.
- Web Search is more robust when SearXNG primary queries time out: official supplemental queries are best-effort and no longer discard otherwise valid primary results.

### Fixed

- Fixed broad uploaded-document inventory questions so ARIA loads the selected document store inventory instead of answering from only one or a few semantically selected document IDs.
- Fixed corpus-wide uploaded-document substance checks when the Meta-Catalog narrows the query to one promising document. ARIA now preserves the original user prompt as a scope signal, keeps the selected document collection, and performs an exhaustive corpus scan before answering.
- Fixed document corpus scans so explicit target collections are passed through the surface loader, recipe runtime, and Memory skill consistently, preventing unrelated documents or recipe-experience records from entering source-bound document answers.
- Fixed a runtime-follow-up edge where a previous package-update frame could keep influencing a later, unrelated document question.

### Upgrade Notes

- Normal managed installs should use `/updates` or `./aria-stack.sh update`.
- Fixed-tag installs can use `fischermanch/aria:0.1.0-alpha.437`.
- Normal updates should recreate only the `aria` service and keep Qdrant, SearXNG, Valkey, and persistent volumes untouched.

## [0.1.0-alpha433] - 2026-06-30

### Fixed

- Fixed exhaustive uploaded-document corpus scan answers when the searched substance itself has zero matches but supporting context terms such as "ingredient" or "composition" have matches. ARIA now keeps per-term scan evidence and can answer from the corpus coverage without overclaiming from a single retrieved document.
- Added a source-bound fallback for exhaustive document scans so an invalid answer-composer response no longer degrades to "matching passages found" when the primary searched term was not found.

## [0.1.0-alpha432] - 2026-06-30

### Fixed

- Fixed corpus-wide uploaded-document questions when the Meta-Catalog selects the structured document-corpus scope (`local|docs|documents`) but labels the context depth as shallow. ARIA now treats that selected scope as sufficient evidence-policy signal to require a document corpus scan before answering.
- This keeps "is this term in any uploaded document?" answers source-bound to corpus coverage instead of allowing a single semantically retrieved document excerpt to answer for the whole uploaded-document set.

## [0.1.0-alpha431] - 2026-06-30

### Fixed

- Fixed deep document corpus scans for explicitly selected named document collections. When document guides or document metadata select a custom uploaded-document collection, the exhaustive scan now treats that selected collection as the allowed source scope even if the collection name is not a plain `aria_docs_<user>` slug.
- Deep document searches now retry the corpus scan after guide selection when the pre-guide scan cannot find an accessible corpus, so source-bound answers over named upload collections no longer fall back to semantic top-k snippets only.
- Added debug visibility for the deep document corpus-scan request in the context ledger.

## [0.1.0-alpha430] - 2026-06-30

### Fixed

- Tightened deep source-bound document searches over uploaded document collections. When the LLM-selected document plan asks for deep docs context, ARIA now requests an exhaustive document corpus scan before semantic top-k snippets can answer, preventing generic section/ingredient wording from masking that the specific searched term was not covered by the retrieved excerpts.
- The deep document corpus scan remains part of the docs evidence policy, not a deterministic router: the Meta-Catalog still chooses the docs/deep context contract, and the Memory skill then proves corpus coverage before source-bound answers can claim presence or absence.

## [0.1.0-alpha429] - 2026-06-30

### Fixed

- Fixed source-bound negative document-search answers. When a docs-only recall does not retrieve chunks that actually contain the query evidence, ARIA now performs an exhaustive literal scan across the selected uploaded document chunks and records how many documents/chunks were scanned before allowing a negative answer.
- Document corpus scans now report per-term coverage and source details for every scanned document, so answers such as "not found in the uploaded documents" are backed by explicit scan coverage instead of only a semantic top-k miss.

## [0.1.0-alpha428] - 2026-06-29

### Fixed

- Fixed source-bound document inventory questions over uploaded document collections. When the Meta-Catalog selects multiple document metadata entries, ARIA now carries document IDs, names, and target collections into the context loader and loads the document metadata inventory directly instead of falling back to a semantic chunk recall that could return only one matching document.
- Fixed a Pre-RAG SSH target recovery edge case where a semantically resolved SSH profile could still leave stale `missing_parameters` safety/execution state behind, causing ARIA to ask for a profile even after resolving the target.

### Changed

- Document inventory recall now uses existing document guide/catalog metadata and skips the embedding/chunk-search path for these list-style document requests, making answers both more complete and cheaper for "what documents do I have?" style prompts.

## [0.1.0-alpha427] - 2026-06-29

### Changed

- Moved StageTiming detail-line insertion into `aria.core.stage_timing` while keeping the existing context-runtime delegate, reducing debug/timing helper code inside the agentic runtime mixin without changing routing behavior.
- Consolidated repeated agentic operation refresh handling in `pipeline.py`. File, message, and read operation refinement now share template-operation refresh, draft hydration, and payload/safety/execution debug rebuilding while keeping their own eligibility and completion rules.
- Began the large routed-action monolith reduction with characterization coverage and small helper cuts. Requested/plural connection scope, explicit-ref resolution, and single-RSS profile handling now have focused helpers while `_resolve_unified_routed_action` remains the orchestration point.
- Added `aria.core.forced_resolution_builder` for forced routed-action finalization, forced-record attachment, retry on `missing_fields == ["connection_ref"]`, and kind-only fallback while `pipeline.py` keeps compatibility delegates.
- Added `RoutedActionDebugBuilder` to centralize routed-action detail-line merging, routing-record attachment, and connection-candidate debug serialization while preserving the existing Pipeline compatibility delegates.
- Added `ConnectionRefScope` to normalize requested/explicit connection refs from drafts and payloads before routed-action gates, guards, RSS single-profile selection, and explicit-ref handling consume them. This is a hygiene/modularization slice only; routing semantics and debug field names are unchanged.
- Added an initial `RoutedActionResolver` request/callback service boundary and routed the Pipeline pre-RAG action gate through it while keeping `_resolve_unified_routed_action` as the compatibility implementation. The resolver now owns the routed-action request prelude, initial routing-chain/no-LLM fallback, and early candidate-pool outcomes without changing routing behavior.
- Extracted the chain-complete routed-action rebuild path from `_resolve_unified_routed_action` into a focused Pipeline helper, keeping plural SSH rebuild, path-hint rebuild, routing records, candidate debug, and requested-connection guard behavior intact.
- Added the `SshTargetScopePolicy` preparation dossier, moved `SshTargetScopeDecision` into `aria.core.ssh_target_scope_policy`, and expanded the policy for SSH plural-target narrowing, agentic multi-target command preparation, and multi-target payload finalization. Direct tests cover requested single-target handling, requested-ref group expansion, `command_draft`, health/package-update command adaptation, and read-only multi-target non-finalization while `pipeline.py` keeps compatibility delegates.
- Extracted routed-action memory/semantic hint resolution into `_resolve_memory_semantic_routed_action_hints`, keeping Memory Assist, semantic candidate resolution, semantic LLM refinement, routing records, planner-candidate selection, and draft hint-path hydration together behind a typed result while `_resolve_unified_routed_action` remains the orchestrator.
- Split the memory/semantic hint path further into focused helpers for memory-hint debug, high-confidence semantic candidate override, deterministic semantic candidate selection, semantic-LLM selection, and SSH memory-hint revalidation, preserving the existing routing debug strings and decision-record stages.
- Moved the routed-action memory/semantic hint decision helpers into `RoutedActionResolver`; `pipeline.py` now supplies Memory Assist results, semantic candidates, requested-ref matching, and draft hydration while the resolver owns the reusable hint decisions and direct unit coverage.
- Extracted routed-action forced-ref, RSS semantic-refine, and kind-only fallback resolution into `_resolve_forced_or_kind_only_routed_action`, preserving requested-ref blocking, plural target context handling, kind-only routing records, candidate debug, and forced-resolution finalization while further reducing `_resolve_unified_routed_action`.
- Moved the forced-ref tail decisions for plural-scope memory hints, requested-ref memory-hint blocking, requested-ref semantic rebinding, default single-profile selection, and RSS semantic refine into `RoutedActionResolver` while keeping Pipeline as the action orchestration adapter.
- Routed forced finalization selection and the kind-only/plural-context fallback through `RoutedActionResolver`, leaving Pipeline with thin compatibility delegates to the existing forced-resolution builder, SSH plural preparation, candidate debug, and requested-connection guard callbacks.
- Split the kind-only/plural-context fallback from `_resolve_forced_or_kind_only_routed_action` into `_resolve_kind_only_or_plural_context_routed_action`, keeping kind-only records, scoped SSH plural handling, multi-target payload preparation, candidate debug, and the requested-connection guard together in a smaller helper.
- Moved SSH plural-finalizer eligibility and requested/plural-scope checks into `SshTargetScopePolicy`, leaving `pipeline.py` to delegate the decision before narrowing/preparing multi-target SSH actions. This is hygiene only; routing behavior and debug contracts stay unchanged.
- Grouped routed-action build, SSH, semantic, and guard callbacks into named callback bundles for the forced/kind-only and kind-only/plural resolver paths, reducing long Pipeline-to-Resolver argument lists without changing behavior.
- Completed the planned Pre-RAG/Capability action-gate cleanup with a local dossier, seeded Runtime Task Contract regression coverage, `_resolve_pre_rag_capability_draft`, `CapabilityActionResult`, shared Pre-RAG capability-result wrapping, `CapabilityActionInputs`, `CapabilityHintResolution`, and `CapabilityActionPreflightResult`. This is hygiene only; action routing, guardrails, and debug contracts stay unchanged.
- Completed the planned `process()` orchestrator cleanup with a local phase dossier, `TurnExecutionState`, named process finalization, shared active-learning hint scheduling, `ProcessTurnContracts`, `ProcessActionRecipeStageResult`, `ProcessContextLoadResult`, `ProcessContextAnswerStageResult`, and `ProcessChatResponseStageResult`. This is hygiene only; stage timing, direct-context fast paths, learning hooks, and routing behavior stay unchanged.
- Completed the planned Agentic Context Runtime cleanup by extracting answer composition and Docs/Notes fast-answer builders into `aria.core.context_answer_runtime`, moving TurnFrame persistence into `aria.core.context_runtime_state`, and moving active-learning hint recall into `aria.core.active_learning_hint_runtime`. Compatibility delegates remain on the mixin; no routing or answer semantics changed.
- Completed the planned MemorySkill cleanup with a local responsibility dossier, `aria.core.memory_recall_helpers` for recall source-entry formatting/prioritization, `aria.core.document_memory_service` for document guide/store/delete flows, `aria.core.memory_admin_query_service` for read-only admin/search/graph queries, and `aria.core.session_compression_service` for old-session rollup orchestration behind the existing MemorySkill facade.
- Started the Legacy/Fallback audit with a local dossier and classified remaining fallback paths as technical safety, migration adapters, no-LLM fallbacks, or removal candidates. Memory keyword fallback now emits a `Routing Debug: memory_keyword_fallback ...` detail line without changing recall behavior.
- Tightened the Pre-RAG capability boundary so an out-of-bounds `capability_draft_decision` cannot fall through into local legacy SSH fallback routing.
- Added Phase-9 fallback guardrails: meta-catalog low-confidence backup actions and unavailable-catalog backup chat now have regression coverage, local capability fallback drafts carry risk markers, and unknown `invalid:*` capability-draft states no longer enable local legacy fallback routing.
- Extracted shared Context evidence helpers from `AgenticContextRuntimeMixin` into `aria.core.context_evidence`. Topic-term extraction, request-scope ignore terms, inventory matching, and normalized evidence text matching now live in a focused module with cached static term sets while existing runtime delegate methods keep compatibility.
- Extracted the Context Surface loader boundary from `agentic_context_runtime.py` into `aria.core.surface_loader_runtime`, keeping the ARIA context mixin closer to orchestration and moving inventory/memory-exists loading into a dedicated runtime service.
- Consolidated duplicated forced-connection resolution record building in `pipeline.py` behind a helper so the unified routed-action path has one implementation for attaching detail lines, routing records, and candidate debug metadata.
- Promoted the bounded Mill WiFi Docs answer from fallback-only to a conservative source-bound fast path. When the selected document evidence clearly contains the Mill heater WiFi setup/troubleshooting instructions, ARIA can answer directly without the second Docs answer-composer LLM call, while unrelated or unsafe document content still uses the normal composer/fallback path.
- Added a conservative Direct-Docs performance fast path for already source-bound document search results. Compact, verified `docs:search` answers can now skip the second answer-composer LLM hop, while large or ambiguous document content still falls back to the composer. The Meta-Catalog router payload was also slimmed by shortening per-candidate descriptive fields without reducing the candidate count.
- Extracted document memory helper functions from `MemorySkill` into `aria.core.document_memory_helpers`. User slug normalization, document payload name/id extraction, document collection matching, document-meta collection detection, and payload user matching now live in a small shared helper module while `MemorySkill` keeps compatibility delegates.
- Extracted RSS execution policy helpers from `pipeline.py` into `aria.core.rss_execution_policy`. `RssActionSelectionPolicy` now owns the exact-feed guard, single-RSS-profile selection, RSS group-bundle selection, digest-option note creation, and ambiguous-candidate refine checks while `pipeline.py` keeps compatibility delegates. This is a hygiene/modularization slice only; explicit RSS feed reads and broad RSS group digests keep their existing behavior.
- Added a fast direct inventory-list answer for multi-source RSS/Connections inventory results so large local source lists stay as readable multi-line markdown and skip the answer-composer hop. The answer composer now preserves line breaks when it is used.
- Added bounded routing diagnostics for ARIA turn arbitration and Meta-Catalog routing. Context ledger/debug lines now include routing payload bytes, system prompt chars, payload key count, and prompt/completion tokens without exposing prompt payload content.
- Compact-serialized bounded decision payloads before sending them to the LLM, reducing routing/request bytes without changing the decision contract.
- Added Multi-Target SSH timing diagnostics. Debug output now includes per-target runtime, summary operator/LLM timing, and aggregate preflight/execution/summary/remember/total timing with the slowest target, without changing SSH policy, guardrails, or target selection.
- Added Web chat route timing diagnostics. Badge details now split post-pipeline handling and route preparation/history/follow-up/flow/history-append timing, and response headers expose template and cookie timing so browser-wall-time gaps can be attributed without changing answer or routing behavior.
- Added an explicit WebSearch performance fast path. Standalone prompts that explicitly ask ARIA to search/research on the internet now skip the Meta-Catalog arbiter and the web-route follow-up rewrite LLM, while vague explicit web follow-ups can still be rewritten from recent chat context.
- Added multi-target official WebSearch supplements for explicit current-product queries. Multi-product searches can now run product-specific official-source queries, so a prompt that asks for the latest Apple Watch Ultra and latest iPhone can surface both official product pages instead of letting one product dominate the result set.
- Added source-bound target coverage hints to WebSearch results for multi-product queries. The final answer composer now sees one compact evidence row per detected product target, preventing one well-ranked product from causing another sourced product to be reported as missing.

### Fixed

- Strengthened the source-bound Docs fallback for Mill WiFi heater instructions. When the selected document/query metadata clearly identifies the Mill WiFi setup source and the retrieved evidence contains app, router/2.4GHz, or WiFi-button instructions, ARIA now returns concrete bounded steps instead of a generic safe-summary fallback after an invalid answer-composer response.
- Restored explicit web-search routing after a Meta-Catalog plain-chat contract. When the user explicitly asks ARIA to search/research on the internet and Web/SearXNG is available, the existing freshness/web contract now normalizes the turn to `web_research`/`web_search` with source-bound evidence instead of falling through to a generic chat answer claiming ARIA cannot browse.
- Reduced runtime follow-up latency for SSH path inspections. If the last runtime outcome contains a requested POSIX path and exposes `inspect_path`, ARIA now builds the read-only SSH inspect follow-up directly from frame evidence without the `runtime_outcome_followup_resolution` LLM hop; unrelated single-command turns fall through to normal Meta-Catalog routing instead of paying that follow-up LLM.
- Kept SSH runtime path-inspection results source-bound in the visible answer. Directory inspection commands such as `du -h --max-depth=1 /tmp ...` and `ls -lah /tmp` are now summarized from their actual stdout instead of being misread as generic `df`/root-filesystem health checks.
- Restored the agentic server-update correction path when the Meta-Catalog narrows a mixed RSS/SSH update turn to `rss_read_feed` even though SSH targets are present in the turn contract. The existing bounded `capability_draft_decision` can now recover the SSH package-update check without adding new keyword routers, and blocked memory hints are fully cleared before forced routed-action finalization.
- Preserved Runtime Task Contract SSH target refs through the Pre-RAG action gate so recovered server-update checks remain multi-target instead of being narrowed by later plural-context alias matching.
- Fixed the `alpha408` Docs answer fallback regression where a failed/invalid Answer Composer response could expose raw multilingual PDF chunks for `docs:search` answers. Source-bound Docs fallback now produces a concise bounded answer for the Mill WiFi heater setup case, or a clear safe source-bound fallback, instead of dumping raw retrieved chunks.
- Kept explicit RSS feed reads bound to the requested feed ref instead of expanding them to a same-named RSS group. A prompt such as "lies den feed heise-security-alerts" now reads only that RSS profile even when several Heise feeds share the `Heise` group, while broad prompts such as "aktuelle security news aus rss" still use grouped RSS digests.
- Normalized RSS Meta-Catalog contracts so RSS inventory questions stay on `connections:inventory` even when an unrelated document also matches words like "security" or "feed", and explicit read-only prompts such as "lies den feed heise-security-alerts" seed the executable `feed_read` path instead of falling through to empty `connections:action` context.
- Made the blocked mutating SSH response explicit and short: ARIA now tells the user that Guardrail/SSH policy blocked the state-changing request and still does not replace it with a read-only probe.
- Preserved runtime context after confirmed single-target SSH actions. Generic SSH command execution now emits a `RuntimeOutcomeFrame`, and immediate read-only follow-ups can be resolved from that frame before normal Meta-Catalog/Docs routing takes over.
- Made runtime SSH path follow-ups more tolerant of bounded-LLM schema variants. If the LLM correctly selects a read-only runtime follow-up but returns an affordance variant or a kind-prefixed SSH target ref, ARIA normalizes that to the existing runtime outcome contract instead of falling through to unrelated Meta-Catalog/Docs routing.
- Kept cited path follow-ups on the runtime SSH context even when the bounded follow-up LLM misclassifies the turn as a new Meta-Catalog request or omits the command. If the path is present in the previous runtime output and `inspect_path` is allowed, ARIA builds a read-only SSH inspect draft for the same target and still runs it through SSH policy and confirmation.
- Treats the visible web chat history as first-class routing evidence. Recent user/assistant turns now flow from the chat route into `pipeline.process`, then into Meta-Catalog routing and the backup turn arbiter as `recent_visible_chat_context`; Meta-Catalog candidate recall also gets a contextual semantic query so elliptic follow-ups to visible SSH/action output can retrieve the referenced connection instead of drifting into unrelated Docs/Memory hits.
- Preserved single-target scope for direct runtime SSH path follow-ups. A follow-up resolved from visible `RuntimeOutcomeFrame` evidence, such as inspecting `/tmp` after a confirmed single-host disk-usage command, now carries an explicit single-target note so later plural SSH scope handling cannot widen it to every SSH profile.
- Improved WebSearch/SearXNG source quality for recency and current-product queries. ARIA now can run an additional official-source search for current product/version questions and ranks official manufacturer/product pages above news, shopping, and deal-style results while still preserving normal dated-news recency when no stronger official source exists.
- Kept explicit internet-search requests on WebSearch even when the Meta-Catalog selects a read-only RSS feed action. A prompt such as "suche im internet ..." now normalizes RSS/feed action contracts back to the existing `web_research`/`web_search` contract instead of reading a topical RSS feed such as Apple Newsroom.

## [0.1.0-alpha403] - 2026-06-26

### Fixed

- Added semantic asset aliases to the Docs Meta-Catalog so English manuals can answer German natural prompts without requiring the user to name the product. Document metadata now enriches heating/WiFi manuals with aliases such as `heizung`, `heizungen`, `heizgeraet`, `wlan`, and `wireless`, so a prompt like "wie kriege ich meine heizungen ans wireless?" can retrieve the Mill heater manual candidate even without the word "Mill".

## [0.1.0-alpha402] - 2026-06-26

### Fixed

- Fixed a Doc Meta-Catalog user-scope mismatch that could hide active document metadata from the Meta-Catalog router. `document_meta_collection_for_user()`, Doc-Meta rebuilds, and Doc-Meta queries now normalize user ids to the same lowercase slug as Memory collections, so mixed-case runtime user ids still query the canonical document meta collection and match normalized payload user ids.

## [0.1.0-alpha401] - 2026-06-26

### Fixed

- Hardened Meta-Catalog routing for natural how-to prompts that match an active user document but do not explicitly say "documents". Active document-meta candidates with lexical overlap are now reserved in the routing candidate set, and a read-only connection answer is normalized back to `docs:search` when a matching document-meta candidate exists. This keeps prompts such as "wie kriege ich meine heizungen ans wireless?" on the Mill manual instead of empty Homebridge/connection context.

## [0.1.0-alpha400] - 2026-06-26

### Fixed

- Hardened Docs Meta-Catalog rebuilds for legacy uploaded document chunks whose stored `user_id` casing differs from the canonical user slug. User-scoped document collections now bootstrap catalog entries from mixed-case legacy chunk payloads, so existing uploaded manuals can be discovered by the Meta-Catalog without re-uploading.

## [0.1.0-alpha398] - 2026-06-26

### Fixed

- Hardened the public update checker after the `alpha397` corrective release. When the GitHub Tags API is rate-limited and the raw `main` changelog is still cached, ARIA now falls back to GitHub's releases Atom feed before using the changelog-only fallback, so future update checks can still discover the newest public prerelease.

## [0.1.0-alpha397] - 2026-06-26

### Added

- Added a versioned Docs Meta-Catalog backed by `aria_doc_meta_<user>` collections. Document uploads now rebuild a per-user catalog from existing document guides, keep the active and previous build in the same collection, leave the old active build intact on rebuild failure, and feed active document-meta hits into the Meta-Catalog router so prompts such as wireless heating can select `docs:search` without the user explicitly saying "documents".
- Hardened the Docs Meta-Catalog migration path for existing document stores. Rebuilds now synthesize catalog entries from legacy document chunks when no document guide exists, discover users from document collections/payloads, and run during startup maintenance so upgraded installs can route old manuals into `docs:search` without a re-upload.

## [0.1.0-alpha394] - 2026-06-26

### Changed

- Added a presentation-stability contract slice after `alpha391`. Broad SSH fleet prompts with a confirmed multi-target objective can expand Meta-Catalog sample targets to the full configured SSH fleet, connection inventory questions such as "what security feeds do I have?" are normalized away from feed-read actions into `connections:inventory`, and simple Notes overview questions can return a source-bound note list without the extra answer-composer LLM hop.
- Adjusted the Chat viewport UI after `alpha393`. The scroll-to-latest arrow is now anchored inside the message pane instead of the full chat shell, and small iPhone layouts keep a usable minimum message history area instead of collapsing the prompt/answer list when Safari reports a tight visual viewport.
- Tightened the Notes inventory fast path after the `alpha392` live smoke. Notes evidence now uses the shared topic-term extraction, and the fast source-bound note list filters loaded hits by the real topic so similar ARIA/A.R.I.A. notes are not listed for an AREA41 query.
- Fixed Meta-Catalog action preflight for seeded action contracts whose merged intents include `context_inventory`. A valid Meta/Turn action seed now bypasses the free pre-RAG chat-intent filter, so mixed connection contracts such as disk-capacity checks can produce an executable SSH preflight instead of failing closed with `capability=-`.
- Hardened Meta-Catalog target propagation for SSH server-update action contracts. Meta-selected SSH targets are now carried as structured `CapabilityDraft.connection_refs` and bound before free alias/context single-target resolution, preventing a selected multi-target server update check from being narrowed to an unrelated SSH profile.
- Hardened mixed Meta-Catalog action contracts for server update checks. If a Meta-Catalog action contract includes RSS advisory sources and SSH server targets, but the action IDs are missing or mixed, ARIA now seeds the SSH multi-target action from the selected SSH targets instead of executing the first RSS feed as the terminal action.
- Added a runtime task/outcome contract for server update checks. Meta-Catalog answer routes over connection context can now be overridden by a bounded runtime task decision when the user is asking for an operational SSH package-update check, and multi-target SSH executions store a structured runtime outcome frame so follow-ups such as "which packages from those are most important?" answer from the previous `apt list --upgradable` results instead of falling into connection inventory.
- Fixed the `alpha388` docs-only contract propagation gap in the normal SkillRuntime path. `RecipeRuntime.run_skills()` now forwards `docs_only=true` to MemorySkill recall, so `docs:search` cannot silently fall back to fact/preference/knowledge/learning recall after the Meta-Catalog selected the Docs surface; a focused regression test covers this path.
- Fixed the post-`alpha386` docs-source isolation gap: `docs:search` now runs MemorySkill in docs-only mode, excludes normal fact/preference/knowledge/learning recall targets, and accepts direct docs answers only when the evidence source is an actual document collection/source.
- Hardened the Meta-Catalog inventory/source contract for `alpha386`. Broad inventory questions now stay on surface-level `connections:inventory` with catalog IDs carried only as hints unless an exact ref is explicitly bound, source-bound evidence is forced whenever local/catalog context is loaded, inventory SkillResults are merged before the LLM-first answer composer, explicit document/note/memory source requests force the matching surface, and Inventory Reindex moved into the Memory menu as Memory Reindex.
- Switched the Strict Meta-Catalog Contract gate to soft mode by default for `alpha385`. The contract instrumentation (`contract_mode`, `evidence_policy`, richer follow-up state, and evidence packets) remains active, but invalid strict contracts no longer block the route unless `routing.meta_catalog_strict_contract_enabled=true` is explicitly enabled for internal comparison testing.
- Added the Strict Meta-Catalog Contract slice for `alpha384`. `aria_meta_catalog_routing` now asks the LLM for an explicit `contract` (`mode=answer|action|clarify|empty`, `evidence_policy=source_bound|allow_general`), validates that contract before accepting the route, carries `contract_mode` and `evidence_policy` through `AriaTurnPlan`, debug output, follow-up `TurnFrame`, and the LLM-first answer-composer evidence packet, and keeps a temporary rollback switch via `routing.meta_catalog_strict_contract_enabled=false` for internal testing only.
- Added the first Qdrant Meta-Catalog migration slice after the `alpha379` architecture review. ARIA can now build a separate `aria_meta_catalog_*` collection with surface and connection capability documents containing safe semantic fields such as what an object knows, what context it can load, candidate actions, loader/executor contracts, risk hints, and confirmation policy. The existing Inventory index remains intact during migration, and the operations reindex flow now rebuilds both indexes side by side.
- Activated the Qdrant Meta-Catalog as the first bounded chat routing step. ARIA now queries `aria_meta_catalog_*`, sends the compact candidate catalog plus the user prompt to `aria_meta_catalog_routing`, validates selected ContextRequests/actions against registered surfaces and catalog candidates, and falls back to the old turn arbiter only when the meta-catalog path is empty or uncertain.
- Moved the legacy keyword router behind the Meta-Catalog contract for normal pipeline turns. Successful `aria_meta_catalog_routing` now skips the old turn-intent, pre-RAG semantic action classification, recipe arbitration, and freshness gates; selected inventory requests can bind to exact `catalog_id/kind/ref`, and selected actions seed the existing executor/guardrail path from the Meta-Catalog instead of re-detecting capability intent from free text.
- Expanded the Meta-Catalog contract beyond coarse surfaces. It now indexes local context families such as facts, preferences, knowledge, context memory, sessions, learning artifacts, notes, and docs, binds selected local families to exact user collections for recall, and maps generic connection actions such as SSH, RSS, websites, SFTP/SMB, HTTP API, mail, webhook, Discord, calendar, and MQTT into existing capability/preflight paths.
- Hardened the Meta-Catalog/backup action contract for `alpha381`. Any validated turn plan with selected actions, `needs_confirmation`, or `plan_action` now enters action preflight or fails closed; it can no longer fall through into direct context answers or final chat. Backup arbiter actions seed the same capability draft path as Meta-Catalog actions, selected multi-SSH targets stay multi-target, and debug now exposes when legacy semantics are used only as a backup fallback.
- Hardened the Meta-Catalog context contract for `alpha382`. A successful Meta-Catalog route with `needs_context=true` and a selected surface but no explicit `context_requests` now synthesizes a validated loader request, e.g. `connections:inventory`, instead of accepting an empty load plan. This keeps source-bound inventory questions on the Inventory loader/direct-answer path and prevents unrelated memory/session context plus final chat from claiming ARIA has no access to configured data.
- Added the LLM-first Answer-Composer contract for `alpha383`. Selected local context and inventory outcomes are now normalized into evidence packets, sent to a bounded `aria_answer_composer` operation for free wording, and then checked by deterministic claim guardrails so source-bound answers cannot claim missing access, invent matches, or use unrelated local context.
- Hardened the remaining Meta-Catalog contracts for `alpha383`: selected non-chat surfaces now force a validated loader request even when the LLM incorrectly sets `needs_context=false`; local memory/search results with `matched=false` stay source-bound empty instead of falling into final chat; and seeded Meta SSH actions can be refined through the existing LLM capability-draft objective contract so package-update checks use the read-only update probe instead of defaulting to uptime.
- Shifted the ARIA turn arbiter toward the Agentic Context Routing directive. The arbitration payload now exposes `routing_meta_context`, and the plan can carry `needs_context`, `context_directions`, and `context_depth` so the LLM decides whether ARIA should deepen context and in which direction instead of only selecting a surface/action menu.
- Let high-confidence local context arbitration run before the legacy turn-intent arbiter and skip the old active-hint/turn-intent/freshness gates for direct local recall. This keeps direct Memory/Learning/Notes questions on the new context-routing path and avoids avoidable LLM/recall hops.
- Added real arbiter-driven local recall limits. Selected Memory/Learning/Docs collections are passed down to `MemorySkill` as `target_collections`, Notes-only routes skip broad memory recall, and document guide lookup can be disabled unless the selected direction needs documents.
- Added first Context Ledger debug lines for ARIA context routing. Details now show selected context directions, depth, collections/actions, query overrides, memory targets, loaded skill contexts, source counts, detail-line counts, embedding tokens, and arbiter tokens.
- Tightened the local-context fast path after the first `alpha363` live test. High-confidence local context turns now skip the pre-RAG action and recipe arbitration stages completely, and Notes-only routes no longer emit a fake `memory_recall` skill result when Memory was intentionally disabled by the arbiter.
- Added a no-context guardrail for agentic local retrieval. When the LLM correctly selects a local context direction such as Notes, Docs, Memory, or combined local sources but ARIA loads zero usable sources, the pipeline now returns a source-bound empty-result answer instead of sending the turn to the final LLM where it could claim ARIA has no access or invent unrelated context.
- Added the same fail-closed contract for selected web side actions. If the ARIA action gate selects a Notes or watched-website side action but the concrete side-flow cannot execute it, the web chat now returns a clear non-execution answer instead of falling through into generic chat.
- Added the Agentic Context Runtime v2 foundation. ARIA now has generic `ContextSurface`, `SurfaceRegistry`, `ContextRequest`, `ContextPacket`, and builtin Surface adapters for Memory, Notes, Docs, Connections, and Web so future data/function surfaces can register metadata instead of requiring central router phrase logic.
- Extended the ARIA turn arbiter with registry-backed `context_requests`. The LLM can now choose registered surfaces such as `connections` with a mode like `inventory`, and ARIA validates that choice against the SurfaceRegistry before any loader or executor is used.
- Added a safe Connection Inventory context path. Questions about configured/observed websites or connections can now load non-secret inventory context instead of being mistaken for watched-website actions; Stage-1 metadata intentionally excludes hosts, URLs, tokens, keys, passwords, and similar sensitive fields.
- Changed final answer context filtering so a later `chat_local_context_relevance` decision can no longer discard context that the explicit ARIA TurnPlan already selected. It now skips with a debug line when the TurnPlan is the semantic authority.
- Tightened the Agentic Context Runtime after live tests. Stage-1 SurfaceRegistry payloads now expose compact `routing_metadata` only, remove the duplicate full menu payload, and keep deep inventory metadata for the selected loader step instead of sending it to the arbiter.
- Generalized inventory loading behind registered ContextSurfaces. `context_inventory` no longer depends on a Connections-only helper; selected surfaces can expose safe inventory metadata through the registry and the answer context stays source-bound.
- Added a Context Isolation contract for selected turns. Answer-context skill results are filtered against the selected `ContextRequest`, and selected Notes/Inventory turns do not run pre-answer Auto-Memory/session/user recall context that could contaminate the answer.
- Added a lightweight `TurnFrame` for follow-up routing. ARIA now passes the previous selected surface/mode/topic to the next arbiter call as weak context, so short follow-ups such as "und was ist mit IT-Security?" can continue an inventory frame without hard-coded phrases.
- Changed the web pre-pipeline side-flow gate to become terminal only for genuine action intents. A stray watched-website action name inside an inventory/context turn no longer blocks the normal pipeline with a non-execution action message.
- Added a content-existence context mode. Topic-specific questions such as "do I have information about X in memory?" are steered toward `exists`/search-style local retrieval instead of being satisfied by shallow inventory metadata alone.
- Hardened generic inventory matching. Configured-item inventory now matches against individual safe item metadata, keeps many selected safe summaries for the deep loader, reports matched-vs-configured counts, avoids generic surface-word matches such as "websites" pulling unrelated items, and does not expose secret URLs/hosts/tokens.
- Removed the extra web pre-pipeline LLM arbitration for normal free-text turns. Slash/UI shortcuts still enter the legacy side flows, but ordinary prompts now go straight to the single pipeline arbiter, which reduces latency and avoids pre-pipeline action misclassification for knowledge/inventory questions.
- Changed chat badge timing to report end-to-end web request time and added `Routing Debug: web_request_timing` with total and pipeline milliseconds, making UI latency visible instead of only showing a partial pipeline/model duration.
- Added tightly scoped direct context answers for already-selected inventory and memory-existence turns. When the TurnPlan selects registered inventory context or a source-bound memory `exists` check, ARIA can answer from the loaded context without a second final-answer LLM call.
- Made memory-existence retrieval more selective by keeping session collections out of `memory_target_collections` unless the TurnPlan explicitly requests sessions.
- Documented ARIA's Qdrant collection contracts in `docs/product/qdrant-collections.md` and made `aria_inventory_*` authoritative for inventory questions. Legacy `website_list` capability drafts now route into `connections:inventory` when the Qdrant inventory index is active, empty inventory results no longer fall back to broad action lists, inventory debug lines expose `authoritative=true`, and evidence-term selection keeps the actual topic in natural-language inventory questions.
- Improved mobile chat viewport handling for iPhone Safari. The chat shell now uses a visual-viewport height variable, keeps the composer above the safe-area inset, and scrolls the message pane to the latest message after layout changes instead of relying on a single immediate `scrollTop` write.
- Hardened source-bound follow-up context. Direct capability inventory answers now store a `TurnFrame`, follow-up plans preserve the previous registered surface/mode unless the user switches surface or requests an action, and empty registered local context returns a source-bound empty result instead of falling through to generic chat.
- Reduced Direct-Context pipeline work for selected local context. High-confidence source-bound Notes/Memory/Docs turns now skip the legacy `turn_intent_arbiter` even when the ARIA turn plan's intent is still `chat`, and Notes-only hits can return a source-bound direct answer instead of paying for a final chat LLM pass.
- Added a fast positive-only ContextSurface selector before the full ARIA turn arbiter. It uses only compact registered-surface metadata, can select one local/source-bound context request, and falls back to the full arbiter for actions, web/freshness, recipes, admin, pending confirmations, learning capture, uncertainty, or invalid surface/mode choices.
- Slimmed the full ARIA turn arbiter payload in registry-backed mode by dropping duplicate legacy surface rows while keeping validated collections/actions. Selected TurnPlan context now skips late recent-context enrichment, direct Memory/Docs search requests can answer source-bound without a final chat LLM when evidence matches, and stage timing now includes `pipeline_wall_time`.
- Tightened the generic evidence contract after the `alpha376` live test. Inventory and memory-existence answers now derive evidence from topic terms instead of raw user-query words, ignore Surface/Mode/request/scope wording such as RSS, websites, feeds, sources, list, inventory, and question filler, allow soft scope words such as monitoring to become the topic only when no stronger topic remains, and preserve the previous TurnFrame surface/mode for short underspecified follow-ups unless the user explicitly switches surface or requests an action.
- Added a Chat scroll-to-latest overlay button. When the user scrolls upward in the chat history, ARIA now shows a compact floating down-arrow that jumps back to the newest message without shifting the composer.
- Hardened the post-`alpha377` semantic evidence contract. Multilingual filler terms such as `and`, `the`, `für`, and `fuer` no longer count as topic evidence, unrelated inventory neighbors are rejected for unmatched topics such as beef grilling, and the fast memory-existence path is rejected when a resource/inventory question does not explicitly target Memory.
- Re-centered the ARIA turn architecture on the full agentic TurnPlan after `alpha378` live regressions. The compact fast context selector and follow-up frame arbiter no longer run before the full turn arbiter, and local frame-preservation helpers no longer override the LLM's selected surface/mode after arbitration. Direct context loading remains an execution optimization after a validated TurnPlan, not an independent semantic router.

## [0.1.0-alpha362] - 2026-06-16

### Added

- Added the ARIA Turn / Surface / Action Arbiter path. The new bounded arbitration module accepts a deterministic menu of allowed surfaces, Qdrant collections, and runtime actions, validates LLM choices against that menu, rejects invented entries, forces confirmation for risky actions, emits a unified routing debug line, and is now integrated into the pipeline before retrieval/action execution.
- Documented the `Agentic Learning Loop v2` product direction: ARIA should turn real usage into controlled learning artifacts such as reflections, routing hints, procedure/recipe/skill candidates, eval candidates, and recipe improvements, with deterministic schemas, policy, guardrails, review, promotion gates, and tests controlling what becomes active.
- Added the first Learning Event Ledger implementation. ARIA can now persist redacted JSONL audit events, load/filter recent events, record successful Auto-Memory `LERNEN` reflections as `memory_reflection` artifacts, and mirror those events into Qdrant as visible `learning_event` memory chunks for the future reflection/review loop.
- Added the first bounded Learning Classifier. Successful Auto-Memory learning events can now be classified into review-only learning candidates such as `source_rule_candidate`, `procedure_candidate`, `recipe_candidate`, or `eval_candidate`, then stored visibly in Qdrant under `aria_learning_candidates_<user>` without activating runtime behavior.
- Added a first Learning Candidate review surface in the Memory Explorer. `learning_candidate` chunks can now be filtered, inspected, marked as reviewed, or rejected in Qdrant payload metadata while promotion remains blocked until validator/eval gates exist.
- Added the first Learning Candidate Validator/Eval dry-run. Review-only candidates now produce visible `learning_eval` chunks in Qdrant under `aria_learning_evals_<user>` with blockers, expected path, expected behavior, negative examples, and `promotion_allowed=false`.
- Added a bounded User Feedback Learning detector in the chat flow. When Auto-Memory is enabled, durable feedback about ARIA's answer quality, source handling, routing, memory, UI, or workflow can create visible Qdrant `learning_event`, `learning_candidate`, and `learning_eval` chunks without activating runtime behavior.
- Added the first runtime Outcome Learning recorder. Explicit URL/source WebSearch outcomes now carry source-quality metadata and, when Auto-Memory is enabled, can create review-only Qdrant `learning_event`, `learning_candidate`, and `learning_eval` chunks for page-excerpt/source-handling behavior.
- Added a Deterministic Meaning Audit document that identifies where free user semantics are still decided by keyword/regex/list logic and sets the next refactor priority toward bounded `turn_intent_arbitration`.
- Added bounded Turn Intent Arbitration around the normal pipeline router. The legacy `KeywordRouter` now acts as a signal source for top-level chat/memory/web intents, and a bounded LLM arbiter can override misleading keyword signals with sufficient confidence while falling back to the deterministic router when unavailable or uncertain.
- Added a Capability Draft Fallback Boundary. The pre-RAG action gate now tries bounded LLM capability drafting before local heuristic drafts, treats LLM `no_action` as authoritative, allows local fallback only for unavailable/uncertain draft states, and records local fallback usage as a review-only learning outcome when Auto-Memory is enabled.
- Added bounded Notes Action Arbitration for chat Notes flows. Natural-language Notes requests can now be classified into canonical Notes commands or `no_action` before the legacy regex handlers run, while slash/UI-style commands and low-confidence cases still fall back to the existing deterministic handlers.
- Added bounded Follow-up Resolution for vague chat rewrites. ARIA now asks a constrained LLM resolver whether follow-up turns should be rewritten for web search or local context, treats high-confidence `no_rewrite` as authoritative, and keeps the old deterministic rewrite helpers only as low-confidence/no-LLM fallback.
- Broadened runtime Outcome Learning beyond WebSearch and local capability fallback. Stored-recipe catalog misses and confirmed routed connection actions can now create review-only Qdrant learning events/candidates/evals when Auto-Memory is enabled.
- Added the first low-risk Learning Candidate Promotion Gate. Reviewing a Qdrant learning candidate now writes a deterministic gate result back into the candidate payload: low-risk `source_rule_candidate` and `routing_hint` candidates become `eligible`, while higher-risk procedures/recipes remain `reviewed_blocked` and runtime activation stays disabled.
- Added a guarded Apply preparation step for eligible low-risk Learning Candidates. The Memory Explorer can now mark eligible `source_rule_candidate`/`routing_hint` candidates as `apply_state=prepared` with `apply_requires_regression=true`, while still keeping `runtime_activation_allowed=false`.
- Added a read-only Apply Preview for prepared low-risk Learning Candidates. Admins can inspect the proposed source-rule/routing-hint structure, provenance, regression requirement, and disabled runtime status before any future activation path exists.
- Added Regression Gate status to Learning Candidate apply preparation and preview. Prepared candidates now default to `regression_status=missing`, the preview shows missing/linked regression state and references, and runtime activation remains disabled.
- Added a Regression Link route in the Learning Candidate Apply Preview. Admins can link concrete pytest refs such as `tests/test_pipeline.py::test_name`, which updates the Qdrant candidate payload to `regression_status=linked`; invalid refs keep the candidate at `missing`.
- Added Regression Ref verification for Learning Candidate Apply Preview. Linked pytest refs can now be checked against the workspace for file and test-function existence, writing `regression_verified`, `regression_test_exists`, and `regression_verify_result` back to Qdrant without running or activating runtime behavior.
- Added focused Regression Test execution for verified Learning Candidate refs. The Apply Preview can now run the linked pytest ref and store `regression_verify_result=passed|failed`, return code, timestamp, and sanitized output in Qdrant while keeping runtime activation disabled.
- Added the first Active Learning Hint activation path. Reviewed/prepared low-risk candidates now require an activation preflight with a passed regression run before they can be stored as visible Qdrant `learning_active_hint` chunks under `aria_learning_active_hints_<user>`.
- Added weak runtime use of active learning hints. Turn intent arbitration can now receive reviewed Qdrant active hints as bounded weak signals, while policy, guardrails, and runtime activation remain deterministic gates.
- Added Active Learning Hint outcome tracking. When Auto-Memory is enabled and a Qdrant active hint is available during turn intent arbitration, ARIA now records a review-only learning outcome so active hints can later be evaluated, refined, or withdrawn.
- Added Universal Host/App Artifact Learning. Confirmed connection-action results can now surface observed paths, Compose files, Dockerfiles, systemd units, ports, packages, and health terms as review-only `app_artifact_candidate`, `install_plan_candidate`, and `health_check_candidate` learning artifacts in Qdrant.
- Added App Identity Hypotheses for host artifact learning. Observed artifacts can now be condensed into review-only `app_identity_candidate` data with runtime kind, app root, entry artifacts, health surfaces, install/update surfaces, and rollback surfaces.
- Added review-only Install/Update Plan Drafts from app identity hypotheses. Drafts include preflight checks, backup targets, proposed steps, health checks, rollback steps, blockers, required confirmation, and disabled runtime activation.
- Added Install/Update Plan Validation gates. Drafts are now assessed for missing gates, mutating steps, required confirmations, regression suggestions, and risk while keeping promotion and runtime activation disabled.
- Added structured Health Check and Regression Drafts from validated install/update plans. Drafts remain non-mutating and review-only, making future checks and tests derive from observed app artifacts instead of ad hoc rules.
- Added Memory Explorer visibility for app-learning candidates. App identity, plan drafts, validation gates, health drafts, and regression drafts now render as structured chips and preview sections for Qdrant learning candidates.
- Added review-only Pytest Skeleton Proposals from regression drafts. Proposals include target file, test function sketches, fixtures, safety notes, and disabled write/runtime activation flags.
- Added read-only Pytest Apply Preview gates for app-learning proposals. The preview renders proposed test code, checks that targets stay under `tests/`, flags existing files and duplicate test functions, and still never writes files automatically.
- Added a manual Pytest Write preparation gate for app-learning proposals. A ready preview can now store a `prepared` Qdrant payload with target file, test names, code preview, and SHA-256 hash while keeping `pytest_write_allowed=false` and writing no files.
- Added prepared artifact review feedback for app-learning proposals. Operators can mark prepared Pytest write artifacts as accepted, needing changes, or rejected; ARIA stores that outcome back into the Qdrant candidate payload as learning feedback while keeping file writes and runtime activation disabled.
- Added Review Outcome Learning for prepared artifacts. Accepted reviews create review-only `artifact_pattern_candidate` chunks, needs-change reviews create `artifact_improvement_candidate` chunks, and rejected reviews create `negative_pattern_candidate` chunks, each with a matching learning event and eval dry-run in Qdrant.
- Added Learning Pattern Recall for app-learning proposals. New Pytest skeleton proposals can now recall prior accepted, needs-change, and rejected artifact review candidates from Qdrant as weak guidance and carry them visibly in the proposal payload without granting write or runtime permission.
- Added the first Recipe Candidate Generator. Successful connection workflow outcomes can now create an additional review-only `recipe_candidate` plus eval dry-run in Qdrant, with similar existing recipe candidates recalled as weak duplicate/improvement guidance and no runtime promotion.
- Added the first Recipe Improvement Loop behavior. When similar `recipe_candidate` or `recipe_improvement` chunks already exist in Qdrant, new successful workflow outcomes now create review-only `recipe_improvement` candidates instead of another duplicate recipe candidate.
- Added Procedure/Skill Memory with gating. Successful connection workflow outcomes now create review-only `procedure_candidate` chunks and eval dry-runs in Qdrant; when similar procedure/skill memories already exist, ARIA can also propose a high-risk review-only `skill_candidate` without implementation, promotion, or runtime activation.
- Added an Async Learning Worker status path. Runtime learning captures now go through a shared background job registry, and the Memory Explorer shows running, completed, failed, and latest learning jobs while Qdrant remains the durable learning store.
- Added Learning Worker job detail, retry, and flush controls. Admins can inspect a job snapshot, force-retry failed/rejected runtime learning jobs with backoff metadata, and clear finished worker history without touching Qdrant learning artifacts.
- Added first Learning Worker budget gates. Runtime learning jobs now carry estimated tokens, consumed token/cost metadata when available, max-attempt limits, in-process budget totals, and budget rejection status in the Memory Explorer.
- Added Learning Worker observability to Stats and Operator Guardrail. `/stats` now surfaces worker running/completed/failed/rejected counts, budget state, latest job links, and a guardrail row that warns on failures, rejections, or exhausted learning budgets.
- Added Learning Worker runtime audit and failure categories. Finished/rejected/maintenance worker events are recorded as a compact JSONL operations audit, summarized in the worker snapshot, and grouped into operational categories such as budget, Qdrant, provider, validator, worker, route, and unknown.
- Added a Learning Review Queue summary to the Memory Explorer. Qdrant learning artifacts now show candidate, eval, active-hint, regression, and activation counts before the normal Memory type filters.

### Fixed

- Removed the rejected direct recall phrase fix and its tests. Questions like "what did I tell you..." are no longer solved through special phrase rules; they must flow through the common ARIA turn/surface/action arbitration path.
- Moved web chat Notes/Websites side flows behind the common ARIA action gate. Free user turns can no longer be terminally answered by those side flows before the shared arbiter has a chance to choose the surface/action plan.
- Let the pipeline use ARIA arbiter-selected collection queries for local recall, web research, and Notes retrieval, including Notes snippets as normal context instead of a pre-pipeline terminal route.
- Avoid spending Active Learning Hint recall on explicit web-search or clear connection-action contexts while keeping active hints available as weak signals for normal free turns.
- Added missing Learning Worker Stats i18n keys so the full release hygiene suite covers the new stats surface cleanly.
- Keep explicit external `http(s)` URLs out of the agentic pre-RAG connection action gate, even when the bounded capability draft would classify them as watched-website reads. Direct URL/anchor questions now stay on the chat freshness/WebSearch path and preserve the literal URL as the search/fetch query.
- Treat recalled `[LERNEN]` memory reflections as durable behavior guidance in the final chat prompt, so questions such as "was hast du aus meinem AREA41 feedback gelernt?" answer from the learning memory instead of claiming nothing was learned while a `LERNEN` source is present.
- Give fetched web page excerpts higher final-answer priority than search snippets and raise the final context budget so official page excerpts are not truncated behind aggregator snippets before the final LLM answer.

## [0.1.0-alpha360] - 2026-06-15

### Fixed

- Keep arbitrary `http(s)` URLs out of watched-website routing so direct page/anchor questions can use web research instead of asking for a configured Website profile.
- Fetch one additional strong domain/path match beyond the first two web-search results, so official pages such as `area41.io/#speakers` can provide page excerpts even when a search engine ranks aggregator pages higher.
- Let agentic Auto-Memory extract durable feedback reflections into per-user `aria_learning_*` collections. These `LERNEN` memories are visible in Memory/Qdrant and are searched during recall as context-only self-improvement guidance.

## [0.1.0-alpha359] - 2026-06-14

### Fixed

- Move document import into its own chat Toolbox group so it is visible as a first-level document entry instead of being hidden inside Commands.
- Fetch and inject page excerpts for concrete web-search result URLs, including explicit `#anchor` URLs, so official pages can provide answer context beyond search snippets.

## [0.1.0-alpha358] - 2026-06-14

### Fixed

- Keep the ARIA working-logo emblem stable while ARIA is busy. The busy indicator now uses a slow rotating light aura and soft glow instead of rotating or flipping the logo itself, avoiding upside-down frames.

## [0.1.0-alpha357] - 2026-06-14

### Fixed

- Restore the ARIA working-logo animation to a vertical emblem turn so the logo no longer rotates upside down while keeping the smoother light pulse from the previous pass.

## [0.1.0-alpha356] - 2026-06-14

### Changed

- Surface document import from the main chat toolbox. The toolbox item opens the Memory document import panel directly and focuses the file picker so RAG document ingestion is no longer hidden in configuration.

## [0.1.0-alpha355] - 2026-06-14

### Fixed

- Smooth the ARIA working-logo animation by replacing the hard 3D flip/scanline loop with a continuous rotation, synchronized energy sweep, and softer light pulse.

## [0.1.0-alpha354] - 2026-06-14

### Fixed

- Link the main-screen Auto-Memory status indicator directly to the Auto-Memory settings section, following the app rule that option indicators should lead to their option settings.

## [0.1.0-alpha353] - 2026-06-14

### Fixed

- Move the Stats cost-card disclaimer below the cost metrics so the card leads with the actual numbers and keeps the explanatory text near the pricing actions.
- Keep the main Auto-Memory indicator aligned with agentic Auto-Memory extraction. Existing configs with Auto-Memory enabled now get `agentic_extraction_enabled=true` filled in at load time when missing, and the UI/Core toggles update both flags together.

## [0.1.0-alpha352] - 2026-06-14

### Fixed

- Keep explicit recipe-catalog questions catalog-bound even when no recipe candidate matches. Questions such as "gibt es ein rezept fuer dns health" now answer from the stored catalog instead of drifting into a generic checklist.
- Carry recent web-search topic context into vague local Notes/Documents follow-ups in the web chat flow. A follow-up like "und was steht dazu in meinen notizen?" now searches local notes for the prior topic instead of using only the pronoun-like phrase.
- Give bounded capability drafting an earlier chance for local system check prompts before freshness/web-search arbitration. Local checks such as Pi-hole inspection no longer fall through to unrelated web results when configured connections can handle the request.
- Let Auto-Memory use a bounded agentic extraction pass when enabled. ARIA can now persist durable user-specific behavior conventions, aliases, preferences, and infrastructure facts from chat messages, while deterministic extraction remains the fallback and persistence stays limited to facts, preferences, and session context.
- Capture action-sensitive memory boundaries through the same agentic Auto-Memory pass. Durable approval requirements, expiry/trust constraints, and "do not act until..." notes are stored as visible memory facts prefixed with `Action boundary:` so future turns can recall them as context without bypassing runtime policy.

## [0.1.0-alpha351] - 2026-06-14

### Fixed

- Keep general advice and chat questions out of the stored-recipe no-match path. Recipe catalog misses now produce a direct no-recipe answer only when the user explicitly asks about a recipe; normal diagnostic and explanation questions continue through chat.
- Block mutating SSH requests before multi-target read-only fallbacks. Install, upgrade, restart, delete, and similar side-effect requests no longer get silently replaced by status probes such as `uptime`.
- Give recent SSH runtime context the first chance for immediate follow-up questions before drafting a fresh SSH action. Follow-ups such as asking for per-server package details can reuse the previous multi-target result instead of losing the target group.
- Stop passing local Notes/RAG context into normal web-search turns unless the user explicitly asks for local context, reducing unrelated note bleed in follow-up searches.

## [0.1.0-alpha350] - 2026-06-14

### Fixed

- Keep the chat window height stable while long conversations grow. On the main chat page, the outer app frame stays fixed to the viewport and only the message history scrolls upward.
- Keep stored-recipe explanation questions catalog-bound. When `recipe_execution_intent` rejects execution, ARIA now uses a bounded LLM explanation step over the matching recipe manifest, or says that no matching recipe exists instead of inventing a generic server-update runbook.
- Keep automatic freshness/web-search routing LLM-first. When an LLM is available, ARIA now asks `chat_freshness_arbitration` for normal chat questions instead of letting currentness/product keyword filters decide whether the LLM may arbitrate; deterministic freshness terms remain only for no-LLM fallback and explicit/local-context gates.
- Consolidate repeated bounded LLM call handling. Recent-runtime context relevance, local chat-context relevance, and stored-recipe catalog explanations now share `BoundedDecisionClient` for LLM calls, JSON parsing, usage extraction, confidence coercion, and error handling.
- Split the chat turn pipeline into clearer internal stages. Recipe arbitration, freshness/web-search arbitration, and recent-runtime-context enrichment now live in dedicated stage helpers instead of being embedded directly in `Pipeline.process()`.
- Continue untangling the chat turn pipeline. Web-search failure prechecks, direct stored-recipe chat responses, and final chat response/usage accounting now run through dedicated stage helpers.
- Move the chat turn stage helpers into `pipeline_turn_stages.py`, including recipe-status and pre-RAG action exits. `Pipeline.process()` now mostly orchestrates stage calls, capability-draft and pre-RAG chat/action arbitration use `BoundedDecisionClient`, and routing-debug line formatting is shared for the touched debug paths.
- Keep free capability drafts agentic-first before local SSH fallbacks. Bounded `capability_draft_decision` now gets the first semantic pass for non-explicit SSH-like prompts, and an explicit LLM `chat/no_action` decision blocks local SSH fallback.

## [0.1.0-alpha349] - 2026-06-13

### Fixed

- Keep follow-up suggestions after read-only runtime context inspect-oriented. When ARIA answers from a recent read-only runtime result, it should offer read-only next steps such as listing affected items per target instead of suggesting state-changing operations.
- Keep free-language SSH intent LLM-first. The deterministic capability router no longer turns natural health, uptime, status, disk, or free-space phrasing into SSH commands such as `uptime` or `df -h`; those prompts are left to the bounded LLM capability draft while deterministic code keeps only explicit commands, executor availability checks, and policy validation.
- Adapt broad multi-target SSH bundles only from bounded LLM `target_intent` values such as `health_check`, `capacity_check`, or `package_update_check`, instead of falling back to health/capacity wordlists in the pipeline.
- Classify SSH requested runtime effect with a bounded LLM step instead of mutating-request wordlists. ARIA now uses `ssh_requested_runtime_effect` to distinguish read-only, mutating, and unknown user intent, while SSH policy still blocks mutating commands and prevents guardrail healthcheck fallbacks from masking state-changing requests.
- Select SSH guardrail healthcheck fallback commands with a bounded LLM step from the explicit allowlist instead of deterministically concatenating every allowed command. ARIA rejects invented or edited selections and still validates the final command through SSH policy before use.
- Decide stored recipe execution intent with a bounded LLM step. Deterministic recipe scoring now only builds a candidate shortlist; `recipe_execution_intent` must explicitly return `execute=true` for ARIA to run a stored recipe, so explanatory or comparison questions about a recipe topic do not execute it.
- Keep action planner scores as ranking hints instead of final semantics. When multiple bounded action candidates match and no LLM decision is available, ARIA now asks for confirmation instead of selecting an action from keyword or score gaps alone.
- Decide local chat context relevance with a bounded LLM step. Local notes, documents, and memory snippets are now filtered through `chat_local_context_relevance` before the final chat prompt; the old regex-based how-to/diagnostic filter remains only as a fallback.
- Link the Memory Map "Compression due" health card directly to the rollup/compression section in Memory setup so the warning has an immediate repair path.
- Keep loose connection target matches LLM-first. Exact alias/ref matches may still resolve deterministically, but a single soft score candidate no longer bypasses semantic LLM resolution when multiple profiles are available.
- Re-check Learned Recipe promotion blockers when loading runtime candidates. Promoted records with multi-target or side-effect blockers are now ignored even if stale or manually edited store data contains a stored recipe id.
- Expose bounded local chat-context relevance decisions in routing debug details. When `chat_local_context_relevance` keeps or filters local notes, documents, or memory context, debug mode now shows the LLM decision, confidence, candidate count, and reason.
- Expose bounded stored-recipe execution intent decisions in routing debug details. When `recipe_execution_intent` accepts or rejects a stored recipe candidate, debug mode now shows execute true/false, confidence, candidate count, selected id when applicable, and reason.
- Expose action-planner and connection-target decisions in routing debug details. Debug mode now shows `action_plan_debug` for bounded planner choices and `connection_target_selection` for semantic/forced/explicit target resolution while keeping the existing human-readable routing lines.

## [0.1.0-alpha348] - 2026-06-13

### Fixed

- Keep recent multi-target SSH runtime context available for immediate follow-up questions. After a multi-target check, ARIA can now answer which SSH targets the previous result referred to instead of falling back to unrelated local RAG context.

## [0.1.0-alpha347] - 2026-06-13

### Fixed

- Route multi-target SSH package/update-status questions such as "sind meine server up to date" to a read-only package update listing instead of reusing the broad health check command. `apt list --upgradable` is now allowed as a safe SSH read-only probe while mutating apt operations remain blocked.

## [0.1.0-alpha346] - 2026-06-11

### Fixed

- Separate Qdrant Brain graph scrolling from the Payload Preview and the classic Memory Graph. The Brain viewport and the regular Memory Graph now own their horizontal scroll areas independently instead of sharing the outer Memory Map frame scroll.

## [0.1.0-alpha345] - 2026-06-10

### Fixed

- Make Qdrant Brain usable on mobile/touch devices by adding a deliberate touch movement mode. Touch users can now scroll and tap the page by default, then enable graph movement when they want to pan or drag nodes, avoiding the previous conflict between browser scroll, graph pan, and node drag.

## [0.1.0-alpha344] - 2026-06-10

### Changed

- Make Qdrant Brain point dragging behave like a real layout edit: connected neighbors are directly nudged while dragging, and the whole moved graph segment stores its current position as the new layout base on release instead of returning to the original coordinates.

## [0.1.0-alpha343] - 2026-06-10

### Changed

- Make Qdrant Brain point dragging feel stickier and closer to Qdrant: moved points keep their dropped position as their new local home, spring pullback is softer, and motion damping is heavier so the graph does not snap back toward its original layout as strongly.

## [0.1.0-alpha342] - 2026-06-09

### Fixed

- Make the Qdrant Brain collection start map readable by replacing the radial collection layout with a lane-based overview and wrapped collection labels. Long collection names now keep reserved text space instead of overlapping neighboring labels.

## [0.1.0-alpha341] - 2026-06-09

### Fixed

- Center Qdrant Brain collection and point views against the actual visible browser viewport instead of only the internal SVG viewBox. Collection labels are included in centering bounds and right-side collection labels flip left, preventing the start view and Center action from landing visibly right-heavy or clipping labels.

## [0.1.0-alpha340] - 2026-06-09

### Changed

- Make Qdrant Brain point drilldowns feel more like a live graph explorer: point nodes can be dragged directly, connected edges act like damped springs, and the graph settles with a short elastic bounce after interaction. Point edges now also render subtle arrowheads for a closer Qdrant-style visual language.

## [0.1.0-alpha339] - 2026-06-09

### Changed

- Make Qdrant Brain point drilldowns more graph-like by building a connected nearest-neighbor backbone per collection and then adding additional semantic neighbor edges. This makes point collections look closer to Qdrant's own visualization instead of appearing as loose dots that merely share a collection.
- Thin Qdrant Brain point edges to keep denser semantic neighborhoods readable.

## [0.1.0-alpha338] - 2026-06-09

### Changed

- Improve Qdrant Brain viewport interaction so graph drag/zoom behaves more like a dedicated graph canvas: pointer dragging no longer selects labels, wheel zoom keeps the cursor anchor stable, toolbar zoom keeps the graph centered, and pan deltas are calculated in SVG coordinates instead of raw CSS pixels.

## [0.1.0-alpha337] - 2026-06-09

### Changed
- Add sparse landmark labels to Qdrant Brain point drilldowns: highly connected points and the active/focused point show short labels directly in the map without returning to a fully labelled dense graph.
- Add a Qdrant Brain center control that recenters the currently visible collection or point graph while preserving the current zoom level.

## [0.1.0-alpha336] - 2026-06-09

### Fixed
- Fix Qdrant Brain drilldown node activation by preventing viewport pan handling from swallowing node pointer events. The payload detail panel now sits below the graph, giving the graph more horizontal room.

## [0.1.0-alpha335] - 2026-06-09

### Changed
- Change the Qdrant Brain on `/memories/map` from a fully labelled all-node graph to a drilldown view. The graph now starts at Collection level, opens a Collection into unlabeled Qdrant-style point nodes, and keeps payload details in the side panel so dense memories stay readable.

## [0.1.0-alpha334] - 2026-06-09

### Fixed
- Fix the Qdrant Brain sampler runtime error caused by a stale `_normalize_user_id` helper reference. `/memories/map` can now sample Qdrant points through the existing user-filter path instead of falling back to the empty-state error.

## [0.1.0-alpha333] - 2026-06-09

### Fixed
- Make the Qdrant Brain visible on `/memories/map` even when the first sampled collections do not produce graphable points. ARIA now samples additional ARIA Qdrant collections beyond the narrow recall/document target set and renders a clear empty-state diagnostic instead of silently showing no Brain section.

## [0.1.0-alpha332] - 2026-06-09

### Added
- Add a Qdrant Brain visualization into `/memories/map`. The existing Memory Map now includes a zoomable, pannable similarity graph built from a bounded Qdrant point sample. ARIA computes semantic edges server-side and exposes only safe labels, previews, collection names, and point IDs to the browser; raw vectors are never rendered.

## [0.1.0-alpha331] - 2026-06-08

### Fixed
- Treat explicit user requests to research/search/browse the internet as Web Search freshness candidates, even when the topic is not a current-version question. The LLM freshness arbiter still crafts the actual query, preventing prompts such as DIY cyberdeck research from falling back to stale model-only chat answers.

## [0.1.0-alpha330] - 2026-06-08

### Fixed
- Hide the static ARIA header logo while the busy animation is active and render the holographic light effect on a transparent logo-emblem mask only. This prevents the old logo from showing underneath and avoids the visual impression of a full square plaque rotating.

## [0.1.0-alpha329] - 2026-06-08

### Fixed
- Keep the ARIA header logo frame static during the global busy animation and animate only the inner logo layer, so the holographic effect feels cleaner and less jumpy.

## [0.1.0-alpha328] - 2026-06-08

### Changed
- Replace the main ARIA header logo with the new ARIA artwork while keeping the existing `logo-aria-v01.png` runtime path for compatibility.
- Regenerate all browser icon assets (`favicon.ico`, `favicon-16x16.png`, `favicon-32x32.png`, `favicon-48x48.png`, `apple-touch-icon.png`) from the new ARIA logo.
- Replace the temporary busy-logo sprite animation with a CSS-driven holographic logo flip, glow halo and scanline effect to avoid visible sprite-frame labels and improve smoothness.

## [0.1.0-alpha327] - 2026-06-08

### Changed
- Replace the subtle busy-logo ring overlay with the new `aria_rotate.png` sprite animation. Whenever ARIA enters the global busy state, the brand logo now switches to the horizontal ARIA rotation sprite.

## [0.1.0-alpha326] - 2026-06-08

### Fixed
- Improve automatic freshness web-search quality for current version and latest release questions. ARIA now steers freshness queries toward official changelogs, GitHub releases, package registries and vendor docs, and ranks those sources ahead of generic news hits for version lookups.

## [0.1.0-alpha325] - 2026-06-08

### Changed
- Speed up the Notes workspace folder and board navigation by loading lightweight note previews for board/sidebar rendering and reading the full Markdown body only when a note is opened, exported, saved, or deleted.

## [0.1.0-alpha324] - 2026-06-08

### Fixed
- Stop passing Notes context into the Web Search skill when web search was added automatically by chat freshness arbitration. This removes visible `Notiz-Kontext` source lines from automatic current-product/version answers while keeping explicit web-search prompts able to use Notes context as search assistance.

## [0.1.0-alpha323] - 2026-06-08

### Changed
- Add a trusted freshness instruction with the current date to final chat prompts when ARIA automatically adds web context for current product/version/setup questions. This keeps answers from mixing fresh web results with outdated fallback dates or training-cutoff language.

### Fixed
- Suppress local Notes/Memory context in automatic freshness web-search answers unless the user explicitly asks for local notes, documents, or memory. Explicit web searches can still use note context as search assistance.

## [0.1.0-alpha322] - 2026-06-08

### Added
- Add chat freshness arbitration for current product, version, release, API, SDK, CLI and setup questions. When Web Search is configured, ARIA can now add web context before the final chat answer instead of relying on stale model knowledge for current tooling questions such as OpenAI Codex setup.

### Fixed
- Keep explicit local notes/document questions out of the automatic freshness web-search path.

## [0.1.0-alpha321] - 2026-06-08

### Fixed
- Treat an explicitly named SFTP target in prompts such as `liste die dateien auf meiner sftp verbindung dev-node-01` as a hard requested profile. If that SFTP profile does not exist, ARIA now reports the missing SFTP profile instead of falling back to stale memory from another SFTP target.

## [0.1.0-alpha320] - 2026-06-08

### Changed
- Keep multi-target SSH operator summaries LLM-authored while sending compact per-target result facts to the summary prompt. This reduces prompt bulk for large health checks without replacing the LLM interpretation.
- Raise bounded multi-target SSH execution parallelism slightly so large read-only checks spend less time waiting for slow targets in serial batches.

### Fixed
- Let requested role phrases such as `developer server` expand through SSH connection metadata before single-target resolution. Prompts like `haben meine developer server noch genug festplattenspeicher` should now stay on the developer-server group instead of collapsing to the first matching host.
- Treat multi-target payloads with `connection_refs` as already resolved in the requested-ref guard, avoiding false “missing connection ref” handling for grouped SSH actions.

## [0.1.0-alpha319] - 2026-06-07

### Changed
- Parallelized allowed multi-target SSH execution with bounded concurrency. Large checks such as `wie fit sind meine server?` no longer wait for each SSH target strictly one after another; result ordering and preflight details stay stable.
- Clear pasted-log/advice prompts can now run a bounded chat-vs-action arbitration before the expensive LLM capability-draft step. This keeps prompts such as `was mach ich damit: Message from syslogd ... soft lockup ...` in chat faster when the LLM chooses advice instead of runtime.

### Fixed
- Ignore stale Memory hints that point outside an already detected plural SSH target group. Prompts such as `haben meine developer server noch genug festplattenspeicher` should stay on the matching developer-server group instead of jumping to an unrelated recent host such as a management server.

## [0.1.0-alpha318] - 2026-06-07

### Fixed
- Let LLM-generated SSH capability drafts still pass through chat-vs-action arbitration before runtime. This keeps pasted log/advice prompts such as `was mach ich damit: Message from syslogd ... soft lockup ...` in chat even if the LLM proposes a diagnostic SSH command first.

## [0.1.0-alpha317] - 2026-06-07

### Fixed
- Prefer a concrete bounded SSH capability draft over Stored Recipe candidates when the draft already contains an explicit command. This prevents simple checks such as `prüf dev-node-01 kurz` from being replaced by broader, complex healthcheck recipes that may trip stricter SSH guardrails.
- Filter weak local RAG/document context from general diagnostic-advice chat answers such as pasted `syslogd`/kernel lockup messages plus `was mach ich damit`, so unrelated manuals are not shown as sources unless local notes/documents are explicitly requested.

## [0.1.0-alpha316] - 2026-06-07

### Added
- Added Runtime Health visibility for third-party sidecars when the ARIA runtime can inspect Docker containers. The card reports Qdrant, SearXNG, and Valkey image/status data without turning missing Docker-socket access into a warning.

### Changed
- Documented the deliberate full-stack sidecar update path and the required smoke checks after Qdrant/SearXNG/Valkey are updated.

### Fixed
- Added LLM arbitration before ambiguous connection routing, so known hosts/services can remain context for general advice or log/error interpretation instead of forcing an action merely because a configured connection name appears.
- Removed the deterministic DNS/Pi-hole command override from SSH agentic resolution. DNS health semantics now stay with the bounded LLM command decision or an explicit LLM-classified Guardrail health bundle; deterministic code only validates policy and runtime safety.

## [0.1.0-alpha315] - 2026-06-07

### Added
- Added an explicit chat Recipe Learn Mode in the chat toolbox. Users can start a bounded learning run, let ARIA observe following chat turns, and finish it into a review-only Learned Recipe candidate; no learned candidate becomes active automatically.
- Added a chat toolbox action and `/chat note` command to save the current chat history as a Markdown Note. The saved note is reindexed into the Notes Qdrant collection when indexing is enabled, while normal Notes deletion removes the derived index entries again.

### Changed
- Polished the Notes workspace with consistent ARIA form styling, calmer editor typography, a wider desktop work area, mobile-friendly stacking, and collapsible folder management.
- Extracted chat-context relevance filtering from the main pipeline into a dedicated core module, keeping the pipeline focused on orchestration while preserving the existing RAG safety behavior.
- Moved the generic routed capability runtime fallback into an `AgenticExecutionHandler`, so normal single-target capability execution now uses the same handler registry shape as RSS and multi-target SSH.

### Fixed
- Filter weak local RAG/document context from general how-to or product-information chat answers, so unrelated manuals are not shown as sources unless the user explicitly asks for local notes/documents.
- Apply that weak local RAG filter even when the normal chat route also carries an automatic `memory_recall` intent, preventing unrelated Arlo/Mill sources on prompts such as Claude Code version checks.
- Filter mixed local Memory/RAG source packets for general chat as well, so a single recall result containing document, fact, and session hits cannot leak unrelated Arlo/Mill sources into normal how-to answers.
- Make the `/help` home page start section clickable by linking Quick Start, Memory, Connections, Recipes, Releases and Upgrades, Pricing, Security, and the local help-system docs to their real `/help?doc=...` pages.
- Keep explicit local Notes/Documents/Memory questions out of connection runtime routing even when the query term matches a connection alias, and recognize natural Notes questions such as `was steht in meinen notizen zu ARIA`.
- Keep general setup/how-to questions that mention SSH/server terms in normal chat instead of turning them into SSH runtime actions.
- Let explicit but vague web-search follow-ups reuse the recent chat topic, so `suche im internet nach der neusten version` after a Claude Code question searches for the relevant product instead of a generic “newest version”.
- Aligned the Notes editor height more closely with the Notes sidebar on desktop so new/edit note screens feel visually calmer.
- Contained long Notes card titles, URLs, tags, and folder labels so the Notes board no longer overflows horizontally on desktop or mobile.
- Format `uptime -s` SSH results as a normal chat answer (`running since ...`) instead of exposing the raw Stored Recipe SSH executor output.
- Suppressed the normal automatic Learned Recipe update path while chat Recipe Learn Mode is active. `/lernen abbrechen` now discards the observed turn without also updating an existing learned recipe through the background auto-learning path.
- Let singular DNS/Pi-hole health role prompts such as `ist mein dns server ok` expand from a primary alias hit to matching primary/secondary DNS SSH profiles, while keeping mutating DNS requests single-target and guardrail-bound.
- Keep DNS resolver-probe hardening scoped to real DNS health/status prompts, so DNS-target disk or uptime questions keep their intended `df`/`uptime` commands instead of being rewritten to `dig`.

## [0.1.0-alpha306] - 2026-06-05

### Fixed
- Let singular role phrases such as `developer server` match Dev/Development connection metadata like `dev server`, `development`, or `entwicklung` instead of blocking the semantic LLM-selected SSH profile as an unknown requested ref.

## [0.1.0-alpha305] - 2026-06-05

### Fixed
- Prefer a real local DNS resolver probe for single-target DNS/Pi-hole health checks when the LLM only proposes a service-active check, while keeping explicit Guardrail health bundles in control when configured.

## [0.1.0-alpha304] - 2026-06-04

### Fixed
- Allowed standard read-only DNS probe commands (`dig`, `host`, `nslookup`) in the SSH read-only policy so DNS health checks can run without an unnecessary confirmation prompt.
- Added a Security Guardrails review link for built-in SSH policy blocks when no specific Guardrail profile is attached to the connection.

## [0.1.0-alpha303] - 2026-06-04

### Fixed
- Prevented the bounded planner / recipe-experience step from overriding an already resolved plural SSH multi-target payload. This keeps prompts such as “haben meine dev-server noch genug festplattenspeicher” on the resolved dev-server group instead of collapsing back to the first learned single target.

## [0.1.0-alpha302] - 2026-06-04

### Fixed
- Tightened plural SSH metadata grouping so the short seed `dev` no longer matches unrelated words such as `device`, and rebuilt already-complete single-target SSH plans into multi-target plans when a plural metadata group is detected.

## [0.1.0-alpha301] - 2026-06-04

### Fixed
- Improved plural SSH group scoping when one matching profile is found through memory/routing but sibling profiles only match through related metadata such as `development`, `entwicklung`, `code-server`, or `vscode`. Prompts such as “dev servers” now stay on the matching server group instead of collapsing to the first matched profile.

## [0.1.0-alpha300] - 2026-06-04

### Fixed
- Moved the optional SSH Service URL next to the metadata “Check with LLM” action so the URL source field is visible where it is used.
- Scoped plural SSH checks to strongly matched connection metadata groups, so prompts such as “dev servers” do not expand to every SSH profile when matching aliases/tags identify a narrower server set.

## [0.1.0-alpha299] - 2026-06-01

### Changed
- Clarified Learned Recipes wording so the overview refers to the local review/learning list instead of the ambiguous term “Store”.

### Fixed
- Let SSH connection metadata suggestions use Host/User/Port when no Service URL is configured, and clarify SSH host-key verification failures during connection tests.

## [0.1.0-alpha298] - 2026-05-21

### Added
- Added an LLM-assisted Guardrail draft flow on the Security page: ARIA can turn a natural-language safety intent into a reviewable Guardrail proposal, while saving remains an explicit user action and deterministic Guardrail evaluation stays unchanged.
- Added a lightweight working-status indicator to the Guardrail AI draft form, so users can see when ARIA is checking context, contacting the LLM, and preparing the review draft.
- Added a Guardrail test mode on the Security page, allowing saved Guardrails to be checked against example requests before they are attached to live connections.
- Added a visible stats billing-period reset on the Costs card. Reset now archives the current token/run log before starting a fresh local usage period.

### Changed
- Clarified Discord startup host reporting: ARIA now reports the configured base URL or an automatically detected local address instead of warning about a missing public URL.
- Clarified the Stats token card request label so it refers to the current local period instead of a misleading fixed 7-day label after a usage reset.
- Clarified the Stats cost card so ARIA labels LLM costs as usage estimates for orientation, not invoice-grade provider billing.
- Changed the default runtime log retention to 90 days and extended startup/maintenance cleanup to prune the redacted LLM prompt debug log alongside token/cost/activity logs.
- Started aligning connection detail pages around the SSH page as the master pattern: the shared connection status block is now collapsible, profile cards show a visible edit action, and the other connection detail pages use collapsible edit/create work areas instead of hidden mode-only cards.
- Moved guardrail attachment UI and save-time validation for SSH, SFTP, SMB, Webhook, and HTTP API connection pages into shared templates/context/helper logic, keeping current single-Guardrail behavior while preparing a cleaner Multi-Guardrail follow-up.
- Scoped saved Guardrails can now carry exact compatible connection kinds, so a File Access Guardrail drafted for SFTP is not offered on SMB connection pages and vice versa.
- Opened the security/advanced option panels by default on Guardrail-capable connection forms, making Guardrail assignment visible without an extra expand step.
- Reworked the Security Guardrails page into focused collapsible sections, so AI drafting, loading/editing, deletion, manual creation, and sample imports are no longer all expanded at once.
- Reworked the SSH connection page into focused collapsible sections and made profile cards open the edit mode, with a visible edit action and clearer access to the Guardrail selector.
- Replaced the unsupported Google Calendar device-code/OAuth setup with a simpler read-only secret iCal URL setup, so LAN/IP-only end-user installs can connect a personal calendar without Google Cloud clients, redirect URIs, client secrets, or refresh-token handling.
- Updated product, help, and wiki docs so current Google Calendar guidance points to the read-only iCal setup instead of the obsolete OAuth path.

### Fixed
- Made Operator Guardrail warnings actionable on the Stats page by listing the exact non-OK checks, their details, and deep links to the relevant section.
- Fixed Stats in-page detail links so targets such as Costs & Pricing open their collapsed details section before scrolling.
- Fixed Guardrail dry-run and runtime evaluation for file, webhook, and HTTP API actions so generated read-only/status Guardrails receive structured operation context such as `file_list`, `read`, `webhook_send`, `status`, and `health` instead of only a bare path or payload.
- Fixed pending routed action execution so user-confirmed SSH/HTTP actions that were classified as `ask_user` can pass their explicit confirmation into runtime policy instead of failing again with the same confirmation-required error.
- Tightened chat admin delete parsing so webhook/API payload text such as `delete user record` is no longer misclassified as a request to delete a connection profile.
- Tightened memory-forget routing so webhook/API/message payloads containing words like `delete` are not intercepted before capability routing.
- Improved deterministic blocked-action fallback text for file write attempts, so read-only Guardrail blocks explain the blocked write more naturally when the LLM explanation path times out.
- Classified HTTP API 4xx/5xx endpoint responses as external endpoint status errors instead of internal recipe failures, with clearer chat wording and no Discord recipe-error alert for expected HTTP status responses.
- Classified runtime Guardrail blocks as intentional security decisions in chat, avoiding the generic profile/access-rights warning and Discord recipe-error alert for expected policy blocks.
- Added direct Guardrail review links to runtime Guardrail block messages and aligned the blocked-action timeout fallback with the same security-decision wording.
- Routed colloquial multi-server health prompts such as `wie fit sind meine server?` into the SSH multi-target health path instead of falling back to generic chat/RAG.
- Fixed connection mode navigation so switching to “new connection” no longer carries an already selected profile ref, and hash links such as `#manage-existing` reliably open the intended edit card.
- Fixed SFTP connection status rows so profile cards receive the same edit URLs as other connection types.
- Removed the obsolete Google Calendar OAuth/device-code routes and setup UI to avoid the repeated `OAuth Client-ID fehlt` loop.
- Limited Google Calendar `next appointment` reads to the single nearest event, while broader upcoming/week ranges still return event lists.

## [0.1.0-alpha280] - 2026-05-16

### Fixed
- Added hidden Google OAuth JSON fallback fields for the Calendar device-code flow, so Safari/form-submit edge cases can still send the parsed client ID even when the visible input value is not received by the backend.

## [0.1.0-alpha279] - 2026-05-16

### Fixed
- Added a backend fallback for Google Calendar device-code start that rereads the submitted form when FastAPI injects an empty client ID, using the last non-empty client ID value from the form before failing.

## [0.1.0-alpha278] - 2026-05-16

### Fixed
- Autofilled the Google Calendar client ID and optional client secret in the browser as soon as an OAuth JSON file is selected, making upload parsing visible before starting the code flow.

## [0.1.0-alpha277] - 2026-05-16

### Fixed
- Let the Google Calendar default device-code flow accept OAuth client JSON files that provide a client ID without a client secret, and omit the secret from token refresh/device requests when the Google client has none.
- Clarified the Google Calendar setup UI so Client Secret is shown as optional for the default code flow and only required for the advanced browser-redirect path.

## [0.1.0-alpha276] - 2026-05-16

### Changed
- Clarified the Google Calendar setup guide by pointing users to download the OAuth client JSON from the Google OAuth Clients list before uploading it in ARIA.
- Pre-filled new Google Calendar profiles with `primary-calendar` as the default connection ref so the device-code setup does not fail on an empty internal profile id.
- Added a server-side Google Calendar default ref fallback so the OAuth/device-code handlers still use `primary-calendar` if the browser submits an empty ref.

## [0.1.0-alpha275] - 2026-05-16

### Added
- Added a Google Calendar device-code sign-in flow as the default self-hosted setup path, so ARIA can connect calendars from LAN/IP-only installs without requiring a public redirect URI.

## [0.1.0-alpha274] - 2026-05-16

### Fixed
- Treated `sind meine server in ordnung`, `are my servers healthy`, and related multi-server health phrasings as broad SSH health checks, so strict per-host guardrails can use the richer allowed status bundle instead of falling back to bare `uptime`.

## [0.1.0-alpha273] - 2026-05-16

### Fixed
- Routed short multi-server health prompts such as `sind meine server ok` into the SSH multi-target health path instead of falling back to generic chat/RAG.

## [0.1.0-alpha272] - 2026-05-16

### Changed
- Kept long-running chat working-status messages category-specific after the 8-second fallback, so server checks continue to show that ARIA is waiting for server responses instead of falling back to a generic working message.

## [0.1.0-alpha271] - 2026-05-16

### Added
- Added lightweight chat working-status messages that show the user what ARIA is likely doing while a request is running, such as checking servers, reading feeds, searching files, preparing messages, or summarizing results.

### Changed
- Let the main chat view expand toward the available viewport height so the message area grows with the screen while the composer remains anchored below it.

## [0.1.0-alpha270] - 2026-05-16

### Added
- Extended the Connection Action Contract and Provider Manifest with planner-level roles, confirmation metadata, sensitive-content metadata, and optional draft capabilities so future providers such as e-mail can share read/search/draft/send boundaries instead of adding provider-specific pipeline branches.
- Added the first generic Agentic Content Access request/result contract and handler registry for read/search/list providers, keeping future mail, files, tickets, notes, and similar content adapters separate from send/write side-effect execution.
- Added an optional Pipeline content-access hook: registered read/search/list handlers can take over from a generic `ActionPlan`, while existing IMAP/file/feed executors remain the fallback when no handler is registered.

### Changed
- Consolidated documentation under `docs/`: public/release docs stay tracked, the internal build log moved to `docs/internal/alpha-build-log.md`, and local-only handoff/history/screenshots now live under ignored `docs/local/`.

### Fixed
- Broadened vague multi-server health prompts such as `wie geht es meinen servern` to the same strongest allowed read-only SSH status bundle used for capacity checks, avoiding narrow `uptime` probes that can be blocked by stricter per-host guardrails.
- Fixed an unterminated mobile CSS block that could break later styles on iPhone-sized screens, added iOS safe-area viewport support, and kept mobile form fields at 16px to avoid Safari input zoom.

## [0.1.0-alpha269] - 2026-05-16

### Fixed
- Broadened vague multi-server capacity checks such as `haben meine server überall genug kapazität?` from a narrow `uptime` probe to the strongest read-only health/capacity bundle allowed across all SSH targets, with deterministic fallback to disk or memory probes when stricter guardrails require it.
- Kept partial capability executions labeled as their actual capability in chat details instead of showing misleading `memory_error` badges for blocked SSH subtargets.

## [0.1.0-alpha268] - 2026-05-15

### Fixed
- Fixed mixed-language plural SSH disk prompts such as `hab ich auf all meinen server mehr als 10gb harddisk speicher frei ?` so they enter the multi-target SSH disk-check path instead of falling back to memory/RAG.
- Added a bounded LLM capability-draft fallback for operational remote prompts that carry a connection-kind signal but miss deterministic capability lexicons, keeping flexible server/disk wording out of memory/RAG while still routing through deterministic policy, guardrails, and runtime.
- Loosened the Pre-RAG action gate so bounded LLM capability classification can override ambiguous keyword-router hits such as false `memory_store` matches, while explicit web-search/recipe-status and runtime guardrails remain deterministic.

## [0.1.0-alpha267] - 2026-05-15

### Added
- Added `docs/product/agentic-flow-map-alpha267.md` to map the controlled Agentic Action Flow from Pre-RAG context enrichment through bounded draft, policy/guardrails, runtime execution, summary, and context-only learning.
- Added `aria/core/agentic_execution.py` and `docs/product/agentic-execution-handler-contract-alpha267.md` as the first generic Agentic execution handler contract for future connection adapters.
- Added `aria/core/agentic_execution_registry.py` and `aria/core/agentic_execution_learning.py` so provider adapters register through a shared execution registry and record successful capability learning through one service.
- Added `aria/core/connection_provider_manifest.py` as the first internal provider-manifest contract, grouping existing Connection Action Contracts by connection kind with auth modes, runtime adapter ids, capability rows, and validation.

### Changed
- Agentic context debug lines now use a shared context-boundary helper, so capability-draft and candidate-pool debug output explicitly carry `boundary=context_enrichment`.
- Bounded planner selection debug now marks the draft phase with `boundary=draft`, making the Agentic debug contract easier to audit before further pipeline modularization.
- Learned Recipe promotion now goes through a shared deterministic promotion gate: multi-target observations stay context-only, side-effect learned actions can become review-ready but not directly executable, and stored-recipe promotion validates the same blockers used by the UI.
- Multi-target SSH learning now marks learned scope as `target_scope=multi_target` / `learning_origin=plural_target_scope`, preventing fleet checks from looking like single-target recipe evidence.
- Learned Recipe candidates now validate `connection_kind` plus `capability` against the Connection Action Contract before re-entering the bounded planner, so stale mismatched records such as RSS/feed actions with SSH scope cannot hijack SSH questions.
- Learned HTTP API action recording now accepts the normalized `api_request` capability as well as the legacy `http_api_request` alias when extracting the learned path.
- Multi-target SSH runtime execution now runs through `MultiTargetSSHExecutionHandler`, the first adapter on the generic Agentic execution hook path, while preserving existing preflight, guardrail, context-memory, learning, and operator-summary behavior.
- RSS feed execution now runs through `RSSFeedExecutionHandler`, moving RSS group-bundle and digest-option enrichment onto the same Agentic execution registry while keeping runtime execution, summaries, context memory, and learning behavior intact.
- Agentic execution learning is now centralized through `AgenticExecutionLearningService`, removing duplicated Learned Recipe recording code from the SSH and RSS handlers.
- The Connection Provider Manifest checklist now documents the concrete internal schema, built-in export, validator, and tests that future community/provider manifests must satisfy before UI or import support is added.

## [0.1.0-alpha266] - 2026-05-15

### Added
- Added `constraints/runtime.txt` as the Docker release-build dependency lock baseline, pinned from the tested `alpha264` container.
- Added an update-reconnect service worker that serves a small multilingual waiting shell when navigation happens during ARIA's brief container-recreate downtime, then polls `/health` and returns to the original page once ARIA is reachable again.
- Added `docs/product/codebase-modularity-audit-alpha257.md` to document the full codebase modularity audit, accepted provider-specific seams, residual watchpoints, and the LLM-first versus deterministic safety boundary.
- RSS digest planning now has a bounded LLM preference extraction step for explicit count/detail requests, passing the requested result count into the read-only RSS runtime while keeping deterministic caps and fallbacks.
- Learned Recipe review cards now show Curator debug metadata (`curation_source`, policy, status, timestamp, and skip/error reason), making it visible when bounded LLM curation ran or why it stayed skipped/context-only.
- Learned Recipe store entries now record qualitative learning signals (`new_pattern`, repeat, wording/scope/action variants, risky deviations) plus weighted learning evidence, so self-learning can distinguish repeated noise from useful variation.
- Added a Learned Recipe promotion preview page that shows the planned stored recipe manifest, policy/side-effect boundary, confidence/risk, trigger set, limits, and step parameters before an admin writes the promoted recipe.
- Added a bounded LLM Learned Recipe Curator that enriches successful single Agentic/Recipe learning events with review-only metadata: confidence, risk level, generalization hint, suggested trigger phrasings, promotion reason, and explicit reuse limits.
- Managed and internal update helpers now prune dangling Docker image layers and unused ARIA Docker images after a successful health check, keeping old image layers from filling `/var/lib/docker` while leaving containers, sidecars, volumes and tagged non-ARIA images untouched.
- Added machine-readable Agentic debug boundary constants that map debug lines back to the canonical context-enrichment, LLM-draft, policy/guardrail, and runtime-execution phases.
- Added `docs/product/agentic-live-regression-dossier.md` as the active live-test dossier for Agentic Action Flow regressions, linking real prompts to expected routing, policy, runtime, debug, and cost behavior.
- Added `aria/core/connection_action_contract.py` and `docs/product/connection-action-contract.md` as the shared contract layer for capability operation, executor-kind, policy-family, required-field, side-effect, and runtime-debug metadata.
- Added `docs/product/legacy-recipe-compatibility-audit.md` to make the remaining Skill-era bridges explicit: public surfaces stay recipe-first, while old imports, `/skills*` redirects, `skills:` config roots, and `skill_*` log/config fields remain compatibility seams until a deliberate migration release removes them.
- Added `aria/core/recipe_result_view.py` as the shared presentation layer for stored recipe execution summaries, skipped/error-continue step labels, and friendly recipe runtime error text.
- Added an Operator Guardrail card on `/stats` that combines Model Gateway Audit, Pricing Coverage, Startup Preflight, runtime health, and update-path status into one release/operations readiness view.
- Added explicit release metadata validation to the `/stats` Operator Guardrail, so missing or inconsistent release labels/versions are surfaced before a public build or update test is trusted.
- Added `docs/release/internal-build-smoke-test.md` as the repeatable internal build/update smoke checklist for `/stats`, Agentic routing, SSH guardrails, Discord confirmation, SMB, RSS, RAG, and managed update-path checks.
- Learned Recipe review cards now expose the underlying Connection Action Contract boundary (`family`, `policy`, `runtime`, side-effect state), making promoted/context-only candidates easier to audit before adoption.
- Learned Recipe review cards now show a localized review-maturity hint, separating strong promotion evidence from candidates that still need a target, action, or more successful runs.
- Bundled recipe template cards now show step count, connection families, trigger count, schedule/manual state, step types, and whether a template has side effects that require confirmation/policy review.
- Added `connection_action_manifest_rows()` plus `docs/product/connection-provider-manifest-checklist.md` as the bridge from today's Python-backed connection contracts to future declarative provider manifests.
- Added `docs/product/operator-observability-guardrails.md` to document the `/stats` release/operations guardrail rows, status semantics, cost-tracking strictness, and maintenance rules.

### Changed
- Docker builds now pin the Python and Docker CLI base image digests, install ARIA through the runtime constraints file, and disable build isolation after pinned `pip/setuptools/wheel` bootstrap, reducing base-image and Python transitive dependency drift before public releases.
- RSS read-only runtimes now size their internal transport budget from the requested digest count, so a `10 news` request is not truncated before the chat summarizer can format all requested entries.
- Learned Recipe curation and Recipe Experience Memory writes now run as non-blocking post-response follow-up work, keeping self-learning context-only while preventing successful chat actions from waiting on curation LLM calls or memory embeddings.
- RSS category reads now fetch the bounded feed set concurrently instead of serially, so slow or timing-out feeds no longer stack into minute-long digest responses.
- File-list summaries now separate directories from file examples, making SMB/SFTP folder listings easier to scan without changing the bounded file-list runtime.
- Routing Workbench kind options, pending chat action route kinds, default Qdrant routing-index kinds, and generic pipeline capability-gate pools now derive from the Connection Catalog / Connection Action Contract instead of page- or pipeline-local provider lists.
- Agentic read/message resolver capability families now derive from the Connection Action Contract, keeping LLM-backed operation resolution attached to the same provider contract used by runtime and policy.
- RSS category digests now collect multiple entries per feed up to a safe cap, instead of always taking one item per feed and formatting at most six items.
- RSS digest summaries now explain request/result gaps such as `10 requested, 4 found/readable, 1 skipped`, making feed count limits, timeouts, and sparse sources visible to the user.
- Learned Recipe review maturity now prefers weighted learning evidence over raw run count, reducing overconfidence from repeated identical executions while still keeping raw success count visible for audit.
- Recipe Experience Memory text now carries the learning signal and weighted evidence as planner context, so future LLM-backed planning can see whether an experience was fresh evidence, wording variation, or repeated noise.
- Learned Recipe cards now route promotable candidates through the promotion preview instead of writing a stored recipe directly from the list action.
- Learned Recipe Experience Memory now includes curated confidence/risk/generalization/limits in its semantic text, so future planning can use richer context while runtime execution remains gated by normal bounded planning and guardrails.
- `/recipes/learned` now explains the full learning lifecycle in the UI: where learned patterns come from, where review candidates and semantic experience memory are stored, what Promote/Dismiss/Delete do, and how learned context is retrieved without bypassing policy or guardrails.
- `/recipes` overview status cards now use compact, non-duplicated status labels and link directly to the matching recipe sections, so the lamp cards behave like the navigation elements they visually resemble.
- `/connections/status` now renders from cached/last-known connection health by default and exposes an explicit live-refresh link, so opening the status page no longer waits on slow SSH, RSS, API, SearXNG, or network probes.
- `agentic_runtime` debug lines now include `boundary=runtime_execution`, making runtime execution visually separate from context enrichment, LLM drafts, and policy decisions.
- Multi-target SSH checks now run an LLM-backed operator-summary pass over the already executed read-only results, with deterministic summaries kept as fallback only; this lets ARIA answer phrased constraints such as free-space reserves more flexibly without letting the LLM choose or bypass execution policy.
- The active alpha backlog now removes the completed Agentic Intelligence block from the open work list and keeps only the ongoing live-regression dossier process as a standing guardrail.
- `pre_rag_action_gate` debug output now includes the context-enrichment boundary plus target/path/content hints, and final chat/RAG responses in debug mode show an explicit `action_path=no_action` line when the Agentic gate intentionally declines to take over.
- The live agentic routing regression now covers the natural German prompt `habe ich genügend freien speicherplatz auf meinen servern?`, ensuring it stays out of `memory_store`/RAG and fans out through the bounded SSH multi-target disk check.
- Learned Recipe review cards now show a localized next-action hint, localize row status/safety labels with the active UI language, and preserve state/kind/sort filters after Promote/Dismiss/Delete actions.
- Learned Recipe admin success messages now use recipe-first `learned_recipes.*` i18n keys instead of legacy `skills.learned_*` compatibility keys.
- Stored recipe summaries now render skipped step markers through the same readable Recipe Result View formatter as executed steps.
- Connection Action Contract tests now pin the side-effect boundary so write/send/publish capabilities stay auditable and cannot silently look read-only.

### Fixed
- Learned Recipes review cards now render as full-width contained cards with wrapped badges and structured details for long LLM curator fields, preventing promotion reasons, trigger lists, and limits from tearing the `/recipes/learned` layout apart.
- Learned Recipe `file_list` candidates now display list/browse labels in the review UI even when older stored learning records still carry legacy `Read File` titles or intents.
- Assistant-message Markdown rendering now supports link labels that contain square brackets, so RSS titles such as Exploit-DB `[webapps]` entries remain clickable in the chat UI.
- Guardrail review hints now keep the visible `/config/security?guardrail_ref=...` path next to the clickable Markdown link, so copied chat text still contains the concrete review target.
- RSS digest formatting now preserves explicit `Link:` lines for source titles that already contain bracketed Markdown labels such as Exploit-DB `[webapps]` entries.
- Guardrail review references in blocked-action answers now render as Markdown links to `/config/security?guardrail_ref=...` instead of plain URL text.
- SSH policy-block responses now use a deterministic safety fast-path after the LLM has identified the intended action, avoiding an extra blocked-action LLM call and recovering the guardrail review URL from the selected connection when the safety decision did not carry it forward.
- Blocked policy/guardrail actions now keep the deterministic block decision but use a bounded LLM explanation step for the user-facing answer, with deterministic fallback, visible planned action, and direct `/config/security?guardrail_ref=...` review links when a guardrail profile is attached.
- Blocked-action LLM explanations now post-process live wording more strictly: if the LLM already mentions the concrete command, ARIA does not append a duplicate planned-action line, and weak guardrail references are replaced with the canonical guardrail review link.
- Blocked-action explanation calls now have a short timeout with deterministic fallback, and clearly mutating SSH requests skip the extra guardrail-intent LLM classification once policy has already blocked the command.
- Guardrail-kind mapping now lives in the Connection Action Contract and is reused by dry-run plus recipe runtimes, removing duplicated HTTP/file/MQTT/SSH mapping tables from execution paths.
- Memory Overview/Map and Stats now share a central Qdrant collection classifier, auto-detect ARIA system collections such as `aria_recipe_experience_*`, show Recipe Experience Memory even when empty, and keep future unknown `aria_*` system collections visible instead of silently dropping them from the graph.
- Learned Recipes flow explainer cards now render explanatory body text with the same subdued visual weight as the meta hints, keeping `/recipes/learned` calmer when the learned store is empty.
- Deleting a Learned Recipe now also purges matching Recipe Experience Memory points from Qdrant for the current user, preventing stale context-only learning data from surviving after an admin deliberately removes a bad candidate.
- `/stats` Operator Guardrail now has a dedicated Cost Tracking row: disabled token tracking and UsageMeter bypasses fail the release guardrail, while estimated-vs-logged cost gaps surface as warnings.
- `/stats` Operator Guardrail now includes Recipe Experience Memory reachability when that metadata is available, so Qdrant learning-memory outages are visible without making disabled/fresh installs look broken.
- Pricing refresh now reuses the shared pricing-settings sync path after preserving manual prices and aliases, so manual alias overrides remain visible in the running settings object immediately after a LiteLLM refresh.
- Agentic runtime debug operation/payload rendering now uses the shared Connection Action Contract instead of a local capability `if` chain, so future connection types have one explicit place to declare their runtime shape.
- Executor registration and capability routing now derive valid `(connection_kind, capability)` bindings from the Connection Action Contract; unsupported runtime bindings fail fast instead of quietly creating a side path outside the modular connection contract.
- Bundled sample-manifest regression coverage is now recipe-first: `samples/recipes/` is pinned as the public import surface, `/recipes` links are required there, and `samples/skills/` is verified only as a parity fallback for old installs.
- Stored recipe step output now keeps its legacy marker for compatibility but also renders a clearer recipe run status, readable per-step states, skipped steps, technical run details, and result text.
- Recipe Result View summaries now include executed/skipped step counts ahead of the detailed step list, making multi-step recipe output easier to scan.
- Operator Guardrail rows now carry stable machine-readable keys, so tests and future UI/admin tooling do not have to infer row meaning from visual order.
- The Legacy Recipe Compatibility Audit now includes an explicit migration gate for removing old Skill-era bridges instead of leaving those compatibility seams as vague cleanup debt.
- Multi-target SSH LLM summaries now carry structured threshold facts and are validated against the measured read-only `df -h` results; if the first LLM summary contradicts hard measurements, ARIA asks the LLM for a bounded repair and only falls back to a measured threshold summary if repair fails.
- Browser favicons are now real bundled favicon assets instead of a PNG served through `/favicon.ico`: ARIA ships `.ico`, 16/32/48 PNG variants and an Apple touch icon, the base template declares all of them, and regression tests pin the route, template links and package-data coverage.
- Multi-target SSH LLM summaries no longer pass unsupported per-call `temperature` overrides to the shared `LLMClient`; skipped or failed summary calls now leave a routing-debug line instead of silently falling back to the old deterministic summary.
- German disk-space questions such as `hab ich noch genug speicherplatz auf meinen servern?` no longer get misclassified as `memory_store` just because `speicherplatz` contains the memory-store verb stem `speicher`.
- Multi-target SSH disk summaries now honor explicit free-space thresholds from the user prompt, so requests like `mehr als 10gb freien festplattenspeicher` report hosts below that threshold instead of reusing the generic all-ok disk summary.
- The memory-store keyword boundary regex now uses Unicode word boundaries instead of an inline German character class, keeping the `speicherplatz` fix while passing the strict i18n literal audit.
- Learned Recipe Dismiss/Delete redirects now render human-readable info messages instead of leaking raw `learned_dismissed:*` / `learned_deleted:*` status codes.
- `/connections/types` now uses cached/last-known connection status rows instead of live-probing every configured service while rendering the type hub, so slow RSS or network endpoints no longer block that page load.

## [0.1.0-alpha251] - 2026-05-12

### Fixed
- The host-side update helper now preflights published Compose ports before recreating the ARIA service. If a new Compose plan would publish a host port that is already occupied by something other than the current ARIA container, the update aborts before touching the running stack instead of failing mid-recreate.
- RSS digests now print the URL explicitly below linked titles, so copied chat output still contains usable links even when the browser drops Markdown link targets during copy/paste.
- Natural plural SSH prompts such as `von meinen server` no longer leak article fragments like `requested_ref=n server` into routing debug output.
- Host-side public updates can now pass `--target-image` to move fixed-tag installs to a newer ARIA image while still recreating only the `aria` service; managed stack helper files are refreshed from the target image and file ownership is restored afterwards.
- `docker/aria-host-update.sh` no longer leaves a stale lock cleanup error on exit after an update, and its managed-file refresh avoids root-owned `.env` files on user-owned installs.
- Managed public stack updates now refresh/recreate only the `aria` service during normal `aria-stack.sh update`; stateful sidecars such as Qdrant/SearXNG remain untouched unless `repair` or `update-all` is run deliberately.
- Multi-target SSH fleet checks now keep all-ok responses compact and action-oriented: when every target looks healthy, ARIA reports the fleet status and "no action required" instead of listing every host result in the main chat answer; mixed results still surface only hosts that need attention, were blocked, or failed while the full execution trace remains in details.
- Plural SSH target requests are now finalized again after bounded planning/template normalization, so a late stale `connection_ref` missing-input state cannot undo the multi-target command draft and ask for one SSH profile.
- Mutating SSH requests such as `starte meinen dns server neu` can no longer be converted into a safe healthcheck guardrail fallback; ARIA keeps the intended mutating command visible and lets SSH policy block it.
- Plural SSH target requests with an empty command draft can now ask the SSH agentic resolver for the missing read-only command before deciding whether bounded multi-target execution is possible, and the resulting multi-target action clears stale `connection_ref` missing-input state.
- The alpha246 live-test sequence is now covered by one regression spanning multi-target SSH, management disk checks, DNS health, blocked restarts, API availability, Discord confirmation, and SMB root listing.
- Chat one-click confirmation buttons still send the signed confirmation command internally, but the visible user bubble now shows the clicked button label instead of the raw `bestätige aktion ...` token command.
- Recent file-context hints such as `im gleichen Ordner` now distinguish a previously listed directory from a previously opened file, so a follow-up after listing `/tmp` stays in `/tmp` instead of jumping to `/`.
- Chat one-click confirmation buttons now post the signed pending-action payload with the confirmation request, so the action can be confirmed even if the browser has not persisted the pending cookie yet; the typed confirmation fallback remains available.
- SSH block previews are now rebuilt when the agentic resolver replaces a stale generic command with the actual intended command, so restart/state-change requests show the mutating command that policy blocked instead of an old `uptime` probe.
- Recent file-context hints such as `im gleichen Ordner` now override default root/path placeholders like `.`, including explicit or single-profile SFTP/SMB routes.
- Plural SSH target requests such as `meine Server` now suppress stale stored-recipe and single-host memory candidates, but safe read-only SSH commands such as `df -h` can fan out across all matching SSH profiles as a bounded multi-target action with a localized multi-target summary.
- Multi-target SSH execution now preflights every target against its own profile allowlist, guardrail allow terms, and SSH read-only policy; mixed target sets execute allowed profiles and report blocked profiles as localized partial failures.
- Multi-target SSH chat responses now include a compact operator summary before per-host details, highlighting how many targets look ok, need attention, were blocked, or failed.

### Changed
- RSS category digests now keep useful operator context in the main chat answer: entries are rendered as a readable list with source, timestamp, short snippet, and clickable Markdown links instead of collapsing everything into a one-line headline/source summary.
- Public-facing release copy was refreshed for the post-`alpha167` rollup: README and Docker Hub overview now describe ARIA as recipe-first with LLM-assisted action planning, and `docs/release/public-alpha-rollup-alpha167-to-next.md` provides a human-readable GitHub/Docker release narrative.
- The active alpha backlog has been compacted so old build history lives in `docs/internal/alpha-build-log.md` / `CHANGELOG.md`, while `docs/backlog/alpha-backlog.md` now focuses on current blockers, live-test focus, and next cleanup steps.
- LiteLLM is no longer a hard base dependency of the ARIA package; model gateway calls load it lazily and Docker installs it explicitly via the `model-gateway` extra, so pricing can remain independent from the runtime provider package.
- SSH, HTTP API, SFTP/SMB file, outbound messaging, and read-only agentic resolvers now share one explicit LLM action-draft contract: enrich context via a target dossier, let the LLM propose only a bounded draft, and leave allow/ask/block decisions to policy and guardrails.
- Agentic Pre-RAG action paths now run inside a request usage scope, so LLM calls used for SSH/HTTP/File/Messaging/Read decisions are reflected in the visible `PipelineResult`, chat token badge, and token log instead of showing misleading `0 tokens`.
- Pending routed actions in chat now expose a one-click confirmation button instead of asking users to manually type a confirmation code; the signed pending-cookie flow and typed-token fallback remain in place for safety and compatibility.
- Agentic routing now fixes the first `alpha238` live-test outliers: generic HTTP availability prompts can use the only configured API profile instead of treating `erreichbar` / `reachable` as a profile name, SMB folder-list prompts default to the share root, and fresh Discord-send prompts are no longer consumed as a pending SMB path reply.
- Natural SSH status/disk wording now keeps the router at Intent/Ziel level and leaves the concrete command proposal to the agentic SSH resolver before guardrails run, instead of baking `uptime` / `df -h` into the capability router itself.
- Introduced an explicit generic Pre-RAG Action Gate in the pipeline: chat/memory requests are first checked for bounded capability/connection actions before document RAG, with `pre_rag_action_gate` debug output showing whether unified routing or direct capability action took precedence
- Natural SSH disk wording now treats `HD`, `HDD`, `hard drive`, and German plate/free-space variants as disk-check terms, so prompts such as `wie sieht die hd auf meinem management server aus` route to the bounded SSH `df -h` action path before generic RAG chat can pull irrelevant documents
- The Workbench surface at `/config/workbench` now links directly to `/config/llm/debug`; the LLM Prompt Debug entry is no longer only visible on the older settings overview
- LLM Prompt Debug now persists redacted audit entries to `data/runtime/llm_audit.jsonl` in addition to the in-memory ring, so prompts remain visible across multiple web workers and can still be cleared from `/config/llm/debug`
- Final chat/RAG responses now tag their LLM gateway call with `source`, `operation=final_chat_response`, `user_id`, and `request_id`, making the exact prompt context and model answer inspectable instead of only token totals
- Recipe `llm_transform` steps now tag their gateway calls as `recipe_runtime` / `llm_transform` for clearer prompt debugging
- Added an admin-only LLM Prompt Debug page at `/config/llm/debug` backed by the central `LLMClient` gateway; recent prompts, responses, source, operation, model, duration, and token usage are captured in memory with secret redaction and no disk persistence
- The LLM gateway now records failed, empty, and successful calls in a bounded in-memory audit ring so agentic routing can be inspected without guessing what was sent to the model
- Soft/ordinal connection targets such as `zweiten dns server` now trigger semantic LLM disambiguation across the available profiles before an alias-derived explicit ref is accepted, so `second DNS server` can resolve to `dns-node-02` instead of the first `dns server` alias match
- SSH restart/state-change requests now get a second mutating-intent LLM pass when the first command proposal incorrectly substitutes a harmless status probe such as `uptime`; the real intended command is then blocked by policy instead of misleading the user
- Explicit SSH command requests such as `führe uptime auf meinem dns server aus` now keep the requested command as the action draft; ARIA no longer expands those into a full healthcheck bundle unless the user asked for a broader health/status check
- Mutating SSH requests now ask the SSH LLM resolver to identify the intended command so the policy layer can block the real requested operation instead of showing a misleading safe `uptime` fallback
- Plural SSH target requests such as `meine Server` no longer accept a single-host semantic LLM guess when no explicit target was selected; until multi-target execution is implemented, ARIA keeps the request bounded instead of silently choosing one server
- Bounded planning now carries an explicit `context_enrichment -> llm_action_proposal -> policy_guardrail_decision -> runtime_execution` contract into the LLM prompt, planner result, and routing debug output, making deterministic context advisory while keeping guardrails as the execution gate
- Natural SSH status requests that arrive with only a generic deterministic `uptime` draft now ask the bounded SSH LLM resolver for a concrete command proposal first, unless the user explicitly requested `uptime`; the resulting command still goes through the same SSH guardrail allow/ask/block policy
- Google Calendar now translates the most common real-world OAuth and API failures more precisely across both connection tests and live `calendar_read` execution, including expired refresh tokens, disabled Calendar APIs, and permission/scope mismatches
- natural calendar search requests no longer depend only on quoted text; ARIA now also extracts simple unquoted filters such as `Termine mit Zahnarzt nächste Woche`
- short calendar follow-ups now reuse recent calendar context more naturally, so requests like `und morgen?` can keep the last calendar filter instead of falling back to a generic chat answer
- the Google Calendar setup page now includes an explicit reconnect hint for the common case where only the refresh token needs to be renewed later
- Google Calendar no longer depends on a manual OAuth Playground copy/paste step; ARIA can now start the Google sign-in flow directly from the connection form and store the refresh token server-side on callback
- Notes can now be browsed more naturally from chat and the toolbox, including folder listing, folder-scoped note lists, and opening a note by query
- Notes folders can now be renamed directly from the Notes UI, while note title edits now explain more clearly that changing the title also renames the note
- note cards on the Notes board now wrap long titles instead of stretching the whole board layout sideways
- `öffne notizen in ordner ...` now resolves into the Notes flow and opens the folder view instead of falling through into unrelated generic routing
- watched websites now have their own lightweight chat entry points for opening and listing profiles, and admin users can start a website profile via the short `beobachte https://...` command that drops into the existing confirm flow
- `/stats` now renders token usage as a compact vertical token card with one prominent total and smaller detail rows, so the added chat/embedding/model metrics no longer break the top-row visual balance
- `/stats` now includes a `Model Gateway Audit` card that shows the active chat model, embedding model, shared `UsageMeter` status, memory embedding wiring, token-log status, and unpriced-token warnings
- LLM and embedding runtime calls are now guarded by a contract test so provider calls stay behind the metered `LLMClient` / `EmbeddingClient` gateway instead of reappearing as untracked side paths
- natural SSH status questions such as `wie geht es meinem dns server` now count as health/status requests for the guardrail fallback, so an unsafe or unlisted narrow `uptime` draft can be replaced by the allowed healthcheck command bundle
- successful SSH healthcheck guardrail fallbacks now enrich Learned Recipe candidates with the natural user wording, the final allowed command bundle, target scope, and fallback provenance; unpromoted learned recipes remain non-executable until review/promotion
- successful recipe/guardrail runs are now also indexed as semantic `Recipe Experience Memory` in Qdrant and retrieved as bounded planner context only, so prior successes can inform planning without becoming a direct executor
- `/stats` now shows Recipe Experience Memory status, collection count, and point count, making the new self-learning context layer visible during testing
- the Learned Recipes review UI now exposes the original user wording and learning origin for each candidate, making promotion decisions easier to audit
- full SSH healthcheck summaries now end with a human conclusion such as `Fazit: unauffällig` or `Fazit: Handlungsbedarf`, so users get an operator-level read instead of only raw metrics
- SSH healthcheck summary wording now uses `result_ssh.*` i18n keys from the language files instead of German text embedded in the summarizer code, with an English regression test covering the full healthcheck path
- a new `scripts/audit_i18n_code_literals.py` helper and `docs/backlog/i18n-code-literal-audit.md` report document the remaining German literals in Python code so the cleanup can be handled deliberately
- Connection Admin now uses structured error codes and `connection_admin.*` i18n keys for success/error messages instead of German runtime strings in Python
- Chat Admin connection/update/backup/status replies now use `chat_admin.*` i18n keys instead of hard-coded German assistant text
- Connection mutation handlers now use `connection_mutation.*` i18n keys and structured errors for form/redirect failures instead of raw German runtime strings
- Connection catalog UI labels, Discord toggle metadata, and chat insert examples now use `connection_catalog.*` / `config_conn.*` i18n keys instead of raw German metadata strings in Python
- Recipe Runtime status output, step error markers, recipe-step summaries, SMB connection errors, and the stored-recipe selection prompt now use `recipe_runtime.*` i18n keys instead of raw German runtime strings
- Chat command catalog no longer carries the old German-to-English insert replacement bridge; delete-connection inserts now use `chat.tool_delete_connection_insert`, and remaining German toolbox text is confined to i18n-backed fallbacks
- Recipe route wizard presets, follow-up-step suggestions, connection-choice hints, and import/wizard validation errors now use `recipes_routes.*` i18n keys instead of raw German UI/runtime strings
- Memory routes now use `memories_routes.*` i18n keys for graph labels, manual memory types, document delete/import errors, backend validation errors, and compression status text instead of raw German route strings
- Chat pending flows now use `chat_pending.*` i18n keys for action confirmations, safe-fix prompts, memory-forget confirmations, and alias follow-ups, removing German UI text from `chat_pending_flows.py`
- Config intelligence/workbench routes now use `config_workbench.*` i18n keys for LLM and embedding profile validation, model API validation, file editor errors, and error-interpreter rule validation
- Main app documentation defaults, runtime reload errors, startup Discord alerts, and unexpected-error responses now use English fallbacks or `app.*` i18n keys instead of German literals in `main.py`
- `/stats` pricing coverage now falls back directly to the ARIA bundled pricing seed and treats rows with logged numeric model costs as priced, avoiding false “unpriced model usage” warnings for known Claude/OpenAI models when the saved pricing catalog is empty or stale
- Action Planner dry-run, heuristic, and bounded-recovery messages now use `action_planner.*` i18n keys, and Notes Store validation/file-action errors now use `notes_store.*` i18n keys instead of German core literals
- Document ingest validation/errors and Safe-Fix held-package summaries/execution messages now use `document_ingest.*` and `safe_fix.*` i18n keys instead of German core literals; localized document stopwords also moved out of Python code
- Config surface routes and Notes route status messages now use `config_surface.*` and `notes_routes.*` i18n keys instead of German route literals
- Routing config/workbench route messages and shared main UI error helpers now use `config_routing_routes.*` and `main_ui.*` i18n keys instead of German route/helper literals
- Config profile helper messages and Stats route summaries now use `config_profile_helpers.*` and `stats_routes.*` i18n keys instead of German helper/route literals
- Action planner candidate detail labels and agentic SSH clarification/confirmation messages now use `action_planner_candidate_details.*` and `ssh_agentic_resolution.*` i18n keys instead of German core literals
- Operations config, connection context hints, action candidate taxonomy labels, and IMAP result summaries now use `config_operations_detail_routes.*`, `connection_context_helpers.*`, `action_candidate_taxonomy.*`, and `result_imap.*` i18n keys instead of German literals
- Auth surface, main config helpers, Notes Magic, HTTP API result summaries, and Website Runtime now use `auth_surface_routes.*`, `main_config_helpers.*`, `notes_magic.*`, `result_http_api.*`, and `website_runtime.*` i18n keys instead of German runtime strings or local German note-folder lexicon in Python
- Google Calendar support errors, Web Search result text/lexicon, config overview helper messages, and chat execution warnings now use `google_calendar_support.*`, `web_search.*`, `config_surface_helpers.*`, and `chat_execution_flow.*` i18n keys instead of inline German strings in Python
- Capability detail lines, action-planner result labels, RSS result summaries, and file-operation summaries now use `capability_catalog.*`, `action_planner_result_state.*`, `result_rss.*`, and `result_file_operation.*` i18n keys instead of hard-coded German labels in Python
- Connections surface headings/cards and Notes context/index fallback text now use `connections_surface_routes.*`, `connections_surface_helpers.*`, `notes_context.*`, and `notes_index.*` i18n keys instead of German UI/runtime strings in Python
- LLM client errors, executor registry errors, learned-recipe promotion validation, and stored-recipe manifest validation now use `llm_client.*`, `executor_registry.*`, `learned_recipe_promotion.*`, and `recipe_manifests.*` i18n keys instead of German runtime strings in Python
- Config guardrail/persona errors, config file-save reload warnings, OPML RSS import exhaustion, and SSH authorized_keys write failures now use `config_access_detail_routes.*`, `config_persona_routes.*`, `config_support_helpers.*`, `connection_reader_helpers.*`, and `connection_support_helpers.*` i18n keys instead of German runtime strings in Python
- User-admin CLI text, secure-store/migration errors, source-lookup previews, SSH template term matching, and HTTP API status term matching now use `user_admin.*`, `secure_store.*`, `secure_migrate.*`, `behavior_families.*`, `execution_dry_run_template_payloads.*`, and `http_api_agentic_resolution.*` i18n keys instead of German literals in Python
- The i18n audit now reports zero `raw_runtime_literal` and zero `llm_prompt` findings after moving the remaining config, connection-health, maintenance, router, routing-hint, RSS grouping, learned-recipe UI, runtime-diagnostics, pipeline, and memory-skill strings into language keys
- The first large `inline_localized` cleanup moved connection runtime, recipe runtime, and chat command catalog fallback text behind `connection_runtime.*`, `recipe_runtime.*`, and `chat.*` language keys, reducing inline localized audit findings from 252 to 93
- A second `inline_localized` cleanup moved capability pipeline messages, recipe overview/wizard fallbacks, and memory hub/upload text behind `pipeline_capability_messages.*`, `skills.*`, and `memories_routes.*` language keys, reducing inline localized audit findings from 93 to 50
- The final `inline_localized` cleanup moved dry-run labels/reasons, learned and stored recipe candidate previews, planner follow-up prompts, connection mutation status messages, pipeline capability details/execution text, auth JSON fallbacks, and docs license summaries behind i18n keys, reducing inline localized audit findings from 50 to 0; remaining German code-literal findings are input lexicon only
- The declarative input-lexicon cleanup moved routing profiles, capability-routing terms, chat notes/admin/website command patterns, action-planner scoring/extractor hints and template overrides, auto-memory rules, routing-resolver scoring, capability-router patterns, recipe-runtime matching terms, connection-catalog extras, semantic resolver prompts, pipeline missing-input patterns, Notes tag normalization, and update-helper failure detection into `aria/lexicons/*.json`; visible Chat Notes replies now use `chat_notes.*` i18n keys, and the German code-literal audit now reports zero findings
- `scripts/audit_i18n_code_literals.py` now has a `--strict` guardrail mode plus regression tests, so new German runtime, inline-localized, LLM-prompt, or input-lexicon literals in Python can fail validation instead of silently re-entering the codebase
- Python package builds now declare ARIA runtime assets as setuptools package data, including `aria/i18n/*.json`, `aria/lexicons/*.json`, templates, and static files, so normal wheel installs keep the i18n and lexicon cleanup usable outside the Docker source tree
- `docs/backlog/alpha-backlog.md` now reflects the current post-`alpha215` working state, separating shipped build facts from unbuilt guardrail/package-data follow-ups and reprioritizing the remaining backlog around Recipe legacy, model-cost tracking, Experience Memory, monolith cleanup, i18n guardrails, and release hygiene
- `/stats` now separates logged USD from estimated USD and can reprice historical token rows from model names plus prompt/completion or embedding token counts once Claude/OpenAI pricing is known, making stale zero-cost rows visible instead of silently understating usage
- Recipe Experience Memory now adds explicit planner-debug lines for retrieved experience hits, including score, target, success count, and previously working action, while marking the layer as `context_only` so learned memory remains planner context and never becomes a direct executor
- Learned Recipe review cards now surface the original user wording, target scope, previously working action, and safety state directly in the admin UI, making it clearer that unpromoted experience is review/context only
- The SSH healthcheck learning path now has an end-to-end regression covering successful guardrail fallback execution, Learned Recipe store payload creation, Experience Memory storage, and later planner-context retrieval/debug formatting
- Learned Recipe admin UI text now uses the `learned_recipes.*` i18n namespace instead of the legacy `skills.learned_*` keys, keeping the visible Recipe-first surface separated from Skill compatibility keys
- Recipes hub, nav, page headings, overview cards, start/custom/system/template sections, save/load hints, wizard controls, wizard form labels, and wizard JavaScript status text now use `recipes.*` / `learned_recipes.*` i18n keys instead of legacy `skills.*` keys or hard-coded German template strings, while old Skill keys remain only for compatibility and internal migration seams
- `recipes_routes.py` is now slimmer and more readable after moving Recipes overview/next-step UI construction into `recipes_surface_context.py`, Wizard preset/follow-up/connection catalog data into `recipes_wizard_catalog.py`, Learned Recipe promote/dismiss/delete action handling into `recipes_learned_actions.py`, sample-template listing/import handling into `recipes_template_import.py`, Wizard form-to-manifest save logic into `recipes_wizard_save.py`, and shared return-to/CSRF/admin helpers into `recipes_route_support.py`
- Recipe runtime matching now uses recipe-first helper names internally (`_recipe_tokens`, `_recipe_match_score`, `_looks_like_recipe_execution_request`) while retaining legacy `skill_*` aliases for compatibility
- Recipe runtime file/guardrail diagnostics now use `recipe_runtime.*` i18n keys instead of embedded German strings, unused duplicated SFTP/SMB list-step helpers were removed, and SFTP/SMB file execution now lives in `recipe_runtime_file_adapters.py` behind a small `RecipeFileRuntime` adapter
- RSS feed parsing, URL cleanup, timestamp normalization, summary formatting, and single-feed execution now live in `recipe_runtime_rss.py`, while `RecipeRuntime` keeps thin compatibility wrappers for existing tests and callers
- Google Calendar OAuth token exchange, event fetching, range calculation, event-time formatting, and result rendering now live in `recipe_runtime_calendar.py`, with `RecipeRuntime.execute_google_calendar_read(...)` preserved as the stable public entry point
- Webhook sends, Discord sends, and HTTP API requests now live in `recipe_runtime_http.py`, reusing the existing guardrail enforcer through dependency injection while keeping the stable `RecipeRuntime` execution methods as thin delegates
- SMTP email send, IMAP read/search, and MQTT publish execution now live in `recipe_runtime_messaging.py`; `RecipeRuntime` keeps compatibility delegates for the existing public methods and shared mail-header helper
- Direct Discord recipe steps now reuse the HTTP runtime adapter for webhook delivery instead of building `URLRequest` calls inside the recipe step executor
- Recipe step execution, condition checks, template rendering, SSH step summaries, and LLM transform steps now live in `recipe_runtime_steps.py`, reducing `RecipeRuntime` to runtime composition and compatibility delegates
- RSS group-read aggregation now also lives in `recipe_runtime_rss.py`, leaving `RecipeRuntime.execute_rss_group_read(...)` as a compatibility delegate
- `/stats` pricing refresh now preserves local/custom pricing entries and lets marked manual overrides (`source_name: Manual` or `notes: source=manual`) keep precedence over refreshed provider prices, so ARIA can update provider catalogs without destroying deployment-specific cost settings
- `/stats` pricing refresh now also imports the public LiteLLM GitHub pricing JSON as a short-timeout remote source without depending on the LiteLLM Python package for pricing, expanding automatic model-price coverage while keeping ARIA's bundled seed and manual overrides as safeguards
- LiteLLM's public GitHub pricing JSON is now the primary pricing source: ARIA caches the last good copy in `data/pricing/litellm_model_prices.json`, refreshes it on startup when older than seven days, uses `/stats` refresh as a forced update, and falls back to the cached copy or bundled emergency seed when GitHub is unavailable
- `/stats` now labels the active LiteLLM GitHub pricing source and local cache explicitly, and the top Costs card uses a compact hero/list layout so estimated/logged/average/request metrics no longer stretch the header row
- `/stats` cost metrics now use a stable two-column LED matrix instead of mixed label/value rows, preventing labels such as `Logged USD` from wrapping away from their values in the narrow top-row card
- `/stats` now stacks the long Model Gateway Audit and Recipe Experience Memory diagnostics as full-width rows, avoiding a broken two-card row with an empty third column
- Recipe legacy internals are reduced further: action-planner recipe candidates now live in `action_planner_recipe_candidates.py`, stored recipe manifests use recipe-first helper/cache names, wizard presets use recipe-type names internally, and old `skill_runtime.py` / `custom_skills.py` / `skills_routes.py` modules are explicit compatibility wrappers instead of `sys.modules` aliases
- Recipe Experience Memory now normalizes learned entries with target/action/experience fingerprints, keeps distinct successful actions for the same learned recipe, applies explicit target/capability/intent ranking bonuses during recall, and surfaces recent experience rows on `/stats` for easier self-learning audits
- Monolith cleanup continued along product seams: Pipeline Recipe Experience context/debug formatting, Recipe Runtime status text, and Recipes manifest delete/export actions now live in dedicated helper modules with thin compatibility delegates in the old entry points
- i18n and packaging hygiene now have stronger regression coverage: the strict German code-literal audit is exercised through its CLI, and package-data tests verify that every current i18n, lexicon, template, and static runtime asset is covered by setuptools package data
- Release hygiene now blocks common generated packaging artifacts (`*.egg-info/`, `build/`, `dist/`, `*.whl`) and has a regression test for current release-label/backlog consistency plus required container source assets such as recipe prompts and sample recipe manifests
- `/stats` now includes an admin-only Pricing Overrides panel for adding local model aliases and manual chat/embedding prices directly from the UI; manual prices are marked as overrides, survive LiteLLM refreshes, and can be removed without exposing provider-synced rows to accidental deletion
- Recipe Experience Memory can now be deliberately promoted from `/stats` into the Learned Recipe review store as a context-only candidate; web/search-derived review entries are supported by the same core contract, while non-promotable capabilities no longer show a stored-recipe Promote action in the Learned Recipes UI
- Natural SSH health questions such as `ist mein dns server ok` now use a bounded LLM guardrail-intent classifier before falling back to the configured healthcheck bundle, instead of requiring a new hard-coded phrase or executing a blocked bare `uptime` probe
- Agentic action resolution now has a shared core contract that separates LLM-proposed action drafts from policy/runtime decisions, with SSH and HTTP API debug paths starting to report the same draft-versus-policy boundary
- SSH and HTTP API agentic resolution now share the same action-draft, policy-result, and debug-line helpers, making the first two capability families follow one visible `LLM draft -> policy decision -> runtime` shape
- File operations now have the same generic agentic action-draft shape for SFTP/SMB list/read/write, plus secret-free file target dossiers and dry-run debug output that separates the proposed file action from the `file_access` policy result
- SFTP/SMB file operations now have a bounded LLM resolver that can fill missing operation details from the file target dossier, while already complete file actions stay deterministic and every draft still flows through the normal payload, confirmation, and `file_access` guardrail checks
- Discord, webhook, email, and MQTT outbound messaging now share a bounded agentic message draft and secret-free message target dossier; the LLM resolver only fills missing content/topic fields, while complete drafts stay deterministic and all sends still require the normal side-effect confirmation/guardrail path
- RSS, Google Calendar, IMAP mail read/search, and watched website read/list flows now share a bounded read-only agentic draft plus secret-free read target dossier; the LLM resolver only fills missing selector/query fields and complete read actions remain deterministic
- Agentic policy actions are now canonicalized to `allow`, `ask_user`, or `block` in the shared core, and dry-run debug for SSH, HTTP API, File, Messaging, and Read capabilities now exposes the same draft-versus-policy boundary
- Deterministic helper logic now has an explicit boundary registry for routing hints, normalizers, policies, runtimes, summaries, and compatibility wrappers, with regression coverage that prevents treating deterministic helpers as new product-level intent logic
- Agentic debug lines now mark whether a line represents a draft, policy, or draft-policy boundary, and routed runtime execution can emit a separate `agentic_runtime` debug line before the human-facing execution details
- Old `bounded_planner_poc` / `ssh_status_agentic_poc` naming has been removed from the active bounded-planner path; the legacy candidate-key fallback is kept only for config compatibility
- Agentic free-form regression coverage now verifies that natural file, message, read/mail, and HTTP status prompts can fill bounded drafts while mutating SSH and HTTP requests are still blocked or confirmed by policy rather than executed directly
- The Model Gateway contract test now blocks direct OpenAI/Anthropic SDK usage and synchronous/asynchronous LiteLLM bypasses outside the central `LLMClient` / `EmbeddingClient`
- `UsageMeter` now has a regression test proving known Claude chat models and OpenAI embedding models resolve to non-zero USD costs through the central ARIA pricing fallback
- `/stats` pricing now uses the ARIA bundled pricing seed plus OpenRouter enrichment instead of only OpenAI/Anthropic rows, covering common OpenAI and Anthropic names offline while OpenRouter remains available as live enrichment
- The `/stats` unpriced-model warning is now a compact status strip with a details link, so a missing price can no longer break the top Costs card layout
- `/stats` pricing refresh now shows a visible result message with refreshed chat/embedding model counts, timestamp, and refresh errors directly in the pricing details panel
- `/stats` pricing details now list the exact unpriced model names and token counts, making custom deployment aliases easy to identify and map
- `/stats` pricing refresh now treats ARIA bundled pricing seed as the primary offline source and keeps OpenRouter as a short-timeout optional enrichment, so a slow OpenRouter response no longer makes the refresh feel stuck
- `/stats` pricing refresh now shows an inline "refreshing prices" indicator next to the button while the HTMX request is running
- Pricing no longer imports `litellm` or reads `litellm.model_cost`; the cost layer now uses an explicit ARIA-owned seed plus optional OpenRouter enrichment, while LiteLLM remains only the current runtime adapter for model calls
- Pricing now supports `pricing.model_aliases` for deployment/provider aliases; common embedding aliases such as `embed-small` and `openai/embed-small` map to `openai/text-embedding-3-small`, fixing false unpriced-token warnings for LiteLLM/OpenAI-compatible embedding deployments

### Fixed
- plural/fleet-style target requests such as `check mal ob meine server noch genug festplatten platz haben` no longer let stale Experience/Memory hints force a single previous SSH profile; ARIA now keeps the bounded SSH draft and asks for an explicit target until safe multi-target execution exists
- unified routing now passes the capability draft's connection kind into the live routing chain, so an SSH disk-space draft such as `df -h` can no longer be hijacked by an unrelated RSS/Qdrant routing candidate
- concrete SSH disk-space drafts now suppress conflicting stored-recipe candidates during routed execution, preventing old fleet-health recipes from producing `recipe_manifest_missing` or Discord recipe-error events for a simple `df -h` check
- generic SSH template commands such as `uptime` are no longer treated as the user's real action when the natural request is mutating; the bounded SSH resolver can infer the dangerous command and the policy blocks it instead
- natural SSH disk-space questions such as `check mal ob meine server noch genug festplatten platz haben` now resolve to a bounded `df -h` disk draft and ask for the target when multiple SSH profiles exist, instead of selecting a generic `server` alias or falling into an old fleet-health stored recipe
- very short connection refs or aliases such as `a` / `b` no longer match arbitrary letters inside normal words when extracting explicit connection targets
- SSH health/status requests such as `ist mein dns server ok` no longer keep the stale blocked `uptime` decision after the guardrail healthcheck bundle has replaced it with an allowed command sequence
- SFTP/SMB list requests now treat the share/root path as a valid `.` default instead of asking for a path when the user wants to list folders on a share root
- clear Discord/message requests no longer fall through to stale SMB/file context when no matching messaging connection profile is configured; ARIA now returns the missing-profile message instead of trying to list a bogus SMB path
- `/connections/types` no longer performs live connection probes while rendering the type overview, avoiding slow page loads caused by status checks that belong on `/connections/status`
- connection detail pages opened from `/connections/types` no longer render as an empty page when no profile exists yet; ARIA now opens the create form automatically for empty connection types such as Discord
- the Discord connection page now receives its toggle-section builder through the normal route-helper dependency wiring, fixing the broken `/config/connections/discord?...` render path
- German HTTP API field labels now use `Base-URL` again in connection-admin validation messages

### Upgrade Notes
- Public release `0.1.0-alpha266` publishes Docker tags `fischermanch/aria:0.1.0-alpha.266` and `fischermanch/aria:alpha`.
- Python dependencies and base-image digests are pinned for Docker release builds; Debian `apt` packages still come from normal Debian repositories unless a future snapshot-repo hardening step is added.
- A hard browser refresh is recommended after updating because this release includes UI, CSS, service-worker, and chat-rendering changes.

## [0.1.0-alpha.167] - 2026-04-25

Public release aligned with the internally tested `alpha167` code line.

### Changed
- the main menu now only shows `Updates` when a newer release is actually available; the old permanent entry added noise on installs that were already current
- ARIA now treats the visible release label as one shared product version line again instead of reinforcing a separate public-vs-internal numbering story in the UI and docs

### Upgrade Notes
- this release intentionally brings the public Docker/GitHub line onto the same visible release number as the internal ARIA line
- managed and internal-local update paths can still differ technically, but the product should now report the same release label for the same code line

## [0.1.0-alpha.127] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.126`.

### Changed
- the main user menu now exposes `Updates` as its own destination instead of only hinting availability with the small header lamp; when a newer release exists, the menu entry itself is marked with `Update verfügbar`, so users can see immediately where to go

### Upgrade Notes
- this release is recommended if users already noticed the update lamp but had to guess that the update flow lives under `/updates`
- the managed update-path fixes from `alpha126` remain the base for this release and should now be easier to discover in normal everyday use

## [0.1.0-alpha.126] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.125`.

### Fixed
- managed GUI updates no longer try to run the critical stack `update` / `repair` / `validate` path via in-container `/managed/...` compose calls; the updater now executes those operations through a short-lived helper container that uses the real host stack path, which fixes the recurring config-sync and stale-mount regressions seen on real managed installs like `whity` and `neo`
- the app header now uses the configured persona/agent name again instead of falling back to `settings.ui.title`, so renamed assistants such as `J.O.E.` show up correctly next to the logo

### Upgrade Notes
- this release is recommended immediately for managed installs using `/updates`
- if a previous `alpha125` update left the stack drifted, run `./aria-stack.sh repair` once after upgrading; future managed updates should then stay on the corrected host-path-aware update flow

## [0.1.0-alpha.125] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.124`.

### Fixed
- managed GUI updates now try one automatic `./aria-stack.sh repair` when the post-update `validate` step still fails once; this closes the painful half-updated state where the image changed but config/data mounts still needed a manual repair
- the managed stack helper now treats `qdrant`, `searxng-valkey`, `searxng`, `aria`, and `aria-updater` as one runtime group for `repair`, `restart`, and `update`, so a repair no longer leaves stateful sidecars on stale bind mounts
- the update helper now self-heals stale red `/updates` states: if the stored helper status says `error`, but `./aria-stack.sh validate` is already clean again, the helper resets itself back to `ok` instead of showing an old failure forever

### Upgrade Notes
- this release is recommended immediately for managed installs using `/updates`
- if a previous update left `/updates` red even after `./aria-stack.sh repair`, `alpha125` will clear that stale helper state automatically once the stack validates cleanly
- if a previous managed update recreated `aria` but left `qdrant` or `searxng` on stale mounts, `alpha125` makes future repair/update runs recreate the whole managed runtime group together

## [0.1.0-alpha.124] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.123`.

### Fixed
- managed GUI updates now resolve the real host-side source path behind the updater's `/managed` bind mount before they call `docker run ... /app/docker/setup-compose-stack.sh`; this fixes the false `/managed/.env` lookup on existing managed installs

### Upgrade Notes
- this release supersedes `alpha123` for managed installs using `/updates`
- if a previous GUI update stopped during `Refresh managed stack files`, upgrade to this release once and rerun the managed update

## [0.1.0-alpha.123] - 2026-04-24

Public hotfix release on top of `0.1.0-alpha.122`.

### Fixed
- managed GUI updates no longer abort the whole update run just because the stack-file refresh helper cannot re-open the managed install through `docker run ... /app/docker/setup-compose-stack.sh`; existing managed installs now continue with their current `.env` and `docker-compose.yml` instead of failing early with `Bestehende Env-Datei nicht gefunden: /managed/.env`

### Upgrade Notes
- this release is recommended immediately for managed installs using `/updates`
- if a previous `alpha122` GUI update already pulled the image but stopped during stack refresh, rerun the managed update after upgrading to this hotfix

## [0.1.0-alpha.122] - 2026-04-24

Public roll-up release covering the internally tested `alpha122` to `alpha167` line since the previous public `alpha121` release.

### Added
- ARIA now has a first real personal end-user path:
  - a dedicated `Google Calendar` connection type with secure secret storage, a guided setup flow, and a read-only live test
  - natural calendar prompts such as `was steht heute in meinem kalender?` and `wann ist mein naechster termin?` now route into the shared planner/guardrail execution path
- ARIA now has a first `Notes / Notizen` product path:
  - a dedicated `/notes` surface with folders, board view, editor, delete, move, and Markdown export
  - Markdown files are the source of truth while Qdrant is used as a derived semantic index
  - notes can already be created, searched, and opened from chat and the toolbox
- ARIA now has a first `Watched Websites / Beobachtete Webseiten` connection type:
  - URL-first profile creation for websites without RSS
  - automatic title/description/alias/tag suggestions
  - grouping and connection health checks through the same connection status pipeline
- `/config/operations` now includes helper-backed restart actions for `qdrant` and `searxng`

### Changed
- the routing stack now behaves much more like one product path instead of separate chat/debug worlds:
  - live chat and the routing workbench share the same routing, planner, payload, and guardrail chain for supported connection kinds
  - Qdrant routing indexes rebuild more automatically, so users do not have to babysit the index manually
  - follow-ups, confirmations, and target hints are handled more consistently across chat and admin tooling
- the UI was cleaned up substantially across the domain hubs:
  - `Memories`, `Connections`, and `Skills` no longer repeat redundant `Next steps` teaser blocks above the real hub navigation
  - the overall menu/domain structure is calmer and more product-like
- `Notes` now behave more like a small file explorer:
  - default board-first view without an already open editor
  - direct board/editor switching instead of hidden lower-page editors
  - a standalone surface instead of hanging off the Memory sub-navigation
- the Memory Map now treats Notes as a first-class knowledge branch:
  - per-user `aria_notes_<user>` collections are shown explicitly
  - the graph now includes `Notizen` as a dedicated branch back to `/notes`
- user-facing docs were refreshed for the current product shape:
  - `README.md`
  - product docs
  - wiki drafts
  - help pages for Memory, Notes, Connections, SearXNG, and Qdrant
- the web layer was significantly simplified internally:
  - large pieces of `main.py` and `aria/web/config_routes.py` were moved into clearer route/helper modules
  - this release keeps behavior but reduces monolith pressure and maintenance drift

### Fixed
- the memory setup no longer exposes a normal UI toggle that can silently disable the whole memory backend; saving the Qdrant setup now keeps Memory enabled
- skill toggles no longer disable each other just because the current page only posted one skill group
- natural SSH disk checks such as `check mal die festplatte auf meinen dns server` now normalize to `df -h` instead of trying to execute the whole sentence as a shell command
- `Admin mode off` hints now lead directly to the real admin-mode toggle, and the old users-surface save path no longer falls into `Not Found`
- Notes editor overflow and width regressions in Safari/Firefox were fixed, and the board/editor flow no longer hides created folders or forces awkward scrolling
- watched website connection flows now jump directly into create/edit mode instead of landing at the top of a longer page
- connection test messaging for webhook, HTTP API, SMTP, and IMAP is clearer around auth, permission, TLS/SSL, timeout, and reachability failures

### Security
- controlled restart actions for `qdrant` and `searxng` now ask for explicit browser confirmation before execution
- guarded outbound and connection-backed actions now keep stronger `allow / ask_user / block` behavior across the unified planner path

### Known Limitations
- Google Calendar is intentionally read-only in this release
- Google Calendar setup is guided in-product, but still uses a manual Google OAuth / OAuth Playground flow
- refresh tokens from Google test-mode projects can still expire after seven days unless the Google-side app moves beyond testing

### Upgrade Notes
- a hard browser reload is recommended after upgrading because this release includes broader UI, CSS, and navigation changes
- if you use managed installs, `/updates` and `./aria-stack.sh update` remain the supported update paths
- if you use Google Calendar, finish the in-product setup flow once after upgrading; no automatic account migration is needed
- Notes use Markdown as the source of truth and Qdrant only as the derived search index, so semantic note search still expects a working Qdrant-backed Memory setup

## [0.1.0-alpha.121] - 2026-04-16

Public roll-up release covering the already internally tested `alpha111` to `alpha121` line since the previous public `alpha110` release.

### Added
- `/config/routing` now exposes a Qdrant-backed routing index admin/debug surface with status, rebuild, testbench output, and live-routing controls for bounded candidate routing
- SSH and SFTP profiles now support a `Service URL`; ARIA can use the linked page plus the active UI language to draft routing-friendly titles, descriptions, aliases, and tags
- SSH profile creation can optionally create a matching SFTP profile with the same connection basics in one step
- `Memory Map` now surfaces routing/system collections in both the textual overview and the graph, so routing data is visible without mixing it into semantic user memory

### Changed
- runtime reloads now build a fresh runtime bundle and swap it atomically under a lock, which reduces stale-state drift after config saves and profile changes
- managed update validation now compares `config`, `prompts`, and `data` host/container views and surfaces the real failing check in the update UI instead of only a generic `exit code 1`
- connection metadata helpers now align generated routing hints more closely with the active UI language, which improves German/English routing coverage for SSH, SFTP, and RSS profiles
- `/config/routing` now includes the live Qdrant-routing controls directly in the UI, including threshold, candidate limit, and low-confidence fallback behavior
- the routing stack now keeps deterministic exact-name and alias matches first, then optionally consults the bounded Qdrant candidate set instead of jumping straight into generic chat behavior
- connection pages make the primary create action more prominent and support richer routing-oriented metadata via titles, descriptions, aliases, tags, and service context
- safety-sensitive SSH custom-command rendering now quotes user query placeholders more defensively, and guardrail matching uses stricter token/boundary behavior for simple deny terms

### Fixed
- managed update and update-button regressions from the internal `alpha111` to `alpha121` line are rolled up into this public release, including stronger mount validation for managed installs and clearer recovery guidance via `./aria-stack.sh repair`
- natural SSH questions such as `Wie lange laeuft mein DNS Server schon?` and `Wie lange ist mein DNS Server schon online?` now route back to `ssh_command` / `uptime` instead of falling into generic chat or SFTP file reads
- natural uptime / health / runtime prompts now win over accidental SFTP `file_read` matches for server-status style questions
- first-contact SSH `known hosts` warnings are filtered from the user-visible stderr output, while real SSH errors stay visible
- routing collections on `/memories/map` are no longer easy to miss; they now appear as a dedicated system branch in the graph
- config saves keep session-cookie lifetime and related runtime settings consistent after reloads instead of quietly continuing with stale route dependencies
- provider preset confusion between chat LLM and embedding configuration pages is resolved; the LLM page again shows chat-model presets and the embeddings page embedding-specific presets
- config save redirects and the logical back-navigation flow on config and skills pages no longer strand users on blank POST result pages or same-page history loops
- explicit Discord sends resolve through the connection routing path again instead of slipping into generic chat or memory behavior

### Upgrade Notes
- managed installs can continue to use `/updates` or `./aria-stack.sh update`; if validation reports a mount mismatch, `./aria-stack.sh repair` remains the supported recovery path
- the internal TAR/NAS update flow stays a private test path; public installs should continue to use `aria-setup` or `docker-compose.public.yml`

## [0.1.0-alpha.110] - 2026-04-12

### Added
- managed stacks now expose `./aria-stack.sh repair` as an official recovery path; it regenerates the managed stack files from the configured ARIA image and recreates the runtime services before running the normal validation again

### Changed
- managed GUI updates now refresh stack files from the target ARIA image via `docker run ... /app/docker/setup-compose-stack.sh` instead of relying on the currently running updater container's bundled script, which reduces stale-helper drift during upgrades
- `./aria-stack.sh update` and `update-all` now refresh the managed stack files from the configured ARIA image before recreating services, so manual host-side updates follow the same safer recovery-aware path as the new repair flow

### Fixed
- managed runtime validation now compares the host `storage/aria-config/config.yaml` with the live container view of `/app/config/config.yaml` and fails loudly when the container does not actually see the same config state
- managed update failures now point operators directly at `./aria-stack.sh repair` when a config-mount mismatch is detected, instead of silently reporting a healthy restart while profiles appear to be missing in the UI

## [0.1.0-alpha.108] - 2026-04-11

### Fixed
- `/updates` now also performs the post-update re-login check server-side, so even an update that was started from an older browser tab or an older UI build cannot fall back into a stale pre-update session after ARIA comes back
- managed GUI updates now clear the current instance auth boundary more reliably in multi-instance setups on the same domain, reducing the chance that `white`, `neo`, or similar stacks reopen with the wrong session after pressing the update button

## [0.1.0-alpha.107] - 2026-04-11

### Fixed
- the GUI update flow now forces a clean per-instance re-login after a managed restart instead of silently reusing the old browser session, which hardens multi-instance setups on the same domain against stale-session mixups after pressing the update button
- `/updates` now redirects through a dedicated relogin path that clears the current instance cookies before returning to `/login`, so `white`, `neo`, and other managed stacks can finish updates on a clean auth boundary

## [0.1.0-alpha.106] - 2026-04-11

### Fixed
- `/config/llm` and `/config/embeddings` no longer show the wrong provider preset list; the LLM page now uses chat-model presets again and the embeddings page now uses embedding-specific presets again

## [0.1.0-alpha.105] - 2026-04-11

### Fixed
- fresh managed installs via `aria-setup` now pull the referenced Docker images before the first `docker compose up`, so a host with an older cached `fischermanch/aria:alpha` image can no longer silently come up on the wrong ARIA version after a supposedly clean reinstall

## [0.1.0-alpha.104] - 2026-04-11

### Fixed
- config save flows that were switched to the new logical `return_to` handling no longer break on pages such as `/config/appearance/save`; affected config forms redirect cleanly again instead of ending on a blank POST result page
- the shared config redirect helper now accepts an explicit `return_to` target consistently, aligning it with the skills redirect behavior and preventing silent regressions across config forms
## [0.1.0-alpha.103] - 2026-04-11

### Fixed
- the embeddings configuration page now uses embedding-specific provider presets instead of reusing the chat-LLM preset list, so fresh installs no longer suggest irrelevant chat providers such as Anthropic on the embeddings screen
- embedding preset defaults are now better aligned with proxy-based setups like LiteLLM, reducing the chance that a fresh profile setup quietly drifts toward a mismatched default embedding model

## [0.1.0-alpha.102] - 2026-04-11

### Changed
- managed installs and the managed compose template no longer inject implicit Ollama LLM or embedding defaults into the runtime environment; fresh installs now leave these runtime overrides empty unless the operator explicitly sets them
- `.env.example`, setup docs, and README environment-override notes now make it explicit that runtime env overrides are optional and should stay unset when ARIA manages saved provider profiles itself

### Fixed
- active saved LLM and embedding profiles now win over stale container environment overrides, so old managed `.env` files can no longer silently force the runtime back to `host.docker.internal` and Ollama defaults after a profile was loaded in the UI
- blank environment values no longer erase valid LLM or embedding runtime settings during config load
- managed stack reinstalls via `aria-setup` no longer materialize misleading default LLM / embedding endpoints that make profile-based setups look broken immediately after startup

## [0.1.0-alpha.101] - 2026-04-11

### Added
- custom skills support conditional steps now, so later actions can be skipped based on earlier outputs; the included Linux fleet healthcheck sample uses this to send a Discord alert only when the LLM marks a run as actionable
- `/config/llm` and `/config/embeddings` now show the active saved profile more clearly, include the effective runtime values, and expose an explicit live test action for the currently loaded profile

### Changed
- the routing foundation is now more data-driven: default routing lexica and capability/status keywords moved out of hard-coded German-heavy lists and into the shared routing lexicon layer, with the pipeline passing language context through more consistently
- chat admin/toolbox command catalog logic and pending admin action helpers were pulled out of `main.py` into dedicated web modules, reducing the size and coupling of the main application module
- `/stats` now collapses every connection family into a summary tile once more than three profiles exist and uses cached health for large groups instead of probing every profile live during first render

### Fixed
- capability detail output now follows the active UI language more consistently, including file-read and other connection-backed actions that previously still emitted German detail lines in English mode
- explicit Discord sends resolve through the connection capability path again instead of falling back into generic chat/memory behavior
- config and skills pages now use a logical app-level back target instead of raw browser history, so saving/reloading forms no longer makes the back button bounce to the same page state
- `/favicon.ico` is served through a dedicated app route again, which restores the classic favicon path for browsers that do not reliably pick up the static PNG reference alone

## [0.1.0-alpha.89] - 2026-04-10

### Changed
- managed compose installs now run a deeper post-start validation through `./aria-stack.sh validate`, so fresh installs, upgrades, and GUI-triggered managed updates confirm both ARIA health and the `aria-updater` sidecar before they report success
- managed update helpers now validate the refreshed stack after the recreate step, instead of stopping at a plain web healthcheck

### Fixed
- ARIA now compares local Qdrant storage against the live Qdrant API and surfaces a clear warning when collections exist on disk but are missing from the API; that makes partial or unloaded memory stores much easier to diagnose from `/memories/config` and `/stats`
- `aria-setup migrate` now normalizes ownership on copied Qdrant storage, which reduces the risk that migrated collections stay on disk but are not loaded by the new managed Qdrant service

## [0.1.0-alpha.88] - 2026-04-10

### Fixed
- auth sessions are now signed with the current instance scope, so a valid login cookie from one ARIA instance can no longer be accepted by another instance on the same host just because both live under the same domain with different ports
- cookie scoping prefers the actual request host and port over a potentially stale configured `ARIA_PUBLIC_URL`, which makes multi-instance setups more resilient after updates, migrations, or reused stack definitions
- managed `./aria-stack.sh update` and `restart` flows now refresh `aria-updater` together with `aria`, so the GUI update helper no longer lags one release behind the main ARIA container on managed installs

## [0.1.0-alpha.87] - 2026-04-09

### Fixed
- auth and session cookies now stay isolated more reliably across multiple ARIA instances on the same host because legacy shared cookies are no longer reused for login/session state after scoped cookies are active
- managed compose installs now write an explicit `ARIA_COOKIE_NAMESPACE`, so browser-side state remains instance-local even if multiple ARIAs share one hostname

## [0.1.0-alpha.86] - 2026-04-09

### Fixed
- `aria-setup` respects explicitly passed install values better during interactive runs instead of prompting for the same `--stack-name`, `--install-dir`, `--http-port`, or `--public-url` again
- the managed install health check now verifies ARIA locally through `127.0.0.1:<ARIA_HTTP_PORT>/health` instead of depending on the public/browser URL during first start
- first-start health checks for managed installs now retry until ARIA is really ready, instead of failing too early on a short startup race directly after `docker compose up -d`
- the public `aria-setup` download flow works again end to end when it has to fetch its helper from GitHub on demand

## [0.1.0-alpha.85] - 2026-04-09

### Added
- die Chat-Toolbox kennt jetzt auch Websuche, Stats, Aktivitäten, Config-Backups und kontrollierte Updates; Admins koennen damit neue Systemfunktionen direkt aus dem Chat starten oder als Link/Statusauskunft anstossen, statt nur ueber die jeweiligen UI-Seiten zu gehen
- `/updates` zeigt jetzt zusaetzlich eine konkrete sichere Update-Sequenz fuer interne `aria-pull`-Setups, Docker Compose und Portainer, damit der Update-Weg direkt in der GUI sichtbar ist
- Managed-Compose-Installationen bringen jetzt einen separaten `aria-updater`-Helper mit; Admins koennen dadurch auf `/updates` ein kontrolliertes GUI-Update mit Status und Log-Auszug anstossen, statt fuer jeden normalen Release wieder auf den Host zu wechseln
- der interne lokale `aria-pull`-/Portainer-Stack kann denselben `/updates`-Button jetzt ebenfalls ueber einen eigenen `aria-updater`-Sidecar nutzen; damit bleibt der gewohnte TAR-/NAS-Update-Weg erhalten, wird fuer Admins aber direkt aus ARIA heraus startbar
- neuer Host-Helper `docker/aria-host-update.sh` erkennt Compose-basierte ARIA-Stacks auf einem Host und aktualisiert gezielt nur den `aria`-Service eines gewaelten Projekts; damit gibt es fuer Multi-Setup-/Portainer-Hosts einen sichereren Update-Weg ausserhalb des Containers
- fuer Host-Updates gibt es jetzt zusaetzlich eine optionale Vorlage `docker/aria-host-update.env.example`, damit Portainer-Zugangsdaten spaeter sauber aus einem dedizierten Host-Update-Kontext oder aus einer kuenftigen UI/DB-Schiene in denselben Helper fliessen koennen
- neues Setup-Script `docker/setup-compose-stack.sh` erstellt jetzt einen kontrollierten ARIA-Compose-Stack in einem eigenen Verzeichnis inklusive `.env`, bind-mount-basiertem `storage/` und lokalem `aria-stack.sh` fuer Start/Status/Updates
- neues Top-Level-Script `aria-setup` dient jetzt als benutzerfreundlicher Ein-Befehl-Einstieg fuer Docker-Installationen, fragt nur fehlende Werte interaktiv ab und kann den niedrigeren Compose-Setup-Helper bei Bedarf auch direkt von GitHub nachladen
- `aria-setup upgrade` aktualisiert jetzt bestehende verwaltete Compose-Installationen auf neue Stack-Layouts, behaelt vorhandene `.env`-Werte und Secrets bei und ergaenzt fehlende Dienste wie `searxng` ohne Neuaufbau des kompletten Hosts
- `aria-setup` erkennt jetzt bestehende verwaltete ARIA-Installationen automatisch und schaltet bei genau einem passenden Fund selbststaendig vom Neuinstallations- in den Upgrade-Pfad um; bei mehreren Funden wird interaktiv ausgewaehlt oder im non-interactive Modus sauber abgebrochen
- `/config/backup` kann jetzt die komplette ARIA-Konfiguration als einzelne JSON-Datei exportieren und spaeter wieder importieren; enthalten sind `config.yaml`, Secure-Store-Secrets und Benutzer, Prompt-Dateien, der Error-Interpreter sowie Custom-Skill-Manifeste
- `/config/security` zeigt jetzt ein direkt importierbares Guardrail-Starter-Pack aus `samples/security`, damit neue Installationen schneller mit wiederverwendbaren SSH-, Datei-, HTTP- und MQTT-Guardrails starten koennen
- die mitgelieferten Skill-Samples wurden um neue Vorlagen fuer Service-Status via SSH, Memory-Pressure via SSH und eine kuratierte RSS-Security-Watchlist erweitert; sie tauchen wie die bestehenden Samples direkt im Skills-UI auf

### Changed
- die Docker-/Compose- und lokalen Stack-Samples schreiben die benoetigte SearXNG-Konfiguration jetzt direkt beim Containerstart nach `/etc/searxng/settings.yml`; damit bleibt der Setup-Weg ohne manuelles Host-File robust, auch wenn Compose-/Portainer-Umgebungen Docker-`configs` nicht sauber bis in den Container durchreichen
- `docker-compose.managed.yml` und `docker/setup-compose-stack.sh` erzeugen jetzt zusaetzlich den internen `aria-updater`-Dienst, hinterlegen dafuer ein eigenes Update-Token in `.env` und geben Managed-Stacks damit einen standardisierten GUI-faehigen Update-Endpunkt
- die lokalen Portainer-/`aria-pull`-Stack-Dateien bringen jetzt ebenfalls einen `aria-updater`-Dienst samt eigenem Healthcheck mit; der ARIA-Container und der Helper teilen sich damit denselben kontrollierten Update-Button, ohne dass der bestehende Qdrant-/Volume-Pfad angeruehrt wird
- die lokalen Helper-Skripte fuer `aria-pull`/Build-Export muessen keine separate SearXNG-Settings-Datei mehr neben das TAR kopieren, weil die Stack-Dateien die Konfiguration jetzt selbst mitbringen
- `docker/export-local-build.sh` und `docker/pull-from-dev.sh` liefern jetzt sowohl den neuen Host-Update-Helper als auch `aria-setup` zusammen mit den bestehenden lokalen Update-Artefakten aus, damit Zielhosts den kompletten verwalteten Setup-/Update-Weg ohne zusaetzliches Nachziehen direkt nutzen koennen
- der Host-Update-Helper kann Registry-/Public-Portainer-Stacks jetzt optional direkt ueber die Portainer-API aktualisieren, wenn `PORTAINER_URL` und `PORTAINER_API_KEY` gesetzt sind; damit muessen Portainer-Stacks nicht mehr ueber wegkopierte YAML-Dateien gepflegt werden
- `docker-compose.managed.yml` bildet jetzt zusammen mit `aria-setup` den neuen kontrollierten Standard fuer Compose-Installationen mit sichtbaren Bind-Mounts statt anonymen Volumes; Portainer bleibt moeglich, ist aber nicht mehr der bevorzugte Setup-Weg
- die GitHub-/Docker-Dokumentation erklaert den Install- und Update-Prozess jetzt klarer in Englisch und trennt sauber zwischen `aria-setup`, manuellem Compose, Portainer und internem `aria-pull`
- GitHub-README, Setup-Doku und Docker-Hub-Overview fokussieren den Oeffentlichkeitsweg jetzt auf `aria-setup` und manuelles Docker Compose; Portainer bleibt nur noch als Legacy-Hinweis im Hintergrund statt als gleichberechtigter Hauptpfad
- `/updates` startet den GUI-Update-Lauf jetzt ohne harten Seitenwechsel direkt in-place, zeigt den Running-State prominenter als eigene Live-Karte und verbindet sich nach einem kurzen ARIA-Recreate ueber Helper-/Health-Polling automatisch wieder
- die Chat-/Config-Schiene liest Custom-Skill-Manifeste und rohe `config.yaml`-Daten jetzt ueber mtime-basierte In-Memory-Caches, statt dieselben Dateien pro Seitenaufruf immer wieder komplett neu zu parsen

### Fixed
- Chat-Antworten koennen jetzt auch sichere interne Markdown-Links wie `/updates` oder `/config/backup/export` rendern; dadurch funktionieren neue Chat-Hilfen fuer Backup, Update, Stats und Aktivitäten als echte klickbare Aktionen statt nur als Text
- auf `/config` und `/config/connections/searxng` zeigt ARIA jetzt klar, wenn der SearXNG-Stackdienst fehlt oder nur mit Warnstatus antwortet, statt die Websearch-Connection kommentarlos wie einen normal verfuegbaren Dienst wirken zu lassen
- ein `HTTP 403` vom internen SearXNG-Stack wird nicht mehr faelschlich als "Stackdienst nicht erreichbar" dargestellt; ARIA markiert den Dienst jetzt als erreichbar mit Warnstatus und erklaert, dass meist `format=json` oder eine Limiter-/Zugriffsregel die JSON-Probe blockiert
- der interne GUI-Update-Pfad fuer `aria-pull`-Setups prueft nach dem Recreate jetzt auch ohne `curl` zuverlaessig per Container-Python auf `/health`, statt den Lauf nur mit einem uebersprungenen Host-Healthcheck enden zu lassen
- die lokalen Update-Helfer (`update-local-aria.sh`, `pull-from-dev.sh`, `aria-host-update.sh`, `export-local-build.sh`) verwenden jetzt portable TAR-Auswahl-Logik statt GNU-awk-spezifischer `match(..., ..., array)`-Muster; dadurch bricht der GUI-Update-Flow in schlankeren Runtime-Umgebungen nicht mehr mit `awk`-Syntaxfehlern ab
- der `/updates`-Button kann den Update-Helper jetzt auch per AJAX anstossen und faellt fuer Admins bei kurzen Container-Restarts nicht mehr so leicht auf eine leere Browser-Fehlerseite zurueck
- der neue Raw-Config-Cache liefert isolierte Kopien zurueck und aktualisiert sich beim Schreiben selbst, damit Config-Seiten weniger YAML parsen muessen, ohne veraltete In-Memory-Mutationen zu riskieren
- der neue Konfig-Import versucht bei Fehlern automatisch auf den vorherigen Snapshot zurueckzugehen, statt die Instanz in einem halb importierten Zustand stehen zu lassen
- die Backup-Seite erklaert jetzt ausdruecklich, dass Connection-Profile und Connection-Secrets mitgesichert werden, lokale SSH-Key-Dateien unter `data/ssh_keys` aber bewusst ausserhalb des Exports bleiben

## [0.1.0-alpha.69] - 2026-04-08

### Added
- pre-alpha Websuche ueber self-hosted `SearXNG` ist lokal vorbereitet: eigener Connection-Typ, eigener Chat-Intent und Quellenanzeige in den Chat-Details
- die Compose-/Portainer-Stacks koennen jetzt zusaetzlich einen separaten `SearXNG`- und `Valkey`-Dienst mitfuehren, inklusive automatisch aktivierter JSON-API fuer ARIA
- `SearXNG` taucht als eigene Connection-Familie in Config, Status und Connection-Hub auf

### Changed
- `Memory`/RAG-Quellen und Web-Quellen nutzen jetzt dieselbe `detail_lines`-Schiene, damit spaetere Recherche- und Websearch-Pfade dieselbe Quellenanzeige im Chat verwenden koennen
- die SearXNG-Stacks nutzen jetzt eine statische `searxng.settings.yml` statt eines Shell-Bootstrap-Blocks im Compose/Portainer-Stack; `secret_key` und Valkey-URL kommen ueber normale Container-Umgebungsvariablen
- SearXNG-Profile in ARIA fragen die Stack-URL nicht mehr pro Verbindung ab; ARIA nutzt dafuer standardmaessig `http://searxng:8080` aus dem Stack bzw. einen zentralen Override und laesst pro Profil nur noch Suchverhalten und Routing-Metadaten konfigurieren
- die SearXNG-Config-Seite ist jetzt schlanker: Kategorien und Engines werden per Checkboxen gepflegt, dazu Sprache, SafeSearch, Zeitbereich, Trefferzahl sowie Name, Aliase und Tags fuer Routing wie `youtube` fuer Videos oder `startpage` fuer Buecher
- der globale Restart-/Health-Poll im Frontend laeuft fuer eingeloggte Seiten jetzt deutlich ruhiger ueber einen getakteten Timeout-Loop statt alle 3 Sekunden per `setInterval`; beim Zurueckkehren in einen sichtbaren Tab wird dafuer einmal zeitnah nachgeprueft
- Connection-Seiten zeigen bestehende Health-/Test-Resultate jetzt standardmaessig aus dem Cache statt beim bloessen Oeffnen sofort neue Live-Probes gegen SSH, SFTP, Discord, HTTP, SearXNG oder MQTT zu fahren; fuer frische Live-Checks bleiben die vorhandenen Test-Buttons zustandig
- der Public-Docker-Weg ist jetzt auf einen konsistenten SearXNG-Stack gezogen: `docker-compose.public.yml`, `docker/portainer-stack.public.yml`, `.env.example` und die Quick-Start-Doku zeigen denselben Compose-/Portainer-Schnitt fuer ARIA + Qdrant + SearXNG + Valkey

### Fixed
- explizite Websuche mischt keinen Auto-Memory-Recall mehr in die Quellen; Web-Details bleiben dadurch bei Anfragen wie `recherchiere im web ...` sauber auf Web-Treffer fokussiert
- SearXNG-Connection-Tests und Websuche geben bei `HTTP 429 Too Many Requests` jetzt einen klaren Hinweis auf den internen Stack-Fix mit `SEARXNG_LIMITER=false`, statt nur den rohen Fehler weiterzureichen
- der interne `aria-pull`-/`update-local-aria`-Flow ueberfaehrt den laufenden Qdrant-Key nicht mehr still mit einem veralteten Wert aus `aria-stack.env`; bei Abweichungen nutzt ARIA fuer den reinen Service-Recreate jetzt den aktiven Live-Key des laufenden Stacks und vermeidet dadurch `HTTP 401 Unauthorized` gegen Qdrant nach Key-Rotationen im Portainer-Stack
- Websuche uebergibt erkannte Trefferdaten jetzt sichtbarer in den Chat-Kontext: Treffer mit publiziertem Datum zeigen ihr Datum in den Details, und bei klaren Recency-/Release-Anfragen werden datierte Ergebnisse fuer die Antwortvorbereitung staerker nach oben sortiert
- explizite Formulierungen wie `suche im internet ...` oder `recherchiere im internet ...` werden jetzt sauber als Websuche erkannt und nicht mehr von der Feed-/RSS-Heuristik als `feed_read` uebernommen
- interne SearXNG-Probes und die eigentliche Websuche senden fuer Stack-Ziele jetzt zusaetzlich lokale Proxy-/IP-Header mit; das macht den internen JSON-API-Pfad robuster gegen Bot-Detection/Proxy-Pruefungen, solange der Dienst ueber `http://searxng:8080` im Stack angesprochen wird
- die Websuche filtert generische Treffer ohne sinnvollen Query-Bezug jetzt haerter weg und priorisiert thematisch passende Ergebnisse vor bloessen `news`-/SEO-Treffern; dadurch rutschen irrelevante Quellen wie fachfremde Sammelseiten bei Produkt-News deutlich seltener in die Antwort

### Security

### Known Limitations
- Websuche ist bewusst noch ein pre-alpha Block: ARIA nutzt die Top-Treffer aus SearXNG, aber noch kein Full-Page-Fetching oder Deep-Research-Crawling

### Upgrade Notes
- fuer interne ARIA-Stacks wird SearXNG jetzt standardmaessig ohne API-Limiter betrieben (`SEARXNG_LIMITER=false`), weil ARIA sonst schnell in `HTTP 429 Too Many Requests` fuer die JSON-API laufen kann
- fuer bestehende Portainer-Stacks aus der Zeit vor `alpha69` gilt: vorhandene Volume- und Netzwerk-Namen weiterverwenden und nur den neuen `searxng`-/`searxng-valkey`-Teil als Delta ergaenzen; den frischen Public-Sample nicht blind ueber funktionierende `aria2_*`-Volumes legen

## [0.1.0-alpha.64] - 2026-04-07
### Added
- `aria --version` und `aria version-check` stehen jetzt als kleine CLI-Schnellchecks fuer installierte Version und oeffentlichen Release-Status bereit
- an zentralen Stellen wie LLM, Embeddings, Memory und RSS gibt es jetzt kurze Kontext-Hinweise mit Direktlink zur passenden Help-Seite
- neue Sample-Skills erweitern die mitgelieferte Sammlung um RSS-Headlines fuer Chat, SSH-Disk-Usage und eine SFTP-Config-Vorschau

### Changed
- LLM- und Embedding-Nutzung laeuft jetzt ueber eine zentrale Metering-Schicht statt nur ueber den Chat-/Pipeline-Pfad; damit koennen kuenftige Modellfunktionen konsistent ueber dieselbe Kosten- und Token-Erfassung laufen
- direkte Hilfs- und Admin-Aufrufe wie RSS-Metadaten, RSS-Gruppierung, Runtime-Diagnostics, Skill-Keyword-Generierung, RAG-Ingest und Memory-Embeddings werden jetzt ebenfalls ueber denselben Token-/Kosten-Zaehler erfasst
- Pipeline-/Chat-Logs aggregieren jetzt alle innerhalb eines Runs angefallenen LLM- und Embedding-Aufrufe zentral, statt nur den letzten Haupt-LLM-Call und separat gemeldete Teilmengen zu beruecksichtigen
- statische Assets wie CSS, Logo und htmx werden jetzt pro Release mit einer Versionskennung ausgeliefert, damit Browser nach UI- und CSS-Updates weniger oft an alten Cache-Dateien haengen bleiben
- `/stats` zeigt fuer den Release-Block jetzt auch die passenden CLI-Kommandos und fuehrt Modellnutzung zusaetzlich nach Quellen wie `chat`, `rss_metadata` oder `rag_ingest` auf
- `/stats` zeigt die Quellen-Aufschluesselung fuer Requests, Tokens und Kosten jetzt zusaetzlich als eigene ausklappbare Kachel `Kosten Details`, statt die Source-Daten nur in tieferen Detailbloecken zu verstecken
- `Preise aktualisieren` in `/stats` refresht den Pricing-Block jetzt per HTMX direkt an Ort und Stelle, statt die ganze Seite neu zu laden und Scroll-/Details-Zustand zu verlieren
- auf der RSS-Seite aktivieren `Kategorien mit LLM aktualisieren`, `Jetzt pingen` und `Check mit LLM` jetzt sichtbar den globalen Busy-Zustand, damit das drehende Logo bei laengeren Aktionen klar zeigt, dass ARIA noch arbeitet
- Klicks auf Collection-Kacheln und Collection-Nodes in der `Memory Map` fuehren jetzt direkt in den passenden Collection-Inhalt statt in eine unklare `all`-Sicht; bei aktivem Collection-Filter oeffnet `Memory` die betroffenen Gruppen ausserdem automatisch
- Dokument-Stores verhalten sich in `Memory` jetzt hierarchisch: ein Klick auf eine Dokument-Collection zeigt zuerst die enthaltenen Dokumente, und erst ein Klick auf ein Dokument oeffnet die zugehoerigen Chunks
- Dokument-Recall priorisiert bei klaren Dokument-Hinweisen jetzt die passendsten Guide-Treffer deutlich enger, damit Fragen zu einem hochgeladenen Manual nicht mehr so leicht mit Chunks aus anderen Dokumenten vermischt werden
- ein Wechsel von Embedding-Modell oder API Base in `/config/embeddings` verlangt bei vorhandenem Memory jetzt eine explizite Bestaetigung und verweist direkt auf den JSON-Export, damit bestehendes Memory/RAG nicht versehentlich in einen unzuverlaessigen Zustand kippt
- Memory- und Dokument-Payloads tragen jetzt einen Embedding-Fingerprint; Recall, Suche und Dokument-Guides mischen dadurch keine alten und neuen Embedding-Generationen mehr still miteinander
- Session-Komprimierung baut jetzt echte Wochen- und Monats-Rollups mit eigener Metadatenstruktur statt nur unsichtbarem generischem Kontext-Wissen; damit wird der Weg fuer spaetere Graph-/Map-Beziehungen klarer
- die `Memory Map` zeigt jetzt zusaetzlich einen einfachen read-only Graphen fuer Typen, Collections, Dokumente und Rollups, damit gespeichertes Memory schneller visuell erfassbar wird

### Fixed
- auf `/config/connections/rss` ist der Ruecksprung zur RSS-Uebersicht im Intro jetzt ein echter Button statt nur ein unauffaelliger Link
- `/updates` zeigt jetzt unterhalb der aktuellen Release Notes auch die fuenf vorherigen Versionen als einklappbare Release-Historie mit ihren jeweiligen Release Notes
- die `Memory Map` gruppiert importierte Dokumente jetzt pro Dokument-Collection in einklappbaren Kacheln, statt alle Dokumente in einem langen Block zu mischen
- `Dokumente im Speicher` startet in der `Memory Map` jetzt standardmaessig eingeklappt, und einzelne Dokumentkarten verlinken direkt auf ihre Chunk-Ansicht
- die alte zweite Bubble-/Kachel-Wiederholung unter `Collections im Speicher` ist aus der `Memory Map` entfernt, damit Collections nicht doppelt und verwirrend erscheinen
- auf `/memories/map` gibt es jetzt zusaetzlich klickbare Collection-Kacheln fuer die vorhandenen Qdrant-Collections; ein Klick oeffnet die normale Memory-Ansicht direkt mit aktivem Collection-Filter, sodass die Eintraege dieser Collection gezielt durchgesehen, exportiert oder gepflegt werden koennen
- Buttons auf Memory-/Config-Seiten laufen auf schmalen Mobile-Viewports nicht mehr pauschal ueber die ganze Breite und sind dadurch wieder klarer als Buttons erkennbar
- auf der RSS-Verbindungsseite verwenden die Aktionsbuttons `Jetzt pingen` und `Check mit LLM` im Matrix-Theme jetzt denselben dunklen Button-Text wie die restlichen Buttons der Seite, statt schlecht lesbarer heller Schrift
- die RSS-Verbindungsseite zeigt nach `Jetzt pingen` jetzt wieder echte Feed-Artikel bzw. Headlines aus dem Feed an, statt nur den Profilnamen bzw. eine generische Erfolgsmeldung
- auf `/config/connections/rss` ist `Kategorien mit LLM aktualisieren` jetzt ebenfalls ein echter Button statt nur ein Link
- gecachte RSS-Gruppen uebernehmen beim Laden jetzt wieder die aktuellen Anzeigenamen aus den Live-Statusdaten, statt alte `ref`-basierte Profilnamen weiter anzuzeigen, wenn sich nur der Display-Name geaendert hat
- LLM-Kosten in `/stats` und den Token-Logs untererfassen jetzt nicht mehr still bestimmte Nebenpfade; auch nicht-interaktive Modellaufrufe ausserhalb des normalen Chat-Flows laufen jetzt durch denselben Metering- und Kostenpfad
- `/stats`, Token-Log-Auswertung und Log-Pruning brechen bei einem unlesbaren oder root-owned Token-Log nicht mehr hart weg, sondern fallen fail-safe auf leere bzw. unveraenderte Log-Ausgaben zurueck
- Login- und Update-Seiten geben bei neuen Releases jetzt klarere Hinweise fuer harte Browser-Reloads, falls nach UI/CSS-Aenderungen noch alte Assets sichtbar bleiben
- bestehendes Memory bleibt bei einem spaeteren Embedding-Wechsel besser abgesichert, weil alte ungetaggte Legacy-Eintraege nur so lange kompatibel bleiben, wie der konfigurierte Memory-Fingerprint nicht auf eine neue Embedding-Generation umgestellt wurde
- `Memory Map` zeigt Session-Rollups jetzt als eigene Wochen-/Monats-Sicht mit Zeitraum und Quellenanzahl, statt verdichteten Kontext nur indirekt ueber die Knowledge-Collection versteckt zu halten

### Security

### Known Limitations

### Upgrade Notes

## [0.1.0-alpha.54] - 2026-04-06

### Added
- `/help` ist jetzt ein echter lokaler Docs-Hub mit Karten, Navigation und Markdown-Rendering auf Basis derselben Quelldateien wie `docs/wiki/` und `docs/help/`
- fuer die Help-/Wiki-Inhalte gibt es jetzt mehrsprachige Seitenvarianten (`*.de.md` / `*.en.md`), damit lokale Hilfe und GitHub-Wiki dieselben Inhalte sauber in der gewaehlten Sprache ausspielen koennen
- zwei neue Spass-Themes stehen in der Appearance-Auswahl bereit: `Nyan Cat` und `Puke Unicorn`

### Changed
- der lokale Help-Hub waehlt Markdown-Dateien jetzt sprachabhaengig aus (`.de.md` / `.en.md`), damit `/help` nicht mehr aus gemischten deutschen und englischen Seiten besteht
- die Preisaufloesung fuer LLM-Kosten ist toleranter: gaengige Claude-Sonnet-Aliase wie `claude-sonnet`, `claude-3-5-sonnet-latest` oder `anthropic/claude-3-5-sonnet-latest` werden grosszuegiger auf bekannte Preis-Eintraege aufgeloest
- die Startseite unter `/config` gruppiert grosse Bereiche wie `Tune Intelligence`, `Fine-Tune Memory`, `Personality & Style`, `Connections` und `Workbench` jetzt in einklappbaren Boxen, damit die Seite bei wachsendem Umfang ruhiger und schneller scannbar bleibt
- `Dokumente importieren` und `Eigene Memory erfassen` sind auf `/memories` jetzt ebenfalls einklappbar, damit die Seite ruhiger bleibt wenn der Fokus auf der bestehenden Memory-Liste liegt

### Fixed
- wichtige Config-Seiten wie `/config/llm`, `/config/embeddings`, `/config/routing`, `/config/skill-routing` und `/config/prompts` bleiben auf iPhone-/Mobile-Viewports jetzt innerhalb der Bildschirmbreite, statt horizontal ueberzulaufen
- `CyberPunk Classic` zeigt die grossen Boxen auf `/config` nicht mehr in einem schmutzig-braunen/senfigen Ton, sondern mit klarerem Pink/Gruen-Look passend zum Theme

### Security

### Known Limitations

### Upgrade Notes

## [0.1.0-alpha.50] - 2026-04-06

### Added
- `Memory` unterstützt jetzt erste RAG-Dokument-Uploads direkt im bestehenden Bereich, ohne neues Hauptmenü oder neue Top-Level-Seite
- `txt`, `md` und `pdf` mit eingebettetem Text können in Dokument-Collections importiert, gechunkt, embedded und in Qdrant gespeichert werden
- `/stats` zeigt im Bereich `Systemzustand` jetzt einen direkten `Updates`-Eintrag mit Status und Link auf `/updates`
- Dokument-Chunks werden in `Memory` jetzt als eigener UI-Typ `Dokument` geführt, statt optisch mit normalem Rollup-Wissen zusammenzufallen
- jeder Dokument-Upload erzeugt jetzt zusätzlich einen internen Dokument-Guide mit Summary und Stichworten, damit Chat-Recall passende Dokumente gezielter vorselektieren kann

### Changed
- `/updates` und `/stats` lesen die installierte ARIA-Version jetzt aus derselben gemeinsamen Release-Metadatenquelle, damit interne und öffentliche Versionsanzeigen konsistent bleiben
- Dokument-Uploads in `Memory` arbeiten jetzt gezielt mit Dokument-Collections wie `aria_docs_*`, statt beliebige Memory-Collections zu vermischen
- `Memory` bietet jetzt einen eigenen Filter und eigene Zählung für Dokumentwissen; `Dokumente` und `Rollup-Wissen` bleiben im UI sauber getrennt
- der Dokument-Import zeigt während Chunking und Qdrant-Ingest einen sichtbaren Arbeitszustand direkt im Upload-Block, nicht nur über das drehende Logo
- importierte Dokumente werden jetzt gesammelt in der `Memory Map` verwaltet, inklusive Dokumentname, Chunk-Anzahl, Vorschau und zentralem Entfernen ganzer Dokumente aus Qdrant
- die `Memory`-Ansicht gruppiert Einträge jetzt zusätzlich nach Typ und zeigt klickbare Typ-Kacheln, damit große Mengen an Facts, Dokumenten, Session-Kontext und Rollup-Wissen nicht in einer langen Mischliste untergehen
- der Chat-Recall nutzt bei Dokumentwissen jetzt zuerst den internen Dokument-Guide-Index und fragt danach gezielt nur passende Dokument-Chunks ab, statt blind alle Dokument-Collections mitzunehmen
- Chat-Details zeigen bei Dokument-Recall jetzt die verwendeten Quellen mit Dokumentname, Collection und Chunk-Referenz an; dieselbe Detail-Schiene kann später auch für Websuche-Quellen wiederverwendet werden
- Quellen in den Chat-Details werden jetzt nutzerfreundlich sortiert: Dokumente/Web zuerst, danach stabilere Memory-Typen vor flüchtigem Session-Kontext
- die globale Restart-Erkennung lädt Seiten nach kurzen `/health`-Aussetzern nicht mehr blind neu, sondern zeigt erst nach mehreren aufeinanderfolgenden Failures einen klaren Reload-Hinweis
- das `Cyberpunk`-Theme mischt jetzt Türkis und dunkles Blau in die bisher sehr grünlastige Neon-Palette
- das ursprüngliche `Cyberpunk`-Theme ist jetzt wieder als `CyberPunk Classic` zurück; der neue Look bleibt separat als `CyberPunk Neo` auswählbar, damit bestehende Setups optisch stabil bleiben

### Fixed
- der Dokument-Upload akzeptiert serverseitig keine Nicht-Dokument-Collections mehr; falsche Collection-Wahlen werden sauber abgewiesen
- PDFs ohne eingebetteten Text geben jetzt eine klare Fehlermeldung statt still zu scheitern; Scan-/Bild-PDFs werden in RAG v1 explizit als nicht unterstützt markiert
- Multipart-Dokument-Uploads werden nicht mehr fälschlich als `Bitte eine Datei auswählen` abgewiesen; die Upload-Route akzeptiert jetzt sowohl FastAPI- als auch Starlette-UploadFile-Objekte sauber
- die Dokument-Verwaltung liegt nicht mehr unpassend mitten im normalen `Memory`-Log, sondern an der thematisch passenderen Stelle in der `Memory Map`
- der sichtbare Upload-Hinweis in `Memory` bleibt nach erfolgreichem Import nicht mehr hängen, sondern wird beim nächsten Seitenaufbau sauber zurückgesetzt
- `/updates` bleibt bei GitHub-API-Rate-Limits nutzbar und fällt für die Versionsbestimmung sauber auf den öffentlichen `CHANGELOG.md` zurück, statt dauerhaft eine störende `403 rate limit exceeded`-Warnung anzuzeigen
- der Dokument-Upload-Hinweis wird im Idle nicht mehr fälschlich angezeigt; das `hidden`-Verhalten der Statusmeldung wird jetzt auch per CSS sauber respektiert
- Discord-Systemevents zeigen beim Start nicht mehr irreführend eine Docker-Bridge-IP als Host an; ohne gesetzte `ARIA_PUBLIC_URL` meldet ARIA jetzt klar, dass die öffentliche URL nicht konfiguriert ist

### Security

### Known Limitations
- RAG v1 unterstützt bei PDFs nur eingebetteten Text; OCR und bildbasierte PDFs sind noch nicht enthalten

### Upgrade Notes

## [0.1.0-alpha.40] - 2026-04-05

### Added

### Changed
- ARIA verwendet für Login-, CSRF- und Session-Cookies jetzt instanzspezifische Cookie-Namen, damit mehrere ARIA-Container auf demselben Host mit unterschiedlichen Ports sich nicht mehr gegenseitig die Browser-Session überschreiben

### Fixed
- der automatische Logout nach wenigen Minuten in Multi-Instanz-Setups wurde behoben; Ursache waren kollidierende Cookie-Namen zwischen z. B. `aria.example.lan:8800` und `aria.example.lan:8810`
- LLM-, Embeddings-, Chat- und Memory-Flows lesen jetzt konsistent die zur aktuellen Instanz gehörenden Cookies, statt versehentlich Session- oder CSRF-Werte einer anderen ARIA-Instanz zu verwenden

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes
- bei mehreren ARIA-Instanzen auf demselben Host kann nach dem Update ein einmaliges Neuanmelden sinnvoll sein, damit alte globale Legacy-Cookies nicht mehr im Browser bevorzugt werden

## [0.1.0-alpha.39] - 2026-04-05

### Added

### Changed
- Login-Timeout und Bootstrap-Einstellungen wurden von `Security Guardrails` nach `Benutzer` verschoben; die Security-Seite fokussiert sich jetzt auf Guardrail-Profile

### Fixed
- geschützte Fetch-/JSON-Requests löschen den Auth-Cookie bei nur temporärer Security-/Auth-Store-Unverfügbarkeit nicht mehr; dadurch verschwinden Sitzungen nicht mehr “einfach so” nach einigen Minuten durch einen Nebenrequest
- der Login-Timeout bleibt damit als konfigurierbare Einstellung relevant, statt von einem separaten Session-Fehlerpfad überlagert zu werden

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.37] - 2026-04-05

### Added
- die Security-Seite zeigt den Login-Timeout jetzt zusätzlich in einer menschenlesbaren Form an, z. B. `12 Stunden` oder `1 Tag 6 Stunden`, damit große Minutenwerte nicht im Kopf umgerechnet werden müssen

### Changed
- Login-Sessions können jetzt über `Security` mit einem konfigurierbaren Default-Timeout gesteuert werden; der Wert wird intern weiter in Sekunden gespeichert und kann zusätzlich per `ARIA_SECURITY_SESSION_MAX_AGE_SECONDS` gesetzt werden
- Update-Checks bleiben für den Zustand `up to date` deutlich frischer, damit neue Public-Releases schneller in Lampe und `/updates` sichtbar werden

### Fixed
- Login-Sessions bleiben bei LLM-/Embeddings-Konfigurationen und normalen Seitenwechseln stabil, statt durch unkritische Nebenrequests oder Runtime-Reloads ungewollt verloren zu gehen
- frisch angemeldete Nutzer werden bei der Modellkonfiguration nicht mehr fälschlich auf `Login` oder `Sitzung abgelaufen` zurückgeworfen, solange die Session gültig ist

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.35] - 2026-04-05

### Added

### Changed

### Fixed
- der Auth-Cookie wird nicht mehr auf unkritischen Responses wie öffentlichen Nebenrequests versehentlich gelöscht; dadurch bleiben Login-Sessions bei `Load models`, Profilwechseln und normalen Seitenwechseln stabil
- LLM- und Embeddings-Konfigurationen können wieder zuverlässig Modelle laden und speichern, ohne Nutzer auf `Login` oder `Bitte zuerst anmelden` zurückzuwerfen

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.34] - 2026-04-05

### Added

### Changed

### Fixed
- gültige, signierte Login-Sessions bleiben jetzt auch dann erhalten, wenn der Security-/Auth-Store während eines Runtime-Reloads kurzzeitig nicht verfügbar ist; ARIA wirft Nutzer in diesem Fall nicht mehr vorschnell auf `/login`
- Debug-Header für die Session-Diagnose wurden vorbereitet (`X-ARIA-Auth-Reason`, `X-ARIA-Auth-Degraded`), damit künftige Auth-Probleme gezielter eingegrenzt werden können

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.33] - 2026-04-05

### Added

### Changed
- `Updates` wurde aus der Hauptnavigation herausgenommen und als Kachel in `/help` neben `Produkt-Info` platziert

### Fixed
- Login-Sessions bleiben in internen HTTP-/LAN-Setups stabiler, weil Auth- und Preference-Cookies nur noch dann `Secure` werden, wenn die App wirklich unter HTTPS läuft oder `ARIA_PUBLIC_URL` explizit auf `https://...` gesetzt ist
- die Client-Restart-Erkennung lädt nach einer kurzen Runtime-Unterbrechung jetzt die aktuelle Seite neu, statt Nutzer blind auf `/login` zu schicken
- die `/updates`-Seite prüft jetzt frisch gegen GitHub und ignoriert veraltete Cache-Zustände, bei denen die installierte Version neuer als die gecachte `latest`-Version ist
- der Typing-Indikator über dem Chat-Composer bleibt im Idle garantiert verborgen und hinterlässt keinen leeren Rahmen mehr

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.30] - 2026-04-05

### Added

### Changed

### Fixed
- JSON-Fetches für LLM-/Embeddings-Modelllisten erhalten bei fehlender oder abgelaufener Session jetzt saubere JSON-Fehler statt Login-HTML; die Config-UIs senden dafür explizit API-artige Request-Header und Credentials

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.29] - 2026-04-05

### Added

### Changed

### Fixed
- auth cookies trust proxy HTTPS headers more conservatively, reducing false logouts on fresh HTTP/container setups where a stray forwarded header could make the browser drop the session cookie

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.28] - 2026-04-05

### Added

### Changed

### Fixed
- `aria-pull` / `update-local-aria.sh` retaggt geladene TAR-Images jetzt korrekt auf das lokale Compose-Image-Tag wie `aria:alpha-local`, damit echte Updates nicht still auf dem alten lokalen Image hängen bleiben

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.27] - 2026-04-05

### Added
- Update-Hinweis auf Basis von GitHub-Tags plus Release-Notes-Seite unter `/updates`

### Changed
- Login-Screen und Menü zeigen jetzt ein dezentes oranges Update-Lämpchen, wenn eine neuere öffentliche Version verfügbar ist

### Fixed

### Security

### Known Limitations
- ARIA ist weiterhin primär ein Personal-Single-User-System
- kein vollständiges RBAC-/Sharing-Modell für Skills, Connections und Memories
- Capability-Ergebnisse werden nicht pauschal automatisch in Memory geschrieben
- Public-Internet-Betrieb bleibt für diese ALPHA-Linie nicht empfohlen

### Upgrade Notes

## [0.1.0-alpha.26] - 2026-04-05

### Added

### Changed
- `README.md` now links Docker Hub directly in the header, next to the GitHub repository link.

### Fixed
- Prompt Studio no longer disables saving for editable prompt files like `prompts/persona.md`; prompt rows now carry explicit `edit` metadata and the shared editor template defaults missing modes to editable.
- LLM and Embeddings config now also create or overwrite a named profile when a different profile name is entered and the normal `Save` button or Enter key is used, instead of silently only updating the current active profile.

### Security

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached

## [0.1.0-alpha.25] - 2026-04-04

### Added
- Added practical, human-readable DE/EN Alpha help docs (`docs/help/alpha-help-system.de.md` / `.en.md`) and made `/help` load the matching language variant

### Changed
- Chat toolbox skill entries now show the actual skill name plus a compact `/skill` badge and a wrapped description/example line, instead of repeating only `/skill` for every skill button
- In the user menu, `Help` now appears after `Config` and before `Users`, so support docs sit closer to settings but still before user administration
- `README.md` is now split into a clear English-first section and a separately labeled German section instead of silently switching language mid-document
- `README.md` now embeds the architecture diagrams directly in both language sections

### Fixed
- `Systemzustand` cards in `/stats` now expose `visual_status` as well, so ARIA Runtime, Model Stack, Memory/Qdrant, Security Store, and Activities/Logs use the same status lamps as the rest of the page

### Security
- Repo/privacy sweep: removed personal dev-host defaults from `docker/pull-from-dev.sh`, neutralized `config/secrets.env`, removed stray root artifacts `=1.2` / `=2.1`, and excluded the then-current local project documentation folder from the public repo while keeping it locally

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached

## [0.1.0-alpha.24] - 2026-04-04

### Added
- `/skills` now exposes bundled sample-skill manifests from `/app/samples/skills` and lets admins import them directly without downloading files out of the container first
- `/config` now exposes bundled sample-connection YAMLs from `/app/samples/connections` and lets admins import them directly into `config.yaml`
- Added `rss-morning-briefing-to-discord-template.json`, a scheduled multi-RSS + LLM + Discord sample for a daily curated morning briefing

### Changed
- Product Info now only exposes user-facing docs; the internal Copy Pack card was removed from the Product Info page
- CyberPunk Pulse buttons and menu labels are now rendered in neon green for stronger theme contrast, and Deep Space was shifted toward a darker violet/nebula palette so it is less close to Harbor Blue
- Skill Wizard now explicitly documents that `llm_transform` prompts can use `{prev_output}` as well as step-specific placeholders like `{s1_output}` and `{s2_output}`

### Fixed
- `samples/` is now packaged into the Docker image, so bundled sample skills, sample connections, and sample guardrails are available inside the container as `/app/samples`

### Security

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached


## [0.1.0-alpha.23] - 2026-04-04

### Added

### Changed
- CyberPunk Pulse theme tuned further: stronger hot-pink panel/glow treatment, while secondary helper/meta/status text and chips now use neon `#00ff00`
- `Produkt-Info` moved out of the top menu and linked from the `/help` page instead, so product docs are presented as support material rather than a main navigation item

### Fixed
- iPhone chat view no longer allows subtle horizontal side-panning/drift while scrolling; chat container and message bubbles are now locked to vertical pan with hard X-axis clipping
- `/help` and `/product-info` docs are now packaged into the Docker image, so read-only help/product pages no longer show missing-file fallbacks in container deployments
- Qdrant DB size in `/stats` no longer stops at `0 B` when telemetry reports collections but zero disk bytes; ARIA now falls through to local storage-path inspection first and only then uses the zero-byte telemetry fallback

### Security

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached

## [0.1.0-alpha.22] - 2026-04-03

### Added
- Read-only `/help` page backed by `docs/help/help-system.md`
- Read-only `/product-info` page with overview, feature list, architecture docs, and embedded architecture diagrams
- Memory JSON export from `/memories` for the current user and current filter/search scope
- `/stats` reset flow with explicit `RESET` confirmation
- MIT `LICENSE` and `THIRD_PARTY_NOTICES.md`

### Changed
- Documentation tree reorganized into public `docs/` and the then-current internal history folder
- Login, Users, and Security UI now explain first-run bootstrap and Admin/User mode boundaries more clearly
- CyberPunk Pulse theme shifted toward stronger hot-pink/magenta accents
- Auto-Memory now skips transient one-off questions and pure tool/action prompts unless they contain stable facts/preferences
- Capability results are intentionally not auto-persisted to Memory by default; future durable state should use explicit summary/state-memory flows
- Memory docs/backlogs now treat weighted multi-collection recall and JSON export as Public Alpha scope, while session rollup and reindex remain post-alpha work

### Fixed
- More robust Qdrant DB size fallback for separate Docker/Portainer Qdrant volumes mounted read-only into the ARIA container
- Long `Tages-Kontext` / `Login-Session` debug IDs no longer cause horizontal overflow on iPhone chat screens
- Help-file tests updated to the new `docs/help/...` paths

### Security
- Third-party attribution for Qdrant and key runtime dependencies documented explicitly

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory unless modeled explicitly
- Public internet exposure is still not recommended for this ALPHA line
- Home Assistant, document ingest, web research, SSE streaming, and full multi-user sharing remain roadmap items

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached
- If you use a separate Qdrant container, ensure the Qdrant storage volume is mounted read-only into the ARIA container as in the updated stack examples

## [0.1.0-alpha.21] - 2026-04-03

### Added
- New UI themes: CyberPunk Pulse, 8-Bit Arcade, Amber CRT, Deep Space
- RSS metadata helper button `Check mit LLM` to suggest/enrich title, description, aliases, and tags
- Global RSS poll interval for all RSS feeds
- Stable per-feed RSS poll phase offset to avoid all feeds becoming due on the same interval edge

### Changed
- RSS routing now uses title, description, aliases, and tags of RSS profiles more strongly
- Short free-form RSS prompts like `was für news gibs auf heise` are recognized more reliably
- Statistics / Startup Preflight / System health now display state mostly via status lamps instead of repeated text labels
- CyberPunk theme adjusted toward stronger hot-pink/magenta accents and a darker black base

### Fixed
- RSS page search now correctly hides non-matching groups and feeds
- RSS search also reacts when the browser clear `x` resets the search field

### Security
- No dedicated security change in this release block

### Known Limitations
- ARIA is still primarily a personal single-user system
- No full shared-skill/shared-connection RBAC model yet
- Capability results are not automatically written into Memory in the same way as normal chat responses
- Public internet exposure is still not recommended for this ALPHA line

### Upgrade Notes
- Update the ARIA container/image, keep persistent volumes
- Hard-refresh the browser after the update if old CSS/theme assets are still cached

## Internal Notes

- Detailed internal build history currently lives in `docs/internal/alpha-build-log.md`
- Public release wording can be derived from:
  - `docs/product/feature-list.md`
  - `docs/backlog/future-features.md`
  - `docs/setup/setup-overview.md`
  - `docs/product/architecture-summary.md`
  - `docs/release/versioning.md`
