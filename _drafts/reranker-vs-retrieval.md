---
layout: post
title: "Reranker vs. Retrieval"
categories: rag-auf-vertraegen-in-azure
serie: "RAG auf Verträgen in Azure"
---

*Entwurf.*

Der POC holt **60 Kandidaten** und lässt sie vom semantischen Reranker
umsortieren. Die Frage dahinter ist eine Budgetfrage: Lohnt sich breit suchen und
nachsortieren — oder wären zwanzig gut gesuchte Treffer genauso gut?

## Drei Sortierungen hintereinander

Im POC greifen drei Mechanismen nacheinander in die Reihenfolge ein, und das ist
selten bewusst entworfen:

1. **Die Suche** liefert `@search.score` aus der Hybrid-Fusion von BM25 und Vektor.
2. **Der semantische Reranker** liefert `@search.reranker_score`; der Code
   sortiert danach und fällt nur zurück, wenn kein Reranker-Score da ist.
3. **`per_doc_cap`** wirft alles weg, was pro Dokument über dem Limit liegt —
   „strikt, kein zweites Auffüllen“. Das ist der stärkste Eingriff, denn er
   entfernt Treffer unabhängig von ihrem Score.

Nach diesen drei Schritten bleiben laut `common.py` `TOP_K = 3` Chunks übrig,
aus `FIRST_K = 22` Kandidaten mit `PER_DOC_CAP = 4`. Die Funktionssignatur in
`RAG_POC.py` trägt andere Standardwerte (`topK0=60`, `per_doc_cap=3`) — **welche
Werte im Betrieb tatsächlich gelten, ist die erste Sache, die ich klären muss.**

## Was zu klären ist

- **Wie viele Treffer bewertet der Reranker überhaupt?** Der semantische Reranker
  in Azure AI Search arbeitet nicht unbegrenzt auf der Kandidatenliste. Wenn die
  Grenze unter 60 liegt, sind die hinteren Kandidaten umsonst geholt. Das steht
  in der Azure-Dokumentation und gehört nachgeschlagen, nicht geraten.
- **Was kostet er an Latenz und Geld?** Semantisches Reranking ist bei Azure AI
  Search ein eigener Posten mit eigener Kontingentierung.
- **Was bringt er?** Der ehrliche Test ist ein A/B mit identischer Query-Menge:
  einmal `QueryType.SEMANTIC`, einmal ohne, beide auf `topK0 = 60`, und die
  Frage, ob der richtige Chunk nach oben wandert.

## Die eigentliche These

Reranking repariert ein schlechtes Retrieval nicht, es sortiert es nur. Wenn der
Chunk mit der Antwort nicht unter den 60 Kandidaten ist, ändert kein Reranker
etwas daran. Der Reranker hilft dort, wo das Retrieval **zu viel** findet, nicht
dort, wo es **das Falsche** findet.

Bei Verträgen ist „zu viel“ der Normalfall: Zwanzig Verträge enthalten eine
Kündigungsfrist, und BM25 findet alle zwanzig. Deshalb die Vermutung, dass
Reranker plus `per_doc_cap` hier mehr bringen als anderswo — und dass von beiden
`per_doc_cap` der wirksamere ist.

Zu prüfen ist auch die Gegenrichtung: `per_doc_cap` schneidet hart. Wenn die
Antwort in **zwei** Chunks desselben Vertrags steht und die Kappe bei 3 liegt,
geht es gut; steht sie in fünf, nicht. Wie oft ist die Antwort über mehrere
Chunks eines Dokuments verteilt?

## Zu messen

| Aufbau | topK0 | Reranker | per_doc_cap |
|---|---:|---|---:|
| A | 20 | nein | keine |
| B | 20 | ja | keine |
| C | 60 | ja | keine |
| D | 60 | ja | 3 |
| E | 60 | ja | 1 |

Gemessen wird Trefferquote in den Top-3 plus Latenz. Wenn B ≈ C, sind die
zusätzlichen 40 Kandidaten überflüssig; wenn D deutlich über C liegt, ist die
Kappe der eigentliche Hebel und der Reranker die Nebensache.
