---
layout: page
title: "text2SQL-Agent auf AWS"
permalink: /text2sql-agent-aws/
---

Eine Serie über den Bau eines Agenten, der natürlichsprachige Fragen in SQL
übersetzt, die Abfrage gegen **Amazon Athena** ausführt und das Ergebnis
verständlich zurückgibt.

![Übersicht: Der Nutzer fragt den Chatbot. Der Chatbot ruft Amazon Bedrock für das Modell auf und den MCP-Server für die Werkzeuge. Der MCP-Server führt SQL auf Amazon Athena aus, Athena liest aus Amazon S3.](/assets/img/text2sql_architecture.jpeg)


{% assign serie = site.categories['text2sql-agent-aws'] | sort: 'date' %}

<h2 class="section-heading">Erschienen</h2>

{% if serie.size > 0 %}
<ul class="post-list-plain">
  {%- for post in serie %}
  <li>
    <span class="post-date">{{ post.date | date: "%d.%m.%Y" }}</span>
    <a class="post-link" href="{{ post.url | relative_url }}">{{ post.title | escape }}</a>
    {%- if post.excerpt %}
    <p class="post-excerpt">{{ post.excerpt | strip_html | normalize_whitespace | truncate: 200 }}</p>
    {%- endif %}
  </li>
  {%- endfor %}
</ul>
{% else %}
<p><em>Noch nichts veröffentlicht.</em></p>
{% endif %}

<h2 class="section-heading">In Arbeit</h2>

<p>Die folgenden Teile sind angelegt, aber noch nicht geschrieben:</p>

<ul class="todo-list">
  <li><strong>Wie misst man den Erfolg von text2SQL-Agenten?</strong> — Execution
  Accuracy, eigene Golden Queries, und der stille Fehler: plausible, aber falsche Zahlen.</li>
  <li><strong>Bedrock AgentCore vs. Converse + MCP</strong> — zwei Wege, denselben
  Agenten zu betreiben. Was gibt man auf, wenn man die Orchestrierung an AWS abgibt?</li>
  <li><strong>Wie kommt der Agent an die Tabellenschemata?</strong> — Glue Data Catalog,
  <code>INFORMATION_SCHEMA</code>, vorgerechnete Schema-Karten: Vergleich der Zugänge.</li>
</ul>
