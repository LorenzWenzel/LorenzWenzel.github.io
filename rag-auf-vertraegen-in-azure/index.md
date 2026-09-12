---
layout: page
title: "RAG auf Verträgen in Azure"
permalink: /rag-auf-vertraegen-in-azure/
---

Eine Serie über Retrieval-Augmented Generation auf deutschsprachigen
Mietverträgen — gebaut mit **Azure Document Intelligence**, **Azure OpenAI** und
**Azure AI Search**, hybrid aus BM25 und Vektorsuche, mit semantischem Reranking.

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
  <li><strong>Wie werden „offene“ Fragen in RAG gelöst?</strong> — „Was steht in § 5?“
  beantwortet Top-k gut. „Welche Verträge laufen 2026 aus?“ strukturell gar nicht.</li>
</ul>
