# -*- coding: utf-8 -*-
"""LLM-as-a-Judge für einen text2SQL-Agenten: Stichprobengröße und Kosten.

Zwei Fragen, die man vor jedem Judge-Setup beantworten sollte:
  1. Wie viele Golden-Fragen braucht es, bis ein Unterschied kein Rauschen ist?
  2. Was kostet es, jede (oder jede zehnte) Frage bewerten zu lassen?

Keine AWS-Aufrufe -- nur Statistik und Listenpreise.
"""
import math

Z_ALPHA = 1.96   # zweiseitig, alpha = 0,05
Z_BETA  = 0.84   # Power 80 %
P_BASE  = 0.80   # angenommene Trefferquote des Agenten

# ---------------------------------------------------------------------------
# 1. Minimal nachweisbarer Unterschied (MDE)
# ---------------------------------------------------------------------------
def mde_unpaired(n, p=P_BASE):
    """Zwei getrennte Stichproben je n Fragen (z. B. A/B auf Produktionsverkehr)."""
    return (Z_ALPHA + Z_BETA) * math.sqrt(2 * p * (1 - p) / n)

FLIP = 0.02  # Anteil Fragen, die bei einer Änderung in *beide* Richtungen kippen
def n_paired(d, flip=FLIP):
    """McNemar: dieselben Fragen, beide Versionen. Nur diskordante Paare zählen.
    p10 = flip (A richtig, B falsch), p01 = flip + d (A falsch, B richtig)."""
    pd = 2 * flip + d
    return (Z_ALPHA * math.sqrt(pd) + Z_BETA * math.sqrt(pd - d * d)) ** 2 / d ** 2

def mde_paired(n):
    lo, hi = 1e-4, 0.5
    for _ in range(60):                       # Bisektion: kleinstes d mit n_paired(d) <= n
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if n_paired(mid) > n else (lo, mid)
    return hi

# ---------------------------------------------------------------------------
# 2. Kosten je 1 000 bewerteter Fragen
# ---------------------------------------------------------------------------
IN_TOK, OUT_TOK = 6_000, 400   # Judge-Aufruf: Frage, Schema-Ausschnitt, Definitionen,
                               # SQL, Ergebnisauszug, Antwort / Begründung + Score
AGENT_PER_1000 = 76.0          # Modellrechnung des Agenten selbst (Caching-Beitrag)

PREISE = {                      # $ je 1 Mio. Token (Claude-API-Listenpreise)
    "Claude Haiku 4.5": (1.00, 5.00),
    "Claude Sonnet 5":  (2.00, 10.00),
    "Claude Opus 5":    (5.00, 25.00),
}
AC_BUILTIN = (2.40, 12.00)      # AgentCore Built-in-Evaluator, Modell inklusive
AC_CUSTOM_JE_1000 = 1.50        # AgentCore Custom-Evaluator, Modell separat

def modell(preis):
    i, o = preis
    return (IN_TOK * i + OUT_TOK * o) / 1e6 * 1000

if __name__ == "__main__":
    print("=== 1a. Unabhängige Stichproben (A/B mit verschiedenen Fragen) ===")
    for n in (50, 100, 200, 400, 800, 1600, 3200):
        print(f"  n = {n:>5} je Arm   ->  nachweisbar ab {100*mde_unpaired(n):5.1f} Prozentpunkten")
    print("\n=== 1b. Gepaart (dieselben Golden-Fragen, beide Versionen) ===")
    for n in (50, 100, 200, 400, 800, 1600):
        print(f"  n = {n:>5} Fragen   ->  nachweisbar ab {100*mde_paired(n):5.1f} Prozentpunkten")
    print("\n  Für +3 Punkte braucht es:")
    d = 0.03
    n_un = ((Z_ALPHA + Z_BETA) * math.sqrt(2 * P_BASE * (1 - P_BASE)) / d) ** 2
    print(f"    ungepaart  ~{n_un:,.0f} Fragen je Arm")
    print(f"    gepaart    ~{n_paired(d):,.0f} Fragen")

    print("\n=== 2. Judge-Kosten je 1 000 bewerteter Fragen ===")
    print(f"  Annahme: {IN_TOK:,} Input- und {OUT_TOK} Output-Token je Bewertung")
    b = modell(AC_BUILTIN)
    print(f"  {'AgentCore Built-in (Modell inkl.)':<36} {b:>7.2f} $")
    for name, p in PREISE.items():
        k = modell(p) + AC_CUSTOM_JE_1000
        print(f"  {'AgentCore Custom + ' + name:<36} {k:>7.2f} $   "
              f"({100*k/AGENT_PER_1000:4.1f} % der Agentenrechnung, bei 10 % Sampling "
              f"{10*k/AGENT_PER_1000:3.1f} %)")
    print(f"\n  Zum Vergleich: der Agent selbst ~{AGENT_PER_1000:.0f} $ je 1 000 Fragen")
    g = 300 * 3 * (modell(PREISE['Claude Opus 5']) + AC_CUSTOM_JE_1000) / 1000
    print(f"  Golden-Set-Lauf: 300 Fragen x 3 Evaluatoren mit Opus 5 ~{g:.0f} $")
