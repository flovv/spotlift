# SpotLift vs. TVSquared (Innovid), Adalyser & Legacy TV Attribution SaaS

A technical, economic, and operational comparison for media data scientists and TV media buyers.

| Dimension | Legacy TV Attribution SaaS (TVSquared / Innovid) | SpotLift (`spotlift` + `spotlift-pro`) |
| :--- | :--- | :--- |
| **Pricing & Contract** | €3,000 – €6,000+ / month; 12-month lock-in contract | **€0** Open Core / **€249** Single Flight Pass / €199–€499 Sub |
| **Delivery Model** | Closed SaaS web portal; requires NDAs | **Python Library** running 100% locally in your Jupyter / Airflow |
| **Data Privacy & GDPR** | Raw web traffic uploaded to third-party SaaS vendors | **Zero Data Leakage:** Telemetry never leaves your VPC / machine |
| **Amazon Telemetry** | ❌ None (Web pixels only; blind to Amazon sales) | ✅ **Native Dual-Stage Distributed Lag via AMC & PPC Auditor** |
| **Prime-Time Overlaps** | Proprietary black-box heuristic | ✅ **Shifted-Gamma EM Deconvolution with GRP Priors** |
| **PPC Cannibalization Audit**| ❌ None | ✅ **Separates Organic Halo from Sponsored Brands Interception** |
| **Amazon Clean Room (AMC)** | ❌ None | ✅ **Production SQL Clean Room Queries** |
| **Extensibility & Automation**| Rigid web UI; manual CSV exports | ✅ **100% Automatable in Python, Airflow, Databricks, BigQuery** |
| **Procurement Friction** | 3–6 month enterprise IT & legal security review | **[Instant expense via Polar.sh Checkout](https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4)** |

## Summary
Legacy TV attribution software was architected for web-only direct-to-consumer funnels using website pixels. Today, significant television viewer response manifests as search and delayed conversion on Amazon. SpotLift is a modern Python-native engine purpose-built to evaluate both immediate GA4 web response and delayed Amazon conversion telemetry via Amazon Marketing Cloud (AMC).
