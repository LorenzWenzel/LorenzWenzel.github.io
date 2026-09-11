import json, random, io, csv, sys
import tiktoken

enc = tiktoken.get_encoding("o200k_base")
def t(s): return len(enc.encode(s))

random.seed(42)

# Realistischer Athena-Resultset eines text2SQL-Agenten:
# "Umsatz je Region und Produktkategorie im letzten Quartal"
REGIONS = ["EU-Central","EU-West","US-East","US-West","APAC-North","APAC-South","LATAM","MEA"]
CATS = ["Elektronik","Haushalt","Bekleidung","Sport","Buecher","Spielzeug","Garten","Drogerie"]
COLS = ["region","product_category","order_month","net_revenue_eur","order_count","avg_basket_eur"]

def make_rows(n):
    rows=[]
    for i in range(n):
        rows.append({
            "region": REGIONS[i % len(REGIONS)],
            "product_category": CATS[(i//len(REGIONS)) % len(CATS)],
            "order_month": f"2026-{(i%12)+1:02d}",
            "net_revenue_eur": round(random.uniform(1000, 950000), 2),
            "order_count": random.randint(12, 48000),
            "avg_basket_eur": round(random.uniform(11.5, 780.0), 2),
        })
    return rows

def f_json_pretty(rows): return json.dumps(rows, indent=2, ensure_ascii=False)
def f_json_compact(rows): return json.dumps(rows, separators=(",",":"), ensure_ascii=False)
def f_json_columnar(rows):
    return json.dumps({"columns": COLS, "rows": [[r[c] for c in COLS] for r in rows]},
                      separators=(",",":"), ensure_ascii=False)
def f_csv(rows):
    b=io.StringIO(); w=csv.writer(b, lineterminator="\n"); w.writerow(COLS)
    for r in rows: w.writerow([r[c] for c in COLS])
    return b.getvalue()
def f_tsv(rows):
    out=["\t".join(COLS)]
    for r in rows: out.append("\t".join(str(r[c]) for c in COLS))
    return "\n".join(out)+"\n"
def f_markdown(rows):
    out=["| "+" | ".join(COLS)+" |", "| "+" | ".join("---" for _ in COLS)+" |"]
    for r in rows: out.append("| "+" | ".join(str(r[c]) for c in COLS)+" |")
    return "\n".join(out)+"\n"
def f_yaml(rows):
    out=[]
    for r in rows:
        out.append("- "+"\n  ".join(f"{c}: {r[c]}" for c in COLS))
    return "\n".join(out)+"\n"
def f_xml(rows):
    out=["<results>"]
    for r in rows:
        out.append("  <row>"+"".join(f"<{c}>{r[c]}</{c}>" for c in COLS)+"</row>")
    out.append("</results>")
    return "\n".join(out)+"\n"
def f_toon(rows):
    out=[f"results[{len(rows)}]{{{','.join(COLS)}}}:"]
    for r in rows: out.append("  "+",".join(str(r[c]) for c in COLS))
    return "\n".join(out)+"\n"

FORMATS = [
    ("JSON (pretty)", f_json_pretty),
    ("JSON (compact)", f_json_compact),
    ("JSON (columnar)", f_json_columnar),
    ("XML", f_xml),
    ("YAML", f_yaml),
    ("Markdown-Tabelle", f_markdown),
    ("TOON", f_toon),
    ("CSV", f_csv),
    ("TSV", f_tsv),
]

SIZES=[10,50,200,1000]
results={"sizes":SIZES,"formats":{},"cols":COLS}
for name,fn in FORMATS:
    results["formats"][name]=[t(fn(make_rows(n))) for n in SIZES]

# Beispiel-Rendering (5 Zeilen) fuer den Post
sample=make_rows(3)
samples={name: fn(sample) for name,fn in FORMATS}

print(json.dumps({"bench":results,"samples":samples}, ensure_ascii=False, indent=1))
