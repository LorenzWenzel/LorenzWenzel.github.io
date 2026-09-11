# -*- coding: utf-8 -*-
"""Was eine n-stufige Werkzeugkette in einem MCP-Agenten kostet.

Kernannahme, die dem Modell zugrunde liegt: Eine Kette der Tiefe n braucht
n+1 Modellaufrufe. Toolaufrufe sind dabei gratis im Sinne von Modellaufrufen –
beliebig viele koennen in einem Turn parallel laufen.
"""
PREIS_IN, PREIS_CACHE, PREIS_OUT = 2.00, 0.20, 10.00   # $/1M, Claude Sonnet 5

PRAEFIX      = 15_527   # Systemprompt + Schemata + Tool-Definitionen (gemessen)
FRAGE        =     40
TOOL_USE     =     60   # ein tool_use-Block, den das Modell erzeugt
TOOL_ERGEBNIS=  1_200   # ein tool_result-Block, den der Host zurueckschickt
ANTWORT      =    400   # finale Ausgabe

def kette(tiefe, breite):
    """tiefe = Runden, in denen das Modell Ergebnisse sehen muss, bevor es weitermacht
       breite = Tools je Runde (laufen parallel, kosten keinen extra Modellaufruf)"""
    verlauf = FRAGE
    cache = voll = out = 0
    for _ in range(tiefe):                 # Aufrufe 1..n: Werkzeuge anfordern
        cache += PRAEFIX; voll += verlauf
        out   += breite*TOOL_USE
        verlauf += breite*(TOOL_USE + TOOL_ERGEBNIS)
    cache += PRAEFIX; voll += verlauf       # Aufruf n+1: Antwort formulieren
    out   += ANTWORT
    kosten = (cache*PREIS_CACHE + voll*PREIS_IN + out*PREIS_OUT)/1e6
    return dict(aufrufe=tiefe+1, tools=tiefe*breite, cache=cache, voll=voll,
                out=out, kosten=kosten)

if __name__ == "__main__":
    print("=== Eine Kette wird tiefer: ein Tool je Runde ===")
    print(f"{'Tiefe':>6}{'Modellaufrufe':>15}{'Toolaufrufe':>13}{'Input (Vollpreis)':>19}{'$/1000 Fragen':>15}")
    for n in range(1,7):
        r = kette(n,1)
        print(f"{n:>6}{r['aufrufe']:>15}{r['tools']:>13}{r['voll']:>19,}{r['kosten']*1000:>15.2f}")

    print("\n=== Gleich viele Tools, andere Form: 6 Toolaufrufe ===")
    print(f"{'Form':<34}{'Modellaufrufe':>15}{'Input (Vollpreis)':>19}{'$/1000 Fragen':>15}")
    breit = kette(1,6); tief = kette(6,1)
    print(f"{'breit  (6 Tools in 1 Runde)':<34}{breit['aufrufe']:>15}{breit['voll']:>19,}{breit['kosten']*1000:>15.2f}")
    print(f"{'tief   (6 Runden à 1 Tool)':<34}{tief['aufrufe']:>15}{tief['voll']:>19,}{tief['kosten']*1000:>15.2f}")
    print(f"{'Faktor':<34}{tief['aufrufe']/breit['aufrufe']:>14.1f}x{tief['voll']/breit['voll']:>18.1f}x{tief['kosten']/breit['kosten']:>14.1f}x")

    print("\n=== Wachstum: verdoppelt sich die Tiefe, vervierfacht sich der Verlauf ===")
    for n in [1,2,4,8]:
        r=kette(n,1)
        print(f"  Tiefe {n}: {r['voll']:>8,} Token zum vollen Preis   ({r['kosten']*1000:7.2f} $/1000)")
