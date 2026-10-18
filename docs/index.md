# SpotLift Documentation

Welcome to **SpotLift**, the Python-native econometric attribution engine for Linear TV & Connected TV (CTV).

## High-Frequency Spot Attribution across GA4 & Amazon

Unlike legacy attribution SaaS tools that rely solely on website pixels, SpotLift measures:
1. **Google Analytics 4 (GA4):** 1-minute resolution direct response sessions and conversions.
2. **Amazon Seller & Vendor Central:** 36-hour distributed lag conversion halo across units, GMV, and brand search impressions.
3. **PPC Cannibalization:** Identifies wasted Sponsored Brands spend on branded queries during TV flights.

## Getting Started

Install SpotLift via pip:
```bash
pip install spotlift
```

Try the instant demo:
```bash
spotlift demo --out-dir ./demo_data
```

## Architectural Philosophy
- **Local Execution:** No raw broadcast or customer telemetry ever leaves your environment.
- **Unbundled & Focused:** Strictly dedicated to high-frequency temporal spot attribution (no spatial matched-market holdouts or Bayesian MMM priors mixed in).
- **Extensible:** Open-Core foundation on PyPI with high-performance compiled Cython extension for complex multi-spot prime-time overlaps.
