# -*- coding: utf-8 -*-
"""Ab wann sich Prompt Caching rechnet – und ab wann ein billigeres Modell
ohne Caching teurer wird als Claude Sonnet 5 mit Caching.

Belastbar sind die Multiplikatoren, nicht die absoluten Preise:
Cache-Write = 1,25 x Input, Cache-Read = 0,1 x Input (90 % Rabatt).
"""
PRAEFIX = 15_527    # Systemprompt + Schemata + Tool-Definitionen (vgl. MCP-Beitrag)
FRAGE, TOOL_USE, TOOL_ERGEBNIS, ANTWORT = 40, 60, 1_200, 400
W_WRITE, W_READ = 1.25, 0.10

# Bedrock, On-Demand, US-Regionen (Stand September 2026)
MODELLE = {
    "Sonnet 5 (mit Cache)":  dict(inp=2.20, out=11.00, cache=True),
    "Sonnet 5 (ohne Cache)": dict(inp=2.20, out=11.00, cache=False),
    "Qwen3-Coder-Next":      dict(inp=0.60, out=1.44,  cache=False),
    "Qwen3 32B":             dict(inp=0.15, out=1.20,  cache=False),
    "Mistral Large 3":       dict(inp=0.50, out=1.50,  cache=False),
    "DeepSeek v3.2":         dict(inp=0.62, out=1.85,  cache=False),
    "Llama 3.3 70B":         dict(inp=0.40, out=1.00,  cache=False),
}

def kosten(aufrufe, inp, out, cache):
    """Kosten je 1000 Nutzerfragen. aufrufe = n+1 bei n-stufiger Kette."""
    verlauf = FRAGE; praefix_kosten = 0.0; voll = 0; ausgabe = 0
    for i in range(aufrufe):
        if cache:
            praefix_kosten += PRAEFIX * inp * (W_WRITE if i == 0 else W_READ)
        else:
            praefix_kosten += PRAEFIX * inp
        voll += verlauf
        if i < aufrufe-1:
            ausgabe += TOOL_USE; verlauf += TOOL_USE + TOOL_ERGEBNIS
        else:
            ausgabe += ANTWORT
    return (praefix_kosten + voll*inp + ausgabe*out)/1e6*1000

if __name__ == "__main__":
    print("=== Kosten je 1000 Fragen, nach Zahl der Modellaufrufe ===")
    stufen=[2,3,4,6,8]
    print(f"{'Modell':<24}" + "".join(f"{k:>10} Aufr." for k in stufen))
    erg={}
    for name,p in MODELLE.items():
        reihe=[kosten(k,**p) for k in stufen]; erg[name]=reihe
        print(f"{name:<24}" + "".join(f"{v:>15.2f}" for v in reihe))

    print("\n=== Was Caching allein bringt (Sonnet 5 gegen sich selbst) ===")
    for k,a,b in zip(stufen, erg["Sonnet 5 (ohne Cache)"], erg["Sonnet 5 (mit Cache)"]):
        print(f"  {k} Modellaufrufe: {a:7.2f} -> {b:7.2f}   ({(1-b/a)*100:4.1f} % gespart)")

    print("\n=== Ab wann ueberholt Sonnet 5 mit Cache ein Modell ohne Cache? ===")
    for name in ["DeepSeek v3.2","Qwen3-Coder-Next","Mistral Large 3","Llama 3.3 70B","Qwen3 32B"]:
        gefunden=False
        for k in range(2,61):
            s=kosten(k,**MODELLE["Sonnet 5 (mit Cache)"]); q=kosten(k,**MODELLE[name])
            if s<q:
                print(f"  {name:<20} ab {k} Modellaufrufen (Kettentiefe {k-1})")
                gefunden=True; break
        if not gefunden:
            print(f"  {name:<20} bleibt bis 60 Aufrufe guenstiger")

    print("\n=== Break-even des Praefix allein: ab welchem Preisverhaeltnis? ===")
    print("  Ein Modell ohne Caching muss billiger sein als ... des Sonnet-Input-Preises:")
    for k in [2,3,5,7,10,20]:
        f=(W_WRITE + W_READ*(k-1))/k
        print(f"   bei {k:>2} Modellaufrufen: {f*100:5.1f} %   (= ${2.20*f:.2f}/Mio.)")
