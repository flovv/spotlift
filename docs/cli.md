# Command Line Interface (CLI)

SpotLift provides a full-featured Command Line Interface (CLI) for running attribution passes, testing configurations, generating production clean-room SQL, and integrating into CI/CD or Airflow pipelines.

---

## 1. Quick Reference

```bash
# Run the instant interactive terminal demo
spotlift demo

# Run attribution over local campaign files
spotlift run --airings airings.csv --telemetry ga4.csv --output results.csv

# Generate BigQuery GA4 extraction SQL
spotlift generate-sql --dialect bigquery-ga4

# Check environment, Python version, and Pro license status
spotlift diagnose
```

---

## 2. Command Details

### `spotlift demo`

Executes an attribution pass on a synthetic benchmark DACH campaign (120 spots across RTL, ProSieben, Sat.1, VOX) with simulated GA4 minute sessions and prime-time collisions.

```bash
spotlift demo
```

Outputs a formatted Rich diagnostic summary showing:
* Broadcast schedule totals (spots, stations, media spend)
* Coverage diagnostics and isolated single spots
* Colliding spots detected within window
* Mean CPIV and total incremental visitor lift

---

### `spotlift run`

Runs the end-to-end attribution engine on your broadcast airings schedule and telemetry stream.

```bash
spotlift run \
  --airings /path/to/schaltplan.csv \
  --telemetry /path/to/ga4_minutes.csv \
  --output /path/to/attributed_spots.csv \
  --window-minutes 6 \
  --collision-attribution weighted_share
```

#### Arguments

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--airings`, `-a` | Path | *Required* | Path to broadcast airings CSV. |
| `--telemetry`, `-t` | Path | *Required* | Path to web telemetry CSV. |
| `--output`, `-o` | Path | `stdout` | Destination path for attributed CSV. |
| `--window-minutes`, `-w`| Integer | `6` | Post-airing response window in minutes. |
| `--collision-attribution`| String | `weighted_share`| Method for colliding spots (`weighted_share` or `naive_proportional`). |
| `--zero-fill-gaps` | Boolean | `false` | Fill missing telemetry minutes with `0.0`. |

---

### `spotlift generate-sql`

Outputs production-tested SQL templates for extracting digital telemetry.

```bash
# Export GA4 BigQuery SQL to file
spotlift generate-sql --dialect bigquery-ga4 > extract_ga4.sql
```

::: tip Amazon Marketing Cloud (AMC) Ingestion
Turnkey AMC extraction queries, 36-hour distributed lag retail halo modeling, and PPC cannibalization audits are enabled via [SpotLift Pro](/pro).
:::

---

### `spotlift diagnose`

Verifies local environment configuration, version alignment, and SpotLift Pro license status.

```bash
spotlift diagnose
```

---

## 3. Environment Variables

| Variable | Values | Description |
| :--- | :--- | :--- |
| `SPOTLIFT_QUIET` | `0` or `1` | Suppresses rich diagnostic terminal banners when running in automated batch pipelines. |
| `SPOTLIFT_API_KEY` | `SL_PRO_...` | Active license key for unlocking SpotLift Pro features. |
| `SPOTLIFT_MOCK_AUTH` | `0` or `1` | Enables local mock authentication for testing environments. |
