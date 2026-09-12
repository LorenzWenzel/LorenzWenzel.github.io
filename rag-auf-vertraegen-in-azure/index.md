---
layout: page
title: "RAG auf Verträgen in Azure"
title_en: "RAG over Contracts in Azure"
permalink: /rag-auf-vertraegen-in-azure/
---

<div data-lang-block="de" markdown="1">
Eine Serie über Retrieval-Augmented Generation auf deutschsprachigen
Mietverträgen — gebaut mit **Azure Document Intelligence**, **Azure OpenAI** und
**Azure AI Search**, hybrid aus BM25 und Vektorsuche, mit semantischem Reranking.
</div>

<div data-lang-block="en" markdown="1">
A series on retrieval-augmented generation over German-language rental contracts
— built with **Azure Document Intelligence**, **Azure OpenAI** and **Azure AI
Search**, hybrid BM25 and vector search, with semantic reranking.
</div>

![Architektur des RAG_POC: Streamlit-UI in Docker mit zwei Pipelines — RAG_POC.py auf den Index "chunks" mit Metadaten-Extraktion, UploadAnswer.py auf den Index "uploadchunks" ohne Metadaten. Beide sprechen mit Azure Document Intelligence für OCR, Azure AI Search für Hybrid-Suche mit semantischem Reranker, und Azure OpenAI für Embeddings und die Chat-Modelle.](/assets/img/rag-poc-architektur.jpeg)

{% include serie-liste.html kategorie="rag-auf-vertraegen-in-azure" %}
