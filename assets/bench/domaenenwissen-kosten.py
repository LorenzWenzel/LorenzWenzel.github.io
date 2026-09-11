# -*- coding: utf-8 -*-
"""Abgerechnete Input-Token je Nutzerfrage für drei Wege, einem text2SQL-Agenten
Domaenenwissen zu geben. Prompt Caching ist in allen Varianten aktiv.

Modell: Der stabile Praefix wird gecacht (Cache-Read = 0,1x Input-Preis), der
Gespraechsverlauf wird bei jedem Folgeturn zum vollen Preis erneut abgerechnet.
"""

PREIS_IN      = 2.00   # $/1M  – Claude Sonnet 5, Listenpreis
PREIS_CACHE   = 0.20   # $/1M  – Cache-Read, 10 % des Input-Preises
PREIS_OUT     = 10.00  # $/1M

SYS_SCHEMA    = 15_000   # Systemprompt + Tabellenschemata
KORPUS        = 250_000  # gesamtes Domaenenwissen (Kennzahldefinitionen, Regeln)
INDEX         =   2_500  # Inhaltsverzeichnis ueber den Korpus
TOOLDEFS      =     600  # MCP-Tool-Definitionen
RAG_TREFFER   =   4_000  # top-k Chunks
DOKUMENT      =   8_000  # eine vollstaendige Datei
FRAGE         =      40
OUTPUT        =     500  # Assistant-Ausgabe je Aufruf
SQL_ERGEBNIS  =   3_000  # Athena-Resultset als CSV (vgl. Teil 1)
SQL_AUFRUFE   =       3  # Modellaufrufe der SQL-Suchkette (in allen Varianten gleich)

VARIANTEN = {
    "0  Alles in den Systemprompt": dict(
        praefix=SYS_SCHEMA + KORPUS, vorab=0, wissen_aufrufe=0, wissen_nutzlast=0),
    "1  RAG in den Systemprompt": dict(
        praefix=SYS_SCHEMA, vorab=RAG_TREFFER, wissen_aufrufe=0, wissen_nutzlast=0),
    "2  RAG hinter MCP-Funktion": dict(
        praefix=SYS_SCHEMA + TOOLDEFS, vorab=0, wissen_aufrufe=1, wissen_nutzlast=RAG_TREFFER),
    "3  Index + Dateiabruf": dict(
        praefix=SYS_SCHEMA + INDEX + TOOLDEFS, vorab=0, wissen_aufrufe=2, wissen_nutzlast=DOKUMENT),
}

def rechne(praefix, vorab, wissen_aufrufe, wissen_nutzlast):
    """Simuliert die Aufrufkette und summiert abgerechnete Token."""
    verlauf = FRAGE + vorab          # waechst mit jedem Turn
    cache_token = 0                  # zum Cache-Read-Preis
    voll_token  = 0                  # zum vollen Input-Preis
    out_token   = 0
    aufrufe = 0

    # 1) Aufrufe, die das Domaenenwissen ausloest
    for _ in range(wissen_aufrufe):
        cache_token += praefix
        voll_token  += verlauf
        out_token   += OUTPUT
        aufrufe     += 1
        verlauf     += OUTPUT + wissen_nutzlast   # Tool-Aufruf + Tool-Ergebnis

    # 2) Aufrufe der SQL-Suchkette
    for i in range(SQL_AUFRUFE):
        cache_token += praefix
        voll_token  += verlauf
        out_token   += OUTPUT
        aufrufe     += 1
        verlauf     += OUTPUT + (SQL_ERGEBNIS if i < SQL_AUFRUFE - 1 else 0)

    kosten = (cache_token*PREIS_CACHE + voll_token*PREIS_IN + out_token*PREIS_OUT)/1e6
    return dict(aufrufe=aufrufe, cache=cache_token, voll=voll_token,
                out=out_token, kosten=kosten)

if __name__ == "__main__":
    print(f"{'Variante':<28}{'Aufrufe':>8}{'Cache-Read':>12}{'Vollpreis':>11}{'$/1000 Fragen':>15}")
    ergebnisse={}
    for name, p in VARIANTEN.items():
        r = rechne(**p); ergebnisse[name]=r
        print(f"{name:<28}{r['aufrufe']:>8}{r['cache']:>12,}{r['voll']:>11,}{r['kosten']*1000:>14.2f}")
    basis = ergebnisse["1  RAG in den Systemprompt"]["kosten"]
    print()
    for name,r in ergebnisse.items():
        print(f"  {name:<28} ×{r['kosten']/basis:.2f} gegenüber Variante 1")
