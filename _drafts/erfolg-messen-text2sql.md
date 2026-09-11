---
layout: post
title: "Wie misst man den Erfolg von text2SQL-Agenten?"
categories: text2sql-agent-aws
serie: "text2SQL-Agent auf AWS"
---

*Teil der Serie [text2SQL-Agent auf AWS](/text2sql-agent-aws/). Entwurf.*

Ohne Messung ist jede Aussage in dieser Serie Meinung. Nur: „richtig“ ist bei
text2SQL überraschend schwer zu definieren.

## Zu klären

- **Execution Accuracy vs. exakter SQL-Vergleich.** Zwei völlig verschiedene
  Abfragen können dasselbe Ergebnis liefern – und dieselbe Abfrage bei anderer
  Sortierung ein anderes. Was zählt als Treffer?
- **Golden Queries statt Benchmark.** Spider und BIRD messen ein generisches
  Modell, nicht den eigenen Data Lake. Wie baut man ein eigenes Set auf, das die
  Fachbereiche abnehmen?
- **Wie viele Fälle braucht es**, bevor eine Verbesserung von 3 % kein Rauschen
  mehr ist?
- **Teilerfolge.** Richtige Tabelle, falscher Join: völliger Fehlschlag oder
  halber Treffer? Eine binäre Metrik verschenkt Diagnoseinformation.
- **Der stille Fehler.** Ein Agent, der plausibel aussehende, aber falsche Zahlen
  liefert, ist gefährlicher als einer, der abbricht. Lässt sich das messen?
- **Was der Nutzer misst**: Abbruchquote, Nachfragen, manuelle Korrekturen.
  Offline-Metriken und Zufriedenheit laufen auseinander.
- Kosten je *gelöster* Aufgabe statt je Anfrage – ein billiger Turn, der drei
  weitere nach sich zieht, ist nicht billig.

## Erwartete These

Ein kleines, fachlich abgenommenes Golden Set schlägt jeden öffentlichen
Benchmark. Zu belegen.
