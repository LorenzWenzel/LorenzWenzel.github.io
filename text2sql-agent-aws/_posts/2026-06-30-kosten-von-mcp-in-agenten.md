---
layout: post
title: "Die versteckten Kosten von MCP in Agenten"
title_en: "The Hidden Cost of MCP in Agents"
date: 2026-06-30 18:40:00 +0200
---

Der Titel führt bewusst ein wenig in die Irre. Es geht hier nicht in erster
Linie um den Preis eines MCP-Aufrufs, sondern darum, **wie MCP in einem Agenten
tatsächlich funktioniert**. Die Kosten sind nur die Rechnung, die man am Ende
für ein Missverständnis bekommt.

Das Missverständnis lautet ungefähr so: *„Der Agent holt sich über MCP die
Daten."*

Das tut er nicht. Und der Unterschied zwischen dieser Vorstellung und dem, was
wirklich passiert, ist der Unterschied zwischen einer Rechnung und einer
dreimal so hohen. Ich spreche da aus Erfahrung :)

## Was wirklich passiert

Das Modell hat keine Ausgänge. Es kann nichts aufrufen, nichts öffnen, nirgends
hinschreiben. Es bekommt Text hinein und gibt Text heraus – strukturierte
Blöcke, aber Text. Alles, was nach „das Modell hat etwas getan" aussieht, hat
in Wahrheit ein anderes Programm getan.

![Architekturdiagramm: Amazon Bedrock links, Agent-Anwendung mit MCP-Client in der Mitte, MCP-Server und Athena rechts. Zwischen Bedrock und MCP-Server besteht keine Verbindung.](/assets/img/mcp-architektur.svg)

Der Ablauf im Einzelnen:

1. Die **Agent-Anwendung** – der Host – schickt an Bedrock den bisherigen
   Gesprächsverlauf und eine Liste der verfügbaren Werkzeuge.
2. Das Modell antwortet mit `tool_use`-Blöcken. Das ist **eine Bitte, keine
   Handlung**: „Ich hätte gern `run_query` mit diesem SQL."
   Die Antwort endet mit `stop_reason: "tool_use"`, und damit ist dieser
   Modellaufruf abgeschlossen und bezahlt.
3. Der **MCP-Client** im Host liest diese Bitte und ruft über das MCP-Protokoll
   das entsprechende Tool auf dem **MCP-Server** auf. Der Server spricht mit
   Athena, Athena mit S3.
4. Das Ergebnis geht zurück an den Host, der es als `tool_result`-Block an den
   Verlauf hängt.
5. Und jetzt der Punkt, um den es geht: Der Host startet einen **vollständig
   neuen Modellaufruf** – mit dem gesamten bisherigen Verlauf plus den neuen
   Ergebnissen.

Zwischen Bedrock und dem MCP-Server gibt es keine Leitung. Es gibt sie auch
nicht heimlich. MCP ist ein Protokoll zwischen dem Host und dem Werkzeug-Anbieter;
das Modell weiß von MCP nicht einmal etwas. Für das Modell sind es einfach
Werkzeuge in einer Liste – ob die über MCP, über einen lokalen Funktionsaufruf
oder über eine Brieftaube bedient werden, ist ihm gleichgültig.

**Das Modell ist zustandslos.** Es erinnert sich an nichts. Jeder Aufruf
bekommt den vollständigen Verlauf neu vorgelegt, weil es keine andere
Möglichkeit gibt, ihm etwas mitzuteilen. Was in Turn 2 hinzukommt, wird in
Turn 3, 4 und 5 wieder mitgeschickt und wieder bezahlt.

## Toolaufrufe sind nicht Modellaufrufe

Aus dieser Mechanik folgt die Regel, auf die es ankommt:

> Für eine **n-stufige Kette** zahlt man **n + 1 Modellaufrufe.**

n Aufrufe, um Werkzeuge anzufordern, plus einen letzten, um aus dem letzten
Ergebnis eine Antwort zu formulieren.

Das Entscheidende daran: **n ist nicht die Zahl der Toolaufrufe.** Ein einzelner
`tool_use`-Turn kann beliebig viele Werkzeuge enthalten, die der Host parallel
ausführt. Sechs Werkzeuge in einer Runde kosten genau so viele Modellaufrufe wie
eines.

![Zwei Ketten im Vergleich: oben sechs parallele Toolaufrufe zwischen zwei Modellaufrufen, unten sechs sequenzielle Toolaufrufe zwischen sieben Modellaufrufen.](/assets/img/mcp-kette.svg)

Oben und unten passiert fachlich dasselbe – sechs Werkzeuge laufen, sechs
Ergebnisse kommen zurück. Oben kostet es zwei Modellaufrufe, unten sieben.

**Breite ist gratis. Tiefe kostet.** Das ist die ganze Regel, und sie ist die
einzige Stellschraube, die wirklich etwas bewegt.

n wird nur dann größer als 1, wenn das Modell ein Ergebnis *sehen* muss, bevor
es den nächsten Aufruf formulieren kann. Erst die Tabellenliste holen, dann das
Schema der passenden Tabelle, dann die Abfrage: drei Stufen, vier
Modellaufrufe. Kann man die Tabellenliste und die Schemata in einem Rutsch
holen, sind es zwei Stufen. Liefert ein einziges Tool beides zusammen, ist es
eine.

## Warum Tiefe mehr als linear kostet

Sieben statt zwei Modellaufrufe klingen nach Faktor 3,5. Die Rechnung fällt
schlechter aus, und der Grund ist die Zustandslosigkeit von oben: Jeder
zusätzliche Turn schickt **alles Bisherige erneut** mit.

Bei einer Kette der Tiefe *n* wird das erste Tool-Ergebnis *n*-mal abgerechnet,
das zweite *n−1*-mal und so weiter. Der abgerechnete Verlauf wächst nicht mit
der Tiefe, sondern mit ihrem Quadrat.

![Säulendiagramm: Kosten je 1000 Fragen steigen von 13,49 Dollar bei Kettentiefe 1 auf 82,82 bei Tiefe 6. Eine gestrichelte Linie markiert 29,09 Dollar für dieselben sechs Tools in einer breiten Kette.](/assets/img/mcp-kettentiefe.svg)

| Tiefe | Modellaufrufe | Toolaufrufe | Verlauf zum Vollpreis | $ / 1 000 Fragen |
|---:|---:|---:|---:|---:|
| 1 | 2 | 1 | 1 340 | 13,49 |
| 2 | 3 | 2 | 3 900 | 22,32 |
| 3 | 4 | 3 | 7 720 | 33,66 |
| 4 | 5 | 4 | 12 800 | 47,53 |
| 5 | 6 | 5 | 19 140 | 63,91 |
| 6 | 7 | 6 | 26 740 | 82,82 |

Verdoppelt man die Tiefe von 4 auf 8, steigt der Verlauf von 12 800 auf
45 720 Token – Faktor 3,6, nicht 2. Und die gestrichelte Linie in der Grafik
ist das eigentliche Argument: **dieselben sechs Werkzeuge, breit statt tief
aufgerufen, kosten 29,09 $ statt 82,82 $.** Faktor 2,8, ohne dass ein einziger
Toolaufruf entfallen wäre.

Deshalb ist Prompt Caching hier keine Optimierung, sondern die Bedingung, unter
der die obere Tabelle überhaupt so moderat aussieht. Ohne Cache käme der
Präfix – Systemprompt, Schemata, Tool-Definitionen – bei *jedem* dieser Aufrufe
zum vollen Preis hinzu.

## Was sonst noch bei jedem Aufruf mitfährt

Die Tool-Definitionen. Sie stehen im `tools`-Parameter, ganz vorn, und sie
gehen bei jedem einzelnen Modellaufruf erneut über die Leitung.

Ich habe einen realistischen Athena-MCP-Server nachgebaut – `run_query`,
`list_tables`, `describe_table`, `get_query_status`, `cancel_query`, jeweils
mit brauchbaren Beschreibungen und JSON-Schema – und nachgemessen:

| | Token |
|---|---:|
| `run_query` | 163 |
| `list_tables` | 102 |
| `describe_table` | 100 |
| `get_query_status` | 87 |
| `cancel_query` | 75 |
| **Server gesamt** | **527** |

Rund **105 Token je Werkzeug**. Das klingt harmlos, skaliert aber mit der Zahl
der angebundenen Server:

| Server | Tools | Token im Präfix |
|---:|---:|---:|
| 1 | 5 | 527 |
| 3 | 15 | 1 581 |
| 5 | 25 | 2 635 |
| 8 | 40 | 4 216 |

Über den Cache kostet das wenig. Gefährlich ist etwas anderes: Die Tool-Liste
steht **am Anfang** des zwischengespeicherten Präfix – die Reihenfolge ist
`tools` → `system` → `messages`, und jede Byte-Änderung entwertet alles
dahinter. Ein MCP-Server, der sich neu verbindet und seine Werkzeuge in anderer
Reihenfolge meldet, invalidiert damit den Cache für den gesamten Rest des
Prompts. Nicht ein bisschen: vollständig.

Der zweite Effekt ist die Auswahl selbst. Vierzig Werkzeuge sind vierzig
Möglichkeiten, das falsche zu greifen – und jeder Fehlgriff ist eine weitere
Stufe in der Kette.

## Wie man Ketten kürzt

Die Reihenfolge ist nach Wirkung sortiert.

### 1. Werkzeuge grobkörniger schneiden

Der wirksamste Hebel und der am seltensten gezogene. Drei Werkzeuge, die
Bausteine liefern, erzwingen drei Stufen. Ein Werkzeug, das die Frage
beantwortet, braucht eine.

Der übliche Zuschnitt bildet die AWS-API eins zu eins ab:

```python
list_tables(database)            # -> 120 Tabellennamen
describe_table(database, table)  # -> Schema einer Tabelle
run_query(sql, database)         # -> Resultset
```

Für die Frage *„Umsatz je Region im letzten Quartal"* entsteht daraus:

```
1  Modell  -> list_tables("analytics")
2  Modell sieht 120 Namen      -> describe_table("fact_orders")
3  Modell sieht das Schema     -> describe_table("dim_region")
   (dass er die zweite Tabelle braucht, merkt er erst hier)
4  Modell hat, was es braucht  -> run_query("SELECT ...")
5  Modell                      -> Antwort
```

Tiefe 4, fünf Modellaufrufe. Zwei davon – Schritt 2 und 3 – sind reine
Beschaffung: Das Modell trifft keine Entscheidung, die ein Programm nicht auch
treffen könnte.

Also übernimmt das Programm sie:

```python
@server.tool()
def schema_fuer_frage(frage: str, max_tabellen: int = 5) -> str:
    """Liefert die für eine Frage relevanten Tabellen samt Schema,
    Partitionsschlüsseln und je drei Beispielzeilen."""
    # Suche über die Tabellen- und Spaltenbeschreibungen aus dem Glue-Katalog.
    # Embedding oder BM25 – Millisekunden, kein Modellaufruf.
    treffer = katalog_suche(frage, k=max_tabellen)
    return "\n\n".join(schema_als_csv(t) for t in treffer)
```

```
1  Modell  -> schema_fuer_frage("Umsatz je Region im letzten Quartal")
2  Modell sieht 3 Schemata      -> run_query("SELECT ...")
3  Modell                       -> Antwort
```

| | Modellaufrufe | Verlauf zum Vollpreis | $ / 1 000 Fragen |
|---|---:|---:|---:|
| feiner Zuschnitt | 5 | 17 100 | 56,13 |
| grober Zuschnitt | 3 | 8 700 | **31,92** |

**43 % günstiger – obwohl das erste Tool-Ergebnis mehr als doppelt so groß
ist.** Genau das ist der Punkt: Nicht die Tokenmenge je Ergebnis ist das
Problem, sondern die Zahl der Runden, durch die sie getragen wird.

Die Regel dahinter lautet: *Was ein deterministisches Programm entscheiden
kann, sollte kein Modellaufruf entscheiden.*

Es gibt eine Grenze. Ein Werkzeug `beantworte_frage(frage)` wäre der ganze
Agent in einem Tool – man hätte die Ketten nicht gekürzt, sondern nur
versteckt. Grobkörnig heißt: alles zusammenfassen, was **keine** Entscheidung
des Modells erfordert. Die Wahl des Joins bleibt beim Modell.

### 2. Künstliche Abhängigkeiten vermeiden

Werkzeuge, deren Eingaben nicht voneinander abhängen, sollten auch nicht so
aussehen. Sonst erzwingt der Zuschnitt eine Reihenfolge, die die Sache gar
nicht braucht.

**Der teuerste Fall: Athenas Asynchronität durchreichen.** Athenas API ist von
Haus aus asynchron – starten, Status abfragen, Ergebnis holen. Ein MCP-Server,
der das eins zu eins spiegelt, sieht harmlos aus:

```python
run_query(sql)         # -> {"query_execution_id": "abc-123"}   startet nur
get_query_status(id)   # -> {"state": "RUNNING"}
get_query_results(id)  # -> Resultset
```

Bei einer Abfrage, die sechs Sekunden läuft, passiert dann das hier:

```
1  Modell -> run_query              -> ID
2  Modell -> get_query_status       -> RUNNING
3  Modell -> get_query_status       -> RUNNING
4  Modell -> get_query_status       -> RUNNING
5  Modell -> get_query_status       -> SUCCEEDED
6  Modell -> get_query_results      -> Resultset
7  Modell                           -> Antwort
```

Sieben Modellaufrufe, von denen vier nichts sagen außer „läuft noch".
**40,82 $ statt 17,09 $ je 1 000 Fragen – Faktor 2,4 für exakt dieselbe
Abfrage.** Ein Sprachmodell als Polling-Schleife ist die teuerste
Warteschleife, die sich bauen lässt.

Das Warten gehört in den Server:

```python
@server.tool()
def run_query(sql: str, database: str, timeout_s: int = 60) -> str:
    """Führt die Abfrage aus und wartet, bis sie fertig ist."""
    qid = athena.start_query_execution(sql, database)
    zustand = warte_bis_fertig(qid, timeout_s)   # Polling hier, nicht im Modell
    if zustand == "TIMEOUT":
        # Nur jetzt lohnt sich eine zweite Stufe – und nur dafür
        # braucht das Modell die ID überhaupt zu sehen.
        return f"Läuft noch. Später erneut abrufen mit query_execution_id={qid}"
    return ergebnis_als_csv(qid)
```

**Der zweite Fall: Handles.** Ein Rückgabewert, den ein anderes Werkzeug als
Pflichtfeld verlangt, verkettet die beiden auf Dauer:

```python
list_tables(database)                  # -> {"catalog_token": "xyz", "tables": [...]}
describe_table(catalog_token, table)   # required: catalog_token
```

Das Token erzwingt die Reihenfolge. Ohne es – und mit einer Liste statt eines
Skalars – kann das Modell alle drei Schemata in **einem** Turn anfordern:

```python
describe_tables(database: str, tables: list[str])
```

| | Modellaufrufe | $ / 1 000 Fragen |
|---|---:|---:|
| drei Schemata seriell (Handle erzwingt es) | 4 | 30,06 |
| drei Schemata parallel | 2 | **17,93** |

40 % weniger, ohne dass ein Werkzeug entfallen wäre. Es wurde nur ein
Pflichtparameter gestrichen.

Woran man künstliche Abhängigkeiten im eigenen Server erkennt:

- Ein Parameter heißt `*_id`, `*_token`, `handle`, `session` oder `cursor` –
  und stammt aus der Ausgabe eines anderen Werkzeugs.
- Ein Werkzeug heißt `open_*`, `start_*` oder `create_*` und hat ein
  Gegenstück `close_*`.
- Ein Werkzeug liefert eine Seite plus Cursor für die nächste. Jede Seite ist
  eine Stufe.
- Ein Werkzeug nimmt einen Skalar, wo eine Liste genauso ginge.

Jeder dieser vier Punkte kostet im Zweifel einen Modellaufruf pro Vorkommen.

### Die übrigen Hebel

**Alle `tool_result`-Blöcke in *einer* Nachricht zurückgeben.** Wer die
Ergebnisse paralleler Aufrufe auf mehrere Nachrichten verteilt, gewöhnt dem
Modell die parallelen Aufrufe still wieder ab – es lernt aus dem Verlauf, dass
das offenbar nicht vorgesehen ist. Ein Implementierungsdetail mit direkter
Wirkung auf n.

**Das Ergebnis kleiner machen.** Jede Zeile, die ein Tool zurückgibt, wird in
jedem Folgeturn erneut abgerechnet. Ein Limit im Werkzeug wirkt deshalb
multiplikativ mit der Kettentiefe – dazu mehr in
[Welches Format sollten MCP-Funktionen zurückgeben?]({% post_url 2026-05-12-mcp-ausgabeformate %})

**Alte Tool-Ergebnisse aus dem Verlauf räumen.** Wenn Schritt 1 nur dazu
diente, den Tabellennamen zu finden, muss sein vollständiges Ergebnis in
Schritt 5 nicht mehr mitfahren. Dafür gibt es Context Editing
(`clear_tool_uses_20250919`), das alte Ergebnisse entfernt statt sie
zusammenzufassen.

**Bei vielen Servern: Werkzeuge nachladen statt alle deklarieren.** Mit
`defer_loading: true` und einem Suchwerkzeug stehen nicht alle vierzig
Definitionen in jedem Aufruf. Ein Werkzeug muss dabei geladen bleiben, sonst
lehnt die API den Request ab.

## Eine Verfeinerung

Es gibt eine Variante, in der der MCP-Client nicht im eigenen Host läuft,
sondern auf der Seite der API – man gibt die Server-URL im Request an, und die
Anthropic-Infrastruktur übernimmt den Client-Part.

Das ändert an allem oben **nichts**. Es verschiebt nur, wer den Client
betreibt. Das Modell ruft weiterhin nichts auf, die Ergebnisse landen weiterhin
als Blöcke im Verlauf, und für eine n-stufige Kette werden weiterhin n + 1
Inferenzen gerechnet. Wer sich davon eine Ersparnis verspricht, hat das
Missverständnis vom Anfang nur eine Ebene tiefer verschoben.

## Methodik

Das Kettenmodell liegt als
[`assets/bench/mcp-ketten.py`](/assets/bench/mcp-ketten.py) im Repo. Annahmen:
Präfix 15 527 Token (Systemprompt, Schemata, Tool-Definitionen), ein
Tool-Ergebnis 1 200 Token, Preise von Claude Sonnet 5 (2,00 $ je Mio.
Input-Token, 0,20 $ Cache-Read, 10,00 $ Output). Die Tool-Definitionen wurden
mit `tiktoken`/`o200k_base` gezählt; für exakte Werte auf Claude-Modellen
`messages.count_tokens` verwenden. Auf Bedrock gelten eigene Preise.

Das Modell rechnet eine saubere Kette ohne Fehlversuche. Reale Agenten greifen
daneben, bekommen Athena-Fehler zurück und probieren erneut – jeder dieser
Versuche ist eine weitere Stufe. Die Zahlen oben sind die Untergrenze.

---

**Kurzfassung:** MCP liefert dem Modell keine Daten. Das Modell äußert einen
Wunsch, der Host führt ihn über den MCP-Client aus, und danach beginnt ein
neuer Modellaufruf mit dem gewachsenen Verlauf. Toolaufrufe sind darum billig
und Modellaufrufe teuer: Eine n-stufige Kette kostet n + 1 Inferenzen, und weil
jede davon den ganzen Verlauf erneut trägt, wächst die Rechnung quadratisch mit
der Tiefe. Wer Kosten senken will, streicht keine Werkzeuge – er legt sie
nebeneinander statt hintereinander.
