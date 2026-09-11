---
layout: post
title: "Bedrock AgentCore vs. Converse + MCP"
categories: text2sql-agent-aws
serie: "text2SQL-Agent auf AWS"
---

*Teil der Serie [text2SQL-Agent auf AWS](/text2sql-agent-aws/). Entwurf.*

Zwei Wege, denselben text2SQL-Agenten zu betreiben: die Orchestrierung an AWS
abgeben oder die Schleife selbst schreiben.

## Zu klären

- Was genau übernimmt AgentCore – Schleife, Speicher, Identität, Tool-Aufrufe?
- Was kostet der eigene `Converse`-Loop an Code, und was gewinnt man an Kontrolle?
- Wie kommt MCP in beiden Varianten ins Spiel, und wo liegen die Tool-Definitionen?
- Observability: Traces, Nachvollziehbarkeit fehlerhafter SQL-Generierung.
- Latenz je Turn im direkten Vergleich.
- Lock-in: Wie teuer wäre der Rückweg?

## Erwartete These

*(noch offen – erst messen, dann behaupten)*
