---
layout: post
title: "Reranker vs. Retrieval"
title_en: "Reranker vs. Retrieval"
date: 2025-10-19 21:40:00 +0200
serie: "RAG auf Verträgen in Azure"
---

Das Retrieval liefert eine sortierte Liste. Oben steht der beste Treffer, unten
der schlechteste, jeder Chunk hat eine Zahl. Warum sollte man diese Liste noch
einmal von einem zweiten Modell umsortieren lassen?

Die Antwort steckt darin, **wonach** das Retrieval sortiert hat.

![Dreiteiliges Schaubild einer RAG-Pipeline. Links die Ingestion offline: Rohdaten und Dokumente, Chunking und Preprocessing, Embedding-Modell, Vektor-Datenbank. In der Mitte Retrieval und Reranking: die Benutzer-Anfrage geht ins Embedding-Modell, von dort in die Vektor-Suche mit ANN gegen die Datenbank, die Top-K Chunks mit k gleich 20 bis 50 liefert. Diese Chunks gehen zusammen mit der ursprünglichen Anfrage in den Reranker, einen Cross-Encoder, der daraus Top-N Chunks mit n gleich 3 bis 5 macht. Rechts die Generation: Prompt-Erstellung aus Kontext und Query, LLM, finale Antwort.](/assets/img/rag-reranker-pipeline.jpeg)

## Das Retrieval hat die Frage nie gesehen

Beim Aufbau des Index wird jeder Chunk einmal durch das Embedding-Modell
geschickt und als Vektor abgelegt. Zu diesem Zeitpunkt existiert die spätere
Frage noch nicht. Der Vektor muss also alles, was der Chunk jemals bedeuten
könnte, in 1 536 Zahlen unterbringen — ohne zu wissen, wonach einmal gefragt
wird.

Zur Abfragezeit passiert dann etwas erstaunlich Einfaches: Die Frage wird
ebenfalls zu einem Vektor, und die Suche vergleicht zwei Zahlenreihen, die
**unabhängig voneinander** entstanden sind. Genau deshalb funktioniert sie
überhaupt so schnell — die Dokumentseite war schon fertig, bevor jemand gefragt
hat. Das ist die Bauart, die man Bi-Encoder nennt.

Bei BM25 ist es dasselbe Muster mit anderen Mitteln: Der Score entsteht aus
Termstatistiken, die im Index stehen. Wie oft der Begriff im Chunk vorkommt, wie
selten er im Bestand ist, wie lang der Chunk ist. Auch das wurde ohne die Frage
berechnet.

Beide Verfahren sortieren also nach der Ähnlichkeit zweier getrennt berechneter
Beschreibungen. Was sie **nicht** tun: den Chunk im Licht der konkreten Frage
lesen.

## Was der Reranker anders macht

Ein Reranker ist ein Cross-Encoder. Er bekommt Frage und Chunk als *eine*
Eingabe, und jedes Wort der Frage kann jedes Wort des Chunks sehen. Aus der
Dokumentation der Sentence-Transformers-Bibliothek:

> We pass both sentences simultaneously to the Transformer network. It produces
> then an output value between 0 and 1 indicating the similarity of the input
> sentence pair.

Das Ergebnis ist keine Distanz zwischen zwei Punkten mehr, sondern ein Urteil
über ein Paar. Der Unterschied in der Qualität ist gut belegt — dieselbe Quelle
sagt dazu schlicht: *„Cross-Encoder achieve better performances than
Bi-Encoders."*

Warum sucht man dann nicht gleich damit? Weil sich nichts vorberechnen lässt.
Für jede Frage muss das Modell einmal pro Kandidat laufen. Die
Sentence-Transformers-Doku beziffert das an einem Clustering-Beispiel: 10 000
Sätze bedeuten rund 50 Millionen Paare und etwa **65 Stunden** Rechenzeit — mit
einem Bi-Encoder sind es **5 Sekunden**, weil jeder Satz nur ein einziges Mal
kodiert wird.

Damit ist die Arbeitsteilung vorgezeichnet, und sie ist genau das, was das
Schaubild oben zeigt:

- **Retrieval** ist billig und darf deshalb breit sein. Es sortiert Millionen auf
  einige Dutzend herunter.
- **Reranking** ist teuer und darf deshalb nur schmal sein. Es sortiert einige
  Dutzend auf eine Handvoll.

## Wie Azure AI Search das macht

Der semantische Reranker in Azure AI Search ist kein eigenes Modell, das man
auswählt, sondern ein Zusatzschritt in der Abfrage: `query_type=SEMANTIC` plus
der Name einer semantischen Konfiguration. Unter der Haube laufen mehrsprachige
Modelle aus der Bing-Entwicklung. Die
[Dokumentation](https://learn.microsoft.com/en-us/azure/search/semantic-search-overview)
beschreibt drei Schritte.

**Erstens: zusammenfassen.** Der Reranker bekommt nicht den Rohtext, sondern
einen „summary string" pro Treffer. Der wird aus den Feldern gebaut, die in der
semantischen Konfiguration stehen, und jedes Feld hat ein Tokenbudget:

| Feld in der Konfiguration | Budget |
|---|---:|
| `title` | 128 Token |
| `keywords` | 128 Token |
| `content` | der Rest |

Der gesamte summary string ist seit November 2024 auf 2 048 Token begrenzt
(vorher 256). Was darüber hinausgeht, wird abgeschnitten — weshalb die
Reihenfolge der Felder in der Konfiguration eine echte Entscheidung ist und
keine Formalie. Im POC steht `heading` als Titel, `content` als Inhalt, und
sieben Metafelder — Objektcode, Straße, PLZ, Ort, Mieter, Einheitencodes — teilen
sich die 128 Keyword-Token.

**Zweitens: bewerten.** Jeder Treffer bekommt einen `@search.rerankerScore`
zwischen 0 und 4. Und das ist kein Ähnlichkeitsmaß, sondern eine Skala mit
ausformulierter Bedeutung:

| Score | Bedeutung laut Microsoft |
|---:|---|
| 4,0 | beantwortet die Frage vollständig |
| 3,0 | relevant, aber unvollständig |
| 2,0 | teilweise relevant |
| 1,0 | verwandt, beantwortet einen kleinen Teil |
| 0,0 | irrelevant |

**Drittens: ausgeben.** Zusätzlich zum Score liefert der Schritt „captions" —
die aussagekräftigsten Passagen, optional mit Hervorhebungen. Die sind immer
wörtlich aus dem Index: *„There's no generative AI model in this workflow that
creates or composes new content."*

### Zwei Grenzen, die man kennen sollte

Der Reranker setzt **nach** BM25 beziehungsweise nach der RRF-Fusion an — er ist
eine zweite Sortierung auf einer bestehenden Liste, keine zweite Suche. Und
diese Liste ist gedeckelt: *„Even if results include more than 50 results, only
the top 50 results progress to semantic ranking."*

## Der Unterschied, der praktisch zählt

Retrieval und Reranking arbeiten an verschiedenen Problemen, und man kann das
eine nicht durch das andere ersetzen.

**Das Retrieval entscheidet, was überhaupt zur Auswahl steht.** Steht der Chunk
mit der Antwort nicht in den Kandidaten, ändert kein Reranker etwas daran. Die
Azure-Doku sagt das ungewöhnlich direkt: Was der semantische Reranker *nicht*
kann, ist *„rerun the query over the entire corpus to find semantically relevant
results"*.

**Der Reranker entscheidet, was von der Auswahl oben landet.** Das ist die
Disziplin, in der ein Retrieval systematisch schwach ist: Es findet bei
Verträgen zwanzig Kündigungsfristen, weil zwanzig Verträge eine haben. Welche
davon zur Frage gehört, ist eine Lesefrage — und Lesen ist genau das, was der
Cross-Encoder tut und die Vektorähnlichkeit nicht.

Ein Nebeneffekt der 0-bis-4-Skala ist dabei nützlicher, als er aussieht:
`@search.score` ist nach oben offen und nur innerhalb einer Ergebnisliste
vergleichbar — ein Score von 12 sagt für sich genommen nichts. Der
`rerankerScore` ist eine absolute Einschätzung. „Alles unter 1,5 gar nicht erst
ins Prompt" ist damit eine Regel, die man formulieren kann. Über Retrieval-Scores
lässt sich so etwas nicht sagen.

---

**Kurzfassung:** Retrieval sortiert nach der Ähnlichkeit zweier Beschreibungen,
die unabhängig voneinander berechnet wurden — der Chunk-Vektor entstand, bevor
die Frage existierte. Ein Reranker liest Frage und Chunk zusammen und ist
deshalb genauer, aber zu teuer, um damit zu suchen. Azure AI Search baut dafür
pro Treffer eine Zusammenfassung aus Titel, Keywords und Inhalt, bewertet sie
auf einer Skala von 0 bis 4 und tut das für höchstens 50 Treffer. Der Reranker
verbessert die Reihenfolge, nicht die Auswahl — was das Retrieval nicht gefunden
hat, bleibt verloren.
