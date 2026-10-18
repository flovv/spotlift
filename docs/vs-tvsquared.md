# SpotLift vs. TVSquared (Innovid), Adalyser & Legacy TV Attribution SaaS

A technical, economic, and operational comparison for media data scientists and TV media buyers.

| Dimension | Legacy TV Attribution SaaS (TVSquared / Innovid) | SpotLift (`spotlift` + `spotlift-pro`) |
| :--- | :--- | :--- |
| **Pricing & Contract** | €3,000 – €6,000+ / month; 12-month lock-in contract | **€0** Open Core / **€249** Single Flight Pass / €199–€499 Sub |
| **Delivery Model** | Closed SaaS web portal; requires invasive NDAs | **Python Library** running 100% locally in your Jupyter / Airflow |
| **Data Privacy & GDPR** | Raw web traffic uploaded to US-hosted SaaS vendors | **Zero Data Leakage:** Telemetry never leaves your VPC / machine |
| **Amazon Seller/Vendor Central** | ❌ None (Web pixels only; blind to Amazon sales) | ✅ **Native Dual-Stage Distributed Lag & PPC Auditor** |
| **Prime-Time Overlaps** | Proprietary black-box heuristic | ✅ **Shifted-Gamma EM Deconvolution with GRP Priors** |
| **PPC Cannibalization Audit**| ❌ None | ✅ **Separates Organic Halo from Sponsored Brands Interception** |
| **Amazon Clean Room (AMC)** | ❌ None | ✅ **5 Parameterized Production SQL Clean Room Queries** |
| **Extensibility & Automation**| Rigid web UI; manual CSV exports | ✅ **100% Automatable in Python, Airflow, Databricks, BigQuery** |
| **Procurement Friction** | 3–6 month enterprise IT & legal security review | **Instant expense on corporate credit card via Polar.sh** |

## Summary
Legacy TV attribution software was architected in the 2010s for web-only direct-to-consumer funnels. Today, 40%–70% of TV search volume goes directly into the Amazon App. SpotLift is the only modern Python-native engine purpose-built to solve both GA4 web attribution and the delayed Amazon conversion halo.
