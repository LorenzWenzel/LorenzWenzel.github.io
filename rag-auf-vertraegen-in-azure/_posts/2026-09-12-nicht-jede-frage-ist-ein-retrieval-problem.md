---
layout: post
title: "Nicht jede Frage ist ein Retrieval-Problem"
title_en: "Not Every Question Is a Retrieval Problem"
date: 2026-09-12 12:45:00 +0200
serie: "RAG auf Verträgen in Azure"
---

„Was steht in § 5 des Vertrags GUT57?" — das beantwortet RAG gut. „Welche
Einheit hat die höchste Miete?" — das beantwortet RAG nicht, und zwar nicht,
weil die Suche schlecht wäre, sondern weil es keine Suchfrage ist.

Dieser Beitrag geht der Grenze nach: Welche Fragen sind Retrieval-Probleme,
welche nicht, woran erkennt man den Unterschied — und was macht man mit den
anderen.

## Wofür Retrieval gebaut ist

Top-k ist eine Wette. Sie lautet: *Die Antwort steht an wenigen Stellen im
Bestand, und die Suche findet diese Stellen.* Wer nach dem Kündigungsparagraphen
eines bestimmten Vertrags fragt, gewinnt die Wette — es gibt genau einen
solchen Chunk, er hat die Objektkennung, BM25 findet sie, der Reranker hebt ihn
nach oben. Ein Chunk ins Prompt, fertig.

Diese Frage nennt die Forschung **lokal**: Sie zielt auf eine Stelle. Und für
lokale Fragen ist die ganze Pipeline aus den vorherigen Beiträgen — Chunking,
Hybrid-Suche, Reranking — die richtige Antwort.

## Wo die Wette verliert

![Zwei Raster aus zwölf Verträgen mal sechs Paragraphen. Links die lokale Frage nach § 5 von GUT57: genau eine Zelle leuchtet, Top-k findet sie. Rechts die globale Frage nach der höchsten Miete: in allen zwölf Verträgen leuchtet § 3, alle mit ähnlichem Score. Top-3 greift drei davon heraus — eine Stichprobe, keine Antwort.](/assets/img/offene-fragen-lokal-global.svg)

Mietverträge sind kein heterogener Wissensbestand, in dem zu einer Frage vier
Chunks passen und tausend nicht. Sie sind **homogen**: Jeder Vertrag hat einen
Mietparagraphen, jeder eine Kündigungsregelung, jeder eine Kaution. Wer nach
„Miete" fragt, bekommt zwölf Treffer mit zwölf ähnlichen Scores — und Top-3
zieht drei davon heraus, sortiert nach Wortlaut, nicht nach Betrag.

Das ist kein Fehler der Suche. Die Suche hat gefunden, was sie finden sollte.
Nur steht die Antwort in keinem der zwölf Chunks. Sie entsteht erst aus dem
Vergleich aller zwölf.

Die GraphRAG-Arbeit von Microsoft (Edge et al., 2024) beschreibt genau diesen
Fall: *„RAG fails on global questions directed at an entire text corpus"*. Die
Autoren nennen es Query-Focused Summarization — eine Frage, die nicht
retrievt, sondern zusammengefasst werden muss. Bei Verträgen tritt das
Problem in drei Formen auf, und sie sind verschieden schwer.

**Vergleich und Aggregation.** „Höchste Miete", „durchschnittliche Laufzeit",
„wie viele Verträge mit Staffelmiete". Braucht die ganze Population. Dazu
kommt eine technische Pointe: Die Zahl 1 250 ist für BM25 gar nicht suchbar —
numerische Felder sind in Azure AI Search vom Volltext ausgenommen — und ein
Embedding kann Zahlen nicht ordnen. „Höher als" existiert im Vektorraum nicht.

**Berechnung.** „Bei wem kann ich in den nächsten zwei Wochen die Miete
indexieren?" Das Datum, das die Antwort ist, steht in keinem Vertrag. Es ergibt
sich aus Mietbeginn, Indexierungsintervall und dem heutigen Tag. Retrieval kann
eine Textstelle finden. Es kann keine Textstelle finden, die es nicht gibt.

**Abwesenheit.** „Welche Verträge haben *keine* Indexierungsklausel?" Man kann
das Fehlen eines Paragraphen nicht retrieven. Es gibt keinen Chunk, in dem
steht, dass etwas nicht drinsteht. Das ist die härteste der drei Formen, und
bei Verträgen ist sie juristisch relevant: Wenn keine Staffelmiete vereinbart
ist, gilt keine — das ist eine belastbare Aussage, die kein Top-k liefern kann.

## Die Möglichkeiten

### Erst strukturieren, dann fragen

![Oben die Ingestion: ein Vertrag geht in eine Extraktion und wird zu einer typisierten Tabellenzeile mit Objekt, Einheit, Miete als Zahl, Indexierungsklausel als Ja/Nein und nächstem Indexierungsdatum. Unten die Abfrage: „Welche Einheit hat die höchste Miete?" wird zu orderby rent desc top 1, „Wer kann in zwei Wochen indexiert werden?" zu einem Datumsfilter. Kein Retrieval, kein Score.](/assets/img/offene-fragen-strukturieren.svg)

Das ist bei homogenen Beständen der Stand der Technik, und die Idee ist so
einfach, dass man sie leicht unterschätzt: **Die Arbeit des Modells wandert vom
Fragezeitpunkt zum Indexaufbau.** Einmal pro Vertrag liest ein Modell den Text
und füllt ein Schema — Miete als Zahl, Mietbeginn als Datum, Indexierungsklausel
als Ja/Nein, nächster Indexierungstermin berechnet. Danach ist „höchste Miete"
keine Suchfrage mehr, sondern eine Abfrage:

```
search=*
$orderby=meta/rent desc
$top=1
```

Kein Retrieval, kein Score, kein Modell. Und die Abwesenheitsfrage, die
Retrieval strukturell nicht beantworten kann, wird trivial:
`$filter=meta/index_clause eq false`.

Azure bringt beide Hälften mit. Für die Extraktion gibt es neben einem
selbstgeschriebenen LLM-Prompt inzwischen
[Content Understanding](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/document/overview),
das genau diesen Fall adressiert — die Doku nennt als Beispiel, *„contractual
parties, renewal dates, and payment terms in legal agreements"* zu
extrahieren, mit typisierten Feldern, die automatisch normalisiert werden, und
mit Konfidenz plus Fundstelle pro Feld, damit unsichere Werte an einen
Menschen gehen. Für die Abfrage hat Azure AI Search
[`$filter` und `$orderby`](https://learn.microsoft.com/en-us/azure/search/search-filters)
auf Feldern mit `filterable`/`sortable`, und seit der Preview 2026-08-01 auch
Facet-Aggregationen: `sum`, `avg`, `min`, `max`, `cardinality` direkt im
Suchdienst. Ob man die Zahlen dort ablegt oder in einer echten Datenbank, ist
dann eine Frage der Menge, nicht des Prinzips.

Der Preis: **Das Schema muss die Frage vorhergesehen haben.** Wer „Miete"
extrahiert hat, aber nicht „Nebenkostenvorauszahlung", steht bei der nächsten
Frage wieder ohne Antwort da. Und einmal pro Vertrag heißt: Wenn sich das
Schema ändert, läuft die Extraktion über den ganzen Bestand neu.

### Map-Reduce über alle Verträge

Für Fragen, die das Schema nicht kennt, bleibt der teure Weg: für jeden
Vertrag den passenden Chunk holen, das Modell den Wert extrahieren lassen, und
am Ende ein Aufruf, der die n Ergebnisse vergleicht. Das ist im Kern, was
GraphRAG mit seinen Community-Zusammenfassungen tut, nur ohne den Graphen —
bei einem homogenen Bestand ist der Vertrag selbst schon die Einheit, über die
man iteriert.

Es funktioniert, es ist vollständig, es braucht kein Schema. Und es kostet
**n + 1 Modellaufrufe pro Frage**. Bei vierzehn Verträgen ist das ein
Rundungsfehler. Bei vierzehnhundert ist es ein Grund, die Frage doch ins Schema
zu nehmen.

### Routing: Die Frage wählt den Weg

![Eine Frage geht in einen Router. Drei Wege: Retrieval für lokale Fragen mit einem Modellaufruf pro Frage; Strukturabfrage für vorhergesehene globale Fragen mit null bis einem Aufruf; Map-Reduce über alle Verträge für unvorhergesehene globale Fragen mit n plus eins Aufrufen.](/assets/img/offene-fragen-drei-wege.svg)

Damit gibt es drei Wege, und die eigentliche Architekturfrage ist, wer
entscheidet, welcher genommen wird. Die Antwort ist heute fast immer:
**das Modell selbst, über Werkzeuge.** Ein Werkzeug `suche_vertragstext`, ein
Werkzeug `frage_tabelle`, und das Modell wählt. Eine lokale Frage landet im
Retrieval, eine globale in der Strukturabfrage.

Wer die
[text2SQL-Serie]({{ '/text2sql-agent-aws/' | relative_url }}) gelesen hat,
erkennt das wieder: Sobald die Verträge strukturiert sind, *ist* „Welche
Einheit hat die höchste Miete?" eine text2SQL-Frage. Die beiden Architekturen
sind nicht Alternativen, sondern zwei Hälften desselben Systems — Retrieval für
den Text, SQL für die Zahlen darin.

## Wie ich es versucht habe

Der POC geht einen Teil dieses Weges, und es lohnt sich, genau zu sagen,
welchen.

Beim Indexaufbau liest GPT-4.1-nano den Vertragskopf — die ersten zwei
Abschnitte, gedeckelt auf 8 000 Zeichen — mit `temperature = 0` und einem
Systemprompt, der Normalisierungen vorschreibt und im Zweifel `null` verlangt.
Das Ergebnis landet als `meta` im Suchindex: Objektcode, Einheitencodes,
Straße, Hausnummer, PLZ, Ort, Mieter, Mietbeginn, Ende der Festmietzeit. Die
Felder sind als `filterable` und teils `sortable` angelegt.

Zur Abfragezeit läuft zuerst das Retrieval, dann `filter_chunks_iterative_exact`:
ein Substring-Abgleich der Frage gegen die Metafelder, Feld für Feld, der die
Kandidaten auf den Vertrag eingrenzt, den die Frage nennt. Steht `GUT57` in der
Frage, bleiben nur GUT57-Chunks.

Das ist eine Instanz von „erst strukturieren, dann fragen" — aber für die
**Identität**, nicht für die **Inhalte**. Es beantwortet die Frage „welcher
Vertrag ist gemeint?", und das ist genau die Stelle, an der lokale Fragen sonst
an der Objektkennung scheitern. Dafür funktioniert es gut.

Die beiden Fragen vom Anfang beantwortet es nicht, und die Gründe sind
aufschlussreich:

- **Das Schema kennt die Miete nicht.** Es enthält, was man braucht, um einen
  Vertrag zu *finden* — nicht, was man braucht, um Verträge zu *vergleichen*.
  Kein Betrag, keine Indexierungsklausel, kein Intervall.
- **Der Filter läuft nach dem Retrieval.** Er grenzt die 22 oder 60 Kandidaten
  ein, die die Suche geliefert hat. Ein Vertrag, der es nicht in die Kandidaten
  geschafft hat, kann nicht hineingefiltert werden. Die Indexattribute
  `filterable` und `sortable` sind gesetzt, aber `$filter` und `$orderby` werden
  nie aufgerufen — die Struktur ist da, sie wird nur nicht als Struktur benutzt.
- **Die Daten sind Strings.** `start_date` und `fixed_term_end` sind vom Typ
  `String`, nicht `DateTimeOffset`. Ein Datumsbereich lässt sich darauf nicht
  filtern, eine Frist nicht berechnen.

Der Weg von hier ist kürzer, als es klingt: das Schema um typisierte Felder
erweitern (`rent: Double`, `index_clause: Boolean`, `next_index: DateTimeOffset`),
die Extraktion über den ganzen Vertrag laufen lassen statt nur über den Kopf,
und die Frage *vor* dem Retrieval als Strukturabfrage stellen, wenn sie eine
ist. Der Router fehlt noch ganz — im POC gehen alle Fragen denselben Weg.

## Was ich daraus schließe

**Die Frage, ob eine Frage ein Retrieval-Problem ist, muss vor dem Retrieval
gestellt werden.** Wer sie nicht stellt, bekommt für globale Fragen eine
Stichprobe, die wie eine Antwort aussieht — drei Verträge mit Mietangaben,
sauber belegt, und der teuerste fehlt. Das ist der gefährlichere Fehler als
gar keine Antwort.

---

**Kurzfassung:** Retrieval beantwortet lokale Fragen — die Antwort steht an
einer Stelle, Top-k findet sie. Bei homogenen Beständen wie Mietverträgen
scheitern drei Fragetypen strukturell: Vergleich und Aggregation (braucht alle
Verträge, und Zahlen sind weder suchbar noch ordnenbar), Berechnung (die
Antwort steht in keinem Text) und Abwesenheit (man kann nicht finden, was
fehlt). Stand der Technik ist, das Modell beim Indexaufbau ein typisiertes
Schema füllen zu lassen und globale Fragen dann als `$filter`/`$orderby` oder
SQL zu stellen — null Modellaufrufe statt n + 1. Ein Router, meist das Modell
selbst über Werkzeuge, wählt den Weg. Der POC strukturiert bereits, aber nur
die Identität, nur aus dem Vertragskopf, und nutzt die Struktur nach dem
Retrieval statt davor.
