---
layout: post
title: "Retrieval-Varianten"
title_en: "Retrieval Variants"
date: 2025-10-12 20:15:00 +0200
serie: "RAG auf Verträgen in Azure"
---

Vor jedem RAG-System steht eine Entscheidung, die man meist nicht trifft, sondern
erbt: Wonach wird eigentlich gesucht? Die Antwort hat drei Stufen — Volltext,
Vektoren, beides — und bei Mietverträgen verhalten sie sich unterschiedlicher,
als die Literatur nahelegt.

Dieser Beitrag geht nur ums Finden. Was danach mit der Trefferliste passiert,
steht in einem eigenen Teil.

## BM25: zählen, aber richtig

BM25 ist die Standardformel für Volltextsuche und in Azure AI Search seit Juli
2020 fest eingebaut — ältere Dienste konnten noch `ClassicSimilarity`, neue
akzeptieren nichts anderes mehr
([Doku](https://learn.microsoft.com/en-us/azure/search/index-similarity-and-scoring)).

Die Idee lässt sich in einem Satz sagen: **Ein Treffer zählt umso mehr, je öfter
der Begriff im Dokument steht, je seltener er im Gesamtbestand ist, und je
kürzer das Dokument.** Drei Faktoren, und alle drei sind bei Verträgen relevant.

### Selten schlägt häufig

Der zweite Faktor — die inverse Dokumenthäufigkeit — ist der wichtigste. Ich
habe ihn an einem Miniaturkorpus aus sechs Vertragsabschnitten nachgerechnet:

| Begriff | in wie vielen Abschnitten | IDF |
|---|---:|---:|
| `der` | 6 von 6 | 0,074 |
| `kaution` | 3 von 6 | 0,693 |
| `mietvertrag` | 2 von 6 | 1,030 |
| `gut57` | 1 von 6 | **1,540** |
| `03.12` | 1 von 6 | **1,540** |

Ein Objektcode, der genau einmal vorkommt, wiegt das Zwanzigfache eines
Artikels. Fragt man nach `GUT57 WE 03.12`, bleibt von sechs Abschnitten **einer**
mit einem Score von 4,30 übrig — alle anderen bei null. Das ist kein Ranking
mehr, das ist ein Treffer.

### Was k1 macht

Der erste Faktor ist subtiler. Man könnte annehmen, ein Begriff, der zwanzigmal
vorkommt, sei zwanzigmal so relevant. BM25 nimmt das ausdrücklich nicht an:

![Vier Kurven für k1 = 0; 0,5; 1,2 und 3,0. Bei k1 = 0 bleibt der Beitrag konstant bei 1×, unabhängig davon wie oft der Begriff vorkommt. Bei größerem k1 wächst der Beitrag mit der Häufigkeit, flacht aber ab — bei k1 = 1,2 erreicht er nach zwanzig Vorkommen etwa das Doppelte.](/assets/img/bm25-saettigung.svg)

Bei der Azure-Voreinstellung `k1 = 1,2` bringt das zwanzigste Vorkommen eines
Begriffs gerade noch das 2,08-fache des ersten. Die Kurve sättigt. Der Grund
steht so in der Dokumentation: Bei der Suche nach „Apollo Spaceflight" soll ein
Artikel über griechische Mythologie, der „Apollo" dutzendfach enthält und
„Spaceflight" nie, nicht über einen Artikel gewinnen, der beide Wörter je ein
paar Mal nennt.

Für Verträge heißt das: Ein Paragraph, der „Kaution" achtmal schreibt, schlägt
einen, der sie einmal definiert, **nicht** um das Achtfache. Richtig so — die
Definition steht meist in dem Paragraphen, der das Wort einmal nennt.

### Was b macht

Der dritte Faktor normalisiert auf die Dokumentlänge, Voreinstellung `b = 0,75`.
Bei `b = 0` ist die Länge egal, bei `b = 1` wird voll normalisiert. Konkret, für
denselben Begriff mit derselben Häufigkeit in einem halb so langen gegenüber
einem doppelt so langen Chunk:

| b | kurzer Chunk | langer Chunk | Verhältnis |
|---|---:|---:|---:|
| 0,00 | 1,375 | 1,375 | 1,00 |
| 0,50 | 1,517 | 1,158 | 1,31 |
| **0,75** | **1,600** | **1,073** | **1,49** |
| 1,00 | 1,692 | 1,000 | 1,69 |

Das ist eine stille Verbindung zum Chunking: Wer Chunks mit stark schwankender
Länge erzeugt — und genau das tut ein Schnitt entlang der Paragraphen —,
bestraft die langen systematisch. Bei fester Token-Zielgröße wie im POC spielt
`b` kaum eine Rolle, weil alle Chunks ungefähr gleich lang sind.

### Wo BM25 aufhört

An der Sprache. In keinem der Verträge steht das Wort „Kündigungsfrist", wenn der
Paragraph „Beendigung des Mietverhältnisses" heißt. BM25 sucht Zeichenketten,
keine Bedeutungen. Der deutsche Analyzer `de.microsoft`, den der POC auf
`heading` und `content` legt, fängt einen Teil davon ab — er lemmatisiert und
zerlegt Komposita, findet also „Mietverhältnis" auch in „Mietverhältnisses"
([Doku](https://learn.microsoft.com/en-us/azure/search/index-add-language-analyzers)).
Aber er macht aus einer Umschreibung keinen Begriff.

## Embeddings: Bedeutung, aber unscharf

Die Vektorsuche dreht das Problem um. Text wird in einen Punkt in einem
hochdimensionalen Raum abgebildet — im POC über `text-embedding-3-small` mit
1 536 Dimensionen —, und Nähe in diesem Raum soll Ähnlichkeit in der Bedeutung
sein. „Wann kann ich raus aus dem Vertrag?" landet dann in der Nähe von
„Beendigung des Mietverhältnisses", ohne ein Wort gemeinsam zu haben.

### Von Wörtern zu Vektoren

Woher diese Nähe kommt, lohnt einen kurzen Umweg, weil er erklärt, warum
Embeddings ausgerechnet an Kennungen scheitern.

Die Grundannahme ist so alt wie schlicht: Wörter, die in ähnlichen Kontexten
auftauchen, haben eine ähnliche Bedeutung — *„a word is characterized by the
company it keeps"*. Man sieht sich dafür in Millionen von Texten an, welche
Wörter jeweils links und rechts neben einem Zielwort stehen.

Ein Beispiel mit einem Fenster von zwei Nachbarwörtern:

- „Der **König** regiert das Land."
- „Der **Herrscher** regiert das Land."
- „Die **Königin** regiert das Land."

„König", „Herrscher" und „Königin" tauchen in fast identischen Kontexten auf —
umgeben von „Der/Die" und „regiert das Land". Ein Modell, das aus dem Kontext
das Zielwort vorhersagen soll (oder umgekehrt), lernt daraus, dass sich die drei
Wörter semantisch ähneln, und ordnet ihnen entsprechend nahe beieinanderliegende
Vektoren zu. „Fahrrad" oder „Banane" tauchen in völlig anderen Kontexten auf und
landen im Vektorraum weit entfernt.

Diese Grundidee ist bis heute unverändert. Was sich geändert hat, ist die
Architektur, mit der sie umgesetzt wird. Statt eines festen Zwei-Wort-Fensters
und eines flachen neuronalen Netzes — wie bei word2vec — betrachten heutige
Modelle mit tiefen Transformer-Architekturen und Self-Attention den gesamten
Satz oder Absatz gleichzeitig und gewichten dabei dynamisch, welche Wörter für
die Bedeutung eines anderen Wortes relevant sind. Dadurch werden Embeddings
**kontextabhängig** — „Bank" bekommt je nach Satz („Ich sitze auf der Bank" vs.
„Ich gehe zur Bank") einen unterschiedlichen Vektor, was mit dem einfachen
Nachbarschaftsprinzip allein nicht möglich wäre. Erst die Rechenleistung und die
Trainingsdatenmengen, die heute zur Verfügung stehen, machen diese deutlich
komplexeren Modelle praktikabel.

Für Verträge ist das kein Nebenaspekt: Dasselbe Prinzip, das „König" und
„Herrscher" zusammenrückt, rückt auch `WE 03.12` und `WE 03.13` zusammen — beide
tauchen in praktisch identischen Kontexten auf, und keiner davon hilft dem
Modell, sie auseinanderzuhalten. Was bei Bedeutung die Stärke ist, ist bei
Identität die Schwäche.

Azure AI Search sucht darin mit **HNSW**, einem Näherungsverfahren: ein
hierarchischer Graph, in dem jeder Punkt mit bis zu `m` Nachbarn verbunden ist
und die Suche sich von groben zu feinen Ebenen durchhangelt. `efConstruction`
(Standard 400) steuert, wie sorgfältig der Graph gebaut wird, `efSearch`, wie
breit zur Laufzeit gesucht wird
([Doku](https://learn.microsoft.com/en-us/azure/search/vector-search-ranking)).
Das Verfahren ist *approximativ* — es findet die nächsten Nachbarn meistens,
nicht garantiert. Wer die Garantie braucht, nimmt `exhaustive: true` und zahlt
mit Laufzeit.

Ein Detail, das gern zu Fehlschlüssen führt: **Der zurückgegebene Score ist nicht
der Kosinus.** Azure rechnet `1 / (1 + Kosinus-Distanz)` und landet damit im
Bereich 0,333 bis 1,00. Wer Schwellenwerte auf „Kosinus > 0,8" setzt, setzt sie
auf etwas anderes, als er denkt; die Doku liefert die Rückrechnung mit.

### Wo Embeddings aufhören

An Kennungen. Ich habe durch den Tokenizer geschickt, was in diesen Verträgen
die Identität trägt:

```
GUT57      -> 3 Token: ['G', 'UT', '57']
SOD118     -> 3 Token: ['S', 'OD', '118']
WE 03.12   -> 5 Token: ['WE', ' ', '03', '.', '12']
ME#0.02    -> 5 Token: ['ME', '#', '0', '.', '02']
```

`GUT57` existiert für das Modell nicht als Einheit. Es zerfällt in drei
Fragmente, von denen keines den Code meint — `UT` und `57` kommen in tausend
anderen Zusammenhängen vor. Der Vektor von `GUT57` liegt deshalb irgendwo
zwischen den Vektoren beliebiger anderer Buchstaben-Zahlen-Kombinationen, und
`WE 03.12` und `WE 03.13` liegen praktisch aufeinander.

Für Fließtext ist das die gewünschte Eigenschaft: Ähnliches soll nahe
beieinander liegen. Für Aktenzeichen ist es genau falsch.

## Hybrid: nicht Kompromiss, sondern Ergänzung

Beide Verfahren scheitern an dem, worin das andere gut ist. Das ist der Grund,
warum hybride Suche heute der Normalfall ist — nicht Vorsicht, sondern
Arbeitsteilung.

Die naheliegende Umsetzung wäre, beide Scores zu normalisieren und zu addieren.
Azure AI Search macht das ausdrücklich **nicht**, und der Grund steht in den
Zahlen: BM25-Scores sind nach oben unbegrenzt, Vektor-Scores liegen zwischen
0,333 und 1,00. Die Skalen haben nichts miteinander zu tun, und eine Umrechnung
müsste man je Korpus neu eichen.

Stattdessen kommt **Reciprocal Rank Fusion** zum Einsatz: Gerechnet wird mit
*Plätzen*, nicht mit Scores. Jede Liste steuert für jedes Dokument
`1 / (k + Platz)` bei, die Beiträge werden addiert, und `k` ist eine Konstante —
in Azure fest 60
([Doku](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)).

![Drei Spalten: die BM25-Trefferliste, die Vektor-Trefferliste und die fusionierte Liste. Jeder Platz steuert 1 durch 60 plus Platz bei. Dokumente, die in beiden Listen vorkommen, landen oben; Dokumente aus nur einer Liste rutschen nach unten.](/assets/img/rrf-fusion.svg)

Der Vorteil ist damit ausgerechnet, dass **die Skalen egal sind**. Es spielt
keine Rolle, ob BM25 einen Score von 4,3 oder 43 liefert — nur der Platz zählt.
Das macht das Verfahren robust gegen Korpuswechsel, gegen andere
Embedding-Modelle und gegen die Tatsache, dass BM25-Scores je nach Shard
schwanken.

### Die Eigenschaft, die dabei entsteht

Interessanter als die Robustheit ist, was RRF implizit belohnt:

| Fall | RRF-Score |
|---|---:|
| Platz 5 in **beiden** Listen | 0,03077 |
| Platz 1 in **nur einer** Liste | 0,01639 |

**Einigkeit schlägt Dominanz um Faktor 1,9.** Ein Dokument, das beide Verfahren
mittelmäßig gut finden, landet vor einem, das nur eines für perfekt hält. Bei
zwei Listen ist das so deutlich, dass ein Dokument, das in einer Liste auf Platz
1 und in der anderen erst auf Platz 100 steht, immer noch vorn liegt
(0,02264 gegen 0,01639).

Für Verträge ist das die richtige Voreinstellung. Die Frage „Kündigungsfrist bei
SOD118?" hat einen lexikalischen Anteil (`SOD118`) und einen semantischen
(`Kündigungsfrist` ≈ `Beendigung`). Der gesuchte Chunk ist der, den beide
Verfahren für plausibel halten — nicht der, den eines für perfekt hält.

### Vier Zahlen, die alle „k" heißen

Die häufigste Verwechslung in hybriden Abfragen, und die Doku warnt
ausdrücklich davor:

![Vier Kästen nebeneinander: maxTextRecallSize mit Standard 1000, k_nearest_neighbors mit 60, die RRF-Konstante k fest 60 als gestrichelter Kasten, und top mit 60. Nur drei davon steuern Mengen.](/assets/img/hybrid-vier-zahlen.svg)

Die RRF-Konstante ist **keine Menge**. Sie größer zu setzen holt keinen einzigen
zusätzlichen Treffer — sie flacht nur ab, wie stark die vorderen Plätze
gegenüber den hinteren gewichtet werden. Bei kleinem `k` dominiert Platz 1
alles, bei großem `k` nähern sich alle Plätze an. Der Wert 60 stammt aus der
Ursprungsarbeit von Cormack, Clarke und Büttcher (2009) und hat sich seither
gehalten.

Die Mengen sind die anderen drei. Im POC steht:

```python
vq = VectorizedQuery(vector=q_emb, k_nearest_neighbors=topK0, fields="embedding")

doc_client.search(
    search_text=query,        # BM25-Seite
    vector_queries=[vq],      # Vektorseite
    top=topK0,
)
```

Zwei Abfragen laufen parallel, RRF verschmilzt sie, `top` bestimmt, was
herauskommt. `maxTextRecallSize` ist nicht gesetzt und steht damit auf 1 000 —
die Volltextseite sucht deutlich breiter, als die 60 vermuten lassen, und liefert
RRF eine entsprechend lange Liste zu.

## Was ich daraus schließe

**Hybrid ist hier nicht die vorsichtige Mitte, sondern die einzige Variante, die
beide Fragetypen bedienen kann.** Bei einem Korpus aus Fließtext könnte man über
reine Vektorsuche diskutieren; bei einem, in dem `GUT57` und `WE 03.12` die
Identität tragen, nicht.

---

**Kurzfassung:** BM25 gewichtet seltene Begriffe hoch, sättigt bei häufigen
Wiederholungen (`k1`) und normalisiert auf die Dokumentlänge (`b`) — für
Objektcodes ist das exakt richtig, für Umschreibungen blind. Embeddings können
Umschreibungen, zerlegen aber `GUT57` in `['G', 'UT', '57']` und verlieren damit
genau die Identität, um die es bei Verträgen geht. Hybride Suche verrechnet
beides nicht über Scores, sondern über Plätze: Reciprocal Rank Fusion mit
`1/(60 + Platz)`. Dadurch sind die unvergleichbaren Skalen egal, und es gewinnt,
worauf sich beide Verfahren einigen — bei Verträgen die richtige Voreinstellung.
