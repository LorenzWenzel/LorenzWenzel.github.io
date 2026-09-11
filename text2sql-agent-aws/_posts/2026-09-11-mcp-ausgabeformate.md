---
layout: post
title: "Wieso MCP-Funktionen keine JSONs zurückgeben sollten"
date: 2026-09-11 14:00:00 +0200
serie: "text2SQL-Agent auf AWS"
---

Wenn man einen Agenten baut, der Fragen in SQL übersetzt und gegen Amazon Athena
ausführt, verbringt man die ersten Wochen mit dem Prompt. Mit der
Tabellenauswahl. Mit Joins, die das Modell falsch herum baut. Womit man sich
*nicht* beschäftigt, ist die Zeile Code, die das Abfrageergebnis in einen String
verwandelt, bevor es zurück an das Modell geht.

Genau die ist auf Dauer die teuerste Entscheidung im ganzen Agenten.

![Ablaufdiagramm: Nutzerfrage geht an den Agenten auf Bedrock, von dort an den MCP-Server und an Athena. Der Rückweg führt über die Serialisierung des Resultsets ins Kontextfenster.](/assets/img/text2sql-pipeline.svg)

Der Hinweg ist billig: eine Frage, ein paar Dutzend Token. Der Rückweg trägt das
Resultset – und alles, was ein MCP-Tool zurückgibt, wird Kontext. Nicht einmal,
sondern in jedem Folgeturn erneut, solange die Konversation läuft.

## Der Versuchsaufbau

Ich habe ein realistisches Athena-Ergebnis genommen – Umsatz je Region und
Produktkategorie, sechs Spalten, wie es ein text2SQL-Agent hundertmal am Tag
produziert – und es in neun Formaten serialisiert. Dann gezählt.

```
region,product_category,order_month,net_revenue_eur,order_count,avg_basket_eur
EU-Central,Elektronik,2026-01,810661.01,12688,710.52
EU-West,Elektronik,2026-02,374789.32,37773,393.09
```

![Balkendiagramm: Tokenbedarf für 1000 Zeilen in neun Formaten. XML 75.740, JSON pretty 68.865, YAML 56.600, JSON compact 46.863, Markdown 28.637, JSON columnar 24.879, TOON 24.629, CSV 23.518, TSV 23.513.](/assets/img/tokenkosten-formate.svg)

Die Spreizung beträgt Faktor **3,2**. Dasselbe Ergebnis, dieselbe Information,
dreimal so viel Kontext – nur weil jemand `json.dumps(rows, indent=2)`
geschrieben hat.

| Format | 10 Zeilen | 200 Zeilen | 1 000 Zeilen | Token je Zeile |
|---|---:|---:|---:|---:|
| XML | 763 | 15 151 | 75 740 | 75,7 |
| JSON (pretty) | 688 | 13 768 | 68 865 | 68,9 |
| YAML | 564 | 11 319 | 56 600 | 56,6 |
| JSON (compact) | 468 | 9 367 | 46 863 | 46,9 |
| Markdown-Tabelle | 321 | 5 757 | 28 637 | 28,6 |
| JSON (spaltenweise) | 277 | 5 000 | 24 879 | 24,9 |
| TOON | 275 | 4 949 | 24 629 | 24,6 |
| CSV | 260 | 4 718 | 23 518 | 23,5 |
| TSV | 256 | 4 716 | 23 513 | 23,5 |

Bei zehn Zeilen ist das alles egal. Der Unterschied zwischen CSV und JSON liegt
bei 200 Token – ungefähr der Preis eines Höflichkeitssatzes im Systemprompt. Ab
ein paar hundert Zeilen kippt es.

## Der Grund ist banal

Es gibt nur einen nennenswerten Effekt, und er steckt in der letzten Spalte der
Tabelle: **wiederholt das Format die Spaltennamen in jeder Zeile oder nicht?**

JSON, YAML und XML tun es. Bei sechs Spalten heißt das, dass `"region"`,
`"product_category"` und `"net_revenue_eur"` tausendmal im Kontext stehen, obwohl
sie einmal genügen würden:

```
[{"region":"EU-Central","product_category":"Elektronik","order_month":"2026-01",
  "net_revenue_eur":810661.01,"order_count":12688,"avg_basket_eur":710.52},
 {"region":"EU-West","product_category":"Elektronik","order_month":"2026-02",
  "net_revenue_eur":374789.32,"order_count":37773,"avg_basket_eur":393.09}]
```

CSV, TSV, TOON und ein spaltenweises JSON (`{"columns": [...], "rows": [[...]]}`)
nennen sie einmal im Kopf. Daraus folgt direkt: **je mehr Spalten und je länger
die Spaltennamen, desto größer der Abstand.** Bei einer Tabelle mit zwanzig
Spalten und sprechenden Namen aus dem Glue-Katalog wird aus Faktor 3 schnell
Faktor 5. Bei zwei Spalten namens `a` und `b` verschwindet der Effekt fast.

Alles andere ist Rauschen: Einrückung, Anführungszeichen, geschweifte Klammern.
Messbar, aber zweitrangig.

## Token sind nicht Qualität

Hier wird es unangenehm, denn die naheliegende Schlussfolgerung – „also immer
CSV“ – hält der Literatur nur halb stand.

Für das TOON-Format melden die Autoren über 244 Abfragen und vier Modelle
**72,2 % Trefferquote gegenüber 71,4 % für JSON**, bei rund 40 % weniger Token
([Benchmarks](https://github.com/toon-format/toon)). Ein Vergleich aus der Praxis
kommt für reine Lookup-Abfragen auf flachen Tabellen sogar auf **95,45 % für CSV
gegenüber 87,5 % für JSON** – bei etwa der Hälfte der Kosten
([Wyzer](https://wyzer.it/blog/Data-Format-Selection-for-Multi-Agent-LLM-Systems-An-Empirical-Analysis-of-Token-Efficiency)).
Das stützt die These.

Nur: eine Untersuchung zu Extraktionsaufgaben findet das genaue Gegenteil.
Dort schlägt ein Markdown-Key-Value-Format mit **60,7 %** das CSV-Format mit
**44,3 %** deutlich – und zwar bei rund dem 2,5-Fachen an Token
([SoftServe](https://medium.com/softserve-technical-communication/rethinking-llm-inputs-json-against-toon-and-markdown-kv-b713bcbe7eb5)).
Das Format, das den Schlüssel neben jeden Wert schreibt, gewinnt genau dann,
wenn das Modell einzelne Werte korrekt *zuordnen* muss statt sie nur zu finden.

Die Wiederholung der Spaltennamen ist also keine reine Verschwendung. Sie ist
Redundanz, und Redundanz kauft Robustheit. Die Frage ist nicht, ob man sie sich
leisten will, sondern ob die Aufgabe sie braucht.

## Welches ist wann am besten?

| Situation | Format | Warum |
|---|---|---|
| Flaches, uniformes Resultset, viele Zeilen | **CSV / TSV** | Günstigste Zeile, und das Modell kennt das Format aus dem Training |
| Zellen enthalten Kommas, Semikolons, Zeilenumbrüche | **TSV** | Spart das Quoting-Chaos; Tabs kommen in Athena-Strings praktisch nie vor |
| Wenige Zeilen (< 50), die der Nutzer mitliest | **Markdown-Tabelle** | 22 % Aufschlag, dafür direkt darstellbar in der Antwort |
| Das Modell muss Werte exakt zuordnen, nicht nur finden | **JSON / Key-Value** | Redundanz als Fehlerkorrektur – hier lohnen die Extra-Token |
| Verschachtelte oder uneinheitliche Struktur | **TOON oder JSON** | CSV kann es schlicht nicht abbilden |
| Ergebnis ist ein einzelner Wert oder eine Kennzahl | **gar keine Tabelle** | Ein Satz Klartext schlägt jedes Format |

Die letzte Zeile ist die wichtigste und wird am häufigsten übersehen. `SELECT
COUNT(*)` braucht keine Serialisierungsstrategie.

## Warum Athena die Entscheidung vorwegnimmt

Für einen text2SQL-Agenten auf AWS ist die Auswahl kleiner, als die Tabelle
suggeriert – und zwar wegen der Quelle.

Athena *kann* komplexe Typen: `ARRAY`, `MAP`, `STRUCT`, beliebig tief
verschachtelt. Nur kommen die am Ausgang nicht sauber heraus. Die CSV-Ausgabe
behandelt Arrays und Maps nicht korrekt, und die gängige Empfehlung lautet,
sie vorher mit `UNNEST` und Punktnotation flachzuklopfen
([Athena Guide](https://athena.guide/articles/complex-types),
[AWS-Doku](https://docs.aws.amazon.com/athena/latest/ug/flattening-arrays.html)).
Was beim Agenten ankommt, ist damit praktisch immer ein Rechteck: *n* Zeilen mal
*m* Spalten, jede Zelle ein Skalar.

Und ein Rechteck entwertet genau die Eigenschaft, für die man JSON sonst
bezahlt. JSONs Stärke ist die Verschachtelung; bei flachen Daten ist sie toter
Ballast. Selbst TOON, das eigens für LLM-Kontexte entworfen wurde, räumt das
ein: bei rein tabellarischen Daten sei CSV kleiner, TOON koste dort 5–10 %
Aufschlag. Der eigene Benchmark des Projekts bestätigt es – im Flat-Only-Track
64 247 Token für CSV gegenüber 68 030 für TOON.

**Für die Athena-Normalform ist das flache, kopfzeilenbasierte Format nicht eine
gute Wahl unter mehreren, sondern die strukturell passende.** Nicht weil CSV
elegant wäre, sondern weil der Datenproduzent am anderen Ende die Verschachtelung
ohnehin schon weggeworfen hat.

## Was das in Euro heißt

Ein Agent, der 200 Abfragen am Tag beantwortet, die im Schnitt 500 Zeilen
zurückgeben. JSON mit Einrückung kostet dafür 34 425 Token je Antwort, CSV
11 770 – eine Differenz von **22 655 Token pro Abfrage**.

Auf den Monat sind das rund **136 Millionen zusätzliche Input-Token**. Bei den
Listenpreisen der Claude-API sind das etwa 272 $ mit Sonnet 5 oder 680 $ mit
Opus 5 – und zwar nur, wenn das Ergebnis *einmal* durchs Modell geht. In einem
Agenten, der nach dem Tool-Ergebnis noch zwei-, dreimal nachdenkt, wird das
Resultset bei jedem Turn erneut abgerechnet. Dann stehen 816 $ bzw. 2 039 $ auf
der Rechnung, für exakt dieselbe Information.

(Auf Bedrock gelten eigene Preise; die Größenordnung verschiebt sich, das
Verhältnis nicht.)

## Praktische Konsequenzen für den MCP-Server

Drei Dinge, die sich daraus für die Tool-Implementierung ergeben:

**Nicht das ganze Resultset zurückgeben.** Die billigste Zeile ist die, die man
gar nicht erst serialisiert. Ein Limit im Tool, ein Hinweis auf die Gesamtzahl
(„1 248 Zeilen, die ersten 100 folgen“) und die Möglichkeit nachzufordern ist
fast immer besser als der vollständige Dump.

**Auf die Doppelung achten.** Wer `structuredContent` nutzt, sollte wissen: die
Spezifikation empfiehlt, denselben Inhalt zusätzlich als serialisiertes JSON in
einem Textblock mitzuliefern – aus Kompatibilitätsgründen
([Diskussion zur Klärung](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1624)).
Wer das naiv umsetzt, bezahlt die Nutzlast zweimal.

**Die Zielgruppe trennen.** Der Textblock ist für das Modell und darf knapp sein;
`structuredContent` kann ein Widget speisen, das gar nicht erst in den Kontext
wandert ([FutureSearch](https://futuresearch.ai/blog/mcp-results-widget/)).
Eine Zusammenfassung für das Modell, die Rohdaten für die Anzeige – das spart
mehr als jede Formatwahl.

## Methodik und Vorbehalte

Gemessen mit `tiktoken` und `o200k_base`. Das ist **nicht** der Tokenizer der
Claude-Modelle, und die absoluten Zahlen verschieben sich entsprechend. Der
gemessene Effekt ist aber kein Tokenizer-Artefakt, sondern strukturell: ein
Format, das denselben String tausendmal wiederholt, tut das unter jedem
Tokenizer. Die Rangfolge bleibt, die Faktoren wackeln in der zweiten
Nachkommastelle. Wer es für die eigene Tabelle genau wissen will, nimmt
`messages.count_tokens`.

Das Skript liegt unter
[`assets/bench/format-tokens.py`](/assets/bench/format-tokens.py) – sechs Spalten,
fester Seed, neun Formatter. Eigene Spaltennamen einsetzen und laufen lassen;
bei breiten Tabellen fällt das Ergebnis deutlicher aus als hier.

---

**Kurzfassung:** Für ein flaches Athena-Resultset ist CSV oder TSV das richtige
Format – nicht aus Geschmack, sondern weil die Quelle flach ist und jedes
verschachtelungsfähige Format diese Fähigkeit ungenutzt mitbezahlt. Ausnahmen
gibt es zwei: wenige Zeilen, die der Nutzer mitliest (Markdown), und Aufgaben,
bei denen das Modell Werte exakt zuordnen muss (dann kauft man sich die
Redundanz bewusst). Die größte Ersparnis liegt ohnehin nicht im Format, sondern
in der Zeile, die man gar nicht erst zurückgibt.
