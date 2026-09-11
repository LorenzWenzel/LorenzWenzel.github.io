---
layout: post
title: "Retrieval-Varianten"
categories: rag-auf-vertraegen-in-azure
serie: "RAG auf Verträgen in Azure"
---

*Entwurf.*

Vier Wege, aus einem Index Kandidaten zu holen — und bei Verträgen verhalten sie
sich unterschiedlicher, als die Literatur nahelegt.

## Die Varianten

1. **Reine Vektorsuche.** Query-Embedding gegen HNSW-Index. Findet Umschreibungen,
   verliert exakte Zeichenketten.
2. **Reine Volltextsuche (BM25).** Findet `GUT57`, `WE 03.12`, `81675` punktgenau,
   scheitert an „Wann darf ich kündigen?“ gegen „Kündigungsfrist“.
3. **Hybrid.** Beides gleichzeitig, Fusion durch die Suchmaschine.
4. **Hybrid + semantischer Reranker.** Die Trefferliste wird danach noch einmal
   umsortiert (eigener Beitrag).

Der POC fährt Variante 4: `search_text` (BM25) und `vector_queries` im selben
Aufruf, `QueryType.SEMANTIC` mit der Konfiguration `default`, `topK0 = 60`.

## Warum das bei Verträgen nicht die übliche Abwägung ist

Mietverträge sind voller **Kennungen, die keine Bedeutung haben, sondern eine
Identität**: Objektcodes wie `GOET9`, Einheitenkennungen wie `ME#0.02`,
Postleitzahlen, Hausnummern. Ein Embedding bildet `WE 03.12` und `WE 03.13` auf
fast denselben Punkt ab — für die Suche ist das genau falsch. BM25 trennt sie
sauber.

Umgekehrt steht in keinem Vertrag das Wort „Kündigungsfrist“, wenn der
Paragraph „Beendigung des Mietverhältnisses“ heißt.

**These:** Bei diesem Korpus ist Hybrid nicht die vorsichtige Mitte, sondern die
einzige Variante, die beide Fragetypen überhaupt bedienen kann.

## Die fünfte Variante im POC

Nach dem Retrieval läuft `filter_chunks_iterative_exact` — ein harter Filter, der
die Query gegen die Metadatenfelder prüft, in fester Reihenfolge:
`property_code`, `unit_codes`, `street`, `street_plus_house`, `postal_code`,
`city`, `tenant`. Trifft ein Feld, wird die Menge auf genau diese Treffer
verkleinert; trifft keines, bleibt alles unverändert.

Das ist faktisch **Metadatenfilterung per Substring-Vergleich nach der Suche**,
nicht in ihr. Zu klären:

- Warum nicht als `filter` direkt in der Suchanfrage? (Azure AI Search kann das.)
- Was passiert bei einer Query, die zwei Objekte nennt?
- Was passiert bei Tippfehlern in der Kennung — der Substring-Vergleich ist exakt.
- Ist die feste Feldreihenfolge die richtige Priorisierung?

## Zu messen

Dieselben ~30 Fragen über alle Varianten, aufgeteilt nach Fragetyp:

| Fragetyp | Beispiel | Vermutung |
|---|---|---|
| Kennungsfrage | „Was steht in GUT57 zur Kaution?“ | BM25 nötig |
| Begriffsfrage | „Wann kann ich kündigen?“ | Vektor nötig |
| Gemischt | „Kündigungsfrist bei SOD118?“ | nur Hybrid |
| Aggregierend | „Welche Verträge laufen 2026 aus?“ | keine Variante |

Metrik: Ist der Chunk, der die Antwort enthält, unter den Top-k? Das lässt sich
ohne LLM-Bewertung auszählen.
