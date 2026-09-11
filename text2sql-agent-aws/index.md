---
layout: page
title: "text2SQL-Agent auf AWS"
permalink: /text2sql-agent-aws/
---

Eine Serie über den Bau eines Agenten, der natürlichsprachige Fragen in SQL
übersetzt, die Abfrage gegen **Amazon Athena** ausführt und das Ergebnis
verständlich zurückgibt. Weniger Prompt-Kosmetik, mehr Messwerte: Was kostet
eine Designentscheidung tatsächlich an Token, an Latenz und an Qualität?

Die Serie arbeitet sich von unten nach oben durch den Stack – vom Format, in dem
Daten den Agenten erreichen, über die Frage, woher er sein Domänenwissen bezieht,
bis zur Wahl der Laufzeitumgebung.

## Erschienen

{% assign serie = site.categories['text2sql-agent-aws'] | sort: 'date' %}
{% if serie %}
<ul>
{% for post in serie %}
  <li>
    <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
    <br><small>{{ post.date | date: "%-d. %B %Y" }}{% if post.excerpt %} — {{ post.excerpt | strip_html | truncate: 120 }}{% endif %}</small>
  </li>
{% endfor %}
</ul>
{% else %}
<p><em>Noch nichts veröffentlicht.</em></p>
{% endif %}

## In Arbeit

Die folgenden Teile sind angelegt, aber noch nicht geschrieben:

- **Wie misst man den Erfolg von text2SQL-Agenten?** — Execution Accuracy,
  eigene Golden Queries, und der stille Fehler: plausible, aber falsche Zahlen.
- **Bedrock AgentCore vs. Converse + MCP** — zwei Wege, denselben Agenten zu
  betreiben. Was gibt man auf, wenn man die Orchestrierung an AWS abgibt?
- **Wie kommt der Agent an die Tabellenschemata?** — Glue Data Catalog,
  `INFORMATION_SCHEMA`, vorgerechnete Schema-Karten: Vergleich der Zugänge.
