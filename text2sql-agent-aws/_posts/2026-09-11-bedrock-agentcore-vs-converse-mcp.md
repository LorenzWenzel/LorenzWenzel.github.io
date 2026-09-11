---
layout: post
title: "Bedrock AgentCore vs. Converse + MCP"
date: 2026-09-11 13:00:00 +0200
serie: "text2SQL-Agent auf AWS"
---

Die Frage ist älter als ihre Antwort. Als ich sie mir notiert habe, hieß der
„native Weg" noch Amazon Bedrock Agents: Aktionsgruppen anlegen, Wissensbasis
anhängen, Anweisungen schreiben, AWS orchestriert. Dieses Produkt ist seit dem
**30. Juli 2026 für Neukunden geschlossen** – es heißt jetzt *Bedrock Agents
Classic*, läuft für Bestandskunden im Wartungsmodus weiter, bekommt keine neuen
Modelle und keine neuen Funktionen mehr
([AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-classic-maintenance-mode.html)).

Der native Weg heißt heute **AgentCore harness**. Und der andere Weg –
Converse + MCP – ist weniger „nativ", als sein Name klingt. Beides muss man
erst einmal sauber definieren, sonst vergleicht man Werbetexte.

## Was die beiden Wege wirklich sind

**Converse + MCP** heißt: Man schreibt die Schleife selbst. Die Converse-API
kennt Werkzeuge nur als Definitionen – der `Tool`-Typ hat genau drei Mitglieder,
`toolSpec`, `cachePoint` und `systemTool`, und keines davon zeigt auf einen
MCP-Server ([API-Referenz](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Tool.html)).
Die Doku sagt es ausdrücklich: Das Modell ruft kein Werkzeug auf, das tut die
Anwendung ([Tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html)).
Der MCP-Client, der die Werkzeuge vom Server holt und ihre Ergebnisse als
`toolResult`-Blöcke zurück in den Verlauf legt, ist also Code, den man besitzt.
In der Praxis nimmt man dafür Strands: Es spricht `ConverseStream`, bringt einen
MCP-Client für stdio und Streamable HTTP mit und setzt Cache-Punkte per
Konfiguration ([Strands](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/)).
Gehostet wird das, wo man will – Fargate, Kubernetes, ein Server.

**AgentCore harness** heißt: Man schreibt die Schleife nicht. Man deklariert
Modell, Systemprompt, Werkzeuge, Speicher und Limits als Konfiguration, und
AgentCore betreibt die Schleife – die übrigens ebenfalls Strands ist, nur eben
nicht in eigener Hand ([harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)).
Darunter liegt die AgentCore Runtime (eine microVM je Session), daneben Gateway
(macht aus Lambda-Funktionen oder APIs einen MCP-Server), Memory (Verlauf und
Langzeitgedächtnis), Identity (Token-Tresor) und Observability (CloudWatch).
Einen eigenen Harness-Preis gibt es nicht; man zahlt die Bausteine darunter.

AWS' eigene Empfehlung ist unmissverständlich: *„Use the harness unless you have
a specific reason to own the loop yourself."* Der Rest dieses Beitrags handelt
davon, ob ein text2SQL-Agent so einen Grund hat.

Es gibt noch einen dritten Weg, den AWS gleich mitliefert: **eigener Code auf
der AgentCore Runtime.** Man bringt die Strands-Schleife im eigenen Container
mit, AWS stellt die Infrastruktur. Das ist kein Kompromiss, sondern für diese
Serie der interessanteste Punkt, deshalb läuft er in der Matrix mit.

## Wer trägt was

![Matrix mit acht Ebenen – Orchestrierungsschleife, Hosting, Gesprächsverlauf, MCP-Server, Nutzer-Auth, Tracing, Prompt Caching, Hooks – und drei Betriebswegen. Blau: selbst gebaut. Grau: von AWS geliefert. Orange: offen oder nicht möglich.](/assets/img/agentcore-wer-traegt-was.svg)

Die Matrix ist die eigentliche Antwort, der Rest sind Fußnoten dazu.

**Die Schleife** ist in den ersten beiden Spalten dieselbe – Strands, in eigener
Hand. In der dritten Spalte gehört sie AWS. Das klingt nach Detail und ist der
ganze Unterschied: Alles, was diese Serie an Hebeln beschrieben hat – wie
Tool-Ergebnisse in den Verlauf kommen, wann aufgeräumt wird, ob parallele
`toolResult`-Blöcke in einer Nachricht zurückgehen –, ist in Spalte drei nicht
mehr Code, sondern entweder ein Konfigurationsfeld oder nichts. AWS'
Vergleichstabelle listet, was der Harness nicht kann: kein eigenes Framework,
keine Hooks, keine Muster jenseits der Agentenschleife, kein bidirektionales
Streaming
([harness vs. Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html)).

**Hosting und Isolation** ist, wo AgentCore am meisten abnimmt. Jede Session
läuft in einer eigenen microVM, die nach der Session gelöscht wird. Wer das
selbst baut, hat Fargate-Tasks oder Pods, die zwischen Nutzern geteilt werden,
und muss die Trennung im Code sicherstellen. Für einen Agenten, der mit den
Athena-Rechten des Nutzers unterwegs ist, ist das kein kosmetischer Punkt.

**Der Gesprächsverlauf** landet beim Harness in AgentCore Memory, mit einem
gleitenden Fenster von 30 Nachrichten als Voreinstellung. Wer den
[Historie-Beitrag]({% post_url 2026-09-11-historie-bei-chatbots %}) gelesen hat,
sieht das Problem: Ein Fenster, das nach *Nachrichten* zählt, behält
Tool-Ergebnisse vollständig – und die machen rund 84 % des Verlaufs aus. Die
Alternative `summarization` gibt es; die Regel „SQL behalten, Zeilen ersetzen"
gibt es als Konfiguration nicht.

**Der MCP-Server für Athena** hat beim Harness einen natürlichen Platz – das
Gateway – und der ist gut. Er hat aber auch einen Preis, dazu gleich mehr.

**Prompt Caching** ist die Zelle, die mich am meisten beschäftigt hat. In
Spalte eins setzt man den `cachePoint` selbst, in Spalte zwei sagt man Strands
`cache_config=CacheConfig(strategy="auto")`. Für den Harness steht in keiner der
Dokumentationsseiten, die ich gelesen habe, ob und wo Cache-Punkte gesetzt
werden. Da der Harness auf Strands läuft, ist es wahrscheinlich; belegt ist es
nicht. Die Prüfung ist dieselbe wie im
[Caching-Beitrag]({% post_url 2026-09-11-prompt-caching-pflicht %}): Die
`metadata`-Events des Streams liefern die Token-Nutzung – steht dort bei
`cacheReadInputTokens` dauerhaft null, zahlt man den vollen Präfix bei jedem
Aufruf, und die Rechnung aus jenem Beitrag gilt mit umgekehrtem Vorzeichen.

## Was sich nicht ändert

Die Modellrechnung. Beide Wege rufen dasselbe Modell über dieselbe API mit
demselben Verlauf auf. Die n+1-Regel aus
[Kosten von MCP in Agenten]({% post_url 2026-09-11-kosten-von-mcp-in-agenten %})
gilt unverändert: eine n-stufige Werkzeugkette kostet n+1 Modellaufrufe, egal
wer die Schleife betreibt. Das Gateway ist ein Hop mehr auf dem Weg zum
Werkzeug, aber kein Modellaufruf mehr.

Der Harness bringt sogar einen kleinen Aufschlag mit: Die Standardwerkzeuge
`shell` und `file_operations` sind in jeder Session dabei und kosten laut Doku
rund **900 Input-Token je Modellaufruf**, ob der Agent sie nutzt oder nicht
([Tools](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-tools.html)).
Bei vier Aufrufen je Frage sind das 3 600 Token – ungecacht rund 7,90 $ je
1 000 Fragen bei Sonnet 5, mehr als die gesamte Infrastruktur unten. Ein
text2SQL-Agent braucht keine Shell; `allowedTools` auf die eigenen Werkzeuge zu
beschränken ist die erste Zeile jeder Harness-Konfiguration.

## Die Rechnung

Dieselben Annahmen wie in den anderen Beiträgen: vier Modellaufrufe je Frage,
drei Werkzeugaufrufe, 22 Sekunden Wandzeit, fünf Fragen je Unterhaltung. Das
Skript liegt unter
[`assets/bench/agentcore-vs-converse.py`](/assets/bench/agentcore-vs-converse.py).

![Liniendiagramm: Infrastrukturkosten je 1000 Fragen über die Fragen je Monat. Fargate-Dauerbetrieb fällt mit steigender Menge, AgentCore harness liegt konstant bei 3,30 Dollar, eigener Code auf Runtime bei 1,16. Schnittpunkt bei rund 22 000 Fragen im Monat.](/assets/img/agentcore-kosten-dichte.svg)

Das Erste, was auffällt: **Die Skala.** Die Modellrechnung für dieselben 1 000
Fragen liegt bei rund 76 $ (Sonnet 5, mit Caching). Die Infrastruktur liegt
zwischen 1 und 4 $. Wer den Vergleich über die Infrastrukturkosten entscheidet,
entscheidet ihn über zwei bis fünf Prozent der Rechnung.

Das Zweite: **Dauerbetrieb hat einen Schnittpunkt, AgentCore nicht.** Zwei
Fargate-Tasks kosten 72 $ im Monat, egal ob eine oder eine Million Fragen
kommen. Je Frage wird das erst ab etwa 22 000 Fragen im Monat – 730 am Tag –
günstiger als der Harness. Ein interner Chatbot für ein Controlling-Team liegt
weit darunter. Dieselbe Rechenlogik wie beim Cache-Write in der Nullvariante des
Domänenwissen-Beitrags: Die Anfragedichte entscheidet, nicht der Listenpreis.

Das Dritte steckt in der Zusammensetzung:

![Ein gestapelter Balken: Memory-Events 2,50 Dollar, Leerlauf-Speicher 0,47, Lambda 0,20, aktiver Speicher 0,06, CPU 0,05, Gateway 0,02.](/assets/img/agentcore-kosten-anteile.svg)

**Die Runtime ist der kleinste Posten.** CPU wird nur bei aktiver Rechenzeit
berechnet, und ein Agent, der auf Modell und Athena wartet, rechnet fast nie.
Zwei Dinge kosten stattdessen: **Memory-Events** – jede Nachricht, jeder
Werkzeugaufruf, jedes Ergebnis ist ein Event zu 0,25 $ je tausend, und eine
Frage erzeugt acht davon – und der **Leerlauf**. Der Speicher einer microVM wird
für die gesamte Sessiondauer berechnet, auch in den 15 Minuten, die sie nach der
letzten Nachricht voreingestellt wartet. Bei fünf Fragen je Unterhaltung ist
das Warten teurer als das Arbeiten. `idleRuntimeSessionTimeout` auf fünf
Minuten senkt die Rechnung um ein Zehntel; der Preis dafür sind mehr
Kaltstarts, wenn jemand nach sechs Minuten doch noch eine Frage hat.

## Wo der Athena-Server hin soll

Der Harness bietet drei Plätze für den MCP-Server, und sie unterscheiden sich
mehr, als die Doku vermuten lässt.

| Ort | Wie | Was dafür spricht | Was dagegen spricht |
|---|---|---|---|
| **Gateway, Lambda-Target** | Athena-Logik als Lambda, Gateway macht daraus MCP | Auth, Policy und Tool-Suche vom Gateway; kein Server zu betreiben | Lambda *wartet* auf Athena und wird dafür bezahlt; Kaltstarts; Tool-Namen tragen ein Präfix `target___tool` |
| **Eigener MCP-Server auf der Runtime** | Container auf Port 8000, `/mcp`, Streamable HTTP | Eigener Code, eigene Rolle, kein Lambda-Umweg | Eingangs-Auth mit JWT oder IAM Pflicht; zweite microVM je Session |
| **Eigener MCP-Server anderswo** | Beliebiger Host, per URL angebunden | Nichts ändert sich am bestehenden Server | Auth und Netzwerk selbst; nicht mehr in AWS' Trace |

Für Athena ist die erste Zeile die naheliegende, und ihr Haken ist genau der,
den der MCP-Beitrag als „künstliche Abhängigkeit" beschrieben hat: Athena ist
asynchron. Ein Lambda, das intern wartet, bis die Abfrage fertig ist, ist die
richtige Form – aber es bezahlt die Wartezeit, und bei acht Sekunden je Abfrage
und drei Abfragen je Frage sind das 0,20 $ je 1 000 Fragen. Klein, aber der
einzige Posten, der mit der Athena-Laufzeit wächst. Ein Lambda, das nur startet
und die Ausführungs-ID zurückgibt, wäre billiger und macht das Modell zur
Polling-Schleife. Diese Falle ist im Harness genauso offen wie überall.

## Was im Betrieb zählt

**Kaltstart.** Eine neue Session bekommt eine neue microVM. Für
Container-Deployments hält AWS einen Pool von zehn warmen VMs vor, danach hängt
die Startzeit an der Image-Größe; für direkte Code-Deployments nennt ein
AWS-Mitarbeiter 2–3 Sekunden
([Samples-Issue](https://github.com/awslabs/agentcore-samples/issues/899)).
Innerhalb einer Session gibt es keinen Kaltstart, solange die Session-ID
mitgeschickt wird – ohne sie landet jede Anfrage auf einer neuen VM.

**Grenzen.** 2 vCPU und 8 GB je Session, 100 MB Nutzlast, 15 Minuten je
synchroner Anfrage, 8 Stunden je Session, 2 500 gleichzeitige Sessions in
Frankfurt, 25 neue Sessions je Sekunde
([Quotas](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)).
Für einen text2SQL-Agenten ist keine davon eng.

**Region.** Harness, Runtime, Memory, Gateway und Identity sind alle in
Frankfurt verfügbar
([Regionen](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html)).
Das war 2025 noch nicht so und ist heute keine Frage mehr.

**Deployment.** Runtime verlangt einen ARM64-Container in ECR mit
`/invocations` und `/ping` auf Port 8080 – oder ein Code-Paket bis 250 MB. Das
ist ein dünner Vertrag; ein Strands-Agent, der heute auf Fargate läuft, ist in
einem Nachmittag umgezogen. Umgekehrt gilt das auch: Der Vertrag bindet wenig.
Was bindet, sind Gateway-Zielkonfigurationen und Memory-Strategien – die gibt es
so nur bei AWS.

## Worauf es ankommt

| Wenn … | dann |
|---|---|
| die Serie-Hebel (Tool-Zuschnitt, Verlauf aufräumen, parallele Ergebnisse) gezogen werden sollen | **eigener Code** – auf Runtime oder anderswo |
| ein Team von zwei Leuten den Agenten betreibt und kein Ops-Kontingent hat | **Harness** |
| unter ~20 000 Fragen im Monat | Harness oder Runtime; Dauerbetrieb lohnt sich nicht |
| über ~50 000 Fragen im Monat und ein Plattform-Team existiert | **Fargate** wird je Frage günstiger – aber nur je Frage |
| Session-Isolation je Nutzer sicherheitsrelevant ist (Athena-Rechte!) | **Runtime**, in beiden Spielarten |
| die Schleife wechseln können muss (Framework, Graph-Muster, Hooks) | **nicht der Harness** |
| Caching-Trefferquote belegt werden muss | zuerst messen, in welcher Spalte man ist |

## Empfehlung

**Für einen text2SQL-Agenten: eigener Code auf der AgentCore Runtime.** Nicht
der Harness, und nicht der eigene Cluster.

Der Grund gegen den Harness ist diese Serie. Fast jeder Hebel, der in den
vorigen Beiträgen etwas gebracht hat, sitzt in der Schleife: Werkzeuge
grobkörniger schneiden geht noch, aber die Ergebnisse paralleler Werkzeuge in
einer Nachricht zurückgeben, Resultsets im Verlauf durch Platzhalter ersetzen,
Cache-Punkte gezielt setzen – das alles ist in der Harness-Spalte entweder ein
Konfigurationsfeld mit anderer Semantik oder nicht vorgesehen. Und die eine
Zelle, die orange ist, weil ich sie nicht belegen konnte, ist ausgerechnet
Prompt Caching.

Der Grund gegen den eigenen Cluster ist die Rechnung: Unter 20 000 Fragen im
Monat zahlt man für leere Container, und die Session-Isolation, die man bei
AgentCore geschenkt bekommt, muss man selbst bauen – für einen Agenten, der mit
Datenbankrechten hantiert, ist das der Teil, den man am wenigsten selbst bauen
will.

Der Harness ist die richtige Wahl für den ersten Prototyp und für Teams, deren
Engpass nicht Token sind, sondern Betriebszeit. Wer damit anfängt, verliert
nichts: Der Harness exportiert nach Strands-Code, und der läuft auf derselben
Runtime weiter. Der Weg von Spalte drei nach Spalte zwei ist vorgesehen; der von
Spalte eins nach irgendwo ist Arbeit.

## Methodik und Vorbehalte

Nichts hier ist gemessen, alles ist gerechnet. Die Preise sind Listenpreise vom
September 2026 aus der
[AgentCore-Preisseite](https://aws.amazon.com/bedrock/agentcore/pricing/) und
den Fargate- und Lambda-Preisseiten für us-east-1; für Frankfurt liegen sie
etwas höher, für ARM-Fargate niedriger. Das Nutzungsprofil – 22 Sekunden,
1 GB, acht Events, fünf Fragen je Unterhaltung – ist eine Annahme; wer sein
eigenes hat, trägt es oben im Skript ein. Die Modellkosten stammen aus dem
Caching-Beitrag und sind dort begründet.

Zwei Dinge habe ich nicht belegen können und sage das lieber, als es zu
überspielen: ob der Harness Prompt Caching setzt, und wie viel Latenz das
Gateway je Werkzeugaufruf hinzufügt. Für Letzteres gibt es CloudWatch-Metriken
(`Latency`, `TargetExecutionTime`), aber keine veröffentlichten Messwerte.

---

**Kurzfassung:** Die klassischen Bedrock Agents sind für Neukunden geschlossen;
der native Weg ist der AgentCore harness, der die Schleife übernimmt – und mit
ihr fast alle Hebel dieser Serie. Converse hat kein MCP, „Converse + MCP" heißt
also: eigene Schleife, eigener MCP-Client, meist Strands. Die Infrastruktur
kostet in jeder Variante 1–4 % der Modellrechnung und entscheidet nichts;
Dauerbetrieb lohnt sich erst ab rund 22 000 Fragen im Monat. Der dritte Weg –
eigener Code auf der AgentCore Runtime – behält die Schleife und bekommt
Isolation, Auth und Tracing geschenkt. Für einen text2SQL-Agenten ist das die
Empfehlung.
