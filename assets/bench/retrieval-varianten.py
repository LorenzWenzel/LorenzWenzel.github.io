# -*- coding: utf-8 -*-
"""Die drei Retrieval-Varianten nachgerechnet: BM25, Tokenisierung von Kennungen, RRF.

Kein Azure-Zugriff noetig – hier wird die Mechanik nachgebaut, nicht der Dienst gemessen.
BM25-Parameter wie in Azure AI Search: k1 = 1.2, b = 0.75.
"""
import math, re
from collections import Counter

K1, B = 1.2, 0.75   # Azure-AI-Search-Voreinstellungen

# --- Ein Miniaturkorpus aus realistischen Vertragsschnipseln -------------------
KORPUS = {
 "GUT57_chunk_03": "§ 3 Kaution Der Mieter leistet eine Kaution in Hoehe von drei Nettokaltmieten. "
                   "Die Kaution ist auf einem Mietkautionskonto anzulegen und getrennt vom Vermoegen "
                   "des Vermieters zu verwahren.",
 "SOD118_chunk_03": "§ 3 Kaution Der Mieter zahlt eine Sicherheitsleistung von zwei Monatsmieten. "
                    "Die Sicherheitsleistung wird verzinst und bei Beendigung des Mietverhaeltnisses "
                    "zurueckgezahlt.",
 "GUT57_chunk_07": "§ 7 Beendigung des Mietverhaeltnisses Die Kuendigung bedarf der Schriftform. "
                   "Die gesetzliche Kuendigungsfrist betraegt drei Monate zum Monatsende.",
 "GUT57_chunk_01": "Mietvertrag ueber Gewerberaum zwischen der GUT57 Grundbesitz GmbH als Vermieterin "
                   "und der Beispiel AG als Mieterin ueber die Einheit WE 03.12 in der Gutenbergstrasse 57.",
 "BRUEHL2_chunk_01": "Mietvertrag ueber eine Tiefgarage zwischen der BRUEHL2 Verwaltung GmbH und "
                     "Julian Jonas ueber den Stellplatz Nr. 8.",
 "SOD118_chunk_12": "§ 12 Schoenheitsreparaturen Der Mieter uebernimmt die Schoenheitsreparaturen. "
                    "Massgeblich ist der uebliche Fristenplan. Die Kaution bleibt davon unberuehrt.",
}

def tok(s):  # bewusst simpel – der echte de.microsoft-Analyzer macht mehr
    return re.findall(r"[\wÄÖÜäöüß§.#/]+", s.lower())

DOCS = {k: tok(v) for k, v in KORPUS.items()}
N = len(DOCS)
AVGDL = sum(len(d) for d in DOCS.values()) / N
DF = Counter(t for d in DOCS.values() for t in set(d))

def idf(t):
    n = DF.get(t, 0)
    return math.log(1 + (N - n + 0.5) / (n + 0.5))

def bm25(query, doc_id, k1=K1, b=B):
    d = DOCS[doc_id]; tf = Counter(d); s = 0.0
    for t in tok(query):
        f = tf.get(t, 0)
        if not f: continue
        s += idf(t) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * len(d) / AVGDL))
    return s

def rang(query, **kw):
    return sorted(((bm25(query, d, **kw), d) for d in DOCS), reverse=True)

if __name__ == "__main__":
    print("=== 1. IDF: wie selten ein Wort ist, entscheidet ===")
    for t in ["kaution", "mietvertrag", "gut57", "we", "03.12", "der"]:
        print(f"  {t:<14} df={DF.get(t,0)}/{N}   idf={idf(t):.3f}")

    print("\n=== 2. Begriffsfrage: 'Kaution' – alle drei Verträge matchen ===")
    for s, d in rang("Kaution")[:4]:
        if s > 0: print(f"  {s:6.3f}  {d}")

    print("\n=== 3. Kennungsfrage: 'GUT57 WE 03.12' – die seltenen Token dominieren ===")
    for s, d in rang("GUT57 WE 03.12")[:4]:
        if s > 0: print(f"  {s:6.3f}  {d}")

    print("\n=== 4. Was k1 macht: Term-Frequenz-Sättigung ===")
    print("  Beitrag eines Terms bei f Vorkommen (IDF=1, Dokumentlaenge = Durchschnitt):")
    print(f"  {'f':>3} " + "".join(f"{'k1='+str(k):>10}" for k in (0.0, 0.5, 1.2, 3.0)))
    for f in (1, 2, 3, 5, 10, 20):
        row = "".join(f"{(f*(k+1))/(f+k):>10.3f}" for k in (0.0, 0.5, 1.2, 3.0))
        print(f"  {f:>3} " + row)

    print("\n=== 5. Was b macht: Längennormalisierung ===")
    print("  Derselbe Term, einmal in kurzem, einmal in langem Dokument (f=2):")
    for b in (0.0, 0.5, 0.75, 1.0):
        kurz = (2*(K1+1))/(2 + K1*(1-b + b*0.5))   # halb so lang wie Durchschnitt
        lang = (2*(K1+1))/(2 + K1*(1-b + b*2.0))   # doppelt so lang
        print(f"  b={b:<5} kurz={kurz:.3f}  lang={lang:.3f}  Verhaeltnis={kurz/lang:.2f}")

    print("\n=== 6. RRF: wie Azure AI Search die zwei Listen verschmilzt (k=60) ===")
    RRF_K = 60
    bm25_liste   = ["GUT57_chunk_01", "BRUEHL2_chunk_01", "SOD118_chunk_03", "GUT57_chunk_03"]
    vektor_liste = ["SOD118_chunk_03", "GUT57_chunk_03", "SOD118_chunk_12", "GUT57_chunk_01"]
    punkte = {}
    for liste in (bm25_liste, vektor_liste):
        for rang_, d in enumerate(liste, start=1):
            punkte[d] = punkte.get(d, 0.0) + 1.0 / (RRF_K + rang_)
    print(f"  {'Dokument':<20}{'BM25':>6}{'Vektor':>8}{'RRF-Score':>12}")
    for d, p in sorted(punkte.items(), key=lambda x: -x[1]):
        rb = bm25_liste.index(d)+1 if d in bm25_liste else None
        rv = vektor_liste.index(d)+1 if d in vektor_liste else None
        print(f"  {d:<20}{(rb or '—'):>6}{(rv or '—'):>8}{p:>12.5f}")
    print(f"\n  Obergrenze bei zwei Listen: 2 x 1/(60+1) = {2/61:.5f}")

    print("\n=== 7. Die Eigenschaft, auf die es ankommt ===")
    einig   = 1/(RRF_K+5) + 1/(RRF_K+5)   # Platz 5 in beiden Listen
    einsam  = 1/(RRF_K+1)                 # Platz 1 in nur einer Liste
    print(f"  Platz 5 in BEIDEN Listen : {einig:.5f}")
    print(f"  Platz 1 in NUR EINER     : {einsam:.5f}")
    print(f"  -> Einigkeit schlaegt Dominanz um Faktor {einig/einsam:.2f}")
    print("  Wie weit darf eine Liste abrutschen, damit Einigkeit noch gewinnt?")
    for r2 in (10, 20, 40, 60, 100):
        beide = 1/(RRF_K+1) + 1/(RRF_K+r2)
        print(f"    Platz 1 + Platz {r2:<4} = {beide:.5f}   {'schlaegt' if beide>einsam else 'verliert gegen'} Platz 1 allein")

    print("\n=== 8. Wie der Embedding-Tokenizer Kennungen zerlegt ===")
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")   # text-embedding-3-small
        for s_ in ["GUT57", "WE 03.12", "ME#0.02", "SOD118", "Kaution", "Kuendigungsfrist"]:
            ids = enc.encode(s_)
            teile = [enc.decode([i]) for i in ids]
            print(f"  {s_:<18} -> {len(ids)} Token: {teile}")
    except ImportError:
        print("  (tiktoken nicht installiert - uebersprungen)")
