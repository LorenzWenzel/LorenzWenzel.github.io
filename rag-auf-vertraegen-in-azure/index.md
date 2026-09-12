---
layout: page
title: "RAG auf Verträgen in Azure"
title_en: "RAG over Contracts in Azure"
permalink: /rag-auf-vertraegen-in-azure/
---

<div data-lang-block="de" markdown="1">
Dieses Projekt ist im Rahmen einer selbstständigen Arbeit in Auftrag eines Projektentwicklers entstanden. Erkenntnisse und Entscheidungen aus dem POC werden hier beschrieben. Es handelt von einer Serie über Retrieval-Augmented Generation auf deutschsprachigen Mietverträgen — gebaut mit **Azure Document Intelligence**, **Azure OpenAI** und **Azure AI Search**. Der einfache POC ist auch auf meinem [GitHub](https://github.com/LorenzWenzel/RAG_POC) zu finden.
</div>

<div data-lang-block="en" markdown="1">
This project was built as part of freelance work commissioned by a real-estate
developer. Findings and decisions from the POC are described here. It's a series
on retrieval-augmented generation over German-language rental contracts — built
with **Azure Document Intelligence**, **Azure OpenAI** and **Azure AI Search**.
The simple POC is also on my [GitHub](https://github.com/LorenzWenzel/RAG_POC).
</div>

![Architektur des RAG_POC: Streamlit-UI in Docker mit zwei Pipelines — RAG_POC.py auf den Index "chunks" mit Metadaten-Extraktion, UploadAnswer.py auf den Index "uploadchunks" ohne Metadaten. Beide sprechen mit Azure Document Intelligence für OCR, Azure AI Search für Hybrid-Suche mit semantischem Reranker, und Azure OpenAI für Embeddings und die Chat-Modelle.](/assets/img/rag-poc-architektur.jpeg)

{% include serie-liste.html kategorie="rag-auf-vertraegen-in-azure" %}
