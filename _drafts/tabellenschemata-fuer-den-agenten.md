---
layout: post
title: "Wie kommt der Agent an die Tabellenschemata?"
categories: text2sql-agent-aws
serie: "text2SQL-Agent auf AWS"
---

*Teil der Serie [text2SQL-Agent auf AWS](/text2sql-agent-aws/). Entwurf.*

Ohne Schema kein SQL. Aber ein Data Lake hat selten zwölf Tabellen, sondern
zwölfhundert – und die passen nicht in den Kontext.

## Zu klären

- Bezugsquellen: Glue Data Catalog, `INFORMATION_SCHEMA`, `SHOW CREATE TABLE`,
  vorgerechnete Schema-Karten.
- Vorab laden oder per Tool nachfragen? (Derselbe Pull/Push-Konflikt wie beim
  Domänenwissen.)
- Vorauswahl: Welche Tabellen sind für diese Frage überhaupt relevant?
- **Das Format ist hier ein anderes als beim Resultset.** Schemata sind
  verschachtelt und uneinheitlich, nicht rechteckig – die Argumentation aus
  Teil 1 greift nicht. Eine Messung über das TPC-DS-Schema (24 Tabellen) sieht
  YAML mit 12 729 Token vorn, vor JSON mit 16 320 (+28 %) und Markdown mit
  20 382 (+60 %). Nachrechnen und gegen Athena-Realität prüfen.
- Was kosten Fremdschlüssel und Beispielwerte – und was bringen sie an Trefferquote?

## Erwartete These

Schema-Verdichtung schlägt Schema-Vollständigkeit. Zu belegen.
