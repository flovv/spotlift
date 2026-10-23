# SpotLift vs. Legacy TV Attribution SaaS

A technical, economic, and operational comparison against legacy platforms like TVSquared (Innovid), Adalyser, and traditional black-box attribution vendors.

---

## Architectural Comparison Matrix

| Dimension | Legacy TV Attribution SaaS (TVSquared / Innovid / Adalyser) | SpotLift (`spotlift` + `spotlift-pro`) |
| :--- | :--- | :--- |
| **Pricing & Terms** | €3,000 – €6,000+ / month; 12-month lock-in contract | **Free Open-Core** / **€249** Single Flight Pass / Pro Sub |
| **Delivery Model** | Closed SaaS web portal; proprietary database | **Python Library** running natively in your Jupyter, Airflow, or dbt pipeline |
| **Data Privacy & GDPR** | Raw customer clickstream sent to 3rd-party servers | **100% On-Prem / Local:** Zero customer data leaves your VPC |
| **Amazon Telemetry** | ❌ Completely blind to Amazon retail demand | ✅ **Native AMC Clean Room & 36h Retail Halo Modeling** |
| **PPC Cannibalization**| ❌ None (assumes all search lift is organic) | ✅ **Audits Sponsored Brands PPC cannibalization** |
| **Prime-Time Collisions**| Proprietary black-box heuristic | ✅ **Shifted-Gamma EM Deconvolution with GRP Priors** |
| **Automation** | Manual CSV uploads and static PDF dashboards | ✅ **Automated via Python scripts, CLI, and Airflow DAGs** |
| **Procurement Cycle** | 3–6 months enterprise IT, legal, and security review | **Instant install via `pip` and [Polar.sh Checkout](https://buy.polar.sh/polar_cl_eHd0shvN1nvDYVV59IkhvvPDNw4Rxmu77INZ023fbF4)** |

---

## Deep Dive: Key Technical Differences

### 1. Data Privacy & GDPR Compliance

* **Legacy SaaS:** Requires placing proprietary JavaScript tags or pixels across your entire website. Every visitor's IP address, device fingerprint, and browsing behavior is transmitted to third-party US cloud servers, triggering complex Data Processing Agreements (DPAs) and consent banner scrutiny.
* **SpotLift:** Operates entirely within your own infrastructure. You query GA4 in your own BigQuery project or Snowflake instance and run attribution locally. **Not a single byte of customer PII ever leaves your security perimeter.**

---

### 2. The Amazon Marketplace Blind Spot

Traditional TV attribution was designed during the early direct-to-consumer (DTC) boom when virtually all TV response landed on `brand.com`. 

Today, between 30% and 50% of consumers who see a TV commercial open the Amazon app on their phone. Legacy tools attribute this response as "unaccounted" or zero lift, misleading brands into cutting profitable TV flights.

SpotLift natively bridges:
* **Immediate Web Sessions:** Minute-by-minute GA4 direct and organic visits.
* **Delayed Amazon Purchases:** Hourly conversion streams extracted via Amazon Marketing Cloud (AMC) clean room SQL.

---

### 3. Open Mathematical Models vs. Black Boxes

When a legacy attribution portal reports that "Spot #412 drove 814 visitors with an index of 142," there is no way to verify the underlying baseline, verify whether random traffic noise was clamped, or adjust response windows.

SpotLift gives quantitative teams complete control:
* Transparent diurnal baseline formulations.
* Unbiased signed lift preservation (avoiding the 15–35% upward rectification bias).
* Exact mathematical specifications for Shifted-Gamma kernel deconvolution.
* Direct access to raw DataFrames for custom econometric downstream modeling.

---

## Conclusion

SpotLift is designed for media data scientists and modern quantitative agencies who demand auditability, speed, and privacy. 

Try the [5-Minute Quickstart](/quickstart) or explore [SpotLift Pro](/pro) for enterprise prime-time deconvolution.
