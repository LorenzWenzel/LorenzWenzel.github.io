---
layout: post
title: "Warum Prompt Caching bei text2SQL-Agenten Pflicht ist"
title_en: "Why Prompt Caching Is Mandatory for text2SQL Agents"
date: 2026-06-28 18:40:00 +0200
---

Die meisten Empfehlungen zur Kostenoptimierung sind Abwägungen: etwas wird
billiger, etwas anderes schlechter. Prompt Caching ist keine. Bei einem
text2SQL-Agenten gibt es keinen Fall, in dem man ohne besser fährt – und der
Grund ist nicht, dass es irgendwann viel spart, sondern dass es **ab dem ersten
Werkzeugaufruf** spart.

## Warum ausgerechnet dieser Agent

Ein text2SQL-Agent hat die günstigste Prompt-Struktur, die es gibt: ein großer,
vollkommen statischer Block – Systemprompt, Tabellenschemata, Tool-Definitionen –
und davor eine kurze, bei jeder Anfrage andere Frage. Fünfzehntausend Token, die
sich nie ändern, gegen vierzig, die sich immer ändern.

Und dazu kommt die Eigenschaft, die alles entscheidet: **Jeder Werkzeugaufruf
erzeugt einen neuen Modellaufruf.** Wie das genau funktioniert, steht in
[Kosten von MCP in Agenten]({% post_url 2026-06-09-kosten-von-mcp-in-agenten %}) – kurz: Das Modell fordert ein
Werkzeug nur an, ausgeführt wird es woanders, und mit dem Ergebnis beginnt eine
neue Inferenz. Eine n-stufige Kette kostet n + 1 Modellaufrufe.

Das heißt: Derselbe unveränderte Präfix geht bei einer einzigen Nutzerfrage
mehrfach über die Leitung. Genau dafür ist Caching gebaut.

## Wie Bedrock das macht

Bedrock unterscheidet zwei Formen. **Implizites Caching** versucht von sich aus,
gleiche Präfixe wiederzuverwenden – ohne Konfiguration, aber ausdrücklich
*best effort*: Ein identischer Prompt garantiert keinen Treffer. **Explizites
Caching** setzt man selbst, mit einem `cachePoint` in der Converse-API
beziehungsweise `cache_control` in InvokeModel. Für einen Agenten, dessen
Rechnung davon abhängt, will man die explizite Variante.

![Diagramm: die drei Blöcke tools, system und messages nebeneinander, der Cache-Breakpoint sitzt hinter system. Eine Änderung in tools entwertet system und messages gleich mit.](/assets/img/caching-praefix.svg)

Die Reihenfolge ist festgelegt: `tools` → `system` → `messages`. Drei Dinge
folgen daraus, die man kennen muss:

**Die Mindestgröße gilt kumulativ.** Claude Sonnet 5 verlangt 1 024 Token je
Checkpoint – aber gezählt wird über alle drei Abschnitte zusammen, nicht je
Abschnitt. Ein Agent mit Schemata im Systemprompt liegt immer darüber. Wer
darunter bleibt, bekommt keinen Fehler, sondern still keinen Cache.

**Eine Änderung vorn entwertet alles dahinter.** Ändert sich `tools`, sind
`system` und `messages` gleich mit ungültig. Das ist derselbe Mechanismus, der
im MCP-Beitrag als Risiko auftaucht: Ein MCP-Server, der seine Werkzeuge in
anderer Reihenfolge meldet, kostet den kompletten Cache – nicht anteilig,
vollständig.

**Die TTL wird bei jedem Treffer neu gestartet.** Das ist die angenehme
Überraschung in der Dokumentation: Solange der Agent läuft, hält sich der Cache
kostenlos am Leben. Fünf Minuten sind die Voreinstellung, eine Stunde lässt
sich per `"ttl": "1h"` anfordern. Für einen Agenten mit Dauerlast reichen die
fünf Minuten, weil sie sich ständig verlängern.

Zwei Grenzen noch: maximal vier Checkpoints je Anfrage, und Caching gibt es nur
bei On-Demand-Inferenz – mit der Batch-API nicht.

## Die Rechnung

Ein Cache-Write kostet das 1,25-Fache des normalen Input-Preises, ein Cache-Read
ein Zehntel. Daraus ergibt sich der Break-even fast von selbst: Das Schreiben
kostet einmalig 25 % Aufschlag, jedes Lesen spart 90 %. Man muss den Präfix
also nur **ein einziges Mal** wiederverwenden, um im Plus zu sein.

Und ein einziger Werkzeugaufruf bedeutet zwei Modellaufrufe.

![Säulendiagramm: ohne Caching 76 bis 361 Dollar je 1000 Fragen, mit Caching 54 bis 154; die Ersparnis wächst von 29 auf 57 Prozent.](/assets/img/caching-ersparnis.svg)

| Modellaufrufe | ohne Caching | mit Caching | gespart |
|---:|---:|---:|---:|
| 2 (ein Toolaufruf) | 76,33 | 54,12 | 29,1 % |
| 3 | 116,78 | 63,83 | 45,3 % |
| 4 | 160,00 | 76,31 | 52,3 % |
| 6 | 254,76 | 109,59 | 57,0 % |
| 8 | 360,62 | 153,95 | 57,3 % |

Dollar je 1 000 Fragen, Claude Sonnet 5, gleicher Präfix, gleiche Kette.

Der einzige Fall, in dem Caching Geld kostet, ist der, in dem der Agent
**überhaupt kein Werkzeug benutzt** – dann zahlt man 25 % Aufschlag für einen
Cache, den nie jemand liest. Bei einem text2SQL-Agenten kommt dieser Fall nicht
vor. Deshalb: Pflicht, nicht Optimierung.

Interessanter als die Ersparnis ist die **Form der Kurve**. Ohne Caching steigen
die Kosten von 2 auf 8 Modellaufrufe um das 4,7-Fache, mit Caching nur um das
2,8-Fache. Caching senkt nicht bloß das Niveau – es nimmt der Kette den
Zinseszins.

## Welche Modelle auf Bedrock das können

Die Liste der Modelle mit **explizitem** Prompt Caching ist überschaubar und
besteht im Wesentlichen aus zwei Familien
([AWS-Dokumentation](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)):

| Familie | Modelle | Mindest-Token | TTL |
|---|---|---:|---|
| Anthropic | Claude Fable 5.1 / 5, Opus 5 | 512 | 5 min, 1 h |
| | Claude Opus 4.8 | 1 024 | 5 min, 1 h |
| | **Claude Sonnet 5**, Sonnet 4.6, Sonnet 4.5 | 1 024 | 5 min, 1 h |
| | Claude Opus 4.7 / 4.6 / 4.5, Haiku 4.5 | 4 096 | 5 min, 1 h |
| | Claude 3.7 Sonnet | 1 024 | 5 min |
| OpenAI | GPT-5.6 Sol / Terra / Luna | 1 024 | 30 min |

Amazon Nova bringt **implizites** Caching für alle Text-Prompts mit, einzelne
Nova-Modelle zusätzlich explizites.

Und damit zur anderen Hälfte: **Qwen, Llama, Mistral und DeepSeek stehen nicht
in dieser Tabelle.** Für sie gibt es auf Bedrock kein Prompt Caching – weder
implizit noch explizit. Jeder Modellaufruf zahlt den vollen Präfix. Dadurch sind sie nahezu irrelevant für text2sql Agenten auf aws. 

## Fallen

**Implizit ist nicht verlässlich.** Die Dokumentation sagt ausdrücklich, dass ein
identischer Prompt keinen Treffer garantiert. Wer sich darauf verlässt, hat
keine Kostenkontrolle, sondern eine Hoffnung.

**Cross-Region-Inferenz erhöht die Zahl der Cache-Writes.** Die automatische
Regionenwahl ist gut für Verfügbarkeit und schlecht für die Trefferquote des
Caches; bei hoher Last kann es zu zusätzlichen Writes kommen.

**Der Rückblick reicht nur etwa 20 Content-Blöcke.** Bedrock bietet für Claude
eine vereinfachte Cache-Verwaltung: ein einziger Breakpoint am Ende des
statischen Teils, der Rest wird automatisch gesucht. Die Suche schaut aber nur
rund zwanzig Blöcke zurück. Wer mehr statischen Inhalt hat, braucht mehrere
Checkpoints.

**`inputTokens` zählt nicht mehr alles.** Ist Caching aktiv, enthält das Feld
nur die *nicht* gecachten Token. Die Gesamtsumme ist
`inputTokens + cacheReadInputTokens + cacheWriteInputTokens`. Wer sein
Kostenmonitoring auf `inputTokens` gebaut hat, sieht nach dem Einschalten einen
Einbruch, der keiner ist.

**Und der übliche Verdächtige:** ein Zeitstempel im Systemprompt, ein
unsortiert serialisiertes Schema, eine Werkzeugliste, die sich je nach Frage
ändert. Jedes davon setzt die Trefferquote auf null, ohne einen Fehler zu
erzeugen.

Nachweisen lässt sich das an genau einer Stelle: `cacheReadInputTokens` in der
Antwort. Steht dort über mehrere Turns hinweg null, arbeitet ein Invalidator im
Hintergrund – und zwar unabhängig davon, was der Code zu tun glaubt.

## Methodik

Das Modell liegt als
[`assets/bench/caching-rechnet-sich.py`](/assets/bench/caching-rechnet-sich.py)
im Repo. Präfix 15 527 Token, ein Tool-Ergebnis 1 200 Token – dieselben
Annahmen wie im MCP-Beitrag, damit die Zahlen vergleichbar bleiben.

Belastbar sind die **Multiplikatoren** – Cache-Write 1,25 ×, Cache-Read 0,1 ×
des Input-Preises –, denn die stehen so in der Dokumentation. Die absoluten
Bedrock-Preise (Sonnet 5 mit 2,20 $ / 11,00 $ je Million Token in der Region,
die offenen Modelle zwischen 0,15 $ und 0,62 $) stammen aus Sekundärquellen und
ändern sich; die Preisseite gibt sie nicht in einer Form her, die ich hier
zitieren möchte. Wer die Rechnung ernst nimmt, setzt die eigenen Zahlen im
Skript ein. Am Verhältnis ändert das wenig, an den absoluten Beträgen viel.

---

**Kurzfassung:** Prompt Caching kostet einmalig 25 % Aufschlag und spart danach
90 %. Weil jeder Werkzeugaufruf einen weiteren Modellaufruf mit unverändertem
Präfix nach sich zieht, rechnet es sich bereits beim ersten – 29 % schon bei
zwei Modellaufrufen, 57 % bei acht. Es senkt nicht nur die Kosten, sondern
flacht auch ihr Wachstum über die Kettenlänge ab. Auf Bedrock können das nur
Claude, GPT-5.6 und Nova; Qwen, Llama, Mistral und DeepSeek nicht.
