---
layout: post
title: "Chunking-Strategien"
categories: rag-auf-vertraegen-in-azure
serie: "RAG auf Verträgen in Azure"
---

*Entwurf.*

Chunking ist die Entscheidung, die man einmal trifft und danach in jedem
Retrieval-Ergebnis wiedersieht. Bei Verträgen gibt es eine naheliegende Grenze —
den Paragraphen — und einen guten Grund, ihr nicht blind zu folgen.

## Was der POC macht

`chunk_tokenwise_with_line_snap`: Zielgröße **800 Token**, **100 Overlap**,
Minimum 600, Maximum 1000, Toleranz 150. Der Schnitt wird anschließend weich auf
die nächste **Zeilengrenze** oder **Satzgrenze** gezogen (Suchfenster 60–200
Token je Richtung). Zeilen, die mit `§` und einer Zahl beginnen, werden als
Überschrift erkannt und dem Chunk als `heading` mitgegeben.

Ein Detail mit Folgen: Der Tokenizer ist ein eigener Regex (`\w+|[^\w\s]`), nicht
der des Embedding-Modells. **„800 Token“ sind also nicht die 800 Token, die
`text-embedding-3-small` zählt** — die tatsächliche Zahl liegt bei deutschem
Vertragsdeutsch mit Komposita vermutlich darüber. Das ist kein Fehler, solange es
konsistent ist, aber es heißt: Die Zahl ist eine Stellschraube, keine Größe.

## Die Alternativen

| Strategie | Idee | Problem bei Verträgen |
|---|---|---|
| Feste Tokenzahl | schneide alle N Token | zerschneidet Sätze und Tabellen |
| **+ Snap** (POC) | wie oben, aber an Zeilen/Sätze gezogen | Größe schwankt |
| Am Paragraphen | ein `§` = ein Chunk | § 5 hat drei Zeilen, § 12 drei Seiten |
| Rekursiv | erst §, dann Absatz, dann Satz | mehr Code, schwerer zu debuggen |
| Semantisch | Schnitt bei Themenwechsel | teuer, bei Formularverträgen kaum Gewinn |
| Parent-Child | klein suchen, groß liefern | zwei Indizes, aber gute Aussichten |

## Die Fragen

**Warum nicht einfach am § schneiden?** Weil die Längenverteilung nicht passt.
Zu prüfen: Wie sieht sie im Korpus tatsächlich aus? Ein Histogramm über alle
Paragraphenlängen beantwortet das in zehn Minuten und entscheidet die Frage.

**Was kostet der Overlap?** 100 von 800 Token sind 12,5 % doppelt im Index —
doppelte Embedding-Kosten, doppelter Speicher, und ein Duplikat kann zweimal in
den Top-k landen. Wie oft passiert das?

**Wie gut ist die §-Erkennung?** Der Regex verlangt `§` am Zeilenanfang mit
maximal drei Leerzeichen davor und höchstens 100 Zeichen Länge. Was ist mit
OCR-Fehlern (`§` als `5`, `$`), mit Anlagen ohne §, mit Tabellen?

**Trägt das `heading` überhaupt?** Es wandert in die semantische Konfiguration
als `title_field`. Bei einer Überschrift wie „§ 7“ ohne Text ist das wenig wert;
bei „§ 7 Schönheitsreparaturen“ viel. Wie verteilt sich das?

## Zu messen

Denselben Fragenkatalog gegen drei Indizes: Snap-Chunking wie im POC, reines
Paragraphen-Chunking, feste 400 Token ohne Snap. Gezählt wird, ob der Chunk mit
der Antwort in den Top-k liegt — und ob er die Antwort **vollständig** enthält
oder an der Schnittkante abbricht. Das Zweite ist bei Verträgen das
interessantere Maß.
