"""Checks the ERM-HS1 instantiation of SinSO.

1. Consistency of SINSO.owl + SinSO_ERM-HS1.owl with the HermiT reasoner (via owlready2; needs Java).
2. Answers the competency questions CQ1, CQ7 and CQ8 (competency_questions.sparql) and writes
   cq_results.md.

Usage: pip install owlready2 rdflib ; python check_ontology.py
"""
from pathlib import Path
import rdflib

here = Path(__file__).resolve().parent

# ---- 1. consistency with HermiT ------------------------------------------------------
import owlready2
from owlready2 import get_ontology, sync_reasoner, default_world, OwlReadyInconsistentOntologyError
owlready2.onto_path.append(str(here))
with open(here / "SINSO.owl", "rb") as f:
    base = get_ontology("http://www.semanticweb.org/ontologies/sinso").load(fileobj=f)
with open(here / "SinSO_ERM-HS1.owl", "rb") as f:
    inst = get_ontology("http://www.semanticweb.org/ontologies/sinso/erm-hs1").load(fileobj=f)
try:
    with inst:
        sync_reasoner(infer_property_values=False, debug=0)
    inconsistent = list(default_world.inconsistent_classes())
    consistency = "CONSISTENT" if not inconsistent else f"unsatisfiable classes: {inconsistent}"
except OwlReadyInconsistentOntologyError as e:
    consistency = f"INCONSISTENT: {e}"
print("HermiT:", consistency)

# ---- 2. competency questions ---------------------------------------------------------
g = rdflib.Graph()
g.parse(here / "SINSO.owl")
g.parse(here / "SinSO_ERM-HS1.owl")
queries = (here / "competency_questions.sparql").read_text(encoding="utf-8").split("# ===SPLIT===")
titles = ["CQ1. What quality attributes must a system include to be sustainable?",
          "CQ7. What are the objectives assigned to the application domain?",
          "CQ8. What quality attributes does the domain contain to be sustainable?"]
md = ["# Results of the competency questions (ERM-HS1 instantiation of SinSO)", "",
      f"HermiT consistency check (SINSO.owl + SinSO_ERM-HS1.owl): **{consistency}**", ""]
for title, q in zip(titles, queries):
    res = g.query(q)
    cols = [str(v) for v in res.vars]
    md += [f"## {title}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    rows = list(res)
    for r in rows:
        md.append("| " + " | ".join(str(x) for x in r) + " |")
    md.append("")
    print(f"{title} -> {len(rows)} rows")
(here / "cq_results.md").write_text("\n".join(md), encoding="utf-8")
print("written cq_results.md")
