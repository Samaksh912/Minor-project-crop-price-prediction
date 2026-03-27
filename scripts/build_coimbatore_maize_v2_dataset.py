from __future__ import annotations

import csv
import json
import logging
import math
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


LOGGER = logging.getLogger("build_coimbatore_maize_v2_dataset")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "backend" / "data"

MAIZE_PATH = DATA_DIR / "maize.csv"
POLICY_PATH = DATA_DIR / "coimbatore_crop_policy_2023_2026.csv"
WEATHER_V1_PATH = DATA_DIR / "formatted_weather.csv"

MODEL_V1_PATH = DATA_DIR / "coimbatore_maize_model_daily.csv"
PANEL_V1_PATH = DATA_DIR / "coimbatore_maize_market_panel.csv"

WEATHER_V2_PATH = DATA_DIR / "coimbatore_weather_nasa_power_daily_20230315_20251030.csv"
MODEL_V2_PATH = DATA_DIR / "coimbatore_maize_model_daily_v2.csv"
PANEL_V2_PATH = DATA_DIR / "coimbatore_maize_market_panel_v2.csv"
VALIDATION_PATH = DATA_DIR / "coimbatore_maize_model_daily_v2_validation.json"

COIMBATORE_LATITUDE = 11.0168
COIMBATORE_LONGITUDE = 76.9558
COIMBATORE_ELEVATION_M = 540.94
NASA_POWER_DAILY_POINT_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_PARAMETERS = {
    "T2M": "tavg",
    "T2M_MIN": "tmin",
    "T2M_MAX": "tmax",
    "PRECTOTCORR": "prcp",
    "WD10M": "wdir",
    "WS10M": "wspd",
    "PS": "pres",
}


@dataclass(frozen=True)
class DailyAggregate:
    modal_price: float
    min_price: float
    max_price: float
    markets_reporting: int
    varieties_reporting: int
    rows_reporting: int


def parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def parse_float(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_maize_rows() -> list[dict]:
    rows: list[dict] = []
    with MAIZE_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["district_name"].strip().lower() != "coimbatore":
                continue
            rows.append(
                {
                    "date": parse_date(row["t"]),
                    "market_id": row["market_id"].strip(),
                    "market_name": row["market_name"].strip(),
                    "crop": row["cmdty"].strip(),
                    "variety": row["variety"].strip(),
                    "min_price": parse_float(row["p_min"]),
                    "max_price": parse_float(row["p_max"]),
                    "modal_price": parse_float(row["p_modal"]),
                }
            )
    rows.sort(key=lambda item: (item["date"], item["market_id"], item["variety"]))
    return rows


def load_policy_rows() -> list[dict]:
    rows: list[dict] = []
    with POLICY_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["crop"].strip().lower() != "maize":
                continue
            rows.append(
                {
                    "date": parse_date(row["date"]),
                    "msp_applicable": row["msp_applicable"].strip(),
                    "msp_value_per_quintal": row["msp_value_per_quintal"].strip(),
                    "govt_procurement_active": row["govt_procurement_active"].strip(),
                    "pmfby_insurance_active": row["pmfby_insurance_active"].strip(),
                    "state_scheme_active": row["state_scheme_active"].strip(),
                    "harvest_season_active": row["harvest_season_active"].strip(),
                    "price_impact_direction": row["price_impact_direction"].strip(),
                }
            )
    rows.sort(key=lambda item: item["date"])
    return rows


def fetch_nasa_power_weather(start_date: date, end_date: date) -> dict[date, dict]:
    query = {
        "parameters": ",".join(NASA_PARAMETERS.keys()),
        "community": "AG",
        "longitude": f"{COIMBATORE_LONGITUDE:.4f}",
        "latitude": f"{COIMBATORE_LATITUDE:.4f}",
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }
    url = f"{NASA_POWER_DAILY_POINT_URL}?{urllib.parse.urlencode(query)}"
    LOGGER.info("Fetching NASA POWER weather: %s", url)

    with urllib.request.urlopen(url, timeout=120) as response:
        payload = json.load(response)

    parameter_map = payload["properties"]["parameter"]
    fill_value = float(payload["header"].get("fill_value", -999.0))
    elevation_m = float(payload.get("geometry", {}).get("coordinates", [None, None, COIMBATORE_ELEVATION_M])[2])
    daily_weather: dict[date, dict] = {}

    date_keys = sorted(next(iter(parameter_map.values())).keys())
    for date_key in date_keys:
        current_date = datetime.strptime(date_key, "%Y%m%d").date()
        row = {}
        for nasa_name, output_name in NASA_PARAMETERS.items():
            raw_value = parameter_map[nasa_name].get(date_key)
            if raw_value is None or raw_value == fill_value:
                value = None
            else:
                value = float(raw_value)
                if output_name == "wspd":
                    value = value * 3.6
                if output_name == "pres":
                    station_pressure_hpa = value * 10.0
                    value = station_pressure_hpa / ((1.0 - (elevation_m / 44330.0)) ** 5.255)
            row[output_name] = value
        daily_weather[current_date] = row

    LOGGER.info(
        "Fetched %d NASA POWER daily weather rows covering %s to %s",
        len(daily_weather),
        start_date,
        end_date,
    )
    return daily_weather


def latest_policy_for(target_date: date, policy_rows: list[dict]) -> dict:
    latest: dict | None = None
    for row in policy_rows:
        if row["date"] <= target_date:
            latest = row
        else:
            break
    return latest or {}


def aggregate_daily(rows: list[dict]) -> dict[date, DailyAggregate]:
    grouped: dict[date, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["date"]].append(row)

    aggregates: dict[date, DailyAggregate] = {}
    for current_date, day_rows in grouped.items():
        modal_values = [row["modal_price"] for row in day_rows if row["modal_price"] is not None]
        min_values = [row["min_price"] for row in day_rows if row["min_price"] is not None]
        max_values = [row["max_price"] for row in day_rows if row["max_price"] is not None]
        markets = {row["market_id"] for row in day_rows if row["market_id"]}
        varieties = {row["variety"] for row in day_rows if row["variety"]}

        aggregates[current_date] = DailyAggregate(
            modal_price=sum(modal_values) / len(modal_values),
            min_price=sum(min_values) / len(min_values),
            max_price=sum(max_values) / len(max_values),
            markets_reporting=len(markets),
            varieties_reporting=len(varieties),
            rows_reporting=len(day_rows),
        )
    return aggregates


def fill_weather_gaps(weather_rows: dict[date, dict], start_date: date, end_date: date) -> dict[date, dict]:
    from datetime import timedelta

    all_dates = []
    current = start_date
    while current <= end_date:
        all_dates.append(current)
        current += timedelta(days=1)

    columns = list(NASA_PARAMETERS.values())
    forward_values = {column: None for column in columns}
    completed: dict[date, dict] = {}

    for current_date in all_dates:
        source_row = weather_rows.get(current_date, {})
        row = {}
        for column in columns:
            value = source_row.get(column)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                value = forward_values[column]
            else:
                forward_values[column] = value
            row[column] = value
        completed[current_date] = row

    backward_values = {column: None for column in columns}
    for current_date in reversed(all_dates):
        row = completed[current_date]
        for column in columns:
            value = row[column]
            if value is None or (isinstance(value, float) and math.isnan(value)):
                row[column] = backward_values[column]
            else:
                backward_values[column] = value

    return completed


def write_weather_csv(weather_rows: dict[date, dict], out_path: Path) -> None:
    fieldnames = ["date"] + list(NASA_PARAMETERS.values())
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for current_date in sorted(weather_rows):
            row = weather_rows[current_date]
            writer.writerow({"date": current_date.isoformat(), **row})


def write_market_panel(
    rows: list[dict],
    weather_rows: dict[date, dict],
    policy_rows: list[dict],
    out_path: Path,
) -> None:
    fieldnames = [
        "date",
        "market_id",
        "market_name",
        "crop",
        "variety",
        "min_price",
        "max_price",
        "modal_price",
        "tavg",
        "tmin",
        "tmax",
        "prcp",
        "wdir",
        "wspd",
        "pres",
        "msp_applicable",
        "msp_value_per_quintal",
        "govt_procurement_active",
        "pmfby_insurance_active",
        "state_scheme_active",
        "harvest_season_active",
        "price_impact_direction",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            weather = weather_rows.get(row["date"], {})
            policy = latest_policy_for(row["date"], policy_rows)
            writer.writerow(
                {
                    "date": row["date"].isoformat(),
                    "market_id": row["market_id"],
                    "market_name": row["market_name"],
                    "crop": row["crop"],
                    "variety": row["variety"],
                    "min_price": row["min_price"],
                    "max_price": row["max_price"],
                    "modal_price": row["modal_price"],
                    **weather,
                    "msp_applicable": policy.get("msp_applicable", ""),
                    "msp_value_per_quintal": policy.get("msp_value_per_quintal", ""),
                    "govt_procurement_active": policy.get("govt_procurement_active", ""),
                    "pmfby_insurance_active": policy.get("pmfby_insurance_active", ""),
                    "state_scheme_active": policy.get("state_scheme_active", ""),
                    "harvest_season_active": policy.get("harvest_season_active", ""),
                    "price_impact_direction": policy.get("price_impact_direction", ""),
                }
            )


def write_model_daily(
    daily: dict[date, DailyAggregate],
    weather_rows: dict[date, dict],
    policy_rows: list[dict],
    out_path: Path,
) -> None:
    fieldnames = [
        "date",
        "modal_price",
        "min_price",
        "max_price",
        "markets_reporting",
        "varieties_reporting",
        "rows_reporting",
        "tavg",
        "tmin",
        "tmax",
        "prcp",
        "wdir",
        "wspd",
        "pres",
        "msp_applicable",
        "msp_value_per_quintal",
        "govt_procurement_active",
        "pmfby_insurance_active",
        "state_scheme_active",
        "harvest_season_active",
        "price_impact_direction",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for current_date in sorted(daily):
            weather = weather_rows.get(current_date, {})
            policy = latest_policy_for(current_date, policy_rows)
            agg = daily[current_date]
            writer.writerow(
                {
                    "date": current_date.isoformat(),
                    "modal_price": round(agg.modal_price, 6),
                    "min_price": round(agg.min_price, 6),
                    "max_price": round(agg.max_price, 6),
                    "markets_reporting": agg.markets_reporting,
                    "varieties_reporting": agg.varieties_reporting,
                    "rows_reporting": agg.rows_reporting,
                    **weather,
                    "msp_applicable": policy.get("msp_applicable", ""),
                    "msp_value_per_quintal": policy.get("msp_value_per_quintal", ""),
                    "govt_procurement_active": policy.get("govt_procurement_active", ""),
                    "pmfby_insurance_active": policy.get("pmfby_insurance_active", ""),
                    "state_scheme_active": policy.get("state_scheme_active", ""),
                    "harvest_season_active": policy.get("harvest_season_active", ""),
                    "price_impact_direction": policy.get("price_impact_direction", ""),
                }
            )


def summarize_missingness(csv_path: Path, key_columns: list[str]) -> dict[str, int]:
    import pandas as pd

    df = pd.read_csv(csv_path)
    return {column: int(df[column].isna().sum()) for column in key_columns if column in df.columns}


def build_validation_report(
    raw_maize_rows: list[dict],
    weather_rows: dict[date, dict],
    policy_rows: list[dict],
) -> dict:
    import pandas as pd

    v1_df = pd.read_csv(MODEL_V1_PATH)
    v2_df = pd.read_csv(MODEL_V2_PATH)

    v1_dates = pd.to_datetime(v1_df["date"])
    v2_dates = pd.to_datetime(v2_df["date"])

    raw_price_dates = sorted({row["date"] for row in raw_maize_rows})
    weekly_v1 = len(v1_dates.dt.to_period("W").unique())
    weekly_v2 = len(v2_dates.dt.to_period("W").unique())

    policy_columns = [
        "msp_applicable",
        "msp_value_per_quintal",
        "govt_procurement_active",
        "pmfby_insurance_active",
        "state_scheme_active",
        "harvest_season_active",
        "price_impact_direction",
    ]
    key_columns = ["modal_price", "tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"] + policy_columns

    report = {
        "weather_source": {
            "provider": "NASA POWER Daily API",
            "url": NASA_POWER_DAILY_POINT_URL,
            "community": "AG",
            "latitude": COIMBATORE_LATITUDE,
            "longitude": COIMBATORE_LONGITUDE,
            "elevation_m": COIMBATORE_ELEVATION_M,
            "parameters": list(NASA_PARAMETERS.keys()),
            "transformations": {
                "wspd": "WS10M converted from m/s to km/h",
                "pres": "PS converted from kPa surface pressure to approximate sea-level hPa using site elevation",
            },
        },
        "raw_maize_price_range": {
            "start": min(raw_price_dates).isoformat(),
            "end": max(raw_price_dates).isoformat(),
            "rows": len(raw_maize_rows),
            "days": len(raw_price_dates),
        },
        "weather_v2_range": {
            "start": min(weather_rows).isoformat(),
            "end": max(weather_rows).isoformat(),
            "rows": len(weather_rows),
        },
        "model_v1": {
            "path": str(MODEL_V1_PATH),
            "date_start": v1_dates.min().date().isoformat(),
            "date_end": v1_dates.max().date().isoformat(),
            "rows": int(len(v1_df)),
            "unique_weeks": int(weekly_v1),
            "missingness": summarize_missingness(MODEL_V1_PATH, key_columns),
        },
        "model_v2": {
            "path": str(MODEL_V2_PATH),
            "date_start": v2_dates.min().date().isoformat(),
            "date_end": v2_dates.max().date().isoformat(),
            "rows": int(len(v2_df)),
            "unique_weeks": int(weekly_v2),
            "missingness": summarize_missingness(MODEL_V2_PATH, key_columns),
        },
    }

    v1_end = v1_dates.max().date()
    v2_end = v2_dates.max().date()
    report["comparison"] = {
        "usable_horizon_extended": v2_end > v1_end,
        "additional_calendar_days": (v2_end - v1_end).days,
        "additional_rows": int(len(v2_df) - len(v1_df)),
        "additional_unique_weeks": int(weekly_v2 - weekly_v1),
        "msp_coverage_complete_v2": all(
            report["model_v2"]["missingness"].get(column, 0) == 0 for column in policy_columns
        ),
        "weather_coverage_complete_v2": all(
            report["model_v2"]["missingness"].get(column, 0) == 0
            for column in ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"]
        ),
    }
    return report


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    maize_rows = load_maize_rows()
    policy_rows = load_policy_rows()

    if not maize_rows:
        raise RuntimeError("No Coimbatore maize rows found in maize.csv")

    price_start = min(row["date"] for row in maize_rows)
    price_end = max(row["date"] for row in maize_rows)

    weather_rows = fetch_nasa_power_weather(price_start, price_end)
    weather_rows = fill_weather_gaps(weather_rows, price_start, price_end)

    daily = aggregate_daily(maize_rows)
    write_weather_csv(weather_rows, WEATHER_V2_PATH)
    write_market_panel(maize_rows, weather_rows, policy_rows, PANEL_V2_PATH)
    write_model_daily(daily, weather_rows, policy_rows, MODEL_V2_PATH)

    validation = build_validation_report(maize_rows, weather_rows, policy_rows)
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2), encoding="utf-8")

    LOGGER.info("Wrote %s", WEATHER_V2_PATH)
    LOGGER.info("Wrote %s", PANEL_V2_PATH)
    LOGGER.info("Wrote %s", MODEL_V2_PATH)
    LOGGER.info("Wrote %s", VALIDATION_PATH)
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
