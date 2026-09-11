---
layout: post
title: "RAG-Strategien bei Verträgen"
categories: rag-auf-vertraegen-in-azure
serie: "RAG auf Verträgen in Azure"
---

*Entwurf.*

Der Beitrag, der die anderen zusammenbindet: Was macht ausgerechnet Verträge zu
einem eigenen Fall, und welche Entscheidungen folgen daraus?

## Was Verträge von Dokumenten unterscheidet

**Sie sind gegliedert, aber ungleich.** Der `§` ist eine echte, vom Autor
gesetzte Grenze — anders als Absätze in Fließtext. Nur ist er kein Maß: § 5 hat
drei Zeilen, § 12 drei Seiten.

**Sie verweisen auf sich selbst.** „im Sinne von § 5 Abs. 2“ ist beim Chunking
ein Verweis ins Nichts, wenn § 5 in einem anderen Chunk liegt. Das Retrieval
liefert den verweisenden Paragraphen, nicht den verwiesenen.

**Sie enthalten Identitäten, keine Begriffe.** `GUT57`, `WE 03.12`, `ME#0.02`,
Postleitzahlen. Für ein Embedding sind das nahezu austauschbare Zeichenfolgen —
für die Frage sind sie das Entscheidende. Das ist das Argument für Hybrid.

**Abwesenheit ist eine Aussage.** Wenn ein Vertrag keine Staffelmiete regelt,
gilt keine. Das ist eine belastbare juristische Information — und RAG kann sie
nicht liefern, weil man das Fehlen eines Paragraphen nicht retrieven kann. Man
kann nur alle Paragraphen sehen und schließen, und genau das tut Top-k nicht.

**Der Kopf trägt die Identität, der Körper den Inhalt.** Mieter, Objekt, Adresse,
Laufzeit stehen fast immer auf der ersten Seite. Der POC nutzt das: Die
Metadaten-Extraktion sieht **nur die ersten beiden Sections**, gedeckelt auf
8 000 Zeichen, mit `temperature = 0` und einem Systemprompt, der Normalisierungen
vorschreibt (`WE03.12` → `WE 03.12`) und im Zweifel `null` verlangt.

## Die Entscheidung dahinter

Nur den Kopf zu lesen ist eine bewusste Abwägung: weniger Kontext heißt weniger
Halluzination, aber auch weniger Abdeckung. Ein Untermietvertrag, dessen Mieter
erst in § 2 auftaucht, fällt durch. Zu prüfen:

- Wie oft liegen die Kopffelder tatsächlich in den ersten zwei Sections?
- Was passiert bei Nachträgen, die den Kopf des Hauptvertrags nicht wiederholen?
- Ist `temperature = 0` plus striktes JSON genug, oder braucht es eine
  Validierung gegen ein Schema?

## Belegpflicht als Sicherheitsnetz

Der Antwortprompt verlangt: ausschließlich aus dem Kontext, jeder relevante Satz
mit `[#rank]` belegt, bei Unklarheit explizit sagen. Das ist die richtige
Vorgabe — mit der bekannten Grenze, dass sie nur gegen Erfindung schützt, nicht
gegen Unvollständigkeit (siehe den Beitrag zu offenen Fragen).

Eine Sache, die der POC gut macht und die selten jemand baut: Der vollständige
User-Prompt wird bei jeder Anfrage nach `./userPrompt/prompt.txt` geschrieben.
Bei einer falschen Antwort lässt sich nachsehen, was das Modell wirklich gesehen
hat — statt zu raten. Für einen Anwendungsfall mit Rechtsfolgen ist das keine
Spielerei.

## Was noch fehlt

- **Verweisauflösung**: Erkannte `§ x`-Verweise mitziehen, wenn der Zielparagraph
  nicht im Kontext ist.
- **Anlagen**: Sie tragen oft die Zahlen (Mietflächen, Beträge) und selten eine
  §-Struktur.
- **Nachträge und Fassungen**: Welcher Vertrag gilt, wenn es drei Versionen gibt?
  Der Index kennt bisher keine Zeitachse.
- **Datenschutz im Betrieb**: Der Korpus enthält Klarnamen und Adressen. Die
  README nennt DSGVO-Konformität als Ziel — was das konkret für Index, Logs und
  die abgelegten Prompts bedeutet, gehört ausgeschrieben.

## Der rote Faden

Wenn diese Serie eine These hat, dann diese: **Bei Verträgen entscheidet nicht
das Modell, sondern was vor dem Modell passiert.** Chunking, Hybrid-Suche,
Metadaten, Kappung pro Dokument — vier Entscheidungen, die alle vor dem ersten
Token fallen. Das Modell macht danach nur noch wenig falsch, wenn es das Richtige
sieht.
