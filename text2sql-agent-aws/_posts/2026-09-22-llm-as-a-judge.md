---
layout: post
title: "LLM-as-a-Judge: Die Entscheidungen des Agenten bewerten"
title_en: "LLM-as-a-Judge: Evaluating the Agent's Decisions"
date: 2026-09-22 10:00:00 +0200
serie: "text2SQL-Agent auf AWS"
---

Jeder Beitrag dieser Serie hat etwas optimiert: das Ausgabeformat, die Länge der
Werkzeugketten, den Cache, den Verlauf. Keiner hat gemessen, ob der Agent
überhaupt richtig antwortet. Das ist die Lücke, um die es hier geht.

Bei text2SQL ist „richtig" schwerer zu fassen, als es klingt. Zwei völlig
verschiedene Abfragen können dasselbe Ergebnis liefern. Dieselbe Abfrage mit
anderer Sortierung liefert ein scheinbar anderes. Und eine falsche Abfrage
liefert eine Zahl, die genauso plausibel aussieht wie die richtige.

## Drei Dinge, die man messen kann

Wer „den Agenten bewerten" will, bewertet in Wahrheit drei verschiedene Dinge,
und sie brauchen verschiedene Werkzeuge:

| Was | Frage | Womit | Ebene |
|---|---|---|---|
| **Ergebnis** | Liefert das SQL die richtigen Zahlen? | Ausführen und mit Referenz vergleichen | Trace |
| **Entscheidungsweg** | Richtige Tabelle, richtige Werkzeuge, wenige Schritte, Rückfrage bei Unklarheit? | Trajektorie gegen Erwartung | Session / Werkzeugaufruf |
| **Antwort** | Gibt der Text das Ergebnis korrekt wieder? | Antwort gegen Tool-Output | Trace |

Die erste Zeile hat einen etablierten Namen: **Execution Accuracy**. Man führt das
erzeugte SQL und ein Referenz-SQL aus und vergleicht die Ergebnismengen. Das ist
deterministisch, braucht kein Sprachmodell und ist das Rückgrat jeder
text2SQL-Bewertung.

Es ist aber nicht fehlerfrei. Eine zusätzliche Spalte, eine andere Rundung, eine
andere Reihenfolge — schon gilt eine inhaltlich richtige Abfrage als falsch.
Umgekehrt kann eine falsche Abfrage „richtig" sein, weil die Testdaten den Fehler
zufällig verdecken: ein fehlender Regionsfilter fällt nicht auf, wenn in den
Daten nur eine Region steht. Die FLEX-Arbeit (Kim et al., NAACL 2025) hat das
gegen Expertenurteile gemessen: Execution Accuracy erreicht ein Cohens Kappa von
**62**, ein LLM-Judge, der Frage, Schema und Fachwissen sieht, **87**
([FLEX](https://aclanthology.org/2025.naacl-long.228/)). Die Rangfolge der Modelle
auf Spider und BIRD verschiebt sich dadurch.

Daraus folgt die Arbeitsteilung, um die sich dieser Beitrag dreht:
**zuerst deterministisch vergleichen, und den Judge dort einsetzen, wo der
Vergleich nicht entscheiden kann.**

## Der stille Fehler

Der naheliegende Schritt — ein Sprachmodell liest Frage und Antwort und urteilt,
ob sie stimmt — hat bei text2SQL einen blinden Fleck, und er ist konstruktionsbedingt.

![Zwei Zeilen. Oben ein Judge ohne Referenz: Der Agent schreibt SUM(gross_revenue) statt netto, Athena liefert 4,21 Millionen, die Antwort gibt 4,21 Millionen wieder, und der Judge bewertet sie als Perfectly Correct, weil sie zum Tool-Output passt. Unten ein Judge mit Referenz: Das Golden SQL mit SUM(net_revenue) liefert 3,58 Millionen, der Vergleich ergibt eine Abweichung und das Urteil FAIL.](/assets/img/judge-stiller-fehler.svg)

Der eingebaute Correctness-Evaluator von AgentCore Evaluations enthält in seinem
Prompt den Satz: *„The tool output ALWAYS takes priority over your own
knowledge."* Das ist für die meisten Agenten die richtige Regel — der Judge soll
nicht sein eigenes Weltwissen gegen eine frische Datenbankabfrage ausspielen.
Für text2SQL heißt es aber: Wenn das SQL falsch war, ist der Tool-Output falsch,
die Antwort gibt ihn getreu wieder, und der Judge bewertet sie als korrekt.

**Ein Judge ohne Referenz misst Konsistenz, nicht Richtigkeit.** Konsistenz ist
notwendig — eine Antwort, die dem eigenen Ergebnis widerspricht, ist sicher
falsch. Hinreichend ist sie nicht.

Das Problem ist nicht neu. In der MT-Bench-Arbeit (Zheng et al., NeurIPS 2023)
bewertete GPT-4 einfache Matheaufgaben falsch, *obwohl es sie selbst lösen
konnte* — es ließ sich von der vorgelegten Antwort in die Irre führen. Mit einer
Referenzlösung im Prompt fiel die Fehlerquote von **14 von 20 auf 3 von 20**
([MT-Bench](https://arxiv.org/abs/2306.05685)). Bei text2SQL ist das
vorgelegte SQL dieselbe Falle: Wer es liest, wird von ihm geleitet.

## Wie stark muss der Judge sein?

Die Frage „besseres oder billigeres Modell als der Generator?" hat eine klare
Antwort, aber sie hängt an einer anderen Frage: **Hat der Judge eine Referenz?**

**Mit Referenz reicht ein kleines Modell.** Der Judge muss die Aufgabe dann nicht
lösen, sondern zwei Dinge vergleichen: das erzeugte gegen das Referenz-SQL, das
erwartete gegen das tatsächliche Werkzeugprotokoll. Vergleichen ist leichter als
Erzeugen. AWS setzt in den eigenen Beispielen für Ground-Truth-Evaluatoren
Claude Haiku 4.5 mit `temperature = 0` ein — nicht das stärkste verfügbare
Modell, sondern das billigste, das den Vergleich zuverlässig schafft.

**Ohne Referenz muss der Judge die Aufgabe selbst beherrschen.** Er muss
entscheiden, ob `SUM(gross_revenue)` die richtige Antwort auf die Frage ist, und
das kann er nur, wenn er es selbst besser weiß. Die Forschung ist hier
ernüchternd: Auf JudgeBench liegen starke Modelle wie GPT-4o bei schwierigen
Antwortpaaren kaum über Zufall
([JudgeBench](https://arxiv.org/abs/2410.12784)); in *Judging the Judges*
erreichen nur die größten Modelle eine brauchbare Übereinstimmung mit Menschen,
und selbst die bleiben deutlich unter der Übereinstimmung von Menschen
untereinander ([Thakur et al.](https://arxiv.org/abs/2406.12624)). Ein Judge
ohne Referenz sollte mindestens so stark sein wie der Generator.

**Und er sollte nicht der Generator sein.** Sprachmodelle erkennen ihre eigenen
Texte und bevorzugen sie; Panickssery et al. fanden einen linearen Zusammenhang
zwischen Selbsterkennung und Selbstbevorzugung
([2024](https://arxiv.org/abs/2404.13076)). In MT-Bench gaben GPT-4 und Claude-v1 sich selbst
eine um 10 bzw. 25 % höhere Siegquote als menschliche Bewerter — die Autoren
halten das bei ihrer Datenmenge allerdings noch nicht für belastbar. Wer Claude Sonnet 5 als Generator betreibt und ohne
Referenz bewerten will, nimmt ein anderes Modell — auf Bedrock notfalls aus einer
anderen Familie.

**Vor allem braucht er dasselbe Wissen.** Im
[Domänenwissen-Beitrag]({% post_url 2026-09-11-domaenenwissen-mcp-oder-rag %})
ging es um die zwanzig Prozentpunkte, die ein Satz Fachwissen auf BIRD ausmacht.
Für den Judge gilt dieselbe Rechnung: Ein Judge, der nicht weiß, dass „Umsatz"
netto gemeint ist, bewertet das Brutto-SQL als korrekt — und zwar ganz
unabhängig davon, wie groß er ist.

Daraus ergibt sich für diesen Agenten folgende Aufteilung:

| Aufgabe | Referenz | Judge | Warum |
|---|---|---|---|
| Ergebnismengen vergleichen | Golden-Resultset | **kein Modell** — Code | deterministisch, billig, reproduzierbar |
| SQL-Äquivalenz, wo das Ergebnis abweicht | Golden-SQL | **Haiku 4.5**, `temperature = 0` | Vergleich, nicht Lösung |
| Trajektorie gegen Erwartung | erwartete Werkzeugfolge | **Haiku 4.5** | Listenvergleich |
| Plausibilität in Produktion | keine | **Opus 5** oder andere Familie, Definitionen im Prompt | muss die Aufgabe selbst lösen |

Und bevor man einem Judge vertraut, misst man ihn: fünfzig bis hundert Fälle von
Menschen bewerten lassen und die Übereinstimmung mit Cohens Kappa angeben, nicht
in Prozent. Prozentuale Übereinstimmung sieht auch dann gut aus, wenn der Judge
fast alles durchwinkt — genau davor warnen Thakur et al.

## Ein eigenes Golden Set

Öffentliche Benchmarks helfen hier wenig, und das nicht nur, weil sie nicht den
eigenen Data Lake abbilden. Eine Untersuchung von 2026 hat die Annotationen von
BIRD und Spider 2.0-Snow geprüft und Fehlerquoten von **52,8 %** und **66,1 %**
gefunden; nach der Korrektur sprang ein Agent von Platz 4 auf Platz 1
([Jin et al.](https://arxiv.org/abs/2601.08778)). Wer seinen Agenten an einem
Benchmark misst, misst zu einem guten Teil die Fehler des Benchmarks.

Das eigene Golden Set besteht aus echten Fragen, und jede hat vier Teile: das
Referenz-SQL, das erwartete Ergebnis, die erwartete Werkzeugfolge und
Zusicherungen in Worten — etwa „fragt nach, wenn kein Zeitraum genannt ist".
Abgenommen wird es vom Fachbereich, nicht vom Entwickler. Sonst misst man, ob
der Agent so denkt wie der, der ihn gebaut hat.

Bleibt die Frage aus dem Entwurf dieses Beitrags: **Wie viele Fragen braucht
es, bis eine Verbesserung kein Rauschen mehr ist?**

![Liniendiagramm: nachweisbarer Unterschied in Prozentpunkten über die Anzahl Golden-Fragen. Gepaart, also dieselben Fragen für beide Versionen: 18,2 Punkte bei 50 Fragen, 10,6 bei 100, 6,3 bei 200, 3,9 bei 400, 2,5 bei 800. Ungepaart: 22,4 bei 50, 15,8 bei 100, 11,2 bei 200, 7,9 bei 400, 5,6 bei 800, 2,8 bei 3200. Drei Punkte sind gepaart ab etwa 600 Fragen nachweisbar, ungepaart erst ab etwa 2800 je Version.](/assets/img/judge-stichprobe.svg)

Mehr, als man hofft. Mit hundert Fragen lässt sich eine Verbesserung von zehn
Prozentpunkten belegen, nicht von drei. Für drei Punkte braucht es rund **600**
Fragen — und das nur, wenn beide Versionen über **dieselben** Fragen laufen und
man die Fragen zählt, die kippen. Vergleicht man stattdessen getrennte
Stichproben, etwa zwei Wochen Produktionsverkehr, sind es rund **2 800 je
Version**. Die praktische Regel: Änderungen immer gepaart auf demselben Set
vergleichen, und kleinen Unterschieden auf kleinen Sets misstrauen.

## Exkurs: Amazon Bedrock AgentCore Evaluations

AWS hat für genau diesen Zweck einen eigenen Dienst gebaut. AgentCore
Evaluations ist seit dem **31. März 2026** allgemein verfügbar, auch in Frankfurt
([Ankündigung](https://aws.amazon.com/about-aws/whats-new/2026/03/agentcore-evaluations-generally-available)).
Er liest die OpenTelemetry-Traces eines Agenten aus CloudWatch, übersetzt sie in
ein einheitliches Format und bewertet sie mit LLM-as-a-Judge auf drei Ebenen:
ganze Session, einzelner Trace, einzelner Werkzeugaufruf
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html)).

Mitgeliefert sind gut ein Dutzend **Built-in-Evaluatoren**, deren Modell und
Prompt fest sind: Goal success rate und Correctness (jeweils auch mit Ground
Truth), Faithfulness, Helpfulness, Instruction following, Coherence, Conciseness,
Response relevance, dazu Harmfulness, Stereotyping und Refusal — und für den
Entscheidungsweg **Tool selection accuracy** und **Tool parameter accuracy**. Bei
einem text2SQL-Agenten ist der Parameter des Werkzeugs das SQL selbst; die
Tool-Parameter-Bewertung ist damit eine Bewertung der Abfrage — mit genau den
Grenzen, die oben beschrieben sind.

**Custom-Evaluatoren** sind der interessantere Teil. Man wählt das Judge-Modell
frei aus den Foundation-Modellen auf Bedrock, schreibt die Anweisung selbst,
definiert die Skala und bekommt Platzhalter für Kontext, Antwort, Werkzeugaufruf —
und für Ground Truth: `expected_response`, `expected_tool_trajectory` und
`assertions`
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/create-evaluator.html)).
Statt eines Modells kann auch eine **Lambda-Funktion** urteilen, die die Spans
der Session und die Referenzen bekommt — deterministische Prüfungen ohne Judge.
Die Empfehlungen von AWS für eigene Judges decken sich mit dem Stand der
Forschung: mit einer binären Skala anfangen, ein bis drei Beispiele in die
Anweisung, ein Evaluator pro Dimension, und die Begründung vor dem Score — die
erzwingt der Dienst selbst.

Es gibt drei Betriebsarten, und die Grenze zwischen ihnen ist die Referenz.
**Online** bewertet einen Anteil des Produktionsverkehrs, etwa zehn Prozent der
Sessions — aber ohne Ground Truth; Evaluatoren mit Referenz-Platzhaltern lässt
der Dienst dort gar nicht zu. **On-Demand** und **Batch** bewerten ausgewählte
oder alle Sessions eines Zeitraums, Batch auch mit Referenzen. Ein
**Dataset-Runner** (noch Preview) spielt ein Golden Set ab, wartet auf die
Telemetrie und bewertet — das ist der Baustein für die Release-Pipeline.

Die Preise: Built-in-Evaluatoren kosten 2,40 $ je Million Input- und 12 $ je
Million Output-Token, Modell inklusive; Custom-Evaluatoren 1,50 $ je tausend
Bewertungen plus das Judge-Modell
([Preise](https://aws.amazon.com/bedrock/agentcore/pricing/)).

## Und bei Converse + MCP?

Im [AgentCore-Beitrag]({% post_url 2026-09-11-bedrock-agentcore-vs-converse-mcp %})
fiel die Entscheidung gegen den AgentCore-Harness: Die Schleife bleibt in eigener
Hand, Converse plus MCP, weil fast alle Hebel dieser Serie in ihr sitzen. Die
naheliegende Befürchtung ist, dass man sich damit auch AgentCore Evaluations
verbaut. **Das ist nicht so.** Der Dienst bewertet Traces, nicht den Harness; die
Doku sagt ausdrücklich, er könne Agenten bewerten, *„hosted under AgentCore
Runtime as well as AI agents hosted outside of AgentCore"*
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/how-it-works-evaluations.html)).

Was es braucht, ist saubere Telemetrie, und hier liegt die eigentliche Arbeit:

- **Mit Strands als Schleife** — der Weg aus dem AgentCore-Beitrag — ist nichts
  weiter zu tun. Strands ist eines der direkt unterstützten Frameworks.
- **Mit einer handgeschriebenen Converse-Schleife** greift die generische
  Unterstützung: Spans nach den OpenTelemetry-GenAI-Konventionen, mit
  `gen_ai.operation.name` = `invoke_agent`, `chat` und `execute_tool`
  ([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-generic.html)).
  Die Falle: Die automatische Instrumentierung von `botocore` und MCP reicht
  nicht — genau diese Scopes schließt der Dienst aus. Die Agentenebene muss man
  selbst instrumentieren.
- **Minimal** genügen die Attribute `agentcore.invocation.user_prompt` und
  `agentcore.invocation.agent_response`. Damit lässt sich die Antwort bewerten,
  aber nicht der Entscheidungsweg — ohne Werkzeug-Spans gibt es keine Trajektorie.

Hinzu kommen CloudWatch Transaction Search und ADOT; außerhalb der Runtime nennt
man die Ziel-Log-Gruppe per Umgebungsvariable
([Doku](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-telemetry.html)).
Die eigene Schleife kostet also nicht den Bewertungsdienst, sondern einen
Nachmittag Instrumentierung.

![Links der Agent mit eigener Schleife (Strands, Converse und MCP) auf AgentCore Runtime oder Fargate, instrumentiert mit ADOT und OpenTelemetry-GenAI-Spans. Die Telemetrie landet in CloudWatch mit Transaction Search. AgentCore Evaluations liest daraus in zwei Bahnen: Online bewertet zehn Prozent der Produktionssessions ohne Referenz, Batch und Dataset bewerten vor jedem Release ein Golden Set mit Referenz, darunter ein Lambda, das das SQL auf Athena ausführt. Schlecht bewertete Sessions gehen an einen Menschen und werden zu neuen Golden-Fragen.](/assets/img/judge-aws-aufbau.svg)

Der Aufbau, den ich für diesen Agenten empfehle, hat zwei Bahnen:

**Vor jedem Release — mit Referenz.** Das Golden Set läuft über den
Dataset- oder Batch-Weg. Ein **Lambda-Evaluator** holt das SQL aus dem
`run_query`-Span, führt es auf Athena aus und vergleicht mit dem vorab
berechneten Referenzergebnis — Execution Accuracy, ohne Modell. Wo das Ergebnis
abweicht, prüft ein **Custom-Judge mit Haiku 4.5** anhand von
`expected_response`, ob die Abfrage trotzdem gleichwertig ist — die FLEX-Idee.
Ein zweiter Custom-Judge vergleicht die **Trajektorie** mit der erwarteten
Werkzeugfolge, ein dritter prüft die **Zusicherungen**. Die Trajektorie ist
dabei nicht nur eine Qualitäts-, sondern eine Kostenmetrik: Wie der
[Beitrag zu den MCP-Kosten]({% post_url 2026-09-11-kosten-von-mcp-in-agenten %})
gezeigt hat, kostet ein Agent, der dieselben sechs Werkzeuge in sechs Stufen
statt in einer aufruft, das 2,8-Fache.

**In Produktion — ohne Referenz.** Online-Bewertung auf einem Teil der Sessions,
mit dem, was sich ohne Wahrheit prüfen lässt: Werkzeugwahl und -parameter,
Faithfulness der Antwort gegenüber dem Ergebnis, ein **Plausibilitäts-Judge mit
starkem Modell**, dem die Kennzahldefinitionen fest in der Anweisung stehen —
die Built-in-Evaluatoren sehen nur, was im Trace steht —, und eine
Lambda-Regelprüfung: Partitionsfilter gesetzt, kein `SELECT *`, nicht mehr als
vier Stufen.

**Dazwischen der Mensch.** Den stillen Fehler findet die Online-Bahn nicht
zuverlässig; dafür ist sie nicht gebaut. Was sie leisten kann, ist Kandidaten zu
liefern: Schlecht bewertete Sessions gehen an eine menschliche Prüfung, und
bestätigte Fehler werden zu neuen Golden-Fragen. So wächst das Golden Set aus
den Fragen, die tatsächlich gestellt werden.

Ohne AgentCore Evaluations ginge es auch: mit einem selbstgebauten Judge über
die Converse-API oder mit den Modell-Evaluierungsjobs von Bedrock, die fremde
Antworten entgegennehmen und eigene Metriken erlauben
([Doku](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-judge.html)).
Letztere bewerten allerdings Prompt-Antwort-Paare, keine Trajektorien — für die
Entscheidungsfindung des Agenten fehlt damit genau die Hälfte, um die es hier
geht. Stichproben, Speicherung und Dashboards baut man in beiden Fällen selbst.

## Was es kostet

Pro Bewertung sieht der Judge Frage, Schemaausschnitt, Definitionen, SQL,
Ergebnisauszug und Antwort — rund 6 000 Token hinein, 400 heraus. Je tausend
bewerteter Fragen:

| Judge | $ / 1 000 Bewertungen | Anteil an der Agentenrechnung | bei 10 % Sampling |
|---|---:|---:|---:|
| Built-in (Modell inklusive) | 19,20 | 25 % | 2,5 % |
| Custom + Haiku 4.5 | 9,50 | 12,5 % | 1,2 % |
| Custom + Sonnet 5 | 17,50 | 23 % | 2,3 % |
| Custom + Opus 5 | 41,50 | 55 % | 5,5 % |

Die Agentenrechnung selbst liegt aus den vorigen Beiträgen bei rund 76 $ je
tausend Fragen (Sonnet 5, mit Caching). Jede Frage in Produktion mit Opus 5 zu
bewerten, verteuert den Agenten um mehr als die Hälfte; bei zehn Prozent
Sampling sind es gut fünf Prozent. Ein Golden-Set-Lauf mit 300 Fragen und drei
Opus-Evaluatoren kostet rund 37 $ — pro Release, nicht pro Tag. **Offline ist
Bewerten billig. Online entscheidet das Sampling.**

## Was ich daraus schließe

**LLM-as-a-Judge ist nicht die Messung, sondern ihr letzter Schritt.** Zuerst
kommt, was deterministisch geht: SQL ausführen, Ergebnisse vergleichen, Regeln
prüfen. Dann Judges mit Referenz, für das, was der Vergleich nicht entscheiden
kann. Und Judges ohne Referenz nur dort, wo es keine Referenz geben kann — in
Produktion.

Die Frage „stärkeres oder schwächeres Modell als der Generator?" ist dabei falsch
gestellt. Die richtige lautet: **Hat der Judge eine Referenz?** Mit Referenz
reicht ein kleines Modell. Ohne muss er mindestens so gut sein wie der
Generator, darf nicht der Generator sein — und braucht dasselbe Fachwissen, sonst
bewertet er gegen seine eigenen Annahmen.

## Methodik

Stichprobengröße und Kosten sind gerechnet, nicht gemessen; das Skript liegt als
[`assets/bench/llm-judge.py`](/assets/bench/llm-judge.py) im Repo. Die
Stichprobenrechnung nimmt eine Trefferquote um 80 %, α = 0,05 und 80 % Power an;
für den gepaarten Fall (McNemar) zusätzlich, dass je 2 % der Fragen bei einer
Änderung in beide Richtungen kippen. Die Kosten rechnen mit 6 000 Input- und 400
Output-Token je Bewertung, Claude-API-Listenpreisen für das Judge-Modell und den
AgentCore-Preisen vom September 2026; auf Bedrock gelten eigene Modellpreise.
Die Aussagen zur Judge-Qualität stammen aus den verlinkten Arbeiten und sind
nicht an einem eigenen Datenbestand nachgemessen.

---

**Kurzfassung:** Ein text2SQL-Agent wird auf drei Ebenen bewertet — Ergebnis,
Entscheidungsweg, Antwort. Das Ergebnis misst man zuerst deterministisch
(Execution Accuracy) und setzt einen Judge nur dort ein, wo der Vergleich nicht
entscheiden kann. Ein Judge ohne Referenz misst Konsistenz, nicht Richtigkeit:
Er bewertet eine Antwort als korrekt, die ein falsches SQL getreu wiedergibt.
Mit Referenz reicht ein kleines Modell wie Haiku 4.5; ohne muss der Judge
mindestens so stark sein wie der Generator, aus einer anderen Familie kommen und
dasselbe Fachwissen haben. Für drei Prozentpunkte Unterschied braucht es rund
600 gepaarte Golden-Fragen. AgentCore Evaluations bewertet auch Agenten mit
eigener Schleife aus Converse und MCP — es braucht nur saubere OpenTelemetry-Spans.
Empfohlen: Golden Set mit Lambda-Execution-Accuracy und Referenz-Judges vor
jedem Release, Online-Sampling ohne Referenz in Produktion, und dazwischen ein
Mensch, der aus schlecht bewerteten Sessions neue Golden-Fragen macht.
