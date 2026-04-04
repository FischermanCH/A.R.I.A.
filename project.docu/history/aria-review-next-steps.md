# ARIA — Review & Nächste Schritte

Quelle: Claude (Architektur-Review auf Basis Status 2026-03-25)
Zielgruppe: Codex als Implementierungspartner

---

## 1. Bewertung aktueller Stand

ARIA ist in einem Monat von einem Chat-Prototyp zu einer ernsthaften Plattform gewachsen. Phase 2A (Memory-Architektur 2.0) ist vollständig abgeschlossen. Das Projekt ist deutlich weiter als der ursprüngliche Masterplan vorgesehen hat.

### Was besonders gut ist

- **Security von Anfang an:** Login, Rollen, CSRF, HMAC-Cookies, Security-Headers. Nachträglich einzubauen wäre extrem aufwändig gewesen.
- **Custom-Skill-System:** Step-Pipeline mit SSH-Execution und Wizard geht weit über den Masterplan hinaus. ARIA ist damit eine Automatisierungsplattform, nicht nur ein Chatbot.
- **Memory-Architektur:** Typisierte Collections (Facts, Preferences, Sessions, Knowledge), gewichtetes Recall, Deduplizierung, Auto-Komprimierung, Forget mit Bestätigung — alles sauber umgesetzt.
- **i18n durchgezogen:** 5 Wellen, alle Seiten mehrsprachig.
- **26 Tests grün.**

---

## 2. Fehlende Kernfunktionen (Concerns)

### 2.1 Konversationshistorie (KRITISCH)

**Problem:** ARIA hat kein Gedächtnis innerhalb einer Chat-Session. Jede Nachricht wird isoliert verarbeitet. Follow-up-Fragen funktionieren nicht:

```
User: "Wie heisst die Hauptstadt von Frankreich?"
ARIA: "Paris."
User: "Und wie viele Einwohner hat sie?"
ARIA: ???  ← Weiss nicht worauf sich "sie" bezieht
```

**Lösung:** Die letzten N Nachrichten (User + Assistant) als Konversationskontext mitsenden. Konfigurierbar, z.B. `chat.history_length: 10` in config.yaml.

**Wo einhängen:** Im Context Assembler, zwischen Persona und Skill-Kontext:

```python
messages = [
    {"role": "system", "content": persona},
    # --- Konversationshistorie (letzte N) ---
    {"role": "user", "content": "Wie heisst die Hauptstadt von Frankreich?"},
    {"role": "assistant", "content": "Paris."},
    # --- Aktueller Turn ---
    {"role": "user", "content": skill_context + "\n\nFrage: " + current_message}
]
```

**Speicherung:** In-Memory pro Session (dict mit session_id als Key). Kein Qdrant nötig — das ist kurzfristiger Kontext, nicht langfristiges Memory. Bei Neustart oder Session-Ablauf weg.

**Token-Budget beachten:** Konversationshistorie frisst Tokens. Max-Limit setzen (z.B. 2000 Tokens für History), älteste Nachrichten zuerst abschneiden.

**Aufwand:** 1 Session.

---

### 2.2 Streaming (UX)

**Problem:** Antworten kommen als Block nach 10-50 Sekunden. Der User starrt auf "ARIA denkt nach..." ohne Feedback ob es 5 oder 50 Sekunden dauert.

**Lösung:** Server-Sent Events (SSE) für Token-Streaming.

**Technik:**
- FastAPI: `StreamingResponse` mit `text/event-stream`
- LiteLLM: `stream=True` Parameter in `acompletion()`
- HTMX: `hx-ext="sse"` oder EventSource in minimalem JS
- Token-Badge erst am Ende anzeigen (wenn usage bekannt)

**Aufwand:** 1 Session. Grösster Umbau ist im Frontend (HTMX → SSE).

---

### 2.3 Websuche

**Problem:** ARIA kann keine aktuellen Informationen abrufen. Für einen Assistenten ist das eine Pflichtfunktion.

**Strategie (bereits definiert):** Provider-native Web-Tools first (z.B. LLM-Gateway mit eingebautem Web-Tool), SearXNG als optionale Power-User-Erweiterung.

**Umsetzung als Skill:**
- Neuer Skill: `web_search.py` + `prompts/skills/web_search.md`
- Router-Keywords: "such", "google", "aktuell", "news", "was passiert"
- Konfigurierbar: welcher Search-Provider (native / SearXNG / keiner)
- Resultate in Skill-Kontext kürzen (Top-5, max 1500 chars)

**Aufwand:** 1-2 Sessions.

---

### 2.4 Health-Checks beim Start

**Problem:** Wenn Qdrant nicht erreichbar ist oder das LLM nicht antwortet, merkt der User das erst beim ersten Chat (memory_error oder Timeout).

**Lösung:** Beim App-Start prüfen:
1. Qdrant erreichbar? → Collections vorhanden?
2. LLM antwortet? → Einfacher Test-Prompt
3. Embedding funktioniert? → Test-Embedding
4. Prompt-Files vorhanden?

Ergebnis in Startup-Log und optional auf einer `/health`-Detailseite (aktuell gibt /health nur `{"status":"ok"}`).

**Aufwand:** Kann in eine bestehende Session integriert werden.

---

## 3. Empfohlene Reihenfolge

| Prio | Feature | Sessions | Begründung |
|------|---------|----------|------------|
| 1 | Konversationshistorie | 1 | Grösster UX-Blocker, ARIA wirkt "dumm" ohne |
| 2 | Streaming | 1 | Wahrgenommene Geschwindigkeit verdreifacht sich |
| 3 | Websuche | 1-2 | Macht ARIA zum vollwertigen Assistenten |
| 4 | Dokument-Ingest / RAG | 2 | Baut auf Memory-System auf, Knowledge-Collections befüllen |
| 5 | Docker-Packaging | 1 | Am Schluss wenn Feature-Set steht |

---

## 4. Technische Hinweise für Implementierung

### Konversationshistorie — Details

```python
# aria/core/conversation.py

from collections import defaultdict

class ConversationStore:
    """In-Memory Konversationshistorie pro Session."""
    
    def __init__(self, max_turns: int = 10, max_tokens: int = 2000):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self._history: dict[str, list[dict]] = defaultdict(list)
    
    def add(self, session_id: str, role: str, content: str):
        self._history[session_id].append({"role": role, "content": content})
        # Älteste abschneiden wenn über max_turns
        if len(self._history[session_id]) > self.max_turns * 2:
            self._history[session_id] = self._history[session_id][-self.max_turns * 2:]
    
    def get(self, session_id: str) -> list[dict]:
        return self._history[session_id].copy()
    
    def clear(self, session_id: str):
        self._history.pop(session_id, None)
```

**Integration in Pipeline:**
- `pipeline.process()` bekommt `session_id` Parameter
- Vor LLM-Call: History aus ConversationStore holen
- Nach LLM-Call: User-Message + Assistant-Response in Store schreiben
- Context Assembler baut History in messages-Array ein

**Integration in Chat-UI:**
- Session-ID aus Cookie oder generieren
- `/cls` und `/clear` rufen `conversation_store.clear()` auf

**Config:**
```yaml
chat:
  history_length: 10        # Letzte N Turns (User+Assistant = 1 Turn)
  history_max_tokens: 2000  # Hard Limit für History-Tokens
```

### Streaming — Details

```python
# In main.py oder pipeline.py

from fastapi.responses import StreamingResponse

@app.post("/chat/stream")
async def chat_stream(message: str = Form(...)):
    async def generate():
        async for chunk in pipeline.process_stream(message, ...):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True, 'usage': usage})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**LiteLLM Streaming:**
```python
response = await acompletion(
    model=self.model,
    messages=messages,
    stream=True,  # ← Einzige Änderung
)
async for chunk in response:
    delta = chunk.choices[0].delta.content
    if delta:
        yield delta
```

---

## 5. Was NICHT vergessen werden sollte

- **Token-Budget für History:** Konversationshistorie frisst Tokens. Ohne Limit explodiert der Verbrauch bei langen Gesprächen. Immer ein Hard-Limit setzen.
- **History vs. Memory:** Konversationshistorie (kurzfristig, in-memory, pro Session) ist NICHT dasselbe wie Memory (langfristig, Qdrant, persistent). Beides muss zusammenspielen: History für den aktuellen Chat, Memory für übergreifendes Wissen.
- **Streaming + Token-Badge:** Bei Streaming ist der Token-Count erst am Ende bekannt. Badge muss nachträglich aktualisiert werden (z.B. via letztem SSE-Event).
- **Streaming + Auto-Memory:** Auto-Memory Extraction braucht die vollständige Antwort. Muss nach Stream-Ende laufen, nicht während.
- **Streaming + Skills:** Skill-Kontext muss VOR dem Stream fertig sein. Die Pipeline-Reihenfolge bleibt: Route → Skills → Context → Stream LLM.

---

## 6. Backlog-Items aus dem Masterplan die noch ausstehen

Zur Vollständigkeit — diese Items aus dem originalen Masterplan und späteren Planungen sind noch offen:

- [ ] Router Stufe 2 (Embedding-basierte Klassifikation) — aktuell nur Keywords
- [ ] Prompt-Registry mit UI-Editor und Variablen-System
- [ ] Prompt-Testing UI (Prompt wählen → Test-Message → Ergebnis sehen)
- [ ] Discord Channel Adapter
- [ ] Telegram Channel Adapter
- [ ] Home Assistant Skill
- [ ] SQLite Memory Fallback (für User ohne Qdrant)
- [ ] Plugin-System (Community Skills via pip install)
- [ ] Qdrant Graph-Visualisierung (vis.js oder d3.js, alle Nodes mit Similarity-Verbindungen)
- [ ] Theming-System (austauschbare Farbschemata)
- [ ] Dockerfile + docker-compose.yml für Distribution

Diese sind NICHT priorisiert und sollen NICHT jetzt umgesetzt werden. Sie dienen als Referenz damit nichts verloren geht.
