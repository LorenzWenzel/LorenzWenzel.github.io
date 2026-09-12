---
layout: page
title: "RAG auf Verträgen in Azure"
permalink: /rag-auf-vertraegen-in-azure/
---

Eine Serie über Retrieval-Augmented Generation auf deutschsprachigen
Mietverträgen — gebaut mit **Azure Document Intelligence**, **Azure OpenAI** und
**Azure AI Search**, hybrid aus BM25 und Vektorsuche, mit semantischem Reranking.

Verträge sind ein unangenehmer Sonderfall für RAG. Sie sind streng gegliedert,
aber ungleich lang; sie enthalten Kennungen wie `WE 03.12` oder `GUT57`, die ein
Embedding verwischt und eine Volltextsuche exakt trifft; sie verweisen auf sich
selbst; und ihre wichtigste Aussage ist manchmal, dass etwas **nicht** drinsteht.
Diese Serie geht die Stellen durch, an denen das den Aufbau verändert.

Grundlage ist ein Proof of Concept, der Mietverträge per OCR einliest, entlang
der Paragraphen zerlegt, Kopfdaten als Metadaten extrahiert und die Antworten
mit Quellenangaben belegt.

![Architektur des RAG_POC: Streamlit-UI in Docker mit zwei Pipelines — RAG_POC.py auf den Index "chunks" mit Metadaten-Extraktion, UploadAnswer.py auf den Index "uploadchunks" ohne Metadaten. Beide sprechen mit Azure Document Intelligence für OCR, Azure AI Search für Hybrid-Suche mit semantischem Reranker, und Azure OpenAI für Embeddings und die Chat-Modelle.](/assets/img/rag-poc-architektur.jpeg)

{% assign leer = "" | split: "," %}
{% assign serie = site.categories['rag-auf-vertraegen-in-azure'] | default: leer | sort: 'date' %}

<h2 class="section-heading">Erkenntnisse</h2>

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
  <li><strong>Retrieval-Varianten</strong> — reine Vektorsuche, BM25, Hybrid, Hybrid
  mit Reranker. Bei Objektcodes und Einheitenkennungen verhalten sie sich sehr
  unterschiedlich.</li>
  <li><strong>Chunking-Strategien</strong> — feste Tokenzahl, Schnitt am Paragraphen,
  semantisch. Und warum „800 Token“ nicht die 800 Token sind, die das Modell zählt.</li>
  <li><strong>Reranker vs. Retrieval</strong> — lohnt es sich, 60 Kandidaten zu holen und
  umsortieren zu lassen, oder wären 20 gut gesuchte genauso gut?</li>
  <li><strong>Wie werden „offene“ Fragen in RAG gelöst?</strong> — „Was steht in § 5?“
  beantwortet Top-k gut. „Welche Verträge laufen 2026 aus?“ strukturell gar nicht.</li>
  <li><strong>RAG-Strategien bei Verträgen</strong> — Verweise, Anlagen, Fristen, und das
  Problem, dass ein fehlender Paragraph eine Aussage ist.</li>
</ul>
