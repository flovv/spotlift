# Python API Reference

Complete reference for all functions, classes, and contracts in the `spotlift` open-core library.

---

## Attribution Core

### `spotlift.analyze_spots()`

The primary high-frequency linear TV attribution function.

```python
spotlift.analyze_spots(
    airings: pd.DataFrame,
    web_telemetry: pd.DataFrame,
    window_minutes: int = 8,
    pre_window_minutes: int = 15,
    baseline_days: int = 21,
    clip_negative: bool = False,
    apply_cr_model: bool = True,
    conversions_source: str | Sequence[str] = "ga4_conversions",
    cr_window_hours: int = 1,
    baseline_fn: Optional[Callable] = None,
    collision_attribution: str = "weighted_share",
) -> pd.DataFrame
```

#### Parameters

* **`airings`** (*pd.DataFrame*): Broadcast airings schedule conforming to `AiringLogSchema` (columns: `spot_id`, `timestamp`, `channel`, `creative_id`, `cost`, `grp`).
* **`web_telemetry`** (*pd.DataFrame*): Minute-level web visits stream conforming to `TelemetryStreamSchema` (columns: `timestamp`, `value`, `channel_source`).
* **`window_minutes`** (*int*, default `8`): Half-open response window duration $[t_0, t_0 + W)$ in minutes.
* **`baseline_fn`** (*Callable*, optional): Custom baseline estimator conforming to `BaselineFn`. Defaults to `compute_diurnal_baseline`. Pass `simple_mean_baseline` for short-history campaigns.
* **`collision_attribution`** (*str*, default `"weighted_share"`): Attribution algorithm for overlapping spots (`"weighted_share"` or `"naive_proportional"`).
* **`apply_cr_model`** (*bool*, default `True`): If `True` and conversion events are present in telemetry, bridges session lift to key events via local hourly conversion rates.
* **`conversions_source`** (*str | Sequence[str]*, default `"ga4_conversions"`): Label or list of custom GA4 sales event names in `web_telemetry["channel_source"]` (e.g., `"key_event_subscription_purchase"` or `["key_event_survey_submitted", "key_event_subscription_purchase"]`). When a list is provided, appends `cr_<event>` and `response_<event>` columns for each event.
* **`cr_window_hours`** (*int*, default `1`): Half-width of the hourly neighborhood for conversion rate calculation.
* **`clip_negative`** (*bool*, default `False`): If `False`, preserves signed lift to avoid upward rectification noise bias. If `True`, clamps negative lift at `0.0`.

#### Returns

* **`pd.DataFrame`**: Enriched DataFrame with spot-level attribution metrics (`baseline_volume`, `observed_volume`, `incremental_lift`, `cpiv`, `conversion_rate`, `key_event_response`, `collision_cluster_id`, `collision_method`).

---

## Data Ingestion & Loaders

### `spotlift.load_airings()`

Loads and validates a broadcast airings log from a CSV file path, buffer, or DataFrame.

```python
spotlift.load_airings(filepath_or_df: Union[str, Path, pd.DataFrame]) -> pd.DataFrame
```

* Validates required columns (`spot_id`, `timestamp`, `channel`, `creative_id`, `cost`).
* Parses and normalizes timestamps with explicit timezone handling.
* Fills missing `grp` with `0.0`.

---

### `spotlift.load_telemetry()`

Loads and validates minute-level digital telemetry.

```python
spotlift.load_telemetry(
    filepath_or_df: Union[str, Path, pd.DataFrame],
    zero_fill_gaps: bool = False,
) -> pd.DataFrame
```

* Verifies strict monotonic minute increments.
* Checks for missing minutes. If `zero_fill_gaps=True`, fills missing timestamps with `0.0`; otherwise raises `TelemetryGapError`.

---

## Baseline Estimators

### `spotlift.compute_diurnal_baseline()`

Calculates the decay-weighted cyclic rolling baseline.

```python
spotlift.compute_diurnal_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[pd.Timestamp],
    window_minutes: int = 6,
) -> tuple[pd.Series, dict[pd.Timestamp, float]]
```

Returns a tuple of `(calibrated_baseline_series, scaling_factors_dict)`.

---

### `spotlift.simple_mean_baseline()`

Fallback baseline computing the pre-spot moving average for short-history flights without multi-week diurnal history.

```python
spotlift.simple_mean_baseline(
    telemetry_series: pd.Series,
    spot_timestamps: list[pd.Timestamp],
    window_minutes: int = 6,
    pre_window_minutes: int = 15,
) -> pd.Series
```

---

## Collision Mathematics

### `spotlift.compute_continuous_weighted_share()`

Analytical exponential-decay weighted share attribution for overlapping broadcast collision clusters.

```python
spotlift.compute_continuous_weighted_share(
    cluster_df: pd.DataFrame,
    telemetry_series: pd.Series,
    baseline_series: pd.Series,
    window_minutes: int = 6,
    half_life_minutes: float = 1.5,
) -> dict[Any, float]
```

Returns a dictionary mapping each `spot_id` to its attributed incremental lift.

---

## Conversion Rate Bridge

### `spotlift.estimate_conversion_rate_for_spot()`

Calculates the volume-weighted conversion rate for a spot based on the surrounding hourly window.

```python
spotlift.estimate_conversion_rate_for_spot(
    spot_timestamp: pd.Timestamp,
    telemetry_df: pd.DataFrame,
    conversions_source: str = "ga4_conversions",
    window_hours: int = 1,
) -> float
```

Seamlessly crosses midnight boundaries using continuous timestamp slices.

---

### `spotlift.apply_conversion_model()`

Enriches an attributed spots DataFrame with `conversion_rate` and `key_event_response` (plus `cr_<event>` and `response_<event>` columns when `conversions_source` is a sequence of multiple custom GA4 events).

```python
spotlift.apply_conversion_model(
    spots_df: pd.DataFrame,
    web_telemetry: pd.DataFrame,
    sessions_source: str = "ga4_direct_organic_sessions",
    conversions_source: str | Sequence[str] = "ga4_conversions",
    cr_window_hours: int = 1,
) -> pd.DataFrame
```

---

## Clean Room SQL Generators

### `spotlift.generate_ga4_bigquery_sql()`

Generates a production Google BigQuery SQL query extracting minute-level direct/organic sessions and conversion events (supports single or multiple custom GA4 key events).

```python
spotlift.generate_ga4_bigquery_sql(
    project_id: str,
    dataset_id: str,
    start_date: str,
    end_date: str,
    conversion_event_name: str | Sequence[str] = "purchase",
    include_paid_search: bool = False,
) -> str
```

---

### `spotlift.generate_amc_telemetry_sql()`

Generates an Amazon Marketing Cloud (AMC) clean room SQL query extracting hourly ordered units and sales.

```python
spotlift.generate_amc_telemetry_sql(
    start_date: str,
    end_date: str,
) -> str
```

---

## Synthetic Benchmark Dataset Generators

### `spotlift.generate_dach_benchmark_dataset()`

Generates a 14-day DACH TV campaign with 250 spots, GA4 minute telemetry, and hourly Amazon telemetry.

```python
spotlift.generate_dach_benchmark_dataset(
    n_days: int = 14,
    n_spots: int = 250,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

### `spotlift.generate_omnichannel_amc_dataset()`

Generates an omnichannel campaign with correlated GA4 web telemetry and dual-format Amazon AMC telemetry (`amc_spot_conversions` with `pageViewStarts`, `addToCart`, `purchases`, `totalProductSales` across `pre`/`post` windows + `amazon_hourly_telemetry`).

```python
spotlift.generate_omnichannel_amc_dataset(
    n_days: int = 14,
    n_spots: int = 180,
    seed: int = 101,
    amc_window_minutes: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

### `spotlift.generate_us_state_dataset()`

Generates a US regional state-targeted TV campaign (`TX`, `FL`, `PA` active states vs. `CA`, `NY`, `IL` zero-spot holdout control states + `US_NATIONAL` aggregate).

```python
spotlift.generate_us_state_dataset(
    n_days: int = 14,
    n_spots: int = 130,
    seed: int = 202,
    active_states: tuple[str, ...] = ("TX", "FL", "PA"),
    control_states: tuple[str, ...] = ("CA", "NY", "IL"),
) -> tuple[pd.DataFrame, pd.DataFrame]
```

---

## SpotLift Pro Dispatch

### `spotlift.install_pro()`

Validates a commercial license key and unlocks Pro capabilities.

```python
spotlift.install_pro(
    api_key: str,
    index_url: Optional[str] = None,
    local_path: Optional[str] = None,
) -> bool
```

---

### `spotlift.analyze_omnichannel_pro()`

Pro entry point dispatches to compiled Cython binaries for Shifted-Gamma EM deconvolution, AMC retail halo, and Excel export.

```python
spotlift.analyze_omnichannel_pro(
    airings: pd.DataFrame,
    web_telemetry: pd.DataFrame,
    amazon_telemetry: Optional[pd.DataFrame] = None,
    window_minutes: int = 8,
    export_html: Optional[str] = None,
    export_excel: Optional[str] = None,
    white_label_config: Optional[dict] = None,
    clip_negative: bool = False,
    apply_cr_model: bool = True,
    conversions_source: str | Sequence[str] = "ga4_conversions",
    cr_window_hours: int = 1,
) -> dict
```

---

### `spotlift_pro.amc_ingestion.analyze_amc_spot_conversions()`

Analyzes pre/post windowed Amazon Marketing Cloud (AMC) clean room tables (`pageViewStarts`, `addToCart`, `purchases`, `totalProductSales`, `newToBrandPurchases`).

```python
spotlift_pro.amc_ingestion.analyze_amc_spot_conversions(
    amc_df: pd.DataFrame,
    airings_df: Optional[pd.DataFrame] = None,
    clip_negative: bool = False,
) -> dict[str, Any]
```
