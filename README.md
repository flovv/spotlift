# spotlift

Measure the lift of TV on web traffic and Amazon responses.

This repository contains the public, open-source core of the project. A
separate private `spotlift_pro` package may provide optimized binaries,
modeling code, or proprietary connectors.

Quick start
-----------

Install requirements (core):

    python -m pip install pandas

Install optional Prophet baseline:

    python -m pip install prophet

Usage example
-------------

    from spotlift import load_ga4_csv, moving_average_baseline

    df = load_ga4_csv("data/ga4.csv")
    baseline = moving_average_baseline(df, value_col="sessions", window=7)

Development
-----------

This repo intentionally keeps the public core lightweight. If you want me to
also scaffold tests, CI, or the private `spotlift_pro` repo layout, tell me and
I will continue.
