# Command Line Interface (CLI)

SpotLift provides a full-featured Command Line Interface (CLI) for running attribution passes, pre-flight data quality audits, constrained budget optimization, and generating production clean-room SQL.

---

## 1. Quick Reference

```bash
# Run the instant interactive terminal demo
spotlift demo

# Run pre-flight schema, cadence, and collision audit
spotlift preflight --spots schaltplan.csv --web ga4_minutes.parquet

# Run causal attribution across broadcast airings, GA4, and Amazon
spotlift run --spots schaltplan.csv --web ga4_minutes.parquet --out results.csv

# Solve constrained budget reallocation with diminishing returns
spotlift optimize --spots results.csv --budget 500000 --max-shift 0.35 --scenarios

# Generate BigQuery GA4 or Amazon Marketing Cloud (AMC) extraction SQL
spotlift sql --source ga4 --project my-gcp-project --dataset analytics_12345
spotlift sql --source amc --start 2026-03-01 --end 2026-03-21

# Authenticate SpotLift Pro license
spotlift auth --key SL_PRO_...
```

---

## 2. Command Details

### `spotlift demo`

Executes an instant attribution pass on a synthetic benchmark campaign with zero external credentials or API keys required.

```bash
spotlift demo --scenario dach --spots 600 --days 14 --out-dir ./demo_data
```

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--scenario`, `-sc` | String | `dach` | Scenario: `dach` (National + 36h AMC lag), `amc` (Omnichannel Clean Room), or `us-state` (Regional). |
| `--spots`, `-s` | Integer | `600` | Number of TV broadcast airings to generate. |
| `--days`, `-d` | Integer | `14` | Flight duration in days. |
| `--out-dir`, `-o` | Path | `./demo_data` | Target directory to export benchmark CSVs and parquet files. |

---

### `spotlift preflight` / `validate-inputs`

Performs non-destructive validation of timestamps, UTC normalization, sample rate cadence, zero-gap detection, and collision severity before launching production attribution passes.

```bash
spotlift preflight --spots tv_airings.csv --web ga4_minute_sessions.parquet --tz Europe/Berlin
```

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--spots`, `-s` | Path | *Required* | Path to TV broadcast schedule (Schaltplan). |
| `--web`, `-w` | Path | *Required* | Path to GA4 minute-level sessions. |
| `--tz`, `-z` | String | `UTC` | Timezone fallback if timestamps lack explicit offsets. |
| `--window` | Integer | `8` | Post-spot treatment window in minutes. |
| `--json` | Flag | `false` | Outputs machine-readable JSON summary for AI coding agents. |

---

### `spotlift run`

Executes the high-frequency attribution engine across broadcast TV, web sessions, and Amazon sales.

```bash
spotlift run \
  --spots /path/to/schaltplan.csv \
  --web /path/to/ga4_minutes.parquet \
  --amazon /path/to/amazon_hourly.csv \
  --format all \
  --out /path/to/attributed_spots.csv
```

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--spots`, `-s` | Path | *Required* | Path to broadcast airings CSV or Parquet. |
| `--web`, `-w` | Path | *Required* | Path to GA4 minute-level session CSV or Parquet. |
| `--amazon`, `-a` | Path | `None` | Optional path to Amazon hourly telemetry CSV/Parquet. |
| `--amc-conversions` | Path | `None` | Optional path to AMC pre/post spot conversions CSV/Parquet. |
| `--window` | Integer | `8` | Post-spot response window in minutes. |
| `--format`, `-f` | String | `csv` | Export format: `csv`, `markdown`, or `all`. |
| `--out`, `-o` | Path | `None` | Destination path for attributed spots CSV. |
| `--markdown-out`, `-m`| Path | `None` | Destination path for executive Markdown report. |
| `--html` | Path | `None` | Path to export interactive HTML report (SpotLift Pro). |
| `--excel` | Path | `None` | Path to export multi-tab agency Excel deck (SpotLift Pro). |
| `--key`, `-k` | String | `None` | SpotLift Pro license key (can also use `SPOTLIFT_API_KEY`). |

---

### `spotlift optimize`

Solves constrained budget reallocation using diminishing-returns response curves ($R(s) = \alpha s^\beta$) and marginal CPIV ($m\text{CPIV}$) equalization.

```bash
spotlift optimize \
  --spots /path/to/attributed_spots.csv \
  --budget 500000 \
  --max-shift 0.35 \
  --scenarios \
  --out /path/to/reallocated_budget.csv
```

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--spots`, `-s` | Path | *Required* | Path to attributed spots CSV/Parquet (or raw airings if `--web` is provided). |
| `--web`, `-w` | Path | `None` | Optional GA4 telemetry path if spots file is not yet attributed. |
| `--budget`, `-b` | Float | `Current Spend`| Target total budget (budget-neutral by default). |
| `--max-shift`, `-m` | Float | `0.35` | Maximum relative budget reallocation allowed per channel ($\pm 35\%$). |
| `--elasticity`, `-e` | Float | `0.70` | Diminishing returns elasticity parameter $\beta$ ($0 < \beta < 1$). |
| `--scenarios` | Flag | `false` | Displays multi-scenario comparison (Conservative, Balanced, Aggressive). |
| `--json` | Flag | `false` | Outputs machine-readable JSON summary for AI coding agents. |
| `--out`, `-o` | Path | `None` | Destination path to export recommended budget CSV. |

---

### `spotlift sql`

Generates production-tested SQL templates for extracting digital telemetry from Google BigQuery or Amazon Marketing Cloud (AMC).

```bash
# GA4 BigQuery SQL
spotlift sql --source ga4 --project my-gcp-project --dataset analytics_12345 --out ga4.sql

# AMC Athena SQL
spotlift sql --source amc --start 2026-03-01 --end 2026-03-21 --out amc.sql
```

---

### `spotlift auth`

Authenticates and caches your SpotLift Pro license key with Polar.sh and activates compiled engine extensions.

```bash
spotlift auth --key SL_PRO_...
```
