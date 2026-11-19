# Results of the competency questions (ERM-HS1 instantiation of SinSO)

HermiT consistency check (SINSO.owl + SinSO_ERM-HS1.owl): **CONSISTENT**

## CQ1. What quality attributes must a system include to be sustainable?

| qualityAttribute | characteristic | dimensions |
|---|---|---|
| Adaptability | Adaptability | Technical, Economical |
| EnergyEfficiency | EnergyEfficiency | Environmental |
| Interoperability | Interoperability | Social, Technical |
| Maintainability | Modularity | Technical, Economical |
| Performance | TimeBehaviour | Technical, Economical, Social, Individual-Personel |
| Reliability | Reliability | Technical, Social, Individual-Personel |
| Scalability | Scalability | Technical, Economical |
| Security | Confidentiality | Social, Individual-Personel |

## CQ7. What are the objectives assigned to the application domain?

| qualityAttribute | objective | indicator | measures |
|---|---|---|---|
| Adaptability | Adapt the deployment and the plans to load and patient state through the per-microservice MAPE-K loop | Capacity gained by adding an ERM replica; plans executed by the MAPE-K loop | Throughput x2.2 at 200 devices with a second replica (E4) | Expert rating 4.12 / 5 |
| EnergyEfficiency | Avoid redundant computation and transmission when monitoring patients | CPU time and network bytes per request with client-side caching | CPU time per request -35% with cache (E2) | Network bytes per request -22% with cache (E2) |
| Interoperability | Deliver patient observations to health information systems as HL7 FHIR R4 resources | Percentage of exchanged resources that are valid FHIR R4 | Expert rating 4.25 / 5 (design review; FHIR adapter not implemented) |
| Maintainability | Redeploy only the affected microservice when the estimation model changes | Number of services redeployed per change | Expert rating 4.38 / 5 (design review) |
| Performance | Serve every reading with a p95 latency below 1 s under normal load (up to 50 devices) | p95 end-to-end latency (ms) | p95 latency 38-58 ms with 10-50 devices (E1): objective met |
| Reliability | Lose no emergency request and recover in less than 5 s when an ERM instance crashes | Failed requests and recovery time after a crash | One replica: 12 failed requests, 4.2 s recovery (E3) | Two replicas: 0 failed requests in 4 of 5 runs (E3) |
| Scalability | Keep the median latency below 1 s and serve at least 90% of the offered load at 100-200 devices | Throughput (req/s) and median latency (ms) under peak load | One ERM replica: 75 req/s and p50 971 ms at 100 devices (E1): not met | Two ERM replicas: 93 req/s and p50 16 ms at 100 devices; 137 req/s at 200 devices (E4) |
| Security | Reject and log 100% of unauthenticated attempts to modify treatment goals | Percentage of unauthorized requests rejected | Expert rating 4.12 / 5 (design review; not measured on the prototype) |

## CQ8. What quality attributes does the domain contain to be sustainable?

| dimension | numberOfQAs | qualityAttributes |
|---|---|---|
| Economical | 4 | Performance, Scalability, Maintainability, Adaptability |
| Environmental | 1 | EnergyEfficiency |
| Individual-Personel | 3 | Performance, Reliability, Security |
| Social | 4 | Performance, Reliability, Security, Interoperability |
| Technical | 6 | Performance, Scalability, Reliability, Maintainability, Adaptability, Interoperability |
