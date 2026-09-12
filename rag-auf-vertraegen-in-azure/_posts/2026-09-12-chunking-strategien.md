---
layout: post
title: "Chunking-Strategien"
title_en: "Chunking Strategies"
date: 2026-09-12 12:00:00 +0200
serie: "RAG auf Verträgen in Azure"
---

Der Chunk ist die Einheit, um die sich in einem RAG-System alles dreht. Er ist
das, was embeddet wird, was einen Score bekommt, was umsortiert wird und was am
Ende im Prompt landet. Und er ist die Entscheidung, die man am schwersten
zurücknimmt: Wer anders schneiden will, baut den Index neu.

Dieser Beitrag geht die Schnittarten durch, die Frage nach der richtigen Größe,
und zwei Dinge, die dabei regelmäßig durcheinandergehen — ob Chunks
unterschiedlich groß sein dürfen, und was die Anzahl der Vektordimensionen damit
zu tun hat.

## Wie groß sollte ein Chunk sein?

Es gibt zwei Grenzen, und nur die obere ist technisch.

Die technische: `text-embedding-3-small` nimmt maximal **8 191 Token** entgegen.
Wer mehr hineingibt, verliert den Rest — die Azure-Dokumentation warnt
ausdrücklich vor „data loss due to truncation".

Die eigentliche Grenze liegt weit darunter, und Microsoft benennt sie in einem
bemerkenswert ehrlichen Satz:

> Chunking is only required if the source documents are too large for the maximum
> input size imposed by models, but it's also beneficial if content is poorly
> represented as a single vector.

*Poorly represented as a single vector* — das ist der Punkt. Und um ihn zu
verstehen, muss man sich klarmachen, was beim Embedden passiert.

![Drei Panels nebeneinander. Links ein zu kleiner Chunk: der Vektor zeigt scharf auf ein einzelnes Thema, aber der Bezug fehlt. In der Mitte ein passender Chunk: ein Thema, vollständig, der Vektor zeigt scharf auf das richtige Thema. Rechts ein zu großer Chunk mit vier Themen: der Vektor ist der Mittelwert der vier Richtungen, kurz, und zeigt in keine davon.](/assets/img/chunking-verduennung.svg)

**Der Vektor hat immer 1 536 Zahlen.** Egal ob zehn Wörter hineingehen oder
achthundert. Was sich ändert, ist nicht die Länge des Vektors, sondern wohin er
zeigt: Er wird über alles gemittelt, was im Chunk steht. Ein Chunk mit einem
Thema zeigt scharf auf dieses Thema. Ein Chunk mit vier Themen zeigt auf deren
Mittelwert — und der liegt nah bei allem und nah bei nichts.

Nach unten gibt es die Gegenbewegung. „Die Frist beträgt drei Monate zum
Monatsende" ist ein scharfer, präziser Satz — und als Chunk wertlos, weil der
Bezug im Satz davor stand. Welche Frist? Welcher Vertrag?

Microsofts Startempfehlung lautet **512 Token mit 25 % Overlap**. Der POC liegt
mit 800 höher, was bei Verträgen vertretbar ist: Ein Paragraph ist eine
Sinneinheit, und die zerschneidet man ungern.

### „800 Token" sind nicht 800 Token

Nur zählt der POC anders als das Modell. `SectionBuilder.py` benutzt eine eigene
Regex:

```python
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
```

Das Modell benutzt `cl100k_base`. Beide heißen „Token" und meinen nicht
dasselbe. An einem typischen Mietvertragsabschnitt nachgezählt:

| | Token |
|---|---:|
| POC-Regex | 165 |
| `cl100k_base` (Modell) | 313 |
| **Faktor** | **1,90** |

Der Unterschied kommt fast vollständig aus einer Eigenschaft des Deutschen:

| Wort | POC | Modell |
|---|---:|---:|
| `Betriebskostenvorauszahlung` | 1 | 10 |
| `Heizkostenvorauszahlung` | 1 | 9 |
| `Schönheitsreparaturen` | 1 | 8 |
| `1.250,00` | 5 | 5 |

Der POC zählt ein Kompositum als ein Token, das Modell zerlegt es in zehn. Ein
Chunk mit `TARGET = 800` ist beim Modell also rund **1 520 Token** groß, `MAX =
1000` sind rund 1 900.

Das ist hier folgenlos — bis zur 8 191er-Grenze bleibt Faktor 4,3 Luft. Folgenlos
wäre es nicht mehr, wenn jemand `TARGET = 6000` setzte in der Annahme, damit
„sicher unter 8 191" zu liegen: Tatsächlich wären es rund 11 400, und der Rest
verschwände stillschweigend.

## Vier Arten zu schneiden

![Vier Spalten zeigen denselben Mietvertrag mit sechs Paragraphen, viermal unterschiedlich geschnitten: nach fester Tokenzahl mit gleich großen Chunks und Schnitten mitten im Satz, am Paragraphen mit sehr ungleich großen Chunks, semantisch am Themenwechsel, und hierarchisch mit kleinen Kind-Chunks für die Suche und großen Eltern-Chunks für die Antwort.](/assets/img/chunking-vier-schnitte.svg)

**Feste Tokenzahl.** Zähle bis n, schneide, weiter. Berechenbar, gleichmäßig,
strukturblind — der Schnitt fällt dahin, wo der Zähler steht, notfalls mitten in
einen Satz. In Azure AI Search ist das die eingebaute Variante: die
[Text Split skill](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents)
mit `textSplitMode: pages`, gesteuert über `maximumPageLength` und
`pageOverlapLength`. Microsofts Standardvorschlag dort: 2 000 Zeichen, 500
Zeichen Overlap. Zeichen, nicht Token — die Doku weist selbst darauf hin, dass
beides nicht deckungsgleich ist.

**Schnitt an der Struktur.** Bei Verträgen liegt es nahe, am `§` zu schneiden:
Ein Paragraph ist eine abgeschlossene Regelung, die Grenze ist im Dokument schon
markiert, und der Autor hat sie gesetzt. Der Haken ist die Streuung. § 1
(Mietsache) hat vierzig Token, § 3 (Miete und Nebenkosten) neunzehnhundert.
Reines §-Schneiden erzeugt einen Index, in dem Chunks um den Faktor fünfzig
auseinanderliegen — dazu unten mehr.

**Semantisch.** Statt an der Form an der Bedeutung schneiden: Sätze einzeln
embedden, aufeinanderfolgende Sätze vergleichen, und dort trennen, wo die
Ähnlichkeit einbricht. Das findet Themenwechsel auch innerhalb eines Paragraphen.
Der Preis steht beim Indexaufbau: ein Embedding-Aufruf pro Satz statt pro Chunk.

**Hierarchisch.** Zwei Ebenen: kleine Chunks für die Suche, große für die
Antwort. Gefunden wird über den präzisen Kind-Chunk, ins Prompt geht der
Eltern-Chunk mit dem Zusammenhang. Das löst die Spannung zwischen „scharfer
Vektor" und „genug Kontext" — nicht durch einen Kompromiss, sondern durch zwei
verschiedene Objekte. Azure AI Search hat dafür nichts Eingebautes; man
modelliert es über ein Feld, das auf den Elternabschnitt zeigt.

### Die eigene Strategie: keine der vier, sondern zwei davon

Der POC macht etwas, das sich in keine der vier Schubladen legen lässt, und das
ist der interessante Teil. Er zählt tokenweise bis 800 — und sucht dann einen
Schnittpunkt, der zur Struktur passt, in dieser Reihenfolge:

1. eine **§-Überschrift** innerhalb der nächsten 150 Token (`GRACE`)
2. sonst ein **Zeilenanfang** innerhalb der nächsten 80 (`LINE_SNAP`)
3. sonst eine **Satzgrenze** innerhalb der nächsten 80 (`SENT_SNAP`)
4. sonst rückwärts dasselbe
5. und am Ende hart: nie kürzer als `MIN = 600`, nie länger als `MAX = 1000`

Die Zählung ist fest, die Grenze ist strukturell, die Streuung ist gedeckelt. Das
ist die sinnvolle Kombination — und die letzte Zeile ist wichtiger, als sie
aussieht.

Dazu kommt eine Kleinigkeit mit großer Wirkung: eine Variable namens `carry`, die
die zuletzt gesehene §-Überschrift in den nächsten Chunk mitnimmt. Ein Chunk aus
der Mitte von § 3 weiß dadurch noch, dass er aus § 3 stammt. Genau das
Kontextproblem aus dem linken Panel oben, mit zwei Zeilen Code erledigt.

## Overlap

![Oben ohne Overlap: ein Satz wird von der Chunkgrenze zerschnitten, Chunk A endet mit „Die Kündigungsfrist beträgt", Chunk B beginnt mit „drei Monate zum Monatsende". Keiner der beiden beantwortet die Frage. Unten mit 100 Token Overlap beginnt Chunk B mit dem Ende von Chunk A und enthält den ganzen Satz. Rechts der Preis: der Index wächst um 12,5 Prozent im POC und um 25 Prozent bei der Microsoft-Empfehlung.](/assets/img/chunking-overlap.svg)

Overlap ist die Versicherung gegen den unglücklichen Schnitt. Ohne ihn kann ein
Satz so zerfallen, dass keine der beiden Hälften die Frage beantwortet — und,
schlimmer, dass beide Vektoren am Thema vorbeizeigen. Mit Overlap kommt jede
Passage mindestens einmal vollständig im Index vor.

Bezahlt wird in Indexgröße: Der POC wiederholt 100 von 800 Token, das sind
12,5 % mehr Chunks; Microsofts 128 von 512 sind 25 %. Dazu kommt ein Effekt, den
man in der Trefferliste sieht: Derselbe Satz kann in zwei Chunks stehen und
zweimal gefunden werden. Genau dagegen gibt es im POC die `per_doc_cap`.

Eine Warnung aus der Azure-Doku ist es wert, zitiert zu werden: *„setting an
overlap value that's too large can result in no overlap appearing at all"* — wer
den Overlap größer als die halbe Chunkgröße wählt, bekommt nicht mehr Sicherheit,
sondern gar keine.

## Dürfen Chunks unterschiedlich groß sein?

Das ist die Frage, bei der sich hartnäckig ein Missverständnis hält. Die kurze
Antwort: **Mathematisch ja, uneingeschränkt.**

Ein Embedding-Modell erzeugt aus beliebig langem Text immer einen Vektor fester
Länge — die variable Anzahl Token wird zu einer festen Anzahl Dimensionen
zusammengefasst. Zehn Wörter ergeben 1 536 Zahlen, achthundert Wörter ergeben
1 536 Zahlen. Die Kosinusähnlichkeit normiert zusätzlich auf die Vektorlänge, der
Betrag trägt also gar keine Information. Es gibt keine Rechenoperation in der
Vektorsuche, die an unterschiedlichen Chunkgrößen scheitert.

**Inhaltlich ist es trotzdem nicht egal** — aber aus dem Grund von weiter oben,
nicht aus einem mathematischen. Je mehr in einem Chunk steht, desto stärker ist
sein Vektor ein Mittelwert, und desto näher rückt er der Mitte des Raums. Ein
sehr langer und ein sehr kurzer Chunk stehen im selben Index nicht unter gleichen
Bedingungen: Der lange ist verwaschen, der kurze scharf. Wenn beide zur Frage
passen, gewinnt systematisch der kurze — nicht, weil er besser passt, sondern
weil er weniger enthält.

Daraus folgt die eigentliche Regel, und sie ist präziser als „gleich groß":

> Unterschiedliche Größen sind unproblematisch. **Unbegrenzt** unterschiedliche
> Größen sind es nicht.

`MIN = 600` und `MAX = 1000` im POC sind damit keine Formalie, sondern genau
diese Deckelung: Faktor 1,7 zwischen dem kleinsten und dem größten Chunk. Reines
§-Schneiden käme auf Faktor fünfzig. Das ist der Grund, warum die
Strukturvariante allein selten reicht.

### Und passen kurze Fragen dann noch auf lange Chunks?

Die Frage hat acht Token, der Chunk achthundert. Beide gehen durch dasselbe
Modell in denselben Raum — das funktioniert, dafür sind die Modelle trainiert.
Aber die Asymmetrie hinterlässt eine Spur: Die Ähnlichkeit zwischen einer kurzen
Frage und einem langen Text fällt tendenziell niedriger aus als zwischen zwei
gleich langen Texten, eben weil der lange Vektor gemittelt ist.

Für das Ranking ist das zunächst folgenlos. Die Suche vergleicht Kandidaten
untereinander, und ein Effekt, der alle Kandidaten gleich trifft, ändert die
Reihenfolge nicht. Er wird erst dann zum Problem, wenn er die Kandidaten **nicht**
gleich trifft — also wieder genau dann, wenn die Chunkgrößen weit auseinander
liegen.

Nebenbei ist das ein Argument für die hybride Suche aus dem
[Retrieval-Beitrag]({% post_url 2026-09-12-retrieval-varianten %}):
BM25 hat mit `b = 0,75` eine explizite Längennormalisierung eingebaut. Die
Vektorseite hat nichts Vergleichbares. Wer beide kombiniert, bekommt die
Längenkorrektur wenigstens auf einer der beiden Seiten geschenkt.

## Sind mehr Dimensionen besser?

![Gruppiertes Balkendiagramm mit drei Embedding-Modellen und zwei Benchmarks. MTEB englisch: ada-002 61,0, 3-small 62,3, 3-large 64,6. MIRACL mehrsprachig: ada-002 31,4, 3-small 44,0, 3-large 54,9. Der Abstand zwischen den Modellen ist auf dem mehrsprachigen Benchmark um ein Vielfaches größer als auf dem englischen. Darunter Dimensionen und Speicherbedarf je 10 000 Chunks.](/assets/img/chunking-dimensionen.svg)

`text-embedding-3-small` liefert 1 536 Dimensionen, `3-large` liefert 3 072. Die
veröffentlichten Werte zeigen zwei sehr verschiedene Bilder, je nachdem welchen
Benchmark man ansieht.

Auf **MTEB** (englisch) liegen zwischen den drei Modellen 1,3 und 2,3 Punkte.
Das ist der Unterschied, für den sich der doppelte Speicher kaum lohnt.

Auf **MIRACL** (mehrsprachig) sind es 12,6 und 10,9 Punkte. Das ist eine andere
Größenordnung — und es ist die Spalte, die bei deutschen Verträgen zählt.

Dazu kommt, dass Dimensionszahl und Modellqualität gar nicht dasselbe sind. Beide
3er-Modelle lassen sich über den `dimensions`-Parameter kürzen, und laut OpenAI
schlägt ein auf **256 Dimensionen** gekürztes `3-large` immer noch ein
ungekürztes `ada-002` mit 1 536. Die Dimensionen sind ein Regler für Speicher und
Latenz, nicht der Träger der Qualität.

### Was mehr Dimensionen bei Verträgen nicht lösen

Eine Sache ändert sich durch keine Dimensionszahl. `GUT57` wird vom Tokenizer in
`['G', 'UT', '57']` zerlegt, und das passiert bei 3 072 Dimensionen genauso wie
bei 1 536 — es ist eine Eigenschaft des Tokenizers, nicht des Vektorraums. Die
Objektkennung, die bei Mietverträgen die Identität trägt, wird durch ein größeres
Embeddingmodell nicht besser gefunden.

Für diesen Fall ist der Hebel nicht die Dimensionszahl, sondern BM25 auf der
anderen Seite der hybriden Suche. Wer bei Verträgen aufrüsten will, rüstet
sinnvoll für MIRACL auf — für die Mehrsprachigkeit, nicht für die Vektorbreite.

## Was ich daraus schließe

**Die Chunkgröße ist kein Tuning-Parameter, sondern eine Entscheidung darüber,
was eine Antworteinheit ist.** Bei Verträgen ist das der Paragraph, und der ist
mal vierzig und mal neunzehnhundert Token lang. Genau deshalb ist weder reines
Token-Zählen noch reines §-Schneiden die Antwort, sondern die Kombination: an der
Struktur schneiden, die Streuung deckeln, die Überschrift mitgeben.

---

**Kurzfassung:** Ein Chunk soll ein Thema vollständig enthalten und nicht mehr —
zu groß verwässert den Vektor zum Mittelwert, zu klein nimmt ihm den Bezug.
Microsoft empfiehlt 512 Token mit 25 % Overlap als Startpunkt; der POC liegt bei
800 mit 12,5 %, wobei seine 800 Token beim Modell rund 1 520 sind, weil deutsche
Komposita anders zerlegt werden. Unterschiedlich große Chunks sind mathematisch
völlig unproblematisch — der Vektor hat immer dieselbe Länge — aber unbegrenzt
unterschiedliche Größen verzerren das Ranking, weshalb `MIN`/`MAX` mehr sind als
Formsache. Und mehr Dimensionen sind nicht per se besser: Bei deutschen Verträgen
zählt der mehrsprachige Benchmark, nicht die Vektorbreite, und die Objektkennung
`GUT57` findet ohnehin BM25 und nicht das Embedding.
