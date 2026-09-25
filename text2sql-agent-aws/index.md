---
layout: page
title: "text2SQL-Agent auf AWS"
title_en: "A text2SQL Agent on AWS"
permalink: /text2sql-agent-aws/
---

<div data-lang-block="de" markdown="1">
Dieses Projekt ist im Rahmen meiner Arbeit entstanden. Aus Gründen der
Vertraulichkeit zeige ich hier nicht die produktive Implementierung, sondern
eine vereinfachte, generalistische Version eines text2SQL-Agenten auf AWS.
Die Fragen und Learnings, die ich in den einzelnen Beiträgen bespreche, sind
reale Entscheidungen, vor denen ich bei der Umsetzung stand, hier jedoch in
verallgemeinerter Form, ohne Details aus dem produktiven Projekt.
</div>

<div data-lang-block="en" markdown="1">
This project was created as part of my work. For confidentiality reasons, I'm
not showing the production implementation here, but a simplified, generic
version of a text2SQL agent on AWS. The questions and learnings I discuss in
the individual posts are real decisions I faced during implementation, but
presented here in generalized form, without details from the production
project.
</div>

![Übersicht: Der Nutzer fragt den Chatbot. Der Chatbot ruft Amazon Bedrock für das Modell auf und den MCP-Server für die Werkzeuge. Der MCP-Server führt SQL auf Amazon Athena aus, Athena liest aus Amazon S3.](/assets/img/text2sql_architecture.jpeg)

{% include serie-liste.html kategorie="text2sql-agent-aws" %}

<h2 class="section-heading">{% include t.html key="in_arbeit" %}</h2>

<p>{% include t.html key="in_arbeit_intro" %}</p>

<ul class="todo-list">
  <li data-lang-block="de"><strong>Wie kommt der Agent an die Tabellenschemata?</strong> — Glue Data Catalog,
  <code>INFORMATION_SCHEMA</code>, vorgerechnete Schema-Karten: Vergleich der Zugänge.</li>
  <li data-lang-block="en"><strong>How does the agent get the table schemas?</strong> — Glue Data Catalog,
  <code>INFORMATION_SCHEMA</code>, precomputed schema cards: a comparison of the approaches.</li>
</ul>
