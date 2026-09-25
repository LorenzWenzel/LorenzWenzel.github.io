---
layout: post
title: "Welche Historie bei einem Chatbot?"
title_en: "How Much History Does a Chatbot Need?"
date: 2026-07-23 20:10:00 +0200
---

Ein Sprachmodell ist **vollständig zustandslos**. Es erinnert sich an nichts, es
kennt den Nutzer nicht, es weiß nicht, was vor zehn Sekunden gesagt wurde. Was
es wissen soll, muss bei jedem einzelnen Aufruf erneut mitgeschickt werden.

Das ist keine Einschränkung der aktuellen Modellgeneration, sondern die
Arbeitsweise: Ein Request geht rein, eine Antwort kommt raus, danach ist die
Sache vergessen. Der Eindruck eines Gesprächs entsteht ausschließlich dadurch,
dass jemand den bisherigen Verlauf jedes Mal wieder vorne dranhängt.

![Säulendiagramm über sechs Turns: der blaue Anteil bereits früher gesendeter Token wächst stetig, der orange Anteil neuer Token bleibt konstant klein.](/assets/img/historie-zustandslos.svg)

Das hat eine unangenehme Konsequenz: Die Frage aus Turn 1 wird in Turn 6 zum
sechsten Mal übertragen und zum sechsten Mal abgerechnet. Der orange Streifen
ist alles, was tatsächlich neu ist.

Frameworks nehmen einem das ab – LangChain, Strands, AgentCore, jedes
Chat-SDK hält den Verlauf selbst und hängt ihn an. Das ist bequem und genau
deshalb gefährlich: **Jedes dieser Frameworks bringt eine Strategie mit, und die
Voreinstellung ist fast immer „alles behalten, bis es nicht mehr passt".** Wer
nichts entscheidet, hat trotzdem entschieden – nur eben nicht selbst. Es lohnt
sich, in der Dokumentation des eigenen Frameworks nachzusehen, was es bei
Überlauf tut: abschneiden, zusammenfassen oder abstürzen.

## Mehr Verlauf ist nicht besser

Die naheliegende Annahme lautet: Je mehr Kontext, desto besser die Antwort.
Sie ist falsch, und zwar aus zwei unabhängigen Gründen.

**Der erste ist die Länge selbst.** Die Untersuchungen zu *Context Rot* zeigen,
dass die Antwortqualität mit wachsender Eingabelänge nachlässt – deutlich
innerhalb des beworbenen Kontextfensters und unabhängig davon, ob der
zusätzliche Text relevant ist
([Chroma](https://www.trychroma.com/research/context-rot)). Dazu kommt der
bekannte *Lost-in-the-Middle*-Effekt: Information am Anfang und Ende wird
zuverlässiger gefunden als Information in der Mitte. Der Mechanismus ist
banal – Aufmerksamkeit verteilt sich über alle Token, und je mehr es sind, desto
weniger entfällt auf jedes einzelne.

**Der zweite Grund ist unangenehmer.** In *LLMs Get Lost In Multi-Turn
Conversation* ([arXiv 2505.06120](https://arxiv.org/abs/2505.06120), ICLR 2026)
fällt die Leistung über sechs Aufgabentypen im Mehrturn-Gespräch um
durchschnittlich **39 %** gegenüber demselben Problem in einem Zug. Modelle mit
über 90 % im Einzelturn landen bei rund 65 %.

Bemerkenswert ist die Zerlegung: Die Fähigkeit selbst sinkt nur um 15 %, die
**Unzuverlässigkeit steigt um 112 %**. Die Autoren beschreiben den Mechanismus
so: Modelle treffen früh Annahmen, stützen sich anschließend übermäßig auf ihre
eigenen vorherigen Antworten – und wenn sie einmal falsch abgebogen sind, finden
sie nicht zurück.

Für die Frage dieses Beitrags ist das der entscheidende Satz. **Der Verlauf ist
nicht nur teuer, er kann auch falsch sein.** Ein Agent, der in Turn 2 die
falsche Tabelle gewählt hat, liest diese Entscheidung in Turn 5 als gegebene
Tatsache. Wer den Verlauf vollständig behält, konserviert damit auch jeden
Irrtum.

## Wie viele vergangene Turns?

Es gibt keine allgemeingültige Zahl, aber eine brauchbare Frage: **Worauf kann
sich die nächste Nutzerfrage realistisch beziehen?**

Bei einem text2SQL-Chatbot ist die Antwort erfreulich eng. Die typischen
Anschlussfragen lauten „und jetzt dasselbe für Q3", „nur EU-Central bitte",
„sortier das nach Umsatz". Sie beziehen sich fast immer auf den letzten, selten
auf den vorletzten Turn. Eine Frage, die sich auf Turn 1 einer zwanzig Turns
langen Sitzung bezieht, ist die Ausnahme – und für die Ausnahme baut man kein
Fenster, sondern Retrieval.

Die Praxis stützt das. Auf einem Benchmark mit 50 Aufgaben stieg die Quote
erledigter Aufgaben von **71 % auf 79 %**, als der Verlauf auf die letzten fünf
Tool-Paare gekürzt wurde; mit zusätzlicher laufender Zusammenfassung auf
**91,6 %**.

![Balkendiagramm: alles behalten 71 Prozent, letzte fünf Tool-Paare 79 Prozent, zusätzlich laufende Zusammenfassung 91,6 Prozent.](/assets/img/historie-aufraeumen.svg)

Die Variante, die alles behält, war die **schlechteste** – bei etwa dreifachem
Tokenverbrauch ([Auswertung](https://usewire.io/blog/pruning-agent-context-raised-accuracy/)).
Aufräumen ist hier also keine Sparmaßnahme mit Qualitätsverlust, sondern beides
auf einmal.

Ein Vorbehalt gehört dazu, und er ist wichtig: Der Effekt ist **nicht linear in
der Modellstärke**. Eine Untersuchung über Modelle von 4 B bis 284 B Parametern
findet eine umgekehrte U-Kurve – nahe null bei schwachem Retriever, bis zu
**11,7 Punkte** Gewinn, wenn ein guter Retriever auf ein mittelstarkes Modell
trifft, und **negativ**, sobald das Modell stark genug ist, seinen Kontext
selbst zu filtern. Ein Modell mit 80,7 % Ausgangsgenauigkeit verlor durch
Maskierung 1,1 Punkte
([Analyse](https://usewire.io/blog/context-pruning-helps-agents-until-it-doesnt/)).

Übersetzt: Wer Claude Sonnet 5 einsetzt und kurze Sitzungen fährt, gewinnt durch
aggressives Kürzen wenig bis nichts. Wer ein kleineres Modell oder lange
Sitzungen hat, gewinnt viel.

## Fenster, Retrieval oder Mischung?

Die drei Bausteine tun verschiedene Dinge, und man wählt nicht zwischen ihnen,
sondern kombiniert sie.

![Fünf Zeilen mit je zehn Turn-Blöcken: alles behalten, gleitendes Fenster, Fenster mit Zusammenfassung, Retrieval und eine Mischung aus allem.](/assets/img/historie-strategien.svg)

**Das gleitende Fenster** ist billig, vorhersagbar und verliert abrupt. Was
herausfällt, ist weg – ohne Warnung, ohne Fehlermeldung. Für Anschlussfragen auf
den letzten Turn ist es genau richtig.

**Die laufende Zusammenfassung** hält den roten Faden über das Fenster hinaus
und verliert dafür schleichend Details. Der Unterschied zum Fenster ist kein
gradueller, sondern ein qualitativer: Ein Fenster verliert plötzlich und
vollständig, eine Zusammenfassung langsam und teilweise. Im Fehlerfall ist das
zweite meist harmloser – der Agent hat dann eine vage Erinnerung statt gar
keiner.

**Retrieval** löst ein anderes Problem als die beiden. In der Literatur hat sich
2026 die Trennung durchgesetzt: *langer Kontext löst Kapazität, Memory löst
Kontinuität über Sitzungen hinweg.* Ein Fenster kann nicht wissen, was der
Nutzer letzte Woche gefragt hat; ein Retrieval-Index schon. Der Preisunterschied
ist erheblich – auf dem LoCoMo-Benchmark rund **6 956 Token je Retrieval-Aufruf
gegenüber etwa 26 000 für den vollen Kontext**
([Übersicht](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)).

Wichtig für die Erwartungshaltung: Der volle Kontext bleibt in diesen
Untersuchungen die **Obergrenze**, nicht der Maßstab, den man mühelos schlägt.
Auf LoCoMo liegt er bei rund 87,5 % Genauigkeit, und die guten Memory-Systeme
nähern sich ihm an, statt ihn zu übertreffen. Wer auf Retrieval umstellt,
tauscht meist ein paar Prozentpunkte gegen eine Größenordnung an Token und
Latenz. Das ist ein guter Handel – aber es ist einer.

**Die Mischung** ist der Produktionsfall: die letzten drei bis fünf Turns
vollständig, davor eine laufende Zusammenfassung, und für alles Ältere ein
Index, den der Agent bei Bedarf abfragt.

## Gehören Tool-Ergebnisse in die Historie?

Diese Frage ist die wichtigste der drei, und sie wird am seltensten gestellt.
Der Grund steht in einer einzigen Zahl: **Beobachtungstoken – also das, was
Werkzeuge zurückgeben – machen rund 84 % eines durchschnittlichen Agenten-Turns
aus.**

Verglichen damit sind Fragen und Antworten Rundungsfehler. Wer den Verlauf
kleinhalten will und dabei über die Zahl der Turns diskutiert, optimiert an den
16 % herum.

Bei einem text2SQL-Agenten kommt eine Asymmetrie hinzu, die die Entscheidung
fast von selbst trifft:

| Bestandteil | Größe | Wert nach der Antwort |
|---|---|---|
| Die Nutzerfrage | winzig | hoch – Anschlussfragen beziehen sich darauf |
| Das erzeugte SQL | klein | **hoch** – zeigt, welche Tabellen und Filter galten |
| Das Resultset | groß | **fast null** – die Antwort ist längst formuliert |
| Die formulierte Antwort | klein | hoch |

Das SQL ist die Zusammenfassung des Resultsets, die man sonst erst erzeugen
müsste. Es sagt dem Modell in zwanzig Zeilen, worüber gerade gesprochen wurde –
welche Tabelle, welcher Zeitraum, welche Filter. Die 1 200 Token Ergebniszeilen
sagen ihm dasselbe, nur sechzigmal so teuer.

Die praktische Regel lautet deshalb: **SQL behalten, Zeilen ersetzen.** Statt
des vollständigen Resultsets bleibt ein Platzhalter im Verlauf:

```
[Ergebnis verworfen: 1 248 Zeilen, 6 Spalten, Summe net_revenue_eur 4,21 Mio. €]
```

Das reicht für „und jetzt dasselbe für Q3" vollständig aus. Für den seltenen
Fall, dass der Nutzer sich doch auf eine konkrete Zeile bezieht, kann der Agent
die Abfrage erneut ausführen – ein zusätzlicher Modellaufruf, aber nur dann.

Die verbreitete Vorgehensweise dafür ist gestuft: Tokenauslastung bei 70 %
beobachten, ab 85 % alte Tool-Ergebnisse durch Platzhalter ersetzen, und erst
bei 95 % eine echte Zusammenfassung durch das Modell erzeugen lassen. Für
Claude-Modelle gibt es dafür Context Editing mit
`clear_tool_uses_20250919`, das alte Ergebnisse entfernt, statt sie
zusammenzufassen.

## Der Konflikt mit dem Cache

Ein Punkt, der in fast allen Anleitungen fehlt: **Jedes Aufräumen entwertet den
Prompt-Cache ab der Schnittstelle.**

Der Cache ist ein Präfix-Vergleich. Wer in der Mitte des Verlaufs ein
Tool-Ergebnis durch einen Platzhalter ersetzt, hat alles ab dieser Stelle
verändert – und zahlt beim nächsten Aufruf für den gesamten Rest wieder den
vollen Preis. Wie teuer das ist, steht in
[Warum Prompt Caching bei text2SQL-Agenten Pflicht ist]({% post_url 2026-06-28-prompt-caching-pflicht %}).

Daraus folgt eine Regel, die dem Bauchgefühl widerspricht: **Selten und in
großen Schritten aufräumen, nicht laufend und in kleinen.** Wer bei jedem Turn
ein bisschen kürzt, hat dauerhaft keinen Cache. Wer alle zehn Turns einmal
kräftig aufräumt, zahlt einmal den Neuaufbau und profitiert dazwischen.

## Ein Vorschlag für den text2SQL-Fall

Als Ausgangspunkt, nicht als Wahrheit:

- **Die letzten 3 Turns** vollständig, inklusive Tool-Ergebnissen.
- **Ältere Turns**: Frage, SQL und Antwort behalten, Resultsets durch einen
  Platzhalter mit Zeilenzahl und Kennzahl ersetzen.
- **Ab etwa 15 Turns** eine laufende Zusammenfassung, die den Gesprächsgegenstand
  festhält – welche Tabellen, welcher Zeitraum, welche Definitionen geklärt
  wurden.
- **Über Sitzungen hinweg** nur das, was der Nutzer explizit gespeichert hat oder
  was fachlich dauerhaft gilt. Nicht den Gesprächsverlauf von gestern.
- **Aufgeräumt wird in Blöcken**, nicht bei jedem Turn.

Und eine Warnung, die aus dem Mehrturn-Befund folgt: Wenn der Agent sich
sichtbar verrannt hat, ist der beste Eingriff nicht Nachfragen, sondern **neu
anfangen** – mit der ursprünglichen Frage, präziser gestellt. Ein Modell, das
einmal falsch abgebogen ist, kommt laut der Untersuchung im selben Gespräch
kaum zurück. Ein „Neue Frage"-Knopf im Chatbot ist deshalb kein
Bedienungsdetail, sondern eine Qualitätsmaßnahme.


---

**Kurzfassung:** Das Modell erinnert sich an nichts; der Verlauf ist etwas, das
man aktiv mitschickt und bei jedem Turn erneut bezahlt. Mehr davon ist nicht
besser: Die Qualität sinkt mit der Länge, und im Mehrturn-Gespräch fällt sie um
durchschnittlich 39 % – vor allem, weil Modelle sich an ihren eigenen früheren
Fehlern festhalten. Die wichtigste Stellschraube sind nicht die Turns, sondern
die Tool-Ergebnisse: Sie machen rund 84 % des Verlaufs aus und sind nach der
Antwort fast wertlos. Bei text2SQL heißt das: SQL behalten, Zeilen durch einen
Platzhalter ersetzen, letzte drei Turns vollständig, Älteres verdichten – und
das Ganze in großen Schritten statt laufend, sonst zahlt der Cache die Zeche.
