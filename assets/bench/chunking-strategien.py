# -*- coding: utf-8 -*-
"""Chunking: die Tokenzaehlung des POC gegen die des Embedding-Modells.

Der POC zaehlt mit einer eigenen Regex (\\w+|[^\\w\\s]). Das Modell zaehlt mit
cl100k_base, dem Tokenizer der text-embedding-3-Familie. Beide heissen "Token",
meinen aber nicht dasselbe -- und bei deutschen Komposita laufen sie weit
auseinander.

    pip install tiktoken
"""
import re
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")   # text-embedding-3-small/-large
POC = re.compile(r"\w+|[^\w\s]", re.UNICODE)  # SectionBuilder.py, _TOKEN_RE

# Ein typischer Vertragsabschnitt. Selbst formuliert -- keine echten Vertragsdaten.
TEXT = """§ 3 Miete und Nebenkosten

(1) Die monatliche Grundmiete beträgt 1.250,00 EUR (in Worten:
eintausendzweihundertfünfzig Euro). Daneben ist eine Betriebskostenvorauszahlung
in Höhe von 210,00 EUR sowie eine Heizkostenvorauszahlung in Höhe von 95,00 EUR
zu entrichten. Die Gesamtmiete beträgt somit 1.555,00 EUR.

(2) Die Miete ist monatlich im Voraus, spätestens bis zum dritten Werktag eines
jeden Monats, kostenfrei auf das Konto des Vermieters zu überweisen. Für die
Rechtzeitigkeit der Zahlung kommt es nicht auf die Absendung, sondern auf die
Gutschrift auf dem Konto des Vermieters an.

(3) Betriebskosten im Sinne des § 556 Abs. 1 BGB in Verbindung mit der
Betriebskostenverordnung (BetrKV) werden jährlich abgerechnet. Die Abrechnung
erfolgt nach dem Verhältnis der Wohnflächen, soweit nicht ein verbrauchsabhängiger
Maßstab zwingend vorgeschrieben ist. Mieteinheit: WE 03.12, Objekt GUT57."""

# POC-Chunkingparameter aus SectionBuilder.py
TARGET, OVERLAP, MIN, MAX = 800, 100, 600, 1000
MODELL_MAX = 8191   # max. Eingabe von text-embedding-3-small


def zerlege(w):
    return POC.findall(w), [enc.decode([t]) for t in enc.encode(w)]


if __name__ == "__main__":
    n_poc = len(POC.findall(TEXT))
    n_mod = len(enc.encode(TEXT))
    faktor = n_mod / n_poc

    print("=== 1. Zwei Tokenzaehlungen auf demselben Text ===")
    print(f"  Zeichen                {len(TEXT):>6}")
    print(f"  Woerter (split)        {len(TEXT.split()):>6}")
    print(f"  POC-Regex              {n_poc:>6}")
    print(f"  cl100k_base (Modell)   {n_mod:>6}")
    print(f"  Faktor Modell / POC    {faktor:>6.2f}")

    print("\n=== 2. Was die POC-Parameter beim Modell bedeuten ===")
    for name, wert in [("MIN", MIN), ("TARGET", TARGET), ("MAX", MAX), ("OVERLAP", OVERLAP)]:
        print(f"  {name:<8} {wert:>5} POC-Token  ->  ~{round(wert*faktor):>5} Modell-Token")
    print(f"  Grenze des Modells: {MODELL_MAX} Token"
          f"  ->  Luft bis dahin: Faktor {MODELL_MAX/(MAX*faktor):.1f}")

    print("\n=== 3. Wo die beiden Zaehlungen auseinanderlaufen ===")
    for w in ["Betriebskostenvorauszahlung", "Heizkostenvorauszahlung",
              "Schoenheitsreparaturen", "GUT57", "WE 03.12", "§ 556", "1.250,00"]:
        p, m = zerlege(w)
        print(f"  {w}")
        print(f"     POC   ({len(p):>2}): {p}")
        print(f"     Modell({len(m):>2}): {m}")

    print("\n=== 4. Der Overlap als Indexaufschlag ===")
    for lab, ov, tg in [("POC", OVERLAP, TARGET), ("Microsoft-Empfehlung", 128, 512)]:
        print(f"  {lab:<22} {ov:>4} / {tg:<4} = +{100*ov/tg:>5.1f} % Chunks im Index")
