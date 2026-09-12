---
slug: reranker-vs-retrieval
title: "Reranker vs. Retrieval"
---

Retrieval returns a sorted list. The best match sits at the top, the worst at
the bottom, every chunk carries a number. So why let a second model reshuffle
that list all over again?

The answer lies in **what** retrieval sorted by in the first place.

![Three-part diagram of a RAG pipeline. Left, offline ingestion: raw data and documents, chunking and preprocessing, embedding model, vector database. Middle, retrieval and reranking: the user query goes into the embedding model, then into vector search (ANN) against the database, which returns Top-K chunks with k around 20 to 50. These chunks, together with the original query, go into the reranker, a cross-encoder, which produces Top-N chunks with n around 3 to 5. Right, generation: prompt construction from context and query, LLM, final answer.](/assets/img/rag-reranker-pipeline.jpeg)

## Retrieval never saw the question

When the index is built, every chunk passes through the embedding model once
and is stored as a vector. At that point, the later question doesn't exist yet.
The vector has to pack everything the chunk could ever mean into 1,536 numbers
— without knowing what it will be asked.

At query time something surprisingly simple happens: the question also becomes
a vector, and the search compares two number sequences that were produced
**independently** of each other. That's exactly why it's so fast — the document
side was already finished before anyone asked anything. This design is called a
bi-encoder.

BM25 follows the same pattern with different means: the score comes from term
statistics that live in the index — how often the term appears in the chunk,
how rare it is across the corpus, how long the chunk is. That, too, was
computed without the question.

Both methods sort by the similarity of two descriptions computed separately.
What neither does: read the chunk in light of the actual question.

## What a reranker does differently

A reranker is a cross-encoder. It receives the question and the chunk as *one*
input, and every word of the question can see every word of the chunk. From the
Sentence Transformers documentation:

> We pass both sentences simultaneously to the Transformer network. It produces
> then an output value between 0 and 1 indicating the similarity of the input
> sentence pair.

The result is no longer a distance between two points, but a judgment about a
pair. The quality difference is well documented — the same source puts it
plainly: *"Cross-Encoder achieve better performances than Bi-Encoders."*

So why not search with it directly? Because nothing can be precomputed. The
model has to run once per candidate, for every single question. The Sentence
Transformers docs put a number on this with a clustering example: 10,000
sentences mean roughly 50 million pairs and about **65 hours** of compute — with
a bi-encoder it's **5 seconds**, because each sentence is encoded exactly once.

That draws the division of labor, and it's exactly what the diagram above
shows:

- **Retrieval** is cheap and can therefore be wide. It narrows millions down to
  a few dozen.
- **Reranking** is expensive and can therefore only be narrow. It narrows a few
  dozen down to a handful.

## How Azure AI Search does it

Azure AI Search's semantic reranker isn't a model you pick, but an extra step in
the query: `query_type=SEMANTIC` plus the name of a semantic configuration.
Under the hood run multilingual models developed at Bing. The
[documentation](https://learn.microsoft.com/en-us/azure/search/semantic-search-overview)
describes three steps.

**First: summarize.** The reranker doesn't get the raw text, but a "summary
string" per hit, assembled from the fields listed in the semantic
configuration — and each field has its own token budget:

| Field in the configuration | Budget |
|---|---:|
| `title` | 128 tokens |
| `keywords` | 128 tokens |
| `content` | the remainder |

Since November 2024, the entire summary string is capped at 2,048 tokens
(previously 256). Anything beyond that is cut off — which makes the field order
in the configuration a real decision, not a formality. The POC sets `heading` as
title, `content` as body, and seven meta fields — property code, street,
postal code, city, tenant, unit codes — share the 128 keyword tokens.

**Second: score.** Every hit gets a `@search.rerankerScore` between 0 and 4. And
that's not a similarity measure, but a scale with a spelled-out meaning:

| Score | Meaning per Microsoft |
|---:|---|
| 4.0 | fully answers the question |
| 3.0 | relevant but incomplete |
| 2.0 | partially relevant |
| 1.0 | related, answers a small part |
| 0.0 | irrelevant |

**Third: output.** Alongside the score, the step returns "captions" — the most
telling passages, optionally with highlights. These are always taken verbatim
from the index: *"There's no generative AI model in this workflow that creates
or composes new content."*

### Two limits worth knowing

The reranker sits **after** BM25 or after RRF fusion — it's a second sort over
an existing list, not a second search. And that list is capped: *"Even if
results include more than 50 results, only the top 50 results progress to
semantic ranking."*

## The distinction that matters in practice

Retrieval and reranking work on different problems, and you can't substitute
one for the other.

**Retrieval decides what's even in the running.** If the chunk with the answer
never made it into the candidates, no reranker will change that. The Azure docs
say this unusually directly: what the semantic reranker *can't* do is *"rerun
the query over the entire corpus to find semantically relevant results."*

**The reranker decides what rises to the top of that selection.** That's exactly
the discipline where retrieval is systematically weak: with rental contracts it
finds twenty notice-period clauses, because twenty contracts have one. Which one
belongs to the question is a reading task — and reading is exactly what a
cross-encoder does and vector similarity doesn't.

One side effect of the 0-to-4 scale is more useful than it looks:
`@search.score` is unbounded and only comparable within a single result list — a
score of 12 says nothing on its own. The `rerankerScore` is an absolute
judgment. "Anything under 1.5 never makes it into the prompt" is a rule you can
actually state. You can't say that about retrieval scores.

---

**In short:** Retrieval sorts by the similarity of two descriptions computed
independently — the chunk vector existed before the question did. A reranker
reads question and chunk together and is therefore more accurate, but too
expensive to search with. Azure AI Search builds a summary from title, keywords
and content for each hit, scores it on a 0-to-4 scale, and does so for at most
50 hits. The reranker improves the order, not the selection — whatever
retrieval didn't find stays lost.
