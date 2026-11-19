"""Builds SinSO_ERM-HS1.owl: the instantiation of the SinSO ontology for the ERM-HS1 lab case.

It follows the pattern of the example individuals of SinSO (domain1, QA1, Objective1, ...):
  Domain --hasQAS--> QualityAttribute --isComposedOf--> <SinSO characteristic> --hasImpact--> <dimension>
  QualityAttribute --hasObjective--> Objective --hasIndicator--> Indicator --obtains--> Measure
  Measure --uses--> Measurement --hasScale--> Scale --belongsTo--> TypeOfScale
and links each quality attribute to the sustainability dimensions with isRelatedTo, as described in
the paper (section "Lab case instantiation in the SinSO ontology"). Measured values come from the
prototype experiments (E1-E4) and the expert evaluation reported in the paper.

Usage: python build_instantiation.py   (writes SinSO_ERM-HS1.owl next to this script)
"""
from pathlib import Path
import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

S = rdflib.Namespace("http://www.semanticweb.org/ontologies/sinso#")
ONT = URIRef("http://www.semanticweb.org/ontologies/sinso/erm-hs1")
E = rdflib.Namespace(str(ONT) + "#")

g = rdflib.Graph()
g.bind("sinso", S); g.bind("erm", E); g.bind("owl", OWL)
g.add((ONT, RDF.type, OWL.Ontology))
g.add((ONT, OWL.imports, URIRef("http://www.semanticweb.org/ontologies/sinso")))
g.add((ONT, RDFS.comment, Literal(
    "Instantiation of SinSO for the ERM-HS1 lab case (Emergency Response Microservice for stage 1 "
    "hypertension patients in a smart home for seniors). Companion artifact of the paper 'Towards "
    "Sustainable Cyber-Physical Systems: An Adaptation-Centric Architectural Framework and a Lab Case "
    "for Healthcare Environments'.")))
g.add((ONT, OWL.versionInfo, Literal("1.0.0")))


def ind(name, cls, label=None):
    u = E[name]
    g.add((u, RDF.type, OWL.NamedIndividual)); g.add((u, RDF.type, cls))
    if label:
        g.add((u, RDFS.label, Literal(label, lang="en")))
    return u


# ---- domain -------------------------------------------------------------------------
dom = ind("ERM_HS1", S.Domain, "ERM-HS1 lab case")
g.add((dom, S.identifier, Literal("ERM-HS1")))
g.add((dom, S.name, Literal("Emergency Response Microservice for stage 1 hypertension patients (smart home for seniors)")))
g.add((dom, S.objective, Literal("Detect critical blood pressure readings and plan emergency responses or treatment-adjustment "
                                 "recommendations, while sustaining the quality attributes of the framework.")))

# ---- scales and measurements ----------------------------------------------------------
def scale(name, type_name, value=None):
    t = ind("Type_" + name, S.TypeOfScale)
    g.add((t, S.nameTypeOfScale, Literal(type_name)))
    sc = ind("Scale_" + name, S.Scale)
    g.add((sc, S.belongsTo, t)); g.add((sc, S.identifierScale, Literal("ID" + name)))
    g.add((sc, S.nameScale, Literal(type_name)))
    if value is not None:
        g.add((sc, S.value, Literal(value, datatype=XSD.int)))
    return sc

sc_ms = scale("Milliseconds", "Ratio scale - milliseconds")
sc_rps = scale("RequestsPerSecond", "Ratio scale - requests per second")
sc_pct = scale("Percentage", "Ratio scale - percentage (0-100)", 100)
sc_count = scale("Count", "Absolute scale - count")
sc_sec = scale("Seconds", "Ratio scale - seconds")
sc_likert = S.Scale1  # SinSO's own Likert 1-5 scale

def measurement(name, text, scale_ind):
    m = ind("Measurement_" + name, S.Measurement)
    g.add((m, S.identifierMeasurement, Literal(name))); g.add((m, S.nameMeasurement, Literal(text)))
    g.add((m, S.hasScale, scale_ind))
    return m

m_lat = measurement("LoadLatency", "Load generator on the Docker prototype; per-request latency, 5 runs x 30 s (experiments E1/E4)", sc_ms)
m_thr = measurement("LoadThroughput", "Load generator on the Docker prototype; completed requests per second, 5 runs x 30 s (E1/E4)", sc_rps)
m_cpu = measurement("CgroupCPU", "CPU time per request from cgroup v2 cpu.stat, relative change with vs. without cache (E2)", sc_pct)
m_net = measurement("NetBytes", "Network bytes per request from /sys/class/net counters, relative change with vs. without cache (E2)", sc_pct)
m_fail = measurement("FailedRequests", "Failed requests after crashing the ERM instance (E3)", sc_count)
m_rec = measurement("RecoveryTime", "Time from the crash to the last failed request (E3)", sc_sec)
m_exp = measurement("ExpertRating", "Expert evaluation, mean agreement of four experts (Likert 1-5)", sc_likert)

# ---- quality attributes ---------------------------------------------------------------
QAS = [
 # key, characteristic class, dimension individuals (isRelatedTo / hasImpact), objective, indicator, measures
 ("Performance", S.TimeBehaviour,
  [S.Longevity, S.Profitability, S.CustomerSatisfaction, getattr(S, "Well-being")],
  "Serve every reading with a p95 latency below 1 s under normal load (up to 50 devices)",
  "p95 end-to-end latency (ms)",
  [("p95 latency 38-58 ms with 10-50 devices (E1): objective met", m_lat)]),
 ("Scalability", S.Scalability,
  [S.Longevity, S.Investment],
  "Keep the median latency below 1 s and serve at least 90% of the offered load at 100-200 devices",
  "Throughput (req/s) and median latency (ms) under peak load",
  [("One ERM replica: 75 req/s and p50 971 ms at 100 devices (E1): not met", m_thr),
   ("Two ERM replicas: 93 req/s and p50 16 ms at 100 devices; 137 req/s at 200 devices (E4)", m_thr)]),
 ("EnergyEfficiency", S.EnergyEfficiency,
  [S.EnergyResources, S.ClimateChange],
  "Avoid redundant computation and transmission when monitoring patients",
  "CPU time and network bytes per request with client-side caching",
  [("CPU time per request -35% with cache (E2)", m_cpu), ("Network bytes per request -22% with cache (E2)", m_net)]),
 ("Reliability", S.Reliability,
  [S.Maintenance, S.Accesability, getattr(S, "Well-being")],
  "Lose no emergency request and recover in less than 5 s when an ERM instance crashes",
  "Failed requests and recovery time after a crash",
  [("One replica: 12 failed requests, 4.2 s recovery (E3)", m_fail),
   ("Two replicas: 0 failed requests in 4 of 5 runs (E3)", m_fail)]),
 ("Security", S.Confidentiality,
  [S.RespectHumanRights, getattr(S, "Well-being")],
  "Reject and log 100% of unauthenticated attempts to modify treatment goals",
  "Percentage of unauthorized requests rejected",
  [("Expert rating 4.12 / 5 (design review; not measured on the prototype)", m_exp)]),
 ("Maintainability", S.Modularity,
  [S.Longevity, S.Maintenance, S.Investment],
  "Redeploy only the affected microservice when the estimation model changes",
  "Number of services redeployed per change",
  [("Expert rating 4.38 / 5 (design review)", m_exp)]),
 ("Adaptability", S.Adaptability,
  [S.Innovation, S.Investment],
  "Adapt the deployment and the plans to load and patient state through the per-microservice MAPE-K loop",
  "Capacity gained by adding an ERM replica; plans executed by the MAPE-K loop",
  [("Throughput x2.2 at 200 devices with a second replica (E4)", m_thr), ("Expert rating 4.12 / 5", m_exp)]),
 ("Interoperability", S.Interoperability,
  [S.Accesability, S.Innovation],
  "Deliver patient observations to health information systems as HL7 FHIR R4 resources",
  "Percentage of exchanged resources that are valid FHIR R4",
  [("Expert rating 4.25 / 5 (design review; FHIR adapter not implemented)", m_exp)]),
]

for i, (key, cls, dims, obj, indic, measures) in enumerate(QAS, 1):
    qa = ind("QA_" + key, S.QualityAttribute, key)
    g.add((dom, S.hasQAS, qa)); g.add((qa, S.specifiedFor, dom))
    ch = ind(key + "_ERM", cls, key + " of ERM-HS1")
    g.add((qa, S.isComposedOf, ch))
    for d in dims:
        g.add((qa, S.isRelatedTo, d)); g.add((ch, S.hasImpact, d))
    o = ind(f"Objective_{key}", S.Objective)
    g.add((o, S.identifierObjective, Literal(f"OBJ{i}"))); g.add((o, S.nameObjective, Literal(obj)))
    g.add((qa, S.hasObjective, o))
    n = ind(f"Indicator_{key}", S.Indicator)
    g.add((n, S.identifierIndicator, Literal(f"IND{i}"))); g.add((n, S.nameIndicator, Literal(indic)))
    g.add((o, S.hasIndicator, n))
    for j, (text, msmt) in enumerate(measures, 1):
        me = ind(f"Measure_{key}_{j}", S.Measure)
        g.add((me, S.identifierMeasure, Literal(f"MEA{i}.{j}"))); g.add((me, S.nameMeasure, Literal(text)))
        g.add((me, S.uses, msmt)); g.add((n, S.obtains, me))

# Axiom A1 (shouldHas Maintainability/Portability/Evolvability/Scalability): explicit for the domain QAs
for key in ("Performance", "Scalability", "EnergyEfficiency", "Reliability", "Security", "Maintainability",
            "Adaptability", "Interoperability"):
    g.add((E["QA_" + key], S.shouldHas, E["Maintainability_ERM"]))
    g.add((E["QA_" + key], S.shouldHas, E["Scalability_ERM"]))

out = Path(__file__).resolve().parent / "SinSO_ERM-HS1.owl"
g.serialize(out, format="pretty-xml")
print("written", out, "| triples:", len(g))
