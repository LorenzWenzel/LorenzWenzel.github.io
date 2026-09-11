# -*- coding: utf-8 -*-
"""Was die Infrastruktur eines text2SQL-Chatbots kostet – je 1 000 Nutzerfragen.

Drei Aufbauten, gleiche Modellrechnung:
  A  Converse + MCP selbst gebaut, gehostet auf Fargate (Agent + MCP-Server, dauerhaft an)
  B  AgentCore harness + Gateway (Athena hinter Lambda) + Memory
  C  Eigener Code (Strands, Converse) auf AgentCore Runtime, MCP-Server ebenfalls auf Runtime

Preise: AWS-Listenpreise, Stand September 2026, USD. Quellen im Beitrag.
"""

# --- AgentCore -----------------------------------------------------------------
RT_VCPU_H   = 0.0895     # Runtime microVM, je vCPU-Stunde, nur aktive CPU
RT_GB_H     = 0.00945    # Runtime microVM, je GB-Stunde, Spitzenspeicher je Sekunde, gesamte Session
GW_INVOKE   = 0.005/1000 # Gateway, je Tool-Aufruf
MEM_EVENT   = 0.25/1000  # Memory, je neues Kurzzeit-Event
MEM_RETR    = 0.50/1000  # Memory, je Langzeit-Abruf
# --- Fargate (x86, us-east-1; ARM waere ~20 % guenstiger) ------------------------
FG_VCPU_H   = 0.04048
FG_GB_H     = 0.004445
# --- Lambda ---------------------------------------------------------------------
LB_GB_S     = 0.0000166667
LB_REQ      = 0.20/1e6

# --- Profil einer Nutzerfrage (Annahmen, im Beitrag begruendet) -------------------
MODELLAUFRUFE   = 4      # 3 Aufrufe SQL-Kette + Antwort (vgl. MCP-Beitrag)
TOOLAUFRUFE     = 3      # Schema, Abfrage, ggf. Korrektur
WANDZEIT_S      = 22     # Sekunden je Frage: Modell ~12 s, Athena ~8 s, Rest
CPU_AKTIV_S     = 2.0    # davon aktive CPU im Agentenprozess
SPITZE_GB       = 1.0    # Speicher des Agentencontainers
FRAGEN_JE_SESSION = 5    # Unterhaltungslaenge
IDLE_S          = 900    # Runtime-Voreinstellung: 15 min Leerlauf bis zum Abbau
EVENTS_JE_FRAGE = 2 + 2*TOOLAUFRUFE   # Frage, Antwort, je Tool: Aufruf + Ergebnis
ATHENA_LAMBDA_S = 8.0    # Lambda wartet auf Athena
ATHENA_LAMBDA_GB= 0.5

def agentcore_runtime_je_frage(idle_s=IDLE_S):
    cpu = CPU_AKTIV_S/3600 * RT_VCPU_H
    mem_aktiv = WANDZEIT_S * SPITZE_GB/3600 * RT_GB_H
    # Leerlauf nach der letzten Frage einer Session wird auf die Fragen der Session umgelegt
    mem_idle = idle_s * SPITZE_GB/3600 * RT_GB_H / FRAGEN_JE_SESSION
    return cpu, mem_aktiv, mem_idle

def variante_B(idle_s=IDLE_S):
    cpu, mem_a, mem_i = agentcore_runtime_je_frage(idle_s)
    gateway = TOOLAUFRUFE * GW_INVOKE
    lam = TOOLAUFRUFE * (ATHENA_LAMBDA_S*ATHENA_LAMBDA_GB*LB_GB_S + LB_REQ)
    memory = EVENTS_JE_FRAGE*MEM_EVENT + 1*MEM_RETR   # ein Langzeit-Abruf je Aufruf
    return dict(runtime_cpu=cpu, runtime_mem=mem_a, runtime_idle=mem_i,
                gateway=gateway, lambda_athena=lam, memory=memory)

def variante_C(idle_s=IDLE_S):
    cpu, mem_a, mem_i = agentcore_runtime_je_frage(idle_s)
    # MCP-Server ebenfalls als Runtime-Session (eigene microVM), grob gleiches Profil, kein Memory-Dienst
    cpu2, mem_a2, mem_i2 = agentcore_runtime_je_frage(idle_s)
    return dict(runtime_cpu=cpu+cpu2, runtime_mem=mem_a+mem_a2, runtime_idle=mem_i+mem_i2,
                gateway=0.0, lambda_athena=0.0, memory=0.0)

def variante_A(fragen_je_monat, tasks=2, vcpu=1.0, gb=2.0):
    """Dauerhaft laufende Fargate-Tasks; Fixkosten werden auf die Fragen verteilt."""
    stunden = 730
    fix = tasks * stunden * (vcpu*FG_VCPU_H + gb*FG_GB_H)
    return fix / fragen_je_monat

if __name__ == "__main__":
    print("=== Variante B: AgentCore harness + Gateway + Memory, je 1 000 Fragen ===")
    b = variante_B()
    for k,v in b.items(): print(f"  {k:<14} {v*1000:8.2f} $")
    print(f"  {'SUMME':<14} {sum(b.values())*1000:8.2f} $")
    print(f"  ...davon Leerlauf-Speicher: {b['runtime_idle']/sum(b.values())*100:.0f} %")
    b5 = variante_B(idle_s=300)
    print(f"  mit idleTimeout 5 min:      {sum(b5.values())*1000:8.2f} $")

    print("\n=== Variante C: eigener Code + eigener MCP-Server auf Runtime, je 1 000 Fragen ===")
    c = variante_C()
    print(f"  SUMME                      {sum(c.values())*1000:8.2f} $")

    print("\n=== Variante A: Fargate dauerhaft (2 Tasks à 1 vCPU / 2 GB), je 1 000 Fragen ===")
    print(f"  Fixkosten je Monat: {2*730*(1*FG_VCPU_H+2*FG_GB_H):.2f} $")
    for fpm in [1_000, 3_000, 6_000, 20_000, 60_000, 200_000]:
        print(f"  {fpm:>8,} Fragen/Monat -> {variante_A(fpm)*1000:8.2f} $")

    print("\n=== Schnittpunkt: ab wie vielen Fragen/Monat ist Fargate je Frage guenstiger als B? ===")
    ziel = sum(b.values())
    fix = 2*730*(1*FG_VCPU_H+2*FG_GB_H)
    print(f"  {fix/ziel:,.0f} Fragen/Monat  (= {fix/ziel/30:,.0f} je Tag)")

    print("\n=== Zum Vergleich: Modellkosten je 1 000 Fragen (Caching-Beitrag, Sonnet 5, 4 Aufrufe, mit Cache) ===")
    print("  76.31 $  -> Infrastruktur ist ein Bruchteil davon")
