---
layout: post
title: "Domänenwissen über MCP oder über RAG?"
date: 2026-09-11 09:00:00 +0200
serie: "text2SQL-Agent auf AWS"
---

Vorweg, damit klar ist, worum es hier **nicht** geht: Dieser Text erklärt RAG
nicht noch einmal. Er untersucht auch nicht die Eigenheiten der Bedrock
Knowledge Base – keine Chunking-Strategien, keine Vektor-Engine, keine Frage,
ob OpenSearch Serverless oder Aurora darunter liegt. Das sind Implementierungs­details.

Die Frage hier liegt eine Ebene darüber und ist von der konkreten
Retrieval-Technik unabhängig: **Woher bekommt der Agent das Wissen, wenn er es
braucht – und wer entscheidet, dass er es braucht?**

## Warum das mehr zählt als jede Formatfrage

Beim [Vergleich der Tabellenformate]({% post_url 2026-09-11-mcp-ausgabeformate %})
ging es um Faktor 3 beim Tokenverbrauch. Hier geht es um eine Größenordnung mehr.

Der BIRD-Benchmark liefert zu jeder Frage einen kurzen Satz Domänenwissen mit –
die Erklärung, was eine Kennzahl im jeweiligen Datenbestand eigentlich bedeutet.
Nimmt man ihn weg, fällt GPT-4 von **54,89 % auf 34,88 %** Execution Accuracy
([BIRD](https://arxiv.org/pdf/2305.03111)). Zwanzig Prozentpunkte, für einen
Satz.

Das ist die wichtigste Zahl dieses Beitrags, und sie beantwortet die
Variantenfrage noch nicht. Sie sagt nur: Domänenwissen ist keine Optimierung,
sondern die Hälfte des Systems. Ein Agent, der nicht weiß, dass „Umsatz“ im
Controlling netto und im Vertrieb brutto gemeint ist, schreibt syntaktisch
perfektes, fachlich falsches SQL – und merkt es nicht.

## Die Varianten

Drei Wege stehen zur Wahl. Ich messe sie gegen eine Nullvariante, die niemand
ernsthaft empfiehlt, die aber die nützlichste Messlatte ist.

**Variante 0 – alles in den Systemprompt.** Der gesamte Korpus steht im Präfix.
Kein Retrieval, keine Entscheidung, kein Fehlerfall. Die Messlatte.

**Variante 1 – RAG vorab in den Systemprompt.** Vor dem ersten Modellaufruf
läuft eine Retrieval-Stufe über die Nutzerfrage und legt die besten Treffer in
den Prompt. Das Modell sieht fertig aufbereitetes Wissen und weiß nicht, dass
retrieved wurde.

**Variante 2 – RAG hinter einer MCP-Funktion.** Der Agent bekommt ein Werkzeug
(`kennzahl_nachschlagen`) und entscheidet selbst, ob und womit er es aufruft.

**Variante 3 – Inhaltsverzeichnis statt RAG.** Kein Vektorindex. Der Präfix
enthält ein Verzeichnis des Korpus – Dateinamen mit je einer Zeile Beschreibung –
und der Agent lädt über MCP gezielt ganze Dokumente nach.

In allen vier Varianten ist **Prompt Caching aktiv**. Das ist keine Feinheit,
sondern Voraussetzung: Ohne Cache entscheidet die Rechnung sich allein an der
Präfixgröße, und alles Weitere wäre Kosmetik.

## Wer löst welchen Modellaufruf aus?

Hier liegt der eigentliche Unterschied zwischen den Varianten, und er wird
selten sauber getrennt. Es gibt zwei Sorten von Modellaufrufen:

- **Aufrufe der SQL-Suchkette.** Abfrage bauen, Fehlermeldung von Athena
  verarbeiten, korrigieren, Ergebnis in eine Antwort gießen. Diese Aufrufe
  sind dem Problem inhärent. Sie fallen in jeder Variante gleich an.
- **Aufrufe, die das Domänenwissen auslöst.** Der Agent stellt fest, dass ihm
  etwas fehlt, ruft ein Werkzeug auf, liest das Ergebnis, entscheidet neu.
  Diese Aufrufe sind eine Folge der Architektur – und vermeidbar.

![Vier Varianten im Vergleich: Variante 0 und 1 mit drei Modellaufrufen der SQL-Kette, Variante 2 mit einem zusätzlichen Wissensaufruf davor, Variante 3 mit zwei.](/assets/img/domaenenwissen-aufrufe.svg)

Variante 0 und 1 zahlen null Zusatzaufrufe: Das Wissen ist schon da, wenn das
Modell zum ersten Mal denkt. Variante 2 kostet einen, Variante 3 mindestens
zwei – erst das Verzeichnis lesen, dann die Datei anfordern, oft noch eine
zweite.

Ein Detail, das man beim Überschlagen unterschätzt: **ein früher Zusatzaufruf
ist teurer als ein später.** Was in Turn 1 in den Verlauf wandert, wird in jedem
Folgeturn erneut abgerechnet. Das nachgeladene Dokument aus Variante 3 reist
durch die gesamte restliche SQL-Kette mit.

## Die Rechnung

Ein realistisches Szenario: Systemprompt und Schemata 15 000 Token, Korpus
250 000 Token, RAG-Treffer 4 000, ein ganzes Dokument 8 000, ein
Athena-Resultset 3 000 (CSV, wie im Formatvergleich empfohlen), drei Aufrufe für die
SQL-Kette. Cache-Read kostet 10 %, Cache-Write 125 % des Input-Preises.

![Gestapelte Balken: Kosten je 1000 Fragen. Variante 0: 195,24 Dollar. Variante 1: 69,24. Variante 2: 80,80. Variante 3: 183,50.](/assets/img/domaenenwissen-kosten.svg)

| Variante | Modellaufrufe | Cache-Read | Vollpreis | $ / 1 000 Fragen |
|---|---:|---:|---:|---:|
| 0 Alles in den Systemprompt | 3 | 795 000 | 10 620 | 195,24 |
| 1 RAG in den Systemprompt | 3 | 45 000 | 22 620 | **69,24** |
| 2 RAG hinter MCP-Funktion | 4 | 62 400 | 24 160 | 80,80 |
| 3 Index + Dateiabruf | 5 | 90 500 | 70 200 | 183,50 |

Zwei Dinge daran haben mich überrascht.

**Variante 2 ist kaum teurer als Variante 1** – 17 % Aufschlag für einen
zusätzlichen Modellaufruf. Der Cache trägt den Präfix so billig, dass ein
weiterer Turn kaum ins Gewicht fällt. Ohne Caching sähe diese Zeile völlig
anders aus.

**Variante 3 ist fast so teuer wie die Nullvariante** – aber aus einem ganz
anderen Grund. Bei Variante 0 liegen 159 von 195 Dollar im Cache-Read des
riesigen Präfix. Bei Variante 3 liegen 140 von 183 Dollar im *Gesprächsverlauf*:
zwei vollständige Dokumente, die durch fünf Turns mitgeschleift werden, zum
vollen Preis. Gleicher Betrag, gegenteilige Ursache.

## Die Falle in Variante 1

Variante 1 gewinnt die Tabelle – aber nur, wenn man sie richtig baut, und die
naheliegende Umsetzung ist die falsche.

Prompt Caching ist ein **Präfix-Vergleich**. Gecacht wird in der Reihenfolge
`tools` → `system` → `messages`, und jede Byte-Änderung entwertet alles
dahinter. Wer die pro Frage retrieveten Chunks in den Systemprompt schreibt –
was der Name der Variante nahelegt –, ändert damit den Präfix bei jeder
einzelnen Anfrage. Die Trefferquote des Caches fällt auf null, und aus 69 Dollar
werden schnell die 195 der Nullvariante.

Die Treffer müssen **hinter** den letzten Cache-Breakpoint, also in die
Nutzernachricht. Fachlich ist das dasselbe Wissen an derselben Stelle im
Kontext; abrechnungstechnisch ist es der Unterschied zwischen der besten und
der schlechtesten Variante. Nachweisen lässt sich das nur an einer Stelle:
`usage.cache_read_input_tokens`. Steht da dauerhaft null, arbeitet ein
Invalidator im Hintergrund.

## Die Falle in Variante 0

Die 195 Dollar der Nullvariante gelten nur bei dichtem Verkehr. Der Präfix muss
geschrieben werden, bevor er gelesen werden kann, und ein Cache-Write kostet
125 % des Input-Preises: 265 000 Token sind **0,66 $ pro Schreibvorgang**. Läuft
der Cache zwischendurch ab, zahlt man erneut.

| Fragen je Cache-Fenster | Aufschlag auf 1 000 Fragen |
|---:|---:|
| 5 | + 132,50 $ |
| 20 | + 33,12 $ |
| 100 | + 6,62 $ |

Bei einem Agenten mit Dauerlast amortisiert sich das. Bei einem, den zwölf
Controller über den Tag verteilt benutzen, verdoppelt es die Rechnung. **Die
Anfragedichte ist bei Variante 0 eine Kostenvariable ersten Ranges** – und sie
taucht in keiner Architekturskizze auf.

## Was die Wissenschaft sagt

Zur Kernfrage – Wissen vorab in den Kontext legen oder den Agenten danach
greifen lassen – gibt es belastbare Vergleichszahlen, wenn auch nicht aus der
text2SQL-Ecke.

Auf dem LOCOMO-Benchmark erreicht der volle Kontext **72,9 %**, werkzeugbasierter
Zugriff **66,9 %** – sechs Punkte Abstand. Bezahlt werden diese sechs Punkte mit
**91 % höherer P95-Latenz und dem Zehnfachen an Token**
([Übersicht](https://usewire.io/blog/memory-as-tools-2026-agent-memory-pattern/)).
Für einfache Fragen bleibt ein einzelner Retrieval-Durchlauf um den Faktor 3
bis 5 günstiger, bei kleinem Qualitätsabstand
([Agentic Retrieval](https://usewire.io/blog/agentic-retrieval-techniques/)).

Das Bild ist also klarer, als die Debatte vermuten lässt:

1. **Ob Domänenwissen da ist, entscheidet über ~20 Punkte.**
2. **Wie es geliefert wird, entscheidet über ~6.**

Die erste Frage ist dreimal so wichtig wie die zweite. Wer noch keinen
kuratierten Korpus hat, sollte nicht über Varianten nachdenken, sondern
Definitionen aufschreiben.

Als Produktionsmuster kristallisiert sich ein Hybrid heraus: die
Retrieval-Schleife grenzt den Korpus auf eine Arbeitsmenge ein, über die das
Modell dann in einem Fenster nachdenkt. Übertragen heißt das: die zwanzig
meistgebrauchten Kennzahldefinitionen fest in den gecachten Präfix, der lange
Rest hinter das Werkzeug.

## Worauf es ankommt

Die Variantenwahl lässt sich nicht allgemein entscheiden, aber die Variablen,
an denen sie hängt, sind überschaubar:

| Wenn … | dann spricht das für |
|---|---|
| der Korpus unter ~30 000 Token bleibt | **Variante 0** – nichts schlägt „ist schon da“ |
| Anfragen selten und über den Tag verteilt kommen | **1 oder 2** – Variante 0 zahlt sich an Cache-Writes arm |
| das Wissen sich häufig ändert | **2 oder 3** – Änderungen berühren den Präfix nicht |
| die Trefferquote des Retrievals unsicher ist | **2** – nur hier kann der Agent nachfassen |
| Dokumente beim Chunken ihren Sinn verlieren | **3** – ganze Datei statt Fragment |
| ein hartes Latenzbudget gilt (< 5 s) | **0 oder 1** – keine zusätzlichen Runden |
| Nachvollziehbarkeit gefordert ist (Audit, Fachabnahme) | **2 oder 3** – der Werkzeugaufruf ist die Protokollspur |
| das Wissen in wenige, klar benannte Dokumente zerfällt | **3** – dann ist ein Verzeichnis ehrlicher als ein Vektorindex |

Zwei dieser Zeilen werden regelmäßig übersehen. Die **Änderungsrate**: Wer
Definitionen im Präfix hält, invalidiert bei jeder Korrektur den Cache für alle
laufenden Sessions. Und die **Nachfassmöglichkeit**: Variante 1 scheitert
lautlos. Liefert das Retrieval den falschen Chunk, sieht das Modell kein
Problem – es weiß ja nicht, dass gesucht wurde. In Variante 2 kann es den
Fehlschlag bemerken und anders fragen. Diese Eigenschaft steht in keiner
Kostentabelle und ist im Betrieb oft die entscheidende.

## Empfehlung

**Startet mit Variante 1, plant Variante 2 ein.**

Variante 1 ist am günstigsten, am schnellsten gebaut und braucht keine
Werkzeug-Disziplin vom Modell. Für ein erstes produktives System reicht das –
unter der Bedingung, dass die Treffer hinter dem Cache-Breakpoint landen.

Variante 2 kostet 17 % mehr und kauft dafür drei Dinge, die sich erst im
Betrieb zeigen: der Agent kann nachfassen, wenn der erste Treffer nichts taugt;
Wissensänderungen entwerten den Cache nicht; und jeder Werkzeugaufruf ist eine
Protokollzeile, mit der sich eine falsche Antwort hinterher erklären lässt.
Gemessen an dem, was ein unentdeckt falscher Umsatzbericht kostet, sind 17 %
kein Preis.

Variante 3 würde ich nur wählen, wenn der Korpus tatsächlich aus wenigen,
sauber benannten Dokumenten besteht, die man nicht zerschneiden darf. Dann ist
ein Verzeichnis ehrlicher als ein Vektorindex – man sieht, was man bekommt.
Ansonsten ist sie die teuerste und langsamste Variante.

Variante 0 ist keine Verlegenheitslösung, sondern bei kleinem Korpus und
dichtem Verkehr die beste Wahl. Nur skaliert sie nicht: Ab etwa 50 000 Token
fängt der Präfix an, auch die Qualität zu kosten – je mehr irrelevanter Text
mitfährt, desto mehr Ablenkung.

## Was diese Rechnung nicht kann

Die größte Schwäche des Modells oben: **Es hält die SQL-Suchkette bei drei
Aufrufen fest – und genau die ist das, was gutes Domänenwissen verändert.**

Spart besseres Wissen einen einzigen fehlgeschlagenen SQL-Versuch, sinken die
Kosten je nach Variante um 31 bis 43 %:

| Variante | 3 SQL-Aufrufe | 2 SQL-Aufrufe |
|---|---:|---:|
| 0 Alles in den Systemprompt | 195,24 | 123,16 |
| 1 RAG in den Systemprompt | 69,24 | 39,16 |
| 2 RAG hinter MCP-Funktion | 80,80 | 49,60 |
| 3 Index + Dateiabruf | 183,50 | 126,80 |

Der Abstand zwischen Variante 1 und 2 beträgt 17 %. Ein eingesparter Fehlversuch
bringt das Doppelte bis Dreifache. **Wer die Variante nach der Kostentabelle
wählt statt nach der Trefferquote, optimiert die falsche Größe.** Die Tabelle
sagt, was eine Variante kostet, wenn alles gleich bleibt – und beim
Domänenwissen bleibt nichts gleich, das ist ja der Zweck.

Deshalb steht am Ende dieselbe Empfehlung wie am Anfang: erst messen, ob das
Wissen ankommt, dann rechnen, was es kostet.

## Methodik

Das Kostenmodell liegt als
[`assets/bench/domaenenwissen-kosten.py`](/assets/bench/domaenenwissen-kosten.py)
im Repo – alle Annahmen stehen oben in der Datei und lassen sich mit den eigenen
Zahlen überschreiben. Preise: Claude Sonnet 5 zu Listenpreisen, 2,00 $ je
Mio. Input-Token, 0,20 $ Cache-Read, 2,50 $ Cache-Write, 10,00 $ Output. Auf
Bedrock gelten eigene Preise.

Das Modell rechnet Token, keine Qualität. Die Qualitätsaussagen stammen aus den
verlinkten Quellen und wurden nicht auf einem eigenen Datenbestand
nachgemessen – das wäre ein eigenes Thema.

---

**Kurzfassung:** Ob Domänenwissen überhaupt vorliegt, ist etwa zwanzig
Prozentpunkte wert; wie es zugestellt wird, etwa sechs. Variante 1 ist am
billigsten, aber nur wenn die Treffer hinter dem Cache-Breakpoint landen –
sonst wird sie zur teuersten. Variante 2 kostet 17 % mehr und kauft dafür
Nachfassen, Entkopplung und eine Protokollspur. Und der größte Hebel liegt
ohnehin woanders: Wissen, das einen fehlgeschlagenen SQL-Versuch verhindert,
spart mehr als jede Variantenwahl.
