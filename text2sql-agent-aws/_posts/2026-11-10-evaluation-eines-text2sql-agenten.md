---
layout: post
title: "Evaluation eines text2SQL-Agenten auf AWS"
title_en: "Evaluating a text2SQL Agent on AWS"
date: 2026-11-10 15:00:00 +0100
serie: "text2SQL-Agent auf AWS"
---

Der [Judge-Beitrag]({% post_url 2026-09-22-llm-as-a-judge %}) hat gefragt, *wer*
über den Agenten urteilen soll und wie stark dieser Richter sein muss. Amazon
Bedrock AgentCore Evaluations kam dort als Exkurs vor. Dieser Beitrag dreht die
Blickrichtung um: **Was genau kann AWS an einem text2SQL-Agenten bewerten, woher
nimmt der Dienst sein Material – und was muss man dafür liefern, je nachdem, wie
der Agent gebaut ist?**

Vorweg, was hier nicht passiert: Es wird nichts gemessen. Kein Golden Set, kein
Lauf, keine Scores. Der Text trägt zusammen, was die Dokumentation am 10. November
2026 hergibt, und ordnet es für die zwei Bauweisen aus dem
[AgentCore-Beitrag]({% post_url 2026-09-06-bedrock-agentcore-vs-converse-mcp %}):
nativ im AgentCore harness, und mit eigener Schleife aus Converse-API und MCP.

## Bewertet wird die Spur, nicht der Agent

Der wichtigste Satz zuerst: **Der Bewertungsdienst ruft den Agenten nie auf.** Er
liest, was der Agent an Telemetrie hinterlassen hat – OpenTelemetry-Spans in
CloudWatch –, übersetzt sie in ein einheitliches Format und bewertet dieses
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html)).
Deshalb ist es ihm gleich, wo der Agent läuft: auf der AgentCore Runtime oder
*„hosted outside of AgentCore"*
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/how-it-works-evaluations.html)).

Die Telemetrie hat drei Stufen: Eine **Session** ist eine Unterhaltung, ein
**Trace** ein Frage-Antwort-Zyklus darin, ein **Span** ein einzelner
Arbeitsschritt
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-telemetry.html)).
Von den Spans wertet der Dienst genau drei Sorten aus
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-telemetry.html)):

| Span-Typ | Kennzeichen | Bei text2SQL |
|---|---|---|
| Invoke agent | `gen_ai.operation.name = invoke_agent` | ein Lauf, von der Frage bis zur Antwort |
| Inference | `gen_ai.operation.name = chat` | ein Modellaufruf – davon gibt es n + 1 |
| Execute tool | `gen_ai.operation.name = execute_tool` | ein Werkzeugaufruf, etwa `run_query` mit dem SQL als Argument |

![Links eine Session mit zwei Traces. Der erste Trace ist aufgeklappt: ein invoke_agent-Span umschließt drei chat-Spans und zwei execute_tool-Spans, schema_fuer_frage und run_query. Der run_query-Span trägt den Werkzeugnamen, das SQL als Argument, die Ergebniszeilen, Status und Dauer. Rechts die drei Bewertungsebenen: SESSION mit Goal success rate, Trajectory-Match und Failure analysis; TRACE mit Correctness, Faithfulness und Helpfulness; TOOL_CALL mit Tool selection accuracy, Tool parameter accuracy und eigenen Prüfungen als Custom-Judge oder Lambda.](/assets/img/eval-trace-ebenen.svg)

Aus diesen Spans zieht der Dienst die Werte, mit denen die Evaluatoren arbeiten:
die Nutzerfrage, die Antwort, den Systemprompt, die Nachrichten jedes
Modellaufrufs, und je Werkzeugaufruf Name, Argumente und Ergebnis
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-generic.html)).
Alles andere im Span – Zeitstempel, Dauer, Status, Token-Zähler – kommt in dem,
was ein Judge vorgelegt bekommt, nicht vor. Es ist trotzdem da, und weiter unten
wird es gebraucht.

Für text2SQL ist das die gute Nachricht dieses Beitrags: **Das SQL ist kein
Zwischenprodukt, das man erst sichtbar machen müsste. Es ist das Argument eines
Werkzeugaufrufs und steht damit als eigener Span im Trace** – zusammen mit dem,
was Athena darauf geantwortet hat.

Wo der Inhalt liegt, hat zwei Spielarten. Bei *unified telemetry* bleiben
Prompts, SQL und Ergebniszeilen am Span, und alles landet in einer Log-Gruppe je
Agent; das ist die Voreinstellung für Agenten, die seit dem 20. Juli 2026
angelegt wurden, und setzt ADOT ab 0.18.0 voraus. Bei *split telemetry* wandern
die Inhalte in eigene Event-Records, die Spans in die gemeinsame Gruppe
`aws/spans`. Der Dienst liest beides; in beiden Fällen braucht er CloudWatch
Transaction Search.

Das Urteil landet dort, wo das Material herkam: als OpenTelemetry-Event mit
Score, Label und Begründung in CloudWatch Logs, wenn möglich an den
ursprünglichen Span gehängt, und als Metrik im Namespace
`Bedrock-AgentCore/Evaluations`
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/results-and-output.html)).
Auf einer Metrik kann ein Alarm sitzen.

## Drei Ebenen, vier Sorten Evaluatoren

Jeder Evaluator arbeitet auf genau einer **Ebene**: `SESSION`, `TRACE` oder
`TOOL_CALL`. Eine Ebene für den einzelnen Modellaufruf gibt es nicht.

Und es gibt vier Sorten, die sich darin unterscheiden, wer urteilt:

| Sorte | Wer urteilt | Was man einstellt |
|---|---|---|
| **Built-in mit Judge** | ein Sprachmodell; Modell und Prompt legt AWS fest | nichts, nur die ID – etwa `Builtin.Faithfulness` |
| **Built-in ohne Modell** | Code von AWS | nichts; die drei `Builtin.Trajectory…Match` |
| **Custom-Judge** | ein Bedrock-Modell eigener Wahl | Anweisung, Skala, Modell, Ebene |
| **Code-based** | eine eigene Lambda-Funktion | alles |

Dazwischen liegen zwei Mischformen. **Drittanbieter-Evaluatoren** aus DeepEval
und AutoEval betreibt AWS wie Built-ins, steht für ihre Qualität aber
ausdrücklich nicht ein
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/third-party-evaluators.html)).
**Abgeleitete Evaluatoren** übernehmen Prompt und Skala eines Built-ins und
laufen auf einem selbst gewählten Modell im eigenen Konto – ein Ausweg, wenn die
regionsübergreifende Inferenz der Built-ins nicht erwünscht ist
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations-cross-region-inference.html)).

Was ein Judge zu sehen bekommt, bestimmen Platzhalter, und die sind je Ebene
fest
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/create-evaluator.html)):

| Ebene | Platzhalter | Inhalt |
|---|---|---|
| `SESSION` | `context`, `available_tools` | alle Fragen, Antworten und Werkzeugaufrufe der Unterhaltung; die verfügbaren Werkzeuge mit Parametern und Beschreibung |
| `TRACE` | `context`, `assistant_turn` | alles Vorherige plus die aktuelle Frage und ihre Werkzeugaufrufe; die zu bewertende Antwort |
| `TOOL_CALL` | `context`, `tool_turn`, `available_tools` | alles bis unmittelbar vor dem Aufruf; der zu bewertende Aufruf; die Werkzeugliste |

Mit Referenz kommen `expected_response` (Trace) sowie `expected_tool_trajectory`,
`actual_tool_trajectory` und `assertions` (Session) hinzu.

Der Kontext wird dem Judge als Protokoll gereicht: `User:`, `Assistant:`,
`Action:` für gewählte Werkzeuge, `Tool:` für deren Ausgaben. **Der Judge liest
also den Trace, nicht nur die Antwort** – einschließlich der Ergebniszeilen von
Athena.

## Was das für text2SQL heißt

Die mitgelieferten Evaluatoren sind allgemein gehalten. Was sie an einem
text2SQL-Agenten tatsächlich prüfen, steht in ihren Prompts, und die sind
veröffentlicht
([Vorlagen](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/prompt-templates-builtin.html)).
Es lohnt, sie zu lesen: Einige tun etwas anderes, als ihr Name verspricht.

**`Builtin.ToolParameterAccuracy` prüft nicht, ob das SQL stimmt.** Die Frage an
den Judge lautet, ob die Parameterwerte aus dem bisherigen Kontext stammen,
*„without hallucinating or fabricating its own values"* – und ausdrücklich nicht,
ob der Aufruf der richtige ist: *„ONLY evaluate whether the parameters used come
from the preceding context."* Für ein SQL-Argument heißt das: Der Evaluator
findet die Spalte, die im Schema nie vorkam, und den Regionscode, den niemand
genannt hat. Er findet nicht `SUM(gross_revenue)`, wo netto gemeint war – die
Spalte steht ja im Schema. Ein Halluzinations-Check, kein Korrektheits-Check.
Das ist enger, als ich es im Judge-Beitrag beschrieben habe. Und es hat eine
Voraussetzung: Der Judge kennt das Schema nur, wenn es in seinem Kontext steht –
sicher also dann, wenn es als Ergebnis eines Werkzeugs wie `schema_fuer_frage`
in den Verlauf kam. Ob ihm auch der Systemprompt vorgelegt wird, sagt die Doku
nicht.

**`Builtin.ToolSelectionAccuracy` hat einen Wiederholungs-Check eingebaut.** Der
Judge soll zuerst alle früheren Werkzeugaufrufe auflisten und prüfen, ob der
aktuelle einen davon mit gleichem Namen und gleichen Argumenten wiederholt. Bei
text2SQL ist das der Agent, der dieselbe Abfrage zweimal stellt.

**`Builtin.Faithfulness` vergleicht die Antwort mit dem Verlauf**, und zum
Verlauf gehören die Tool-Ausgaben. Es fängt den Agenten, der 4,21 Mio. liest und
4,12 schreibt. Den stillen Fehler aus dem Judge-Beitrag – falsches SQL, getreu
wiedergegeben – fängt es konstruktionsbedingt nicht.

**`Builtin.Correctness` mit `expectedResponse` ist Execution Accuracy durch die
Hintertür.** Mit Referenz wechselt der Evaluator den Prompt, und der verlangt
bei Faktenfragen mit einer einzigen richtigen Antwort *„the correct specific
values (names, numbers, dates, locations)"*. Steht im Golden Set „Der Nettoumsatz
in Q3 lag bei 3,58 Mio. €", fällt eine Antwort mit 4,21 Mio. durch – ohne dass
jemand SQL ausführt. Das trägt bei Kennzahlfragen. Bei einer Ergebnistabelle mit
zweihundert Zeilen trägt es nicht mehr.

**Die drei Trajektorie-Evaluatoren brauchen kein Modell.**
`TrajectoryExactOrderMatch`, `InOrderMatch` und `AnyOrderMatch` vergleichen die
tatsächliche Folge der Werkzeugnamen programmatisch mit der erwarteten; der
Token-Verbrauch ist null
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html)).
Für diese Serie ist `ExactOrder` die interessante Variante: Erwartet man
`[schema_fuer_frage, run_query]`, fällt jede Session durch, in der der Agent
`run_query` ein zweites Mal braucht – also genau die zusätzliche Stufe, die nach
der n+1-Regel aus dem
[MCP-Beitrag]({% post_url 2026-06-09-kosten-von-mcp-in-agenten %}) einen
weiteren Modellaufruf kostet. Verglichen werden allerdings nur Namen, nicht
Argumente, und zwar so, wie sie im Trace stehen – hinter einem Gateway also mit
dessen Präfix.

**`Builtin.FailureAnalysis` geht bis auf den Span hinunter.** Der Evaluator
untersucht jeden Span einer Session, hält je Fehler einen Befund mit Span-ID,
Kategorie und Konfidenz fest, sucht die Ursache – die in einem früheren Span
liegen kann – und gruppiert ähnliche Fehler über Sessions hinweg zu Mustern mit
Ursache und Änderungsvorschlag
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/builtin-failure-analysis.html)).
Unter den Kategorien sind einige, die man aus dieser Serie kennt:
Ausführungsfehler wie Timeouts, halluzinierte Parameter, Werkzeugdefinitionen,
die nicht zum Verhalten passen, und **wiederholte Werkzeugaufrufe ohne
Fortschritt** – die Polling-Schleife aus dem MCP-Beitrag. Drei Einschränkungen:
Es gibt ihn nur im Batch, sein Urteil ist eine Einschätzung ohne Referenz, und
der Score ist umgekehrt gepolt – 1,0 heißt „Fehler gefunden".

**Ein Lambda-Evaluator bekommt den ganzen Trace.** Die Funktion erhält alle
Spans der Session als `sessionSpans`, dazu das Ziel (Trace- oder Span-ID) und die
Referenzen, und gibt Label, optional Wert und Erklärung zurück
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-based-evaluators.html)).
Damit wird prüfbar, was im Span steht und kein Judge ansieht: der SQL-Text
(Partitionsfilter gesetzt? `SELECT *`?), der Status des Werkzeugaufrufs, die
Dauer, die Zahl der `chat`-Spans – also die Kettentiefe – und bei Strands die
Token-Zähler samt `gen_ai.usage.cache_read.input_tokens`
([Strands](https://strandsagents.com/docs/user-guide/sdk/observability-evaluation/traces/)).
Ob der Cache aus dem
[Caching-Beitrag]({% post_url 2026-06-28-prompt-caching-pflicht %}) trifft, wird
so zu einer Bewertungsregel. Die Grenzen: höchstens 300 Sekunden Laufzeit und
6 MB Nutzlast – was darüber liegt, wird abgeschnitten.

Für den eigenen SQL-Judge gibt es noch eine Abkürzung: Ein
**Multi-Dimension-Evaluator** bewertet ein Ziel in *einem* Judge-Aufruf auf
mehreren benannten Dimensionen – Tabellenwahl, Filter, Aggregation,
Kennzahldefinition –, jede mit eigener Anweisung und Skala
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/multi-dimension-evaluators.html)).
Der Preis dafür: Scheitert der eine Aufruf, scheitern alle Dimensionen.

Als Landkarte – die Built-ins ohne ihr Präfix `Builtin.`:

| Was will ich wissen? | Womit | Ebene | Wo |
|---|---|---|---|
| Stimmen die Zahlen in der Antwort? | `Correctness` + `expectedResponse` | Trace | offline, mit Referenz |
| Stimmt die Ergebnismenge? | Lambda: Ergebnis aus dem `run_query`-Span gegen ein Golden-Resultset | Tool-Call | offline, mit Referenz |
| Gibt die Antwort das Ergebnis getreu wieder? | `Faithfulness` | Trace | auch online |
| Erfundene Tabellen, Spalten, Filterwerte? | `ToolParameterAccuracy` | Tool-Call | auch online |
| Richtiges Werkzeug, keine Wiederholung? | `ToolSelectionAccuracy` | Tool-Call | auch online |
| Fachlich plausibles SQL – netto statt brutto? | Custom-Judge, Definitionen in der Anweisung | Tool-Call | auch online |
| Erwartete Werkzeugfolge, kein Zusatzversuch? | `TrajectoryExactOrderMatch` | Session | offline, mit Referenz |
| Fragt er nach, wenn der Zeitraum fehlt? | `GoalSuccessRate` + `assertions` | Session | offline, mit Referenz |
| Partitionsfilter, kein `SELECT *`, Kettentiefe, Cache-Treffer? | Lambda | Tool-Call, Session | auch online |
| Welche Fehlermuster gibt es, und wo entstehen sie? | `FailureAnalysis` | Session → Span | nur Batch |

### Was fehlt

Drei Lücken, die man kennen sollte, bevor man plant:

- **Es gibt kein Referenzfeld für SQL oder Ergebnismengen.** Referenzen haben
  genau drei Formen: `expectedResponse` (ein Text je Trace), `assertions` (Sätze
  je Session) und `expectedTrajectory` (Werkzeugnamen). Ein Lambda bekommt sie
  durchgereicht – wer aber ein Golden-SQL oder ein Golden-Resultset vergleichen
  will, muss es als Text in eines dieser Felder legen oder im Lambda anhand der
  Frage aus einem eigenen Speicher holen.
- **Online gibt es keine Referenz.** Evaluatoren mit Referenz-Platzhaltern lässt
  der Dienst in Online-Konfigurationen nicht zu; er erkennt sie schon beim
  Anlegen.
- **Bewertet wird, was das Werkzeug zurückgegeben hat.** Liefert `run_query` die
  ersten 100 von 1 248 Zeilen, sehen Judge und Lambda 100 Zeilen. Was im
  MCP-Server geschieht – Athenas Ausführungs-ID, gescannte Bytes, Wartezeit –,
  kommt bei den Evaluatoren nur an, wenn es im Ergebnis oder als Attribut im
  Span steht.

## Wann bewertet wird

Vier Betriebsarten. Sie unterscheiden sich vor allem darin, wer die Spans
einsammelt und ob eine Referenz mitkommen darf
([Vergleich](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations.html)):

| | On-demand | Dataset-Runner (Preview) | Batch | Online |
|---|---|---|---|---|
| Auslöser | ein API-Aufruf, synchron | das SDK ruft den Agenten je Szenario auf, wartet, bewertet | ein Job, asynchron | laufend |
| Spans | bringt der Aufrufer mit | sammelt das SDK oder der Dienst | findet der Dienst in CloudWatch | liest der Dienst aus Log-Gruppe oder Endpunkt |
| Umfang | eine Session, ein Evaluator, bis 10 Ergebnisse | ein Golden Set | bis 500 Sessions, 10 Evaluatoren | Stichprobe, voreingestellt 10 %; bis 25 Evaluatoren |
| Referenz | ja | ja, aus dem Dataset | ja, je Session | nein |
| Ergebnis | sofort in der Antwort | je Szenario oder aggregiert | Mittelwert je Evaluator, Details in CloudWatch | Logs, Metriken, Dashboard |
| Wofür | Evaluator ausprobieren, eine Session untersuchen | Release-Pipeline | Vorher-nachher, Regression, Fehleranalyse | Monitoring |

Das Dataset-Format passt auf text2SQL fast ohne Umbau: je Szenario die Fragen
als `turns` mit optionaler `expected_response`, dazu `expected_trajectory` und
`assertions`
([Schema](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations-schema.html))
– drei der vier Teile, die das Golden Set im Judge-Beitrag hatte. Der vierte,
das Referenz-SQL, hat kein Feld; siehe oben. Statt fester Fragen kann auch ein
Modell den Nutzer spielen (*User simulation*); dann gelten als Referenz nur
Zusicherungen.

Zwei Zeitangaben gehören dazu. Nach einem Lauf dauert es zwei bis fünf Minuten,
bis CloudWatch die Telemetrie aufgenommen hat; die Dataset-Runner warten deshalb
voreingestellt 180 Sekunden. Und Online bewertet eine Session erst, wenn sie
abgeschlossen ist – wenn also 15 Minuten lang (einstellbar von 1 bis 60) keine
Anfrage mehr kam; danach vergehen typischerweise noch einmal bis zu 15 Minuten
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ab-testing-target-based.html)).

**Bewertung ist Monitoring, kein Schutz.** Sie verhindert keine falsche Antwort,
sie zählt sie. Wer verhindern will, braucht etwas, das *vor* dem Werkzeugaufruf
sitzt: in der eigenen Schleife einen Hook im Code, beim Harness die
Lifecycle-Hooks, deren `before_tool_call` einen Aufruf per Lambda ablehnen kann.
Die führt AWS' Vergleichstabelle inzwischen; als der AgentCore-Beitrag entstand,
stand dort noch „keine Hooks".

## Weg 1: nativ im AgentCore harness

Beim Harness gehört die Schleife AWS, und mit ihr die Telemetrie: *„Every
harness invocation automatically generates traces, logs, and metrics through
AgentCore Observability in CloudWatch. […] No extra configuration."*
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-operations.html)).
In der Vergleichstabelle der Doku ist Observability eine der Zeilen, in denen
der Harness „Yes" ohne eigenen Code hat und die Runtime „Custom"
([harness vs. Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html)).

Was zu tun bleibt, ist wenig:

1. **Transaction Search** in CloudWatch einschalten, einmal je Konto.
   `agentcore deploy` erledigt das.
2. **Evaluatoren wählen** und starten. Für Batch nimmt die CLI die Harness-ID
   direkt entgegen und löst Log-Gruppe und Service-Namen selbst auf
   ([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations-start.html));
   eine Online-Konfiguration braucht dieselben beiden Angaben, eine Liste von
   Evaluatoren, eine Sampling-Rate und eine Ausführungsrolle.
3. **Custom-Evaluatoren** für das bauen, was die Built-ins nicht abdecken. Das
   ist auf beiden Wegen dieselbe Arbeit.

Session-ID, Log-Gruppe, Export: alles vorhanden, weil der Harness auf der
Runtime läuft.

Der native Weg hat einen zweiten Vorteil, und er liegt hinter der Bewertung.
**AgentCore optimization** baut auf den Evaluatoren auf: *Recommendations*
erzeugen aus Traces und einem Ziel-Evaluator einen überarbeiteten Systemprompt
oder schärfere Werkzeugbeschreibungen; *A/B-Tests* teilen den Verkehr über das
Gateway und melden je Evaluator Mittelwert, p-Wert und Konfidenzintervall
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization.html)).
Beim Harness ist der Systemprompt Konfiguration – ein Vorschlag lässt sich
einspielen, ohne Code anzufassen.

Was man auf diesem Weg nicht in der Hand hat, ist der Inhalt des Trace. Eigene
Attribute an einem Span setzt man in der Schleife, und die gehört beim Harness
AWS.

## Weg 2: Converse + MCP

Hier gehört die Schleife einem selbst, und damit auch die Frage, woher die Spans
kommen. Die erste Erkenntnis ist ernüchternd: **Die Converse-API und MCP
erzeugen von sich aus nichts, was der Dienst bewertet.** Es gibt automatische
OpenTelemetry-Instrumentierung für beide – für `botocore` samt `bedrock-runtime`
und für MCP. Genau diese Scopes schließt die Doku aus, damit sie keine
*„spurious agent, tool, or inference spans"* erzeugen
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-generic.html)).
Ein Converse-Aufruf ist für den Dienst kein Modellaufruf, solange niemand einen
`chat`-Span darum legt. Wer das tut, hängt an der Bauart der Schleife.

### Mit Strands

Der Weg aus dem AgentCore-Beitrag. Strands bringt die Telemetrie mit: Ein Agent
erzeugt `invoke_agent`-, `chat`- und `execute_tool`-Spans unter dem Scope
`strands.telemetry.tracer`, ohne zusätzliche Bibliothek
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-strands.html)).
Auch der Aufruf eines MCP-Werkzeugs läuft durch die Werkzeugausführung von
Strands und bekommt seinen `execute_tool`-Span – auf der Seite des Clients,
nicht im MCP-Server.

Es fehlt nur der Export: `aws-opentelemetry-distro` ab 0.18.0 als Abhängigkeit
und der Start über `opentelemetry-instrument python main.py`
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)).
Der Rest hängt am Hosting:

- **Auf der AgentCore Runtime** setzt die Runtime die `session.id` und
  exportiert in die Log-Gruppe des Agenten. Mehr ist es nicht.
- **Außerhalb** – Fargate, EKS, Lambda – kommen vier Dinge dazu: eine eigene
  Log-Gruppe; ein Satz Umgebungsvariablen (`AGENT_OBSERVABILITY_ENABLED=true`,
  `OTEL_RESOURCE_ATTRIBUTES` mit dem `service.name`,
  `OTEL_EXPORTER_OTLP_TRACES_HEADERS` mit der Log-Gruppe); eine Resource Policy,
  die X-Ray das Schreiben in diese Log-Gruppe erlaubt; und die Session-ID, die
  man selbst als OpenTelemetry-Baggage `session.id` setzt. Die Bewertung ist
  durchgehend nach Sessions organisiert – fehlt die ID, fehlt der Anker.

### Mit einer handgeschriebenen Schleife

Wer die Converse-Schleife selbst schreibt, schreibt auch die Spans. Der Dienst
nimmt jeden Agenten, der sich an eine von zwei Konventionen hält – OpenTelemetry
GenAI oder OpenInference –, und verlangt drei Dinge:

1. einen **Scope-Namen** mit dem Präfix `opentelemetry.instrumentation.` (oder
   `openinference.instrumentation.`),
2. auf jedem Span das **Kennzeichen** `gen_ai.operation.name`,
3. die **Inhalte in den dokumentierten Attributen** – nicht in einer eigenen
   Hülle, denn der Dienst liest sie als Zeichenkette, ohne sie zu zerlegen.

Als Skizze, abgeleitet aus der Attributliste der Doku und nicht ausgeführt:

```python
tracer = trace.get_tracer("opentelemetry.instrumentation.text2sql_agent")
span = tracer.start_as_current_span

# Außerhalb der Runtime vorher: session.id als Baggage setzen.
with span("invoke_agent text2sql") as lauf:
    lauf.set_attribute("gen_ai.operation.name", "invoke_agent")
    lauf.set_attribute("gen_ai.task.input", frage)

    while True:
        with span("chat") as modell:
            modell.set_attribute("gen_ai.operation.name", "chat")
            modell.set_attribute("gen_ai.system_instructions", systemprompt)
            modell.set_attribute("gen_ai.input.messages", json.dumps(verlauf))
            antwort = bedrock.converse(...)                    # Converse
            modell.set_attribute("gen_ai.output.messages",
                                 json.dumps(antwort["output"]))

        if antwort["stopReason"] != "tool_use":
            break

        for aufruf in tool_uses(antwort):
            name, args = aufruf["name"], json.dumps(aufruf["input"])
            with span(f"execute_tool {name}") as werkzeug:
                werkzeug.set_attribute("gen_ai.operation.name", "execute_tool")
                werkzeug.set_attribute("gen_ai.tool.name", name)
                werkzeug.set_attribute("gen_ai.tool.call.arguments", args)
                ergebnis = mcp.call_tool(name, aufruf["input"])  # MCP
                werkzeug.set_attribute("gen_ai.tool.call.result", ergebnis)

    lauf.set_attribute("gen_ai.task.output", antworttext(antwort))
```

Der Werkzeug-Span ist die Stelle, an der die Bewertung des SQL hängt: Ohne
`gen_ai.tool.call.arguments` gibt es für keinen Evaluator auf Tool-Ebene etwas
zu lesen.

Es gibt eine Abkürzung, und sie ist eine Sackgasse. Setzt man nur
`agentcore.invocation.user_prompt` und `agentcore.invocation.agent_response`,
bewertet der Dienst die Antwort – *„the agent prompt and response only, not
inference or tool spans"*. Für text2SQL heißt das: keine Tool-Ebene, keine
Trajektorie, Faithfulness ohne Tool-Ausgabe. Also genau die Hälfte, um die es
geht.

### Was beiden Varianten gemeinsam ist

Außerhalb der Runtime zeigt eine Online-Konfiguration nicht auf einen
Agent-Endpunkt, sondern auf Log-Gruppe und Service-Namen – den aus
`OTEL_RESOURCE_ATTRIBUTES`
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/create-online-evaluations.html)).
Die Dataset-Runner des SDK sind neutral gebaut: Sie verlangen einen
`agent_invoker`, und der darf den Agenten per `invoke_agent_runtime`, per HTTP
oder als Funktionsaufruf ansprechen
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations-on-demand.html)).
Selbst A/B-Tests gehen, wenn der Agent als Gateway-Ziel registriert ist
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ab-testing-3p-agents.html)).
Und wenn trotz allem keine Scores erscheinen – typische Meldungen sind
`LogEventMissingException` und `ToolSpanMappingException` –, liefert AWS einen
Diagnose-Skill für Coding-Assistenten mit
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/diagnose-evaluation-issues.html)).

Dazu kommt ein Vorteil, den der Harness nicht hat: **Wer die Spans schreibt,
bestimmt, was ein Lambda-Evaluator prüfen kann.** Die Athena-Ausführungs-ID, die
gescannten Bytes, die Trefferliste der Schemasuche – ein zusätzliches Attribut
am Werkzeug-Span, und es steht für jede Regelprüfung bereit.

## Die beiden Wege nebeneinander

![Links zwei Wege, einen Agenten zu bauen. Weg 1, nativ: Der AgentCore harness erzeugt Spans automatisch. Weg 2, Converse + MCP mit eigener Schleife: Mit Strands ist die Telemetrie eingebaut und braucht nur ADOT; bei einer handgeschriebenen Schleife setzt man die drei Span-Typen invoke_agent, chat und execute_tool selbst, automatische botocore- und MCP-Spans wertet der Dienst nicht aus. Beide Wege schreiben nach Amazon CloudWatch mit Transaction Search. AgentCore Evaluations liest die Spans, ordnet sie ein, übersetzt sie in ein einheitliches Format und bewertet auf den Ebenen Session, Trace und Tool-Call mit LLM-Judges, Code ohne Modell und Musteranalyse. Die Ergebnisse gehen als OpenTelemetry-Events und Metriken zurück nach CloudWatch.](/assets/img/eval-zwei-wege.svg)

| | Harness (nativ) | Eigene Schleife mit Strands | Handgeschriebene Converse-Schleife |
|---|---|---|---|
| Spans erzeugen | AWS, automatisch | Strands, eingebaut | selbst: drei Span-Typen, GenAI-Attribute |
| Export nach CloudWatch | AWS | ADOT-Paket und Startbefehl | ADOT-Paket und Startbefehl |
| Session-ID | Runtime | Runtime – außerhalb: Baggage | Runtime – außerhalb: Baggage |
| Log-Gruppe und Service-Name | löst die CLI aus der Agent-ID auf | Runtime: ebenso – außerhalb: selbst anlegen und angeben | wie Strands |
| Golden Set abspielen | SDK-Runner mit eigenem Aufrufer | SDK-Runner; auf der Runtime auch per CLI | wie Strands |
| Eigene Attribute im Span | nicht vorgesehen | ja | ja |
| Recommendations einspielen | Konfiguration | Code oder Configuration Bundle | Code oder Configuration Bundle |
| Evaluatoren, Ebenen, Betriebsarten, Preise | gleich | gleich | gleich |

## Was es kostet

Die Preise sind auf beiden Wegen dieselben
([Preisseite](https://aws.amazon.com/bedrock/agentcore/pricing/)):
Built-in-Evaluatoren 2,40 $ je Million Input- und 12 $ je Million Output-Token,
Modell inklusive; Custom-Evaluatoren 1,50 $ je 1 000 Bewertungen plus das
Judge-Modell im eigenen Konto. Batch-Bewertungen kosten 25 % weniger: 1,80 $
und 9 $ je Million Token. Mit dem Profil aus dem Judge-Beitrag – 6 000 Token
hinein, 400 heraus – sind das 14,40 $ statt 19,20 $ je 1 000
Built-in-Bewertungen. Die Trajektorie-Evaluatoren verbrauchen keine Token.

Der text2SQL-eigene Kostentreiber steht in der Platzhaltertabelle oben: **Der
Kontext des Judges enthält die Tool-Ausgaben.** Ein Resultset, das der Agent im
Verlauf trägt, liest auch jeder Judge, der diesen Trace bewertet – bei Built-ins
zum Token-Preis, gedeckelt bei 200 000 Input-Token je Bewertung
([Quotas](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)).
AWS' eigenes Rechenbeispiel geht von 15 000 Input-Token je Bewertung aus. Das
Zeilenlimit im Werkzeug aus dem
[Format-Beitrag]({% post_url 2026-04-21-mcp-ausgabeformate %}) spart also
zweimal: beim Agenten und bei seinem Prüfer.

## Worauf es ankommt

| Wenn … | dann |
|---|---|
| der Agent im Harness läuft | ist die Telemetrie da; die Arbeit beginnt bei den Evaluatoren |
| die Schleife Strands ist und auf der Runtime läuft | eine Abhängigkeit, ein Startbefehl – danach wie nativ |
| die Schleife Strands ist und auf Fargate läuft | zusätzlich Log-Gruppe, Umgebungsvariablen, Resource Policy, Session-ID per Baggage |
| die Converse-Schleife handgeschrieben ist | drei Span-Typen selbst setzen; die automatische `botocore`-Instrumentierung zählt nicht |
| nur Frage und Antwort im Trace stehen | lässt sich die Antwort bewerten – nicht das SQL, nicht der Weg |
| das SQL bewertet werden soll | muss es als Argument in einem `execute_tool`-Span stehen |
| Richtigkeit gemessen werden soll | offline und mit Referenz: `Correctness` + `expectedResponse`, für Ergebnismengen ein Lambda |
| nur Produktionsverkehr vorliegt | Halluzination, Treue, Regeln, Plausibilität – nicht Richtigkeit |
| eine falsche Abfrage verhindert werden soll | ist Bewertung das falsche Werkzeug; das ist ein Hook vor dem Werkzeugaufruf |
| Resultsets groß sind | zahlt der Judge sie mit – Zeilenlimit im Werkzeug |

## Was ich daraus schließe

**Die Frage „nativ oder Converse + MCP" entscheidet nicht, was sich bewerten
lässt, sondern wer die Spur legt.** Evaluatoren, Ebenen, Betriebsarten und
Preise sind auf beiden Wegen identisch, weil der Dienst nur die Spans in
CloudWatch sieht – nicht, wer die Schleife betreibt. Der Harness nimmt einem die
Instrumentierung ab. Die eigene Schleife kostet sie – mit Strands auf der Runtime eine
Abhängigkeit und einen Startbefehl, außerhalb der Runtime einen Nachmittag,
handgeschrieben etwas mehr – und gibt dafür die Kontrolle darüber, was im Span
steht. Die Empfehlung aus dem AgentCore-Beitrag, eigener Code auf der Runtime,
verliert bei der Bewertung nichts Wesentliches.

**Für text2SQL liegt der Wert des Dienstes eine Ebene tiefer, als sein Name
nahelegt.** Nicht die Antwort ist das Interessante, sondern der
`run_query`-Span: Dort steht das SQL, dort steht das Ergebnis, und dort setzen
die Prüfungen an, die für diesen Agenten zählen – erfundene Spalten,
wiederholte Abfragen, fehlende Partitionsfilter, die Kettentiefe. Die Antwort zu
bewerten, ohne den Weg zu sehen, ist der stille Fehler mit besserem Dashboard.

Anfangen würde ich so:

- **Im Release**, auf einem Golden Set über den Dataset-Runner:
  `TrajectoryExactOrderMatch` (kein Modell), `Correctness` mit erwarteter
  Antwort, `GoalSuccessRate` mit Zusicherungen, und ein Lambda für die
  Ergebnismenge.
- **In Produktion**, auf einer Stichprobe: `ToolParameterAccuracy`,
  `Faithfulness`, ein Custom-Judge für das SQL mit den Kennzahldefinitionen in
  der Anweisung, und ein Lambda für die Regeln.
- **Regelmäßig**, als Batch über die jüngsten Produktionssessions:
  `FailureAnalysis` zusammen mit `GoalSuccessRate` – nicht als Urteil, sondern
  als Liste der Stellen, an denen ein Mensch hinsehen sollte.

## Methodik und Vorbehalte

Nichts hier ist gemessen oder ausgeführt. Der Beitrag gibt die
AWS-Dokumentation vom 10. November 2026 wieder und zieht Schlüsse daraus; die
Codeskizze ist aus der Attributliste abgeleitet, nicht getestet. Dataset
evaluation ist als Public Preview gekennzeichnet, ihre Schnittstellen können
sich ändern.

Fünf Dinge habe ich nicht belegen können und sage das lieber, als es zu
überspielen:

- ob `tool_turn` neben Name und Argumenten auch das Ergebnis des
  Werkzeugaufrufs enthält – die Doku nennt nur *„the tool call under
  evaluation"*;
- ob der Systemprompt Teil von `context` ist. Für einen Agenten, dessen Schemata
  im Systemprompt stehen, entscheidet das, ob `ToolParameterAccuracy` echte
  Spalten für erfunden hält;
- unter welchem Scope der Harness seine Spans schreibt; dass sie entstehen und
  die Batch-CLI sie findet, steht in der Doku, das Wie nicht;
- ob ein Lambda-Evaluator wie ein Custom-Evaluator mit 1,50 $ je 1 000
  Bewertungen abgerechnet wird – die Preisseite nennt ihn nicht eigens;
- ob das freie `metadata`-Feld eines Dataset-Szenarios beim Evaluator ankommt.
  Wenn ja, wäre es der natürliche Platz für das Referenz-SQL.

Und eine Unstimmigkeit: Die Preisseite spricht von 13 Built-in-Evaluatoren, die
Vorlagenseite führt 17 Prompts, dazu kommen die drei Trajektorie-Evaluatoren
und die Fehleranalyse. Ich habe mich an die Dokumentation gehalten.

---

**Kurzfassung:** AgentCore Evaluations bewertet nicht den Agenten, sondern
seine OpenTelemetry-Spans in CloudWatch – auf drei Ebenen: Session, Trace und
einzelner Werkzeugaufruf. Bei text2SQL steht das SQL als Argument im
`run_query`-Span und ist damit selbst bewertbar, samt dem Ergebnis von Athena.
Die Built-ins prüfen dabei enger, als ihre Namen klingen:
`ToolParameterAccuracy` findet erfundene Spalten, nicht falsche Kennzahlen;
`Faithfulness` findet falsch wiedergegebene, nicht falsch berechnete Zahlen.
Richtigkeit gibt es nur offline und mit Referenz – `Correctness` mit erwarteter
Antwort, Trajektorie-Vergleich ohne Modell, für Ergebnismengen ein Lambda, das
den ganzen Trace bekommt. Online bleibt, was sich ohne Wahrheit prüfen lässt.
Zwischen nativem Harness und eigener Schleife aus Converse und MCP unterscheidet
sich nicht, was bewertet werden kann, sondern wer die Spans erzeugt: Der Harness
tut es automatisch, Strands mit einem Paket und einem Startbefehl, eine
handgeschriebene Schleife setzt die drei Span-Typen selbst – denn die
automatischen `botocore`- und MCP-Spans wertet der Dienst nicht aus.
