---
layout: page
title: "text2SQL-Agent auf AWS"
title_en: "A text2SQL Agent on AWS"
permalink: /text2sql-agent-aws/
---

<div data-lang-block="de" markdown="1">
Eine Serie über den Bau eines Agenten, der natürlichsprachige Fragen in SQL
übersetzt, die Abfrage gegen **Amazon Athena** ausführt und das Ergebnis
verständlich zurückgibt.
</div>

<div data-lang-block="en" markdown="1">
A series on building an agent that translates natural-language questions into
SQL, runs the query against **Amazon Athena**, and returns the result in plain
language.
</div>

![Übersicht: Der Nutzer fragt den Chatbot. Der Chatbot ruft Amazon Bedrock für das Modell auf und den MCP-Server für die Werkzeuge. Der MCP-Server führt SQL auf Amazon Athena aus, Athena liest aus Amazon S3.](/assets/img/text2sql_architecture.jpeg)

{% include serie-liste.html kategorie="text2sql-agent-aws" %}

<h2 class="section-heading">{% include t.html key="in_arbeit" %}</h2>

<p>{% include t.html key="in_arbeit_intro" %}</p>

<ul class="todo-list">
  <li data-lang-block="de"><strong>Wie misst man den Erfolg von text2SQL-Agenten?</strong> — Execution
  Accuracy, eigene Golden Queries, und der stille Fehler: plausible, aber falsche Zahlen.</li>
  <li data-lang-block="en"><strong>How do you measure the success of a text2SQL agent?</strong> — Execution
  accuracy, your own golden queries, and the silent failure: plausible but wrong numbers.</li>

  <li data-lang-block="de"><strong>Wie kommt der Agent an die Tabellenschemata?</strong> — Glue Data Catalog,
  <code>INFORMATION_SCHEMA</code>, vorgerechnete Schema-Karten: Vergleich der Zugänge.</li>
  <li data-lang-block="en"><strong>How does the agent get the table schemas?</strong> — Glue Data Catalog,
  <code>INFORMATION_SCHEMA</code>, precomputed schema cards: a comparison of the approaches.</li>
</ul>
