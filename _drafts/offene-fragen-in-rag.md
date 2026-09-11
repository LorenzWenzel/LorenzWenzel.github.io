---
layout: post
title: "Wie werden „offene“ Fragen in RAG gelöst?"
categories: rag-auf-vertraegen-in-azure
serie: "RAG auf Verträgen in Azure"
---

*Entwurf.*

Zwei Fragen an denselben Korpus:

> „Was steht in GUT57 zur Kaution?“

> „Welche Verträge laufen 2026 aus?“

Die erste beantwortet Top-k-Retrieval gut. Die zweite beantwortet es **nie** —
und zwar nicht schlecht, sondern strukturell gar nicht.

## Warum das kein Qualitätsproblem ist

Der POC liefert `TOP_K = 3` Chunks an das Modell, bei `per_doc_cap` von 3 bis 4
also aus höchstens drei Dokumenten. Eine Frage, deren Antwort lautet „diese
sieben von zwanzig“, kann aus drei Chunks nicht richtig beantwortet werden. Das
Modell bekommt gar nicht die Gelegenheit, sich zu irren — es sieht die anderen
siebzehn Verträge nicht.

Schlimmer: Es **merkt** das nicht. Die Antwort wird plausibel klingen, Quellen
tragen und eine Teilmenge nennen, als wäre sie die Menge. Der Systemprompt
verlangt Belege für jede Aussage; er kann nicht verlangen, dass etwas belegt
wird, das nicht im Kontext liegt.

Das ist die gefährlichste Fehlerart in diesem ganzen Aufbau: **eine vollständig
belegte, vollständig falsche Antwort.**

## Welche Fragetypen betroffen sind

| Typ | Beispiel | Top-k? |
|---|---|---|
| Punktuell | „Kaution in GUT57?“ | ja |
| Vergleichend | „Unterscheiden sich GUT57 und SOD118 bei der Kaution?“ | oft |
| Aggregierend | „Wie viele Verträge haben eine Staffelmiete?“ | nein |
| Filternd | „Welche laufen 2026 aus?“ | nein |
| Negativ | „Welche Verträge regeln keine Schönheitsreparaturen?“ | nein |

Die letzte Zeile ist die härteste: Abwesenheit lässt sich nicht retrieven.

## Lösungsrichtungen

**1. Die Frage gar nicht an RAG geben.** Die Metadaten liegen bereits strukturiert
im Index — `start_date`, `fixed_term_end`, `city`, `tenant`, `unit_codes`,
`property_code`. „Welche Verträge laufen 2026 aus?“ ist keine Retrieval-Frage,
sondern eine Abfrage über ein Feld. Das ist dieselbe Aufgabe wie in der anderen
Serie, nur mit dem Suchindex statt Athena als Datenquelle.

**2. Query-Routing.** Ein vorgeschalteter Schritt entscheidet: punktuelle Frage →
RAG, aggregierende Frage → strukturierte Abfrage. Kostet einen Modellaufruf und
verlagert das Problem auf die Klassifikation.

**3. Map-Reduce über alle Dokumente.** Jeden Vertrag einzeln fragen, Antworten
einsammeln. Korrekt, aber teuer und langsam — und bei zwanzig Verträgen noch
machbar, bei zweitausend nicht.

**4. Vorberechnen.** Die Felder, nach denen gefragt wird, beim Indexieren
extrahieren — was der POC für den Vertragskopf bereits tut. Die Frage ist, wie
weit man das treibt: Staffelmiete, Kündigungsfristen, Indexklauseln als
Metadatenfelder?

**5. Ehrlich abbrechen.** Erkennen, dass die Frage aggregierend ist, und sagen:
„Diese Frage kann ich über den Volltext nicht verlässlich beantworten.“ Die
unbeliebteste Lösung und oft die richtige.

## Zu klären

- Wie häufig sind aggregierende Fragen bei echten Nutzern? Ohne diese Zahl ist
  jede der fünf Richtungen eine Wette.
- Lässt sich der Fragetyp zuverlässig klassifizieren — und was kostet ein
  Fehlurteil in jede Richtung?
- Wo ist die Grenze von Richtung 4? Jedes vorberechnete Feld ist eine Wette
  darauf, dass jemand danach fragt.
