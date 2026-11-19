# SinSO ontology and the ERM-HS1 lab-case instantiation

| File | Content |
|---|---|
| `SINSO.owl` | The SinSO ontology v1.0.0 (copy of the published dataset, CC BY 4.0): Restrepo Gutierrez, L. F. (2023). *SINSO Ontology*, Mendeley Data, V2. https://doi.org/10.17632/ygv49pb4dx.2 |
| `SinSO_ERM-HS1.owl` | Instantiation of SinSO for the ERM-HS1 lab case (imports SinSO): the domain, its eight quality attributes, the SinSO characteristics they are composed of, the sustainability dimensions they are related to, and their objectives, indicators, measures, measurements and scales (with the values measured in experiments E1–E4 and in the expert evaluation) |
| `catalog-v001.xml` | Lets Protégé resolve the import of SinSO from the local `SINSO.owl` |
| `build_instantiation.py` | Script that generates `SinSO_ERM-HS1.owl` |
| `competency_questions.sparql` | SPARQL queries for the competency questions CQ1, CQ7 and CQ8 |
| `check_ontology.py` | Checks consistency with the HermiT reasoner and answers the competency questions → `cq_results.md` |
| `cq_results.md` | Output of `check_ontology.py` (consistency result and answers to CQ1, CQ7, CQ8) |

```bash
pip install owlready2 rdflib      # HermiT needs Java 8+
python build_instantiation.py
python check_ontology.py
```

In Protégé (5.6+): open `SinSO_ERM-HS1.owl` from this folder (the import of SinSO is resolved
from `SINSO.owl` through `catalog-v001.xml`), then Reasoner > HermiT > Start reasoner, and run
the queries in the SPARQL Query tab.

The instantiation checks that the design of the lab case declares the quality attributes, goals,
indicators and measures required by SinSO; it does not by itself measure them.
